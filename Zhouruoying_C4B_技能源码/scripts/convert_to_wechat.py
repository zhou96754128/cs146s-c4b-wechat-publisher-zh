#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wechat-publisher v2.0 — Markdown / Word → 微信公众号「可直接粘贴」HTML

基于 Elite20 提供的 wechat-publisher starter kit 改造（Zhouruoying_C4B）。

改造分两类：

A. 新增能力（starter 的 "What This Starter Kit Does NOT Do (Yet)" 清单）
   1. 主题/配色系统 —— 4 套内置主题，--theme 切换；所有样式由调色板推导
   2. Callout 高亮框 —— > [!NOTE] / [!TIP] / [!WARNING] / [!INFO] 及中文别名
   3. 自动目录 —— --toc 依据 h2/h3 生成带序号的导航清单
   4. 中英混排优化 —— CJK 与拉丁字母/数字之间补空格；CJK 语境下半角标点转全角
   5. 文章元数据 —— YAML front matter 或 --title/--author/--date/--abstract
   6. 页脚版权 —— --footer；缺省读 front matter 的 footer 字段
   7. 图片处理 —— 本地图片转 base64 PNG 内联（微信只认 PNG base64）

B. 修复 starter 声明了却没实现的行为（详见 references/CHANGELOG-vs-starter.md）
   1. 空文件应报错 —— 原实现返回成功、产出空 HTML
   2. 非 UTF-8 回退 GBK —— 原实现直接 utf-8 打开，非 UTF-8 直接抛异常
   3. 内联 CSS 白名单过滤 —— 原实现定义了 ALLOWED_CSS 却从未调用（死代码）
   4. <strong>/<em> 内容保真 —— 原实现 get_text() 展开，嵌套行内元素丢失
   5. 代码块换行保留 —— 原实现塞进 p.string，微信里换行被吃掉
   6. 图片尺寸约束 —— img 补 max-width:100%;height:auto，防溢出手机屏

用法：
    python3 convert_to_wechat.py input.md output.html
    python3 convert_to_wechat.py input.md output.html --theme blue --toc
    python3 convert_to_wechat.py input.md output.html --theme warm --footer "(c) 2026 Zhouruoying"
    python3 convert_to_wechat.py input.md output.html --no-cjk      # 关闭中英混排优化
    python3 convert_to_wechat.py --list-themes

