# 微信公众号 HTML 限制清单（脚本强制执行的版本）

本文件是约束的「单一事实来源」。脚本 `check_restrictions()` 与净化流水线都按它执行，
并把结果写进每次运行的报告与 `--report` JSON。

## 一、允许 / 禁止的标签

**允许**：`p, h2, h3, ul, ol, li, span, img, a, table, tr, th, td, br`

| 禁止标签 | 原因 | 脚本的处理 |
|----------|------|------------|
| `<h1>` | 微信把 h1 保留给文章标题 | 降级为 `<h2>` |
| `<div>` | 渲染不可靠 | 降级为 `<p>` |
| `<script>` | 安全，必被剥离 | 整块删除 |
| `<style>` | 只允许内联样式 | 删除，样式已转内联 |
| `<iframe>` / `<video>` / `<audio>` | 外链嵌入不允许 | 删除或转成链接 |
| `<pre>` / `<code>`（块级） | 微信里换行会被吃掉 | 转单个 `<p>` + 显式 `<br>` |

## 二、允许 / 禁止的属性

**保留**：`style, src, href, alt, title, colspan, rowspan`
**剥离**：`class`、`id`、`name`、`on*`（事件）、`data-*`、`aria-*`

## 三、CSS 规则

只允许**内联**写在 `style=""` 里，不允许 `<style>` 块或外链 CSS。

**允许的属性**：`color, background-color, font-size, font-weight, font-style,
line-height, text-align, margin, padding, border, border-left, border-collapse,
text-decoration, display, vertical-align, max-width, width, border-radius,
white-space, word-break, overflow-x`

**禁止的属性**（会被逐条剔除）：
`position, float, grid, grid-template-columns/rows, flex, flex-direction,
justify-content, align-items, animation, transition, transform, z-index,
visibility, top/left/right/bottom, filter, backdrop-filter, box-shadow, @media`

> **实现细节**：校验是**按元素 `style` 属性逐条扫**，不是对整页 HTML 做 grep。
> 因此它不会把正文里恰好出现的英文单词误判成 CSS，也能报出「第几处违规、违反哪一条」。
> 自检用例 G 专门验证这一点：向输出注入一条违规 CSS，校验器必须抓出来，否则自检失败。

## 四、图片规则

| 方式 | 可用? | 说明 |
|------|-------|------|
| `<img src="https://...">` | ⚠️ | 可访问才显示；微信可能改存到自己 CDN |
| `<img src="data:image/png;base64,...">` | ✅ | 粘贴时微信自动转存，最稳 |
| `<img src="data:image/svg+xml;base64,...">` | ❌ | 保存后图片消失 |
| 内联 `<svg>...</svg>` | ❌ | 被整体剥离 |

**脚本策略**：本地图片自动转 **base64 PNG** 内联（`--no-embed` 关闭）；检测到 SVG
**主动拦截并警告**，而不是静默产出一张会在微信里消失的图。单图 >10 MB 跳过并警告
（微信上限），文件缺失同样警告不崩。

## 五、文章上限

| 限制 | 值 |
|------|-----|
| 正文字数 | 约 20,000 中文字符（`MAX_CHARS`，超出警告） |
| 图片数量 | 100 张（`MAX_IMAGES`，超出警告） |
| 单图大小 | 10 MB |
| 图片格式 | PNG / JPG / GIF |
| GIF 大小 | ≤ 2 MB |

## 六、常见坑（都对应脚本里的一条防线）

1. **保存后格式变了** → 用了禁止标签或禁止 CSS：本脚本在输出前逐条剥离。
2. **图片不见了** → SVG data URI 或失效外链：脚本拦截 SVG 并提示改用 PNG。
3. **代码换行被吃掉** → `<pre><code>` 不被支持：脚本转 `<p>` + `<br>` 保住换行。
4. **表格太宽** → 微信没有横向滚动：需在源文里拆表，或改写成列表。
5. **粘贴后大片空白** → 微信对 margin 的折叠与浏览器不同：用 `soft` 底色块代替空白分隔。
