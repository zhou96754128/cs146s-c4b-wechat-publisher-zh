---
name: wechat-publisher
description: >
  把 Markdown / Word / 纯文本转成微信公众号「可直接粘贴」的 HTML：内联 CSS 排版、
  标签与属性净化、4 套主题配色、callout 高亮框、自动目录、中英混排优化、本地图片
  base64 内联、发布限制自检。当用户说「转公众号」「公众号排版」「WeChat HTML」
  「convert to WeChat」「把这篇文章发到公众号」，或给出 .md / .docx / .txt 要求
  排版成公众号可粘贴格式时使用。
license: 基于 Elite20 提供的 wechat-publisher starter kit 改造（作者 Zhouruoying）
---

# WeChat Publisher v2.0 — Markdown/Word → 公众号 HTML

## 这个技能解决什么

公众号编辑器只吃**内联样式的窄子集 HTML**：`<div>`、`<h1>`、`class`、`<style>` 块、
`float/flex/grid` 的一律被剥掉或渲染异常；代码块、表格、图片换行在粘贴后经常崩。
手工改一篇 3000 字文章要 1 小时以上，且每次都要重来。

本技能把这一步变成一条命令：**源文件进 → 可粘贴 HTML 出**，并在输出前用规则清单自检。

## 快速开始

```bash
# 1. 最简：默认主题 + 目录
python3 scripts/convert_to_wechat.py article.md article_wechat.html

# 2. 常用：换主题 + 页脚署名
python3 scripts/convert_to_wechat.py article.md out.html --theme blue --footer-text "© 2026 Zhouruoying"

# 3. 先看有哪些主题
python3 scripts/convert_to_wechat.py --list-themes

# 4. 自检（不需输入文件，9 条正反例）
python3 scripts/convert_to_wechat.py --self-test
```

拿到 HTML 后：浏览器打开 → `Ctrl+A` → `Ctrl+C` → 粘进公众号编辑器 → 手机预览 → 发布。

## 输入 → 输出契约

| 输入 | 处理方式 |
|------|----------|
| `.md` / `.markdown` | `markdown` 解析（extra / fenced_code / nl2br / sane_lists） |
| `.txt` | 按纯文本包段落 |
| `.html` | 直接进入净化流水线（便于二次加工） |
| `.docx` | `python-docx` 读取段落、标题、加粗/斜体，**含表格**；未装则明确报错提示安装 |

| 输出 | 说明 |
|------|------|
| `*.html` | 可粘贴 HTML，全部内联样式 |
| `--report x.json` | 验证报告（字符数、图片数、违规项、主题），便于留痕 |
| 退出码 | `0` = 通过；非 0 = 有硬违规或输入错误（可直接进 CI） |

## 四项新增能力的写法

**1. 主题**：`--theme default|blue|warm|minimal`，全部样式由调色板推导，
不写死颜色。细节见 `references/wechat_styles.md`。

**2. Callout 高亮框**：在 Markdown 里用 GitHub 风格引用块，首行标记类型：

```markdown
> [!NOTE]
> 知识点正文……

> [!WARNING]
> 注意正文……
```

四种类型与中文别名（`[!知识点]`、`[!小技巧]`、`[!警告]`、`[!补充说明]` 等）等价。
渲染成带图标、浅色底、左侧色条的独立区块，且**颜色不依赖主题**——保证在微信里
四种语义始终可区分。

**3. 自动目录**：默认生成（`--no-toc` 关闭），依据 `h2`/`h3` 两级、带序号。
目录是**纯文本编号，不带 `id` 锚点**——微信不认 `id`，带锚点的目录点不动。

**4. 中英混排优化**：CJK 与拉丁字母/数字之间自动补空格（`AI工具` → `AI 工具`），
CJK 语境下的半角 `, : ; ? !` 转全角。**默认跳过代码块与行内代码**，不污染代码。
`--no-cjk` 关闭。

另有：YAML front matter 或 `--title/--author/--date/--abstract` 控制标题头与摘要，
`--footer-text` 控制页脚（另有 `--no-header` / `--no-footer`）。

## 图片处理

本地图片自动转 **base64 内联**（`--no-embed` 关闭）：

- **标签必须与真实字节一致**：先嗅探魔术字节（PNG / JPEG / GIF）再决定 data URI 的
  mime，不写死 PNG。装了 Pillow 就把图统一转 PNG，未装则按原格式内联——两条路径
  产出的标签都不会与实际字节不符（贴错 mime 在微信侧会裂图）。
- 微信**只认 PNG/JPG/GIF 的 base64**；SVG 的 data URI 与内联 `<svg>` 保存后会丢图，
  因此脚本主动拦截 SVG 并给警告，而不是静默产出坏图。
- 单图 >10 MB 跳过（微信上限）；文件缺失、`.svg`、字节无法识别也同样跳过，并把该
  `<img>` **换成一行居中提示**——不留本地路径，避免一张坏图让整篇校验失败。
- 所有 `<img>` 自动补 `max-width:100%; height:auto`，防在手机屏上溢出。

## 强制遵守的公众号限制

完整清单见 `references/wechat_restrictions.md`。脚本自动执行的核心几条：

- 允许标签仅 `p,h2,h3,ul,ol,li,span,img,a,table,tr,th,td,br`；其余按语义降级
  （`<h1>`→`<h2>`，`<div>`→`<p>`，`script/style/iframe` 删除）。
- 属性仅保留 `style,src,href,alt,title,colspan,rowspan`；`class/id/on*` 一律剥离。
- **内联 CSS 白名单过滤**：`position/float/flex/grid/animation/transition/@media` 等
  布局与动效属性会被逐条剔除（按元素 `style` 逐条扫，不是整页 grep）。
- 代码块 → 单个 `<p>` + 显式 `<br>`，保住换行（`<pre><code>` 在微信里换行会被吃掉）。
- 长文 / 图片数量超限会警告。

## 校验器（不只看输出，还自证）

每次运行结束打印一份报告：主题、字数、图片数、**违规项计数**、是否通过。
`--self-test` 跑 9 条内建用例：1 条完整管线正例 + 8 条负例（空文件、GBK 输入、
脏 HTML、SVG 图、本地 PNG 内联、代码保护护栏、校验器自证、data URI 标签与字节
一致且坏图降级为提示行）。
校验器本身也在用例里被验证——它必须能抓出人为注入的违规，否则算失败；用例还做过
变异验证（把 mime 写死回 PNG，该用例立刻转红），证明它测的是真东西而不是空跑。

## 边界与已知取舍

| 情况 | 处理 |
|------|------|
| 空文件 | 报错退出，**不产出空 HTML** |
| 非 UTF-8 | 依次尝试 UTF-8 → UTF-8-sig → GBK → GB18030 → Big5 |
| 外部图片 URL | 保留原样并提示先上传微信素材库 |
| 超宽表格 | 暂不特殊处理（微信无横向滚动），建议拆表（见限制文档） |
| 数学公式 | 未支持，建议先渲成 PNG 再插入 |

`references/CHANGELOG-vs-starter.md` 记录了相对 starter 的全部改动与实测证据。