然后：浏览器打开 output.html → Ctrl+A → Ctrl+C → 粘进公众号编辑器。
"""

import sys
import os
import re
import json
import base64
import argparse
from pathlib import Path

# ============================================================
# 依赖自动安装（starter 的既有做法，保留）
# ============================================================


def install_dependencies(quiet=False):
    """Install required packages if not available."""
    missing = []
    for mod, pkg in (("markdown", "markdown"),
                     ("bs4", "beautifulsoup4"),
                     ("docx", "python-docx"),
                     ("lxml", "lxml")):
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)

    if missing:
        if not quiet:
            print("Installing missing packages: " + ", ".join(missing) + "...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install",
                               *missing, "--break-system-packages", "-q"])
        if not quiet:
            print("Done!\n")


install_dependencies()

# 依赖自动安装完成后再导入（首次运行可能刚刚才装上）
import markdown                              # noqa: E402

try:                                         # Word 支持可选：没装 python-docx 也能跑 Markdown
    from docx import Document                # noqa: E402
except ImportError:                          # pragma: no cover
    Document = None


# ============================================================
# 主题 / 调色板  —— 新增能力 1
# ============================================================

THEMES = {
    "default": {
        "label": "默认 · GitHub 灰（通用技术文）",
        "primary": "#333333",
        "accent": "#0366d6",
        "soft": "#f6f8fa",
        "border": "#dddddd",
        "muted": "#666666",
        "mark_bg": "#f5f5f5",
        "mark_fg": "#d73a49",
    },
    "blue": {
        "label": "蓝色 · 科技/知识（教程、原理讲解）",
        "primary": "#1f3a5f",
        "accent": "#2b6cb0",
        "soft": "#eef4fb",
        "border": "#c9ddf2",
        "muted": "#4a6f96",
        "mark_bg": "#eaf2fb",
        "mark_fg": "#1f6fb2",
    },
    "warm": {
        "label": "暖色 · 个人叙事（复盘、经历分享）",
        "primary": "#43281c",
        "accent": "#c05621",
        "soft": "#fdf3ec",
        "border": "#f0d6c2",
        "muted": "#8a6a56",
        "mark_bg": "#fbeee4",
        "mark_fg": "#b7521e",
    },
    "minimal": {
        "label": "极简 · 黑白高对比（观点、檄文）",
        "primary": "#111111",
        "accent": "#111111",
        "soft": "#fafafa",
        "border": "#e5e5e5",
        "muted": "#555555",
        "mark_bg": "#f2f2f2",
        "mark_fg": "#111111",
    },
}

# Callout 语义色固定不随主题变，保证「看到黄色就知道是警告」这一认知稳定
CALLOUTS = {
    "note":    {"icon": "📘", "title": "知识点", "fg": "#1f4e79", "bg": "#eef4fb", "bd": "#2b6cb0"},
    "tip":     {"icon": "💡", "title": "小技巧", "fg": "#1c5c3a", "bg": "#eefaf1", "bd": "#2f9e63"},
    "warning": {"icon": "⚠️", "title": "注意",   "fg": "#8a4b00", "bg": "#fff7e6", "bd": "#d99a2b"},
    "info":    {"icon": "📌", "title": "补充说明", "fg": "#5a3a7a", "bg": "#f5f0fb", "bd": "#8a63c9"},
}

# 中文别名 → 语义 key
CALLOUT_ALIASES = {
    "note": "note", "note!": "note", "知识": "note", "知识点": "note", "note-blue": "note",
    "tip": "tip", "技巧": "tip", "小技巧": "tip", "hint": "tip",
    "warning": "warning", "warn": "warning", "注意": "warning", "警告": "warning", "caution": "warning",
    "info": "info", "说明": "info", "补充": "info", "补充说明": "info",
}


def build_styles(theme):
    """由调色板推导出全部内联样式。"""
    t = THEMES[theme]
    p_color = "#3f3f3f"          # 正文不用纯黑，避免手机上对比过锐
    return {
        "h2": ("font-size: 21px; font-weight: bold; line-height: 1.5; "
               "color: " + t["primary"] + "; margin: 28px 0 12px 0; "
               "padding-left: 10px; border-left: 4px solid " + t["accent"] + ";"),
        "h3": ("font-size: 17px; font-weight: bold; line-height: 1.6; "
               "color: " + t["accent"] + "; margin: 20px 0 8px 0;"),
        "p": ("font-size: 16px; line-height: 1.75; color: " + p_color + "; "
              "margin: 12px 0; word-break: break-word;"),
        "li": ("font-size: 16px; line-height: 1.75; color: " + p_color + "; "
               "margin: 6px 0;"),
        "ul": "margin: 12px 0; padding-left: 22px;",
        "ol": "margin: 12px 0; padding-left: 22px;",
        "code_inline": ("background-color: " + t["mark_bg"] + "; color: " + t["mark_fg"] + "; "
                        "font-size: 14px; padding: 2px 5px; border-radius: 3px;"),
        "code_block": ("background-color: " + t["soft"] + "; color: #24292e; font-size: 13px; "
                       "line-height: 1.6; padding: 14px 16px; margin: 14px 0; "
                       "border-radius: 6px; border: 1px solid " + t["border"] + "; "
                       "white-space: pre-wrap; word-break: break-all; overflow-x: auto;"),
        "blockquote": ("background-color: " + t["soft"] + "; color: " + t["muted"] + "; "
                       "padding: 12px 16px; margin: 14px 0; "
                       "border-left: 4px solid " + t["border"] + ";"),
        "table": "border-collapse: collapse; margin: 14px 0; font-size: 14px; width: 100%;",
        "th": ("background-color: " + t["soft"] + "; color: " + t["primary"] + "; font-weight: bold; "
               "padding: 8px 10px; text-align: left; border: 1px solid " + t["border"] + ";"),
        "td": ("padding: 8px 10px; border: 1px solid " + t["border"] + "; "
               "color: " + p_color + "; font-size: 14px;"),
        "a": "color: " + t["accent"] + "; text-decoration: underline;",
        "hr": ("border: none; border-top: 1px solid " + t["border"] + "; margin: 24px 0;"),
        "img": "max-width: 100%; height: auto; display: block; margin: 14px auto; border-radius: 4px;",
        "meta_title": ("font-size: 26px; font-weight: bold; line-height: 1.4; "
                       "color: " + t["primary"] + "; margin: 8px 0 10px 0;"),
        "meta_line": ("font-size: 14px; color: " + t["muted"] + "; margin: 0 0 18px 0;"),
        "abstract": ("background-color: " + t["soft"] + "; border: 1px solid " + t["border"] + "; "
                     "border-radius: 6px; padding: 14px 16px; margin: 16px 0 22px 0;"),
        "abstract_text": ("font-size: 15px; line-height: 1.7; color: " + t["muted"] + "; margin: 0;"),
        "toc_box": ("background-color: " + t["soft"] + "; border: 1px solid " + t["border"] + "; "
                    "border-radius: 6px; padding: 14px 18px; margin: 16px 0 22px 0;"),
        "toc_title": ("font-size: 16px; font-weight: bold; color: " + t["primary"] + "; margin: 0 0 8px 0;"),
        "toc_item": ("font-size: 15px; line-height: 1.9; color: " + t["accent"] + "; margin: 0;"),
        "footer": ("font-size: 13px; color: " + t["muted"] + "; text-align: center; "
                   "margin: 28px 0 8px 0; padding-top: 14px; "
                   "border-top: 1px solid " + t["border"] + ";"),
    }


# ============================================================
# 输入读取 —— 含修复 B2（非 UTF-8 回退 GBK）
# ============================================================

from html import escape as _esc  # noqa: E402  (放在此处便于分块阅读)

_ENCODINGS = ("utf-8", "utf-8-sig", "gbk", "gb18030", "big5")


def detect_encoding(path):
    """UTF-8 优先，逐级回退 GBK/GB18030/Big5。

    starter 只用 utf-8 打开，遇到 GBK 存的中文文档直接抛 UnicodeDecodeError。
    这是修复项 B2。
    """
    raw = Path(path).read_bytes()
    for enc in _ENCODINGS:
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "utf-8"          # 全部失败则兜底，靠 errors='replace' 不崩


def read_text(path):
    enc = detect_encoding(path)
    return Path(path).read_text(encoding=enc, errors="replace"), enc


FRONT_MATTER_RE = re.compile(r"^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?", re.S)


def split_front_matter(text):
    """解析开头的 YAML front matter（只支持单层 key: value，保持零新依赖）。"""
    m = FRONT_MATTER_RE.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip().lower()] = v.strip().strip('"').strip("'")
    return meta, text[m.end():]


def read_markdown(path, strip_meta=True):
    text, enc = read_text(path)
    meta, body = split_front_matter(text)
    html = markdown.markdown(body, extensions=[
        "extra",          # tables / footnotes / def_list / attr_list
        "fenced_code",    # ```code blocks```
        "nl2br",          # 单个换行 → <br>
        "sane_lists",     # 列表解析更稳
    ])
    return html, meta, body, enc


def read_docx(path):
    """Word → HTML。starter 只处理段落，这里补上表格（Word 里常见）。"""
    doc = Document(path)
    parts = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style_name = para.style.name if para.style else ""
        if style_name.startswith("Heading"):
            level = style_name.replace("Heading ", "").strip()
            tag = "h2" if level in ("1", "2") else "h3"
            parts.append("<%s>%s</%s>" % (tag, _esc(text), tag))
            continue
        p_html = "<p>"
        for run in para.runs:
            t = run.text
            if not t:
                continue
            t = _esc(t)
            if run.bold and run.italic:
                p_html += '<span style="font-weight:bold;font-style:italic;">%s</span>' % t
            elif run.bold:
                p_html += '<span style="font-weight:bold;">%s</span>' % t
            elif run.italic:
                p_html += '<span style="font-style:italic;">%s</span>' % t
            else:
                p_html += t
        p_html += "</p>"
        parts.append(p_html)

    for table in getattr(doc, "tables", []):
        rows = []
        for row in table.rows:
            cells = "".join("<td>%s</td>" % _esc(c.text.strip()) for c in row.cells)
            rows.append("<tr>%s</tr>" % cells)
        parts.append("<table>%s</table>" % "".join(rows))

    return "\n".join(parts), {}, None, "docx"


# ============================================================
# 中英混排优化  —— 新增能力 4
# ============================================================

_CJK_CHAR = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_LATIN_NUM = re.compile(r"[0-9A-Za-z@#$%&*+=/~^]")
# 只在紧邻汉字时替换，且刻意排除 . 与括号（小数、版本号、文件名、代码标识符风险高）
_PUNCT_MAP = {",": "，", ":": "：", ";": "；", "?": "？", "!": "！"}


def cjk_spacing(text):
    """在汉字与拉丁字母/数字交界处补一个空格。例：AI时代 → AI 时代。"""
    if not text:
        return text
    out = []
    prev = ""
    for ch in text:
        if prev:
            a_cjk, b_cjk = bool(_CJK_CHAR.match(prev)), bool(_CJK_CHAR.match(ch))
            a_lat, b_lat = bool(_LATIN_NUM.match(prev)), bool(_LATIN_NUM.match(ch))
            if ((a_cjk and b_lat) or (a_lat and b_cjk)) and prev != " " and ch != " ":
                out.append(" ")
        out.append(ch)
        prev = ch
    return "".join(out)


def cjk_punct(text):
    """汉字语境下的半角 , : ; ? ! 转全角。其余标点不动（保守）。"""
    if not text:
        return text
    res = []
    for i, ch in enumerate(text):
        if ch in _PUNCT_MAP:
            left_cjk = i > 0 and bool(_CJK_CHAR.match(text[i - 1]))
            right_cjk = i + 1 < len(text) and bool(_CJK_CHAR.match(text[i + 1]))
            if left_cjk or (right_cjk and ch in "?!"):
                res.append(_PUNCT_MAP[ch])
                continue
        res.append(ch)
    return "".join(res)


# ============================================================
# HTML 净化管线
# ============================================================

from bs4 import BeautifulSoup, NavigableString  # noqa: E402

# WeChat 允许的标签（严格白名单，超出即解包保留内容）
ALLOWED_TAGS = {
    "p", "h2", "h3", "ul", "ol", "li", "span", "img", "a",
    "table", "tr", "th", "td", "br",
}

# 允许保留的属性（class/id/on* 一律删）
ALLOWED_ATTRS = {"style", "src", "href", "alt", "title", "colspan", "rowspan"}

# 内联 CSS 白名单 —— starter 定义了 ALLOWED_CSS 却从未使用（死代码），这里是真过滤
ALLOWED_CSS = {
    "color", "background-color", "font-size", "font-weight", "font-family",
    "font-style", "line-height", "letter-spacing", "text-align", "text-decoration",
    "text-indent", "margin", "margin-top", "margin-bottom", "margin-left",
    "margin-right", "padding", "padding-top", "padding-bottom", "padding-left",
    "padding-right", "border", "border-top", "border-bottom", "border-left",
    "border-right", "border-color", "border-style", "border-width",
    "border-radius", "border-collapse", "width", "max-width", "min-width",
    "height", "max-height", "word-break", "word-wrap", "white-space", "display",
    "overflow-x", "vertical-align",
}
# 微信编辑器会直接丢弃的属性（references/wechat_restrictions.md）
FORBIDDEN_CSS = {
    "position", "float", "grid", "grid-template-columns", "grid-template-rows",
    "flex", "flex-direction", "justify-content", "align-items", "animation",
    "transition", "transform", "z-index", "visibility", "top", "left", "right",
    "bottom", "filter", "backdrop-filter", "box-shadow", "@media",
}


def filter_css(style_str):
    """按白名单过滤内联样式，返回规范化后的 style 串。"""
    kept = []
    for decl in (style_str or "").split(";"):
        if ":" not in decl:
            continue
        prop, val = decl.split(":", 1)
        prop = prop.strip().lower()
        val = val.strip()
        if not prop or not val or prop.startswith("@"):
            continue
        if prop in FORBIDDEN_CSS or prop not in ALLOWED_CSS:
            continue
        flat = val.replace(" ", "").lower()
        if prop == "display" and flat in ("flex", "grid", "inline-flex", "inline-grid"):
            continue
        if "url(" in flat and prop != "background-color":
            continue
        kept.append("%s: %s" % (prop, val))
    return "; ".join(kept)


# ============================================================
# 结构净化 + 行内保真 + Callout 高亮框
# ============================================================

# > [!NOTE] 标题   /   > 【注意】标题
_CALLOUT_HEAD_RE = re.compile(r"^\s*[\[【]\s*!?\s*([A-Za-z\u4e00-\u9fff]+)\s*[\]】][ \t]*")


def _replace_keep_contents(soup, tag, style=None, name="span"):
    """把 tag 换成新标签并**保留内部结构**。

    修复 B4：starter 用 `span.string = tag.get_text()`，会把 `**加粗里的 `code`**`
    这类嵌套内容压成纯文本，行内代码/链接直接丢失。
    """
    new = soup.new_tag(name)
    if style:
        new["style"] = style
    for child in list(tag.contents):
        new.append(child.extract())
    tag.replace_with(new)
    return new


def _code_block_to_p(soup, pre, style):
    """<pre><code> → 扁平 <p>，换行显式转 <br>、缩进转 nbsp（修复 B5）。"""
    code = pre.find("code")
    src = code if code is not None else pre
    lang = ""
    for c in (src.get("class") or []):
        if str(c).startswith("language-"):
            lang = str(c)[len("language-"):]
            break
    p = soup.new_tag("p")
    p["style"] = style
    if lang:
        cap = soup.new_tag("span")
        cap["style"] = "font-size: 12px; color: #888888;"
        cap.string = lang
        p.append(cap)
        p.append(soup.new_tag("br"))
    for i, line in enumerate(src.get_text().rstrip("\n").split("\n")):
        if i:
            p.append(soup.new_tag("br"))
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        p.append(NavigableString("\u00a0" * indent + stripped))
    pre.replace_with(p)
    return p


def build_callout(soup, bq):
    """把 `> [!NOTE] ...` 引用块转成高亮框。命中返回新节点，未命中返回 None。

    新增能力 2。支持 note/tip/warning/info 及中文别名（见 CALLOUT_ALIASES）。
    """
    ps = bq.find_all("p")
    inner = ps[0] if ps else bq
    marker = None
    for node in inner.find_all(string=True):
        s = str(node)
        if _CALLOUT_HEAD_RE.match(s):
            marker = node
            break
        if s.strip():
            break
    if marker is None:
        return None
    m = _CALLOUT_HEAD_RE.match(str(marker))
    raw = m.group(1)
    kind = CALLOUT_ALIASES.get(raw.lower()) or CALLOUT_ALIASES.get(raw)
    if not kind:
        return None
    c = CALLOUTS[kind]
    marker.replace_with(NavigableString(str(marker)[m.end():]))

    title_buf, body_nodes, hit_br = [], [], False
    for node in list(inner.contents):
        if not hit_br and getattr(node, "name", None) == "br":
            hit_br = True
            node.extract()
            continue
        if not hit_br:
            title_buf.append(node.get_text() if hasattr(node, "get_text") else str(node))
            node.extract()
        else:
            body_nodes.append(node.extract())
    if not hit_br:                       # 标记与正文同行 → 全部当正文，用默认标题
        title_buf, body_nodes = [], list(title_buf and [] or []) + body_nodes
    title = re.sub(r"\s+", " ", "".join(title_buf)).strip() or c["title"]

    box = soup.new_tag("p")
    box["style"] = ("background-color: %s; border-left: 4px solid %s; "
                    "border-radius: 4px; padding: 12px 14px; margin: 14px 0;"
                    % (c["bg"], c["bd"]))
    head = soup.new_tag("span")
    head["style"] = "font-size: 15px; font-weight: bold; color: %s;" % c["fg"]
    head.string = c["icon"] + " " + title
    box.append(head)

    body = soup.new_tag("span")
    body["style"] = "font-size: 15px; line-height: 1.7; color: #3f3f3f;"
    for node in body_nodes:
        body.append(node)
    for extra in ps[1:]:
        body.append(soup.new_tag("br"))
        for node in list(extra.contents):
            body.append(node.extract())
        extra.decompose()
    if len(body.contents):
        box.append(soup.new_tag("br"))
        box.append(body)

    bq.replace_with(box)
    return box


def sanitize(soup, styles):
    """按微信限制改造结构：去禁标签、降级标题、框/代码/引用/强调重写。"""
    for name in ("script", "style", "iframe", "object", "embed", "form", "input"):
        for el in soup.find_all(name):
            el.decompose()

    for h1 in soup.find_all("h1"):
        h1.name = "h2"
    for div in soup.find_all("div"):
        div.name = "p"

    # callout 必须先于普通引用块处理
    for bq in list(soup.find_all("blockquote")):
        build_callout(soup, bq)

    for pre in list(soup.find_all("pre")):
        _code_block_to_p(soup, pre, styles["code_block"])
    for code in list(soup.find_all("code")):
        _replace_keep_contents(soup, code, styles["code_inline"], "span")
    for bq in list(soup.find_all("blockquote")):
        _replace_keep_contents(soup, bq, styles["blockquote"], "p")
    for tag in list(soup.find_all(["strong", "b"])):
        _replace_keep_contents(soup, tag, "font-weight: bold;", "span")
    for tag in list(soup.find_all(["em", "i"])):
        _replace_keep_contents(soup, tag, "font-style: italic;", "span")
    for hr in list(soup.find_all("hr")):
        p = soup.new_tag("p")
        p["style"] = styles["hr"]
        hr.replace_with(p)
    return soup


# ============================================================
# 属性清洗 + 默认样式套用
# ============================================================

STRIP_ATTR_RE = re.compile(r"^(on|data-|aria-)|^class$|^id$|^name$", re.I)


def clean_attributes(soup):
    """删禁属性、过滤内联 CSS、对超白名单标签解包（保留内容）。"""
    for tag in list(soup.find_all(True)):
        if tag.name not in ALLOWED_TAGS:
            _replace_keep_contents(soup, tag, tag.get("style"), "span")
            continue
        for attr in list(tag.attrs.keys()):
            if attr not in ALLOWED_ATTRS or STRIP_ATTR_RE.match(attr):
                del tag.attrs[attr]
        if tag.has_attr("style"):
            filtered = filter_css(tag["style"])
            if filtered:
                tag["style"] = filtered
            else:
                del tag.attrs["style"]
    return soup


def apply_styles(soup, styles):
    """给「还没有内联样式」的元素套默认样式。

    已有 style 的说明是作者意图或上一步派生的语义样式，不动它——
    这是 starter 的「美化」和「保真」能同时成立的关键。
    """
    for name, key in (("h2", "h2"), ("h3", "h3"), ("p", "p"), ("li", "li"),
                      ("ul", "ul"), ("ol", "ol"), ("table", "table"),
                      ("th", "th"), ("td", "td"), ("a", "a"), ("img", "img")):
        for el in soup.find_all(name):
            if not el.get("style"):
                el["style"] = styles[key]
    return soup


# ============================================================
# 图片处理 —— 新增能力 6（本地图片 → base64 PNG）
# ============================================================

IMG_MIME_OK = {"image/png", "image/jpeg", "image/jpg", "image/gif"}
_MAX_IMG_BYTES = 10 * 1024 * 1024          # 微信单图 10 MB 上限


def _load_pillow():
    try:
        from PIL import Image  # noqa: F401
        return True
    except Exception:
        return False


_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
_GIF_MAGICS = (b"GIF87a", b"GIF89a")


def sniff_image_mime(data):
    """按真实字节判定图片类型（不看扩展名）；认不出来返回 None。"""
    if data.startswith(_PNG_MAGIC):
        return "image/png"
    if data.startswith(_JPEG_MAGIC):
        return "image/jpeg"
    if data.startswith(_GIF_MAGICS):
        return "image/gif"
    return None


def to_png_bytes(path, warn):
    """本地图片 → (字节, mime)。

    为什么连 mime 一起返回：**data URI 里的标签必须与真实字节一致**。初版和
    starter 一样写死 data:image/png;base64，一旦源图是 JPEG/GIF 且本机没有
    Pillow，就会产出「字节是 JPEG、标签写着 PNG」的裂图——内置自检当时覆盖
    不到，是真实文章实跑才暴露的缺陷（记作修复 B8）。

    策略：能转就转成真 PNG；没有 Pillow 时按字节嗅探，只放行微信支持的
    PNG/JPG/GIF，其余格式明确警告并跳过，绝不产出标签与字节不符的 data URI。
    """
    raw = Path(path).read_bytes()
    if not raw:
        warn("图片是空文件，已跳过：%s" % path.name)
        return None, None
    if raw.startswith(_PNG_MAGIC):
        return raw, "image/png"
    if _load_pillow():
        try:
            import io
            from PIL import Image
            buf = io.BytesIO()
            img = Image.open(io.BytesIO(raw))
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGBA")
            else:
                img = img.convert("RGB")
            img.save(buf, format="PNG")
            return buf.getvalue(), "image/png"
        except Exception as exc:                       # 坏图 / 不支持的格式
            warn("图片转 PNG 失败：%s -> %s" % (path.name, exc))
            return None, None
    mime = sniff_image_mime(raw)
    if mime is None:
        warn("无法内联 %s：本机未安装 Pillow，且字节既不是 PNG 也不是 JPG/GIF；"
             "请先转成 PNG 再重跑" % path.name)
        return None, None
    warn("未安装 Pillow，按原始格式内联（mime=%s）：%s" % (mime, path.name))
    return raw, mime


def embed_images(soup, base_dir, warn, embed=True):
    """把本地图片内联成 base64，网络图片保持 URL。

    references/wechat_restrictions.md：微信只认 PNG/JPG/GIF，SVG 保存后会消失；
    且外链图片容易被防盗链拦截，本地图必须内联。
    """
    import base64
    stats = {"embedded": 0, "remote": 0, "skipped": 0, "mimes": {}}

    def _placeholder(node, text):
        """把无法内联的图换成一行居中提示（修复 B9）。

        为什么不「跳过但留着 img」：微信侧本地路径根本加载不到，更糟的是
        残留的本地 src 会被 check_restrictions 判为 error —— 一张坏图就能让
        整篇文章转换失败并返回 exit=1。实跑暴露：跳过必须伴随**替换**。
        """
        ph = soup.new_tag("p")
        ph["style"] = "font-size: 13px; color: #999999; text-align: center;"
        ph.string = text
        node.replace_with(ph)

    for img in soup.find_all("img"):
        src = (img.get("src") or "").strip()
        if not src:
            warn("图片缺少 src，已移除该空标签")
            _placeholder(img, "[此处原有一张未指定来源的图片，已移除]")
            stats["skipped"] += 1
            continue
        if src.startswith(("http://", "https://")):
            stats["remote"] += 1                        # 外链保留，风险写进报告
            continue
        if src.startswith("data:"):
            stats["embedded"] += 1
            continue
        if not embed:
            stats["skipped"] += 1
            continue
        path = Path(base_dir) / src if not Path(src).is_absolute() else Path(src)
        if not path.exists():
            warn("图片不存在，已替换为降级提示：%s" % src)
            _placeholder(img, "[图示缺失：%s —— 找不到该文件，请检查路径]" % src)
            stats["skipped"] += 1
            continue
        if path.suffix.lower() == ".svg":
            warn("SVG 不被微信支持（保存后消失），已替换为降级提示：%s" % src)
            _placeholder(img, "[图示：%s —— SVG 不被微信支持，请导出为 PNG 后重跑]"
                         % path.name)
            stats["skipped"] += 1
            continue
        data, mime = to_png_bytes(path, warn)
        if data is None:
            _placeholder(img, "[图示：%s —— 无法内联（详见运行日志），请转成 PNG 后重跑]"
                         % path.name)
            stats["skipped"] += 1
            continue
        if len(data) > _MAX_IMG_BYTES:
            warn("图片超过 10 MB 上限，已跳过：%s（%.1f MB）"
                 % (path.name, len(data) / 1024 / 1024))
            _placeholder(img, "[图示：%s —— 超过微信 10 MB 上限，请压缩后重跑]"
                         % path.name)
            stats["skipped"] += 1
            continue
        b64 = base64.b64encode(data).decode("ascii")
        img["src"] = "data:%s;base64,%s" % (mime, b64)
        stats["mimes"][mime] = stats["mimes"].get(mime, 0) + 1
        stats["embedded"] += 1
    return stats


# ============================================================
# 自动目录 —— 新增能力 3
# ============================================================

def build_toc(soup, styles, *, max_level=3, title="本文目录"):
    """按 h2/h3 生成编号目录块。

    为什么不做成可点击锚点：微信会把 id 属性剥掉，站内锚点在发布后失效，
    点了不动的「假链接」体验比纯目录更差。这里诚实做成纯文本编号目录。
    """
    heads = [h for h in soup.find_all(["h2", "h3"])
             if h.get_text().strip()]
    if len(heads) < 2:
        return None
    box = soup.new_tag("p")
    box["style"] = styles["toc_box"]
    t = soup.new_tag("span")
    t["style"] = styles["toc_title"]
    t.string = title
    box.append(t)
    n1 = n2 = 0
    for h in heads:
        if h.name == "h2":
            n1 += 1
            n2 = 0
            label = "%d. %s" % (n1, h.get_text().strip())
            indent = ""
        else:
            if max_level < 3:
                continue
            n2 += 1
            label = "　　%d.%d %s" % (n1, n2, h.get_text().strip())
            indent = "padding-left: 12px;"
        item = soup.new_tag("p")
        item["style"] = styles["toc_item"] + " " + indent
        item.string = label
        box.append(item)
    return box


# ============================================================
# 元信息头 / 页脚版权 —— 新增能力 5
# ============================================================

def build_header(soup, styles, meta):
    """标题 + 作者/日期 行 + 摘要框。三者都缺时返回 None。"""
    title = (meta.get("title") or "").strip()
    author = (meta.get("author") or "").strip()
    date = (meta.get("date") or "").strip()
    abstract = (meta.get("abstract") or "").strip()
    if not (title or author or date or abstract):
        return None
    wrap = []
    if title:
        h = soup.new_tag("p")
        h["style"] = styles["meta_title"]
        h.string = title
        wrap.append(h)
    line = "　".join([x for x in (author, date) if x])
    if line:
        p = soup.new_tag("p")
        p["style"] = styles["meta_line"]
        p.string = line
        wrap.append(p)
    if abstract:
        box = soup.new_tag("p")
        box["style"] = styles["abstract"]
        txt = soup.new_tag("span")
        txt["style"] = styles["abstract_text"]
        txt.string = abstract
        box.append(txt)
        wrap.append(box)
    return wrap


def build_footer(soup, styles, meta):
    """页脚版权行。没有作者/显式页脚时返回 None（宁可不加，不加假的）。"""
    text = (meta.get("footer") or "").strip()
    if not text:
        author = (meta.get("author") or "").strip()
        if author:
            text = "© %s　保留所有权利　转载请注明出处" % author
    if not text:
        return None
    p = soup.new_tag("p")
    p["style"] = styles["footer"]
    p.string = text
    return p


# ============================================================
# 中英混排的「代码保护」包装
# ============================================================

_FENCE_RE = re.compile(r"(```.*?```|~~~.*?~~~)", re.S)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def apply_cjk_to_markdown(body, do_spacing=True, do_punct=True):
    """对正文做中英混排优化，**跳过代码块与行内代码**。

    这是改造里最容易出错的一处：无脑给全文补空格会把 `for i in range(3)`
    变成 `for i in range(3 )` 之类，或者把代码里的 `x=1` 动掉。这里做了两层保护。
    """
    if not (do_spacing or do_punct):
        return body
    parts = _FENCE_RE.split(body)
    out = []
    for i, seg in enumerate(parts):
        if i % 2 == 1:                       # 奇数段 = 围栏代码块，原样保留
            out.append(seg)
            continue
        code = _INLINE_CODE_RE.findall(seg)
        chunks = _INLINE_CODE_RE.split(seg)
        rebuilt = []
        for j, chunk in enumerate(chunks):
            if do_spacing:
                chunk = cjk_spacing(chunk)
            if do_punct:
                chunk = cjk_punct(chunk)
            rebuilt.append(chunk)
            if j < len(code):
                rebuilt.append(code[j])
        out.append("".join(rebuilt))
    return "".join(out)


# ============================================================
# 交付前硬验证 —— 按 references/wechat_restrictions.md 逐条机器检查
# ============================================================

FORBIDDEN_TAGS = ("script", "style", "iframe", "h1", "div",
                  "form", "input", "button", "object", "embed", "svg")
_FORBIDDEN_CSS_PROPS = ("position", "float", "flex", "grid", "animation",
                        "transition", "transform", "box-shadow", "@media", "@font-face")
MAX_CHARS = 20000
MAX_IMAGES = 100
MAX_IMG_BYTES = 10 * 1024 * 1024


def check_restrictions(html, *, max_chars=MAX_CHARS, max_images=MAX_IMAGES):
    """返回 (ok, issues)。issues 每项 {level, rule, detail}。

    规则来源：references/wechat_restrictions.md（微信编辑器实测限制）。
    这是本技能的「可验证」证据来源——不是我说合规，是它自己查出问题。
    """
    soup = BeautifulSoup(html, "lxml")
    issues = []

    for name in FORBIDDEN_TAGS:
        n = len(soup.find_all(name))
        if n:
            issues.append({"level": "error", "rule": "禁止标签",
                           "detail": "<%s> × %d" % (name, n)})

    bad_attrs = {}
    for tag in soup.find_all(True):
        for a in tag.attrs:
            low = a.lower()
            if low.startswith("on") or low in ("class", "id"):
                bad_attrs[low] = bad_attrs.get(low, 0) + 1
    for a, n in sorted(bad_attrs.items()):
        issues.append({"level": "error", "rule": "禁止属性",
                       "detail": "%s= × %d" % (a, n)})

    css_hits = {}
    for tag in soup.find_all(True):
        style = tag.get("style") or ""
        for prop in _FORBIDDEN_CSS_PROPS:
            if re.search(r"(?<![\w-])" + re.escape(prop) + r"\s*:", style, re.I):
                css_hits[prop] = css_hits.get(prop, 0) + 1
    for prop, n in sorted(css_hits.items()):
        issues.append({"level": "error", "rule": "禁止 CSS",
                       "detail": "%s: × %d（微信会丢弃）" % (prop, n)})

    imgs = soup.find_all("img")
    if len(imgs) > max_images:
        issues.append({"level": "error", "rule": "图片数量",
                       "detail": "%d > %d 上限" % (len(imgs), max_images)})
    remote = 0
    for img in imgs:
        src = (img.get("src") or "").strip()
        if src.startswith(("http://", "https://")):
            remote += 1
        elif not src.startswith("data:image/"):
            issues.append({"level": "error", "rule": "图片源",
                           "detail": "非法 src：%s" % (src[:60] or "(空)")})
    if remote:
        issues.append({"level": "warning", "rule": "外链图片",
                       "detail": "%d 张外链图（可能被防盗链拦截，建议内联）" % remote})

    text = soup.get_text()
    if len(text) > max_chars:
        issues.append({"level": "error", "rule": "篇幅",
                       "detail": "%d 字 > %d 上限" % (len(text), max_chars)})

    ok = not any(i["level"] == "error" for i in issues)
    return ok, issues


# ============================================================
# 主流程
# ============================================================

MD_EXTENSIONS = ["extra", "fenced_code", "nl2br", "sane_lists"]


def convert(src, out_path=None, *, theme="default", embed=True, toc=True,
            header=True, footer=True, cjk=True, extra_meta=None, report_path=None):
    """Markdown / Word → 公众号可直接粘贴的 HTML。返回结果字典（含验证结论）。"""
    src = Path(src)
    warn_log = []
    if not src.exists():
        raise FileNotFoundError("输入文件不存在：%s" % src)
    if src.stat().st_size == 0:
        # 修复项 B1：starter 对空文件返回成功并产出空 HTML，属于静默失败
        raise ValueError("输入文件是空文件：%s" % src.name)

    suffix = src.suffix.lower()
    if suffix in (".md", ".markdown", ".txt", ".mdx"):
        text, enc = read_text(src)
        meta, body = split_front_matter(text)
        if cjk:
            body = apply_cjk_to_markdown(body)
        html = markdown.markdown(body, extensions=MD_EXTENSIONS)
    elif suffix == ".docx":
        html, meta, _body, enc = read_docx(src)
    elif suffix in (".html", ".htm"):
        text, enc = read_text(src)
        meta, body = split_front_matter(text)
        html = body
    else:
        raise ValueError("不支持的输入格式：%s（支持 .md/.markdown/.txt/.docx/.html）" % suffix)

    if theme not in THEMES:
        warn_log.append("未知主题 %r，回退 default（可选：%s）"
                        % (theme, ", ".join(sorted(THEMES))))
        theme = "default"
    styles = build_styles(theme)

    soup = BeautifulSoup(html, "lxml")
    sanitize(soup, styles)
    clean_attributes(soup)
    apply_styles(soup, styles)

    img_stats = embed_images(soup, src.parent, warn_log.append, embed=embed)

    meta_all = dict(meta)
    for k, v in (extra_meta or {}).items():
        if v:
            meta_all[k] = v

    if header:
        head_nodes = build_header(soup, styles, meta_all)
        if head_nodes:
            for node in reversed(head_nodes):
                soup.insert(0, node)
    toc_box = build_toc(soup, styles) if toc else None
    if toc_box is not None:
        soup.insert(0, toc_box)
    if footer:
        foot = build_footer(soup, styles, meta_all)
        if foot is not None:
            soup.append(foot)

    out_html = str(soup)
    ok, issues = check_restrictions(out_html)

    if out_path is None:
        out_path = src.with_name(src.stem + "_wechat.html")
    out_path = Path(out_path)
    out_path.write_text(out_html, encoding="utf-8")

    report = {
        "ok": ok, "input": str(src), "output": str(out_path),
        "theme": theme, "theme_label": THEMES[theme]["label"],
        "encoding": enc, "bytes": out_path.stat().st_size,
        "chars": len(BeautifulSoup(out_html, "lxml").get_text()),
        "images": img_stats, "issues": issues, "warnings": warn_log,
    }
    if report_path:
        Path(report_path).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


# ============================================================
# 命令行入口 + 自检套件
# ============================================================

SELFTEST_MD = """---
title: 自检样例文章
author: Zhouruoying
date: 2026-10-05
abstract: 用于验证转换管线的样例摘要。
---

