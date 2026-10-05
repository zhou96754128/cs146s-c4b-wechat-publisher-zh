# WeChat Publisher v2.0 — 样式与调色板参考

本文件是 `scripts/convert_to_wechat.py` 中 `THEMES` / `CALLOUTS` / `build_styles()` 的
人类可读版本。**样式全部由调色板推导**，改主题只需换一组色值，不必逐条改 px。

## 一、4 套内置主题（`--theme`）

| key | 名称 | 适用场景 | primary | accent | soft | border | muted |
|-----|------|----------|---------|--------|------|--------|-------|
| `default` | 默认 · GitHub 灰 | 通用技术文 | `#333333` | `#0366d6` | `#f6f8fa` | `#dddddd` | `#666666` |
| `blue` | 蓝色 · 科技/知识 | 教程、原理讲解 | `#1f3a5f` | `#2b6cb0` | `#eef4fb` | `#c9ddf2` | `#4a6f96` |
| `warm` | 暖色 · 个人叙事 | 复盘、经历分享 | `#43281c` | `#c05621` | `#fdf3ec` | `#f0d6c2` | `#8a6a56` |
| `minimal` | 极简 · 黑白高对比 | 观点、檄文 | `#111111` | `#111111` | `#fafafa` | `#e5e5e5` | `#555555` |

每个主题另有 `mark_bg` / `mark_fg` 两个色值专供行内代码底色与字色
（如 default 为 `#f5f5f5` / `#d73a49`）。

查看当前可用主题与中文说明：

```bash
python3 scripts/convert_to_wechat.py --list-themes
```

## 二、由调色板推导的默认样式（`build_styles()`）

| 元素 | 关键样式 |
|------|----------|
| `h2`（章节标题） | 21px 粗体 / lh 1.5 / primary 色 / 左 4px accent 色条 |
| `h3`（小节标题） | 17px 粗体 / lh 1.6 / accent 色 |
| `p`（正文） | 16px / lh 1.75 / `#3f3f3f`（不用纯黑，手机上对比更柔）/ `word-break: break-word` |
| `li` | 16px / lh 1.75 / 上下 6px 间距 |
| 行内代码 | `mark_bg` 底 / `mark_fg` 字 / 14px / 圆角 3px |
| 代码块 | `soft` 底 / 13px / lh 1.6 / `white-space: pre-wrap` / `overflow-x: auto` |
| 引用块 | `soft` 底 / muted 字 / 左 4px border 色条 |
| 表格 | `border-collapse` / 100% 宽 / 14px；表头 `soft` 底 primary 字 |
| 链接 | accent 色 + 下划线 |
| 分隔线 | 1px `border` 色上边线 |
| 图片 | `max-width: 100%; height: auto; display: block`（防溢出手机屏） |
| 标题头 | 26px 粗体 primary + 14px muted 元信息行 |
| 摘要块 | `soft` 底 + `border` 描边 + 圆角 6px |
| 目录块 | `soft` 底 + `border` 描边；条目 15px accent 色，行高 1.9 |
| 页脚 | 13px muted / 居中 / 顶部 1px 分隔线 |

> 实现要点：默认样式**只在元素本身没有 `style` 属性时才补**，不覆盖作者手写的内联样式。

## 三、Callout 高亮框（`> [!TYPE]`）

四种语义的配色**固定、不随主题变化**——这样在微信里「看到黄色就是警告」的认知始终成立。

| 类型 | 图标 | 默认标题 | 文字色 | 底色 | 左边条 |
|------|------|----------|--------|------|--------|
| `note` | 📘 | 知识点 | `#1f4e79` | `#eef4fb` | `#2b6cb0` |
| `tip` | 💡 | 小技巧 | `#1c5c3a` | `#eefaf1` | `#2f9e63` |
| `warning` | ⚠️ | 注意 | `#8a4b00` | `#fff7e6` | `#d99a2b` |
| `info` | 📌 | 补充说明 | `#5a3a7a` | `#f5f0fb` | `#8a63c9` |

中文别名等价可用：`[!知识]` `[!知识点]` `[!小技巧]` `[!技巧]` `[!警告]` `[!注意]`
`[!说明]` `[!补充]` `[!补充说明]`，以及 `[!warn]` `[!hint]` `[!caution]`。

写法（首行标记类型，正文接在后面的引用行）：

```markdown
> [!TIP]
> 先跑 `--self-test` 再跑真实文章，出问题能立刻定位到是环境还是内容。
```

## 四、移动端硬约束（为什么是这些数值）

- **正文字号 ≥ 16px**：更小在手机上读不动。
- **行高 1.75**：中文密排时 1.5 显挤、2.0 显散。
- **不用纯黑**：`#3f3f3f` / `#333` 比 `#000` 在 OLED 屏上更耐读。
- **显示宽度约 375px**：所有块级元素须自适应，图片必须 `max-width:100%`。
- **表格无横向滚动**：列多的表要在源文里拆开，见 `wechat_restrictions.md`。