# 一级标题应被降级为 h2

正文混排 AI时代 的写法，还有 `x=1` 这样的行内代码。

## 第一节

> [!WARNING] 别踩这个坑
> 半角逗号在中文里, 看起来会有点怪.

- 列表项一
- 列表项二

```python
def f(x):
    return x + 1
```

| 列 A | 列 B |
| --- | --- |
| 1 | 2 |
"""

SELFTEST_DIRTY_HTML = """<h1>脏输入</h1>
<div class="wrapper" id="w1">
<p onclick="alert(1)" style="color:red; position:fixed; float:left;">正文</p>
<script>alert(2)</script>
<style>.x{color:red}</style>
<p><a href="https://example.com" class="link">链接</a></p>
<iframe src="https://evil.example"></iframe>
</div>"""


def run_self_test(workdir=None):
    """正例 1 条 + 反例 8 条，逐条打印 PASS/FAIL。返回 (exit_code, passed, failed)。"""
    import shutil
    import tempfile

    tmp = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="wechat-selftest-"))
    tmp.mkdir(parents=True, exist_ok=True)
    results = []

    def case(name, fn):
        try:
            fn()
            results.append((name, True, ""))
        except AssertionError as exc:
            results.append((name, False, str(exc) or "断言失败"))
        except Exception as exc:                       # 非预期异常也算失败
            results.append((name, False, "%s: %s" % (type(exc).__name__, exc)))

    # ---- 正例：完整管线 ----
    md_path = tmp / "sample.md"
    md_path.write_text(SELFTEST_MD, encoding="utf-8")
    out_path = tmp / "sample_wechat.html"

    def case_positive():
        rep = convert(md_path, out_path)
        html = out_path.read_text(encoding="utf-8")
        assert rep["ok"], "存在 error 级问题：%s" % rep["issues"]
        assert "<h1" not in html, "h1 未降级"
        assert "AI 时代" in html, "中英混排未补空格"
        assert "x=1" in html, "行内代码被改动"
        assert "别踩这个坑" in html and "⚠️" in html, "callout 未生成"
        assert "\u00a0\u00a0\u00a0\u00a0return x + 1" in html, "代码块缩进丢失"
        assert "本文目录" in html, "目录未生成"
        assert "© Zhouruoying" in html, "页脚未生成"
        assert "class=" not in html, "残留 class 属性"
        assert "<div" not in html, "残留 div"
    case("正例 · 完整管线（主题/目录/callout/混排/代码/页脚）", case_positive)

    # ---- 反例 A：空文件必须报错（starter 会静默成功）----
    def case_empty():
        empty = tmp / "empty.md"
        empty.write_text("", encoding="utf-8")
        try:
            convert(empty, tmp / "empty.html")
        except ValueError:
            return
        raise AssertionError("空文件未报错——静默失败未修复")
    case("反例A · 空文件应报错（修复 B1）", case_empty)

    # ---- 反例 B：GBK 编码回退（starter 会 UnicodeDecodeError）----
    def case_gbk():
        gbk = tmp / "gbk.md"
        gbk.write_bytes("# 中文标题\n\n这是一段用 GBK 保存的中文。".encode("gbk"))
        rep = convert(gbk, tmp / "gbk.html")
        html = (tmp / "gbk.html").read_text(encoding="utf-8")
        assert rep["encoding"] in ("gbk", "gb18030"), "编码未回退：%s" % rep["encoding"]
        assert "这是一段用 GBK 保存的中文" in html, "中文未正确解码"
    case("反例B · GBK 输入按 GBK 解码（修复 B2）", case_gbk)

    # ---- 反例 C：脏 HTML 净化（script/iframe/onclick/class/div/h1）----
    def case_dirty():
        dirty = tmp / "dirty.html"
        dirty.write_text(SELFTEST_DIRTY_HTML, encoding="utf-8")
        rep = convert(dirty, tmp / "dirty_wechat.html")
        html = (tmp / "dirty_wechat.html").read_text(encoding="utf-8")
        assert rep["ok"], "净化后仍有 error：%s" % rep["issues"]
        for bad in ("<script", "<iframe", "<h1", "<div", "onclick", "class=",
                    "position:", "float:"):
            assert bad not in html, "残留禁止内容：%s" % bad
        assert "正文" in html and "链接" in html, "净化误删正文"
    case("反例C · 脏 HTML 净化保留正文（修复 B3/B6）", case_dirty)

    # ---- 反例 D：SVG 图片被识别并替换为降级提示 ----
    def case_svg():
        svg = tmp / "pic.svg"
        svg.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
        md = tmp / "svg.md"
        md.write_text("![图](pic.svg)\n", encoding="utf-8")
        rep = convert(md, tmp / "svg_wechat.html")
        html = (tmp / "svg_wechat.html").read_text(encoding="utf-8")
        assert "SVG 不被微信支持" in html, "SVG 未被拦截"
        assert any("SVG" in w for w in rep["warnings"]), "SVG 未产生警告"
    case("反例D · SVG 图被拦截并警告（微信会丢图）", case_svg)

    # ---- 反例 E：PNG 本地图内联为 base64 ----
    def case_png_inline():
        png = tmp / "px.png"
        png.write_bytes(bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
            "890000000a49444154789c6300010000050001"
            "0d0a2db40000000049454e44ae426082"))
        md = tmp / "png.md"
        md.write_text("![像素](px.png)\n", encoding="utf-8")
        rep = convert(md, tmp / "png_wechat.html")
        html = (tmp / "png_wechat.html").read_text(encoding="utf-8")
        assert "data:image/png;base64," in html, "PNG 未内联"
        assert rep["images"]["embedded"] == 1, "内联计数不对：%s" % rep["images"]
    case("反例E · 本地 PNG 内联为 base64（防防盗链）", case_png_inline)

    # ---- 反例 F：中英混排不破坏代码 ----
    def case_cjk_guard():
        body = "正文 AI时代 混排\n\n```\nfor i in range(3)\n```\n\n行内 `a,b=1,2` 保持。\n"
        out = apply_cjk_to_markdown(body)
        assert "AI 时代" in out, "未补空格"
        assert "for i in range(3)" in out, "代码块被改动：%r" % out
        assert "`a,b=1,2`" in out, "行内代码被改动：%r" % out
    case("反例F · 混排优化不碰代码（新增能力 4 护栏）", case_cjk_guard)

    # ---- 反例 G：校验器自身能发现违规（负向验证校验器）----
    def case_checker_catches():
        ok, issues = check_restrictions(
            '<p style="position:fixed;">a</p><h1>b</h1><script>x</script>')
        assert not ok, "校验器漏报"
        rules = {i["rule"] for i in issues}
        assert "禁止 CSS" in rules and "禁止标签" in rules, "规则覆盖不全：%s" % rules
    case("反例G · 校验器能捕获违规（校验器自证）", case_checker_catches)

    # ---- 反例 H：data URI 的标签必须与真实字节一致（修复 B8）----
    # 不变量：把每个 data URI 解回字节再嗅探一次，标签必须等于嗅探结果。
    # 这样无论本机有没有 Pillow（有则转真 PNG、无则原样内联），结论都成立；
    # 初版写死 image/png 时，JPEG/GIF 源图会被贴上 PNG 标签（微信侧裂图）。
    def case_mime_match():
        import base64 as _b64
        import re as _re
        samples = {
            "photo.jpg": _b64.b64decode(
                "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0"
                "aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAA"
                "AAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q=="),
            "anim.gif": _b64.b64decode(
                "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"),
        }
        for fname, blob in samples.items():
            assert sniff_image_mime(blob), "测试素材本身无法识别：%s" % fname
            (tmp / fname).write_bytes(blob)
        (tmp / "weird.bin").write_bytes(b"\x00\x01\x02\x03 not an image")
        md = tmp / "mime.md"
        md.write_text("![j](photo.jpg)\n\n![g](anim.gif)\n\n![w](weird.bin)\n",
                      encoding="utf-8")
        rep = convert(md, tmp / "mime_wechat.html")
        html = (tmp / "mime_wechat.html").read_text(encoding="utf-8")
        uris = _re.findall(r"data:(image/[a-z]+);base64,([A-Za-z0-9+/=]+)", html)
        assert len(uris) == 2, "应内联 2 张图，实际 %d 张" % len(uris)
        for label, blob in uris:
            real = sniff_image_mime(_b64.b64decode(blob))
            assert real == label, "标签与字节不符：标签=%s 实际=%s" % (label, real)
        assert rep["images"]["skipped"] == 1, \
            "无法识别的图片未被跳过：%s" % rep["images"]
        assert any("weird.bin" in w for w in rep["warnings"]), "跳过未产生警告"
        # 修复 B9：坏图不能被留成「残留本地 src」，否则一张图就让整篇校验失败
        assert rep["ok"], "坏图导致整篇转换失败（修复 B9）：%s" % rep["issues"]
        assert "无法内联" in html, "坏图未替换为降级提示"
    case("反例H · 标签与字节一致 + 坏图降级为提示行（修复 B8/B9）", case_mime_match)

    passed = sum(1 for _, ok_, _ in results if ok_)
    failed = len(results) - passed
    for name, ok_, detail in results:
        print("%-4s %s%s" % ("PASS" if ok_ else "FAIL", name,
                             "" if ok_ else "  → " + detail))
    print("\n自检结果：%d/%d PASS" % (passed, len(results)))
    if workdir is None:
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        print("产物保留在：%s" % tmp)
    return (0 if failed == 0 else 1), passed, failed


# ============================================================
# 命令行入口
# ============================================================

def _fmt_report(report):
    mark = "✅" if report["ok"] else "❌"
    lines = [
        "%s 转换完成：%s" % (mark, report["output"]),
        "   主题：%s（--theme %s）" % (report["theme_label"], report["theme"]),
        "   字符数：%d · 输出 %d 字节 · 源编码：%s"
        % (report["chars"], report["bytes"], report["encoding"]),
        "   图片：内联 %d / 外链 %d / 跳过 %d"
        % (report["images"]["embedded"], report["images"]["remote"],
           report["images"]["skipped"]),
    ]
    errs = [i for i in report["issues"] if i["level"] == "error"]
    warns = [i for i in report["issues"] if i["level"] == "warning"]
    lines.append("   限制校验：%s（%d error / %d warning）"
                 % ("通过" if report["ok"] else "未通过", len(errs), len(warns)))
    for i in errs + warns:
        lines.append("     - [%s] %s：%s" % (i["level"], i["rule"], i["detail"]))
    for w in report["warnings"]:
        lines.append("     - [提示] %s" % w)
    if report["ok"]:
        lines.append("   下一步：浏览器打开该 HTML → Ctrl+A → Ctrl+C → 粘进公众号编辑器")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="convert_to_wechat.py",
        description="Markdown / Word → 微信公众号「可直接粘贴」HTML（纯本地，零第三方服务）",
        epilog="自检：python3 convert_to_wechat.py --self-test")
    ap.add_argument("input", nargs="?", help="输入文件（.md / .markdown / .txt / .docx / .html）")
    ap.add_argument("-o", "--output", help="输出 HTML 路径（默认 输入名_wechat.html）")
    ap.add_argument("--theme", default="default",
                    help="主题：default / blue / warm / minimal（默认 default）")
    ap.add_argument("--title", help="覆盖标题（默认取 front matter）")
    ap.add_argument("--author", help="覆盖作者（页脚署名用）")
    ap.add_argument("--date", help="覆盖日期")
    ap.add_argument("--abstract", help="覆盖摘要（标题下的引言块）")
    ap.add_argument("--footer-text", help="自定页脚文案；缺省用 front matter 的 footer / 作者署名")
    ap.add_argument("--no-toc", action="store_true", help="不生成目录")
    ap.add_argument("--no-header", action="store_true", help="不生成标题头")
    ap.add_argument("--no-footer", action="store_true", help="不生成页脚")
    ap.add_argument("--no-embed", action="store_true", help="不内联本地图片")
    ap.add_argument("--no-cjk", action="store_true", help="不做中英混排优化")
    ap.add_argument("--report", help="把验证报告另存为 JSON")
    ap.add_argument("--list-themes", action="store_true", help="列出全部主题后退出")
    ap.add_argument("--self-test", action="store_true", help="跑内置正反例自检套件")
    ap.add_argument("--keep-selftest", help="自检产物保留到该目录（默认用临时目录并清理）")
    args = ap.parse_args(argv)

    if args.list_themes:
        for key in ("default", "blue", "warm", "minimal"):
            print("%-9s %s" % (key, THEMES[key]["label"]))
        return 0

    if args.self_test:
        code, passed, failed = run_self_test(args.keep_selftest)
        return code

    if not args.input:
        ap.print_help()
        return 2

    extra_meta = {"title": args.title, "author": args.author, "date": args.date,
                  "abstract": args.abstract, "footer": args.footer_text}
    try:
        report = convert(
            args.input, args.output, theme=args.theme,
            embed=not args.no_embed, toc=not args.no_toc,
            header=not args.no_header, footer=not args.no_footer,
            cjk=not args.no_cjk, extra_meta=extra_meta, report_path=args.report)
    except (FileNotFoundError, ValueError) as exc:
        print("❌ %s" % exc, file=sys.stderr)
        return 1

    print(_fmt_report(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
