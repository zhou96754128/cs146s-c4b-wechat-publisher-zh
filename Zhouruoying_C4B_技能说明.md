# Zhouruoying C4B 技能说明 · wechat-publisher v2.0

> 一句话：把 Markdown / Word / 纯文本变成**微信公众号里能直接粘贴的 HTML**，
> 并在输出前用规则清单自检——源文件进，可粘贴 HTML 出。

- 技能标识：`wechat-publisher`（包 `Zhouruoying_C4B_wechat-publisher.skill`）
- 基底：Elite20 提供的 `wechat-publisher` starter kit；本人在其之上做了 **4 项能力扩展 + 9 处缺陷修复**
- 依赖：核心链路只用 Python 3 标准库。可选 `markdown`（富解析）、`python-docx`（读 Word）、`Pillow`（图片统一转 PNG）。**没有硬依赖**——缺了会降级或明确报错，不会静默产出坏东西。

## 1. 它替谁省事

公众号编辑器只吃**内联样式的窄子集 HTML**。`<div>`、`<h1>`、`class`、`<style>` 块、
`float/flex/grid` 一律被剥掉或渲染异常；代码块、表格、图片换行粘进去经常崩。
手工改一篇 3000 字文章要 1 小时以上，而且下次还得重来。

本技能把这一步压成**一条命令**，并在写文件前用规则清单自检，把「排版事故」提前变成
退出码。

## 2. 输入 → 输出契约

| 输入 | 处理 |
|------|------|
| `.md` / `.markdown` | markdown 解析（extra / fenced_code / nl2br / sane_lists） |
| `.txt` | 按纯文本包段落 |
| `.html` | 直接进净化流水线（便于二次加工） |
| `.docx` | `python-docx` 读段落、标题、加粗/斜体、表格；未装则明确报错并给出安装命令 |

| 输出 | 说明 |
|------|------|
| `*.html` | 可粘贴 HTML，样式**全部内联** |
| `--report x.json` | 验证报告（字符数、图片数、违规项、主题），可留痕 |
| 退出码 | `0` = 通过；非 0 = 有硬违规或输入错误（可直接接 CI） |

## 3. 四项新增能力

**① 主题系统**：`--theme default|blue|warm|minimal`。整套样式由调色板推导，
不写死颜色，换主题不会漏掉某个角落。细节见 `references/wechat_styles.md`。

**② Callout 高亮框**：Markdown 里用 GitHub 风格引用块 + 首行类型标记：

```markdown
> [!NOTE]
> 知识点正文……

> [!WARNING]
> 注意正文……
```

四种类型（note/tip/warning/info）与中文别名（`[!知识点]`、`[!小技巧]`、`[!警告]`、
`[!补充说明]`）等价，渲染成带图标、浅底、左侧色条的独立区块。**颜色不随主题变**——
这样四种语义在任何主题下都始终可区分。

**③ 自动目录**：默认生成（`--no-toc` 关），取 `h2`/`h3` 两级带序号。
目录是**纯文本编号、不带 `id` 锚点**——微信不认 `id`，带锚点的目录点不动，
与其给个点了没反应的目录，不如给一个纯编号的。

**④ 中英混排优化**：CJK 与拉丁字母/数字之间自动补空格（`AI工具` → `AI 工具`），
CJK 语境下半角 `, : ; ? !` 转全角。**默认跳过代码块与行内代码**，不污染代码。
`--no-cjk` 关闭。

另有：YAML front matter 或 `--title/--author/--date/--abstract` 控制标题头与摘要，
`--footer-text` 控制页脚（`--no-header` / `--no-footer`）。

## 4. 图片处理（本次改动最集中的地方）

本地图片自动内联为 base64（`--no-embed` 关）：

- **标签必须与真实字节一致**：先嗅探魔术字节（PNG / JPEG / GIF）再决定 data URI 的
  mime，不写死。装了 Pillow 就把图统一转 PNG，未装则按原格式内联。
  两条路径产出的标签都与字节相符——**贴错 mime 在微信侧就是裂图**，这是不能靠
  「反正大部分是 PNG」蒙过去的地方。
- **SVG 主动拦截**：SVG 的 data URI 与内联 `<svg>` 在微信里保存后会丢图，
  所以脚本给警告而不是静默产出坏图。
- **坏图降级为提示行**：超 10 MB、文件缺失、`.svg`、字节无法识别 —— 一律把该
  `<img>` 换成一行居中提示。**不留本地路径**：残留的本地 src 会被自家校验器判为
  硬违规，一张坏图就能让整篇文章转换失败（这是实跑暴露的真实缺陷，见 B9）。
- 所有 `<img>` 自动补 `max-width:100%; height:auto`，防手机屏溢出。

## 5. 强制遵守的公众号限制

完整清单见 `references/wechat_restrictions.md`，脚本自动执行的核心几条：

- 允许标签仅 `p,h2,h3,ul,ol,li,span,img,a,table,tr,th,td,br`；其余按语义降级
  （`<h1>`→`<h2>`，`<div>`→`<p>`，`script/style/iframe` 删除）。
- 属性仅留 `style,src,href,alt,title,colspan,rowspan`；`class/id/on*` 一律剥离。
- **内联 CSS 白名单过滤**：`position/float/flex/grid/animation/transition/@media` 等
  逐条剔除——是**按每个元素的 `style` 逐条扫**，不是整页 grep。
- 代码块 → 单个 `<p>` + 显式 `<br>`，保住换行（`<pre><code>` 在微信里换行会被吃掉）。

## 6. 怎么证明它真的能用

`--self-test` 跑 **9 条内建用例**：1 条完整管线正例 + 8 条负例（空文件、GBK 输入、
脏 HTML、SVG 图、本地 PNG 内联、代码保护护栏、校验器自证、data URI 标签与字节一致
且坏图降级）。

三条硬证据：

1. **自检 9/9 PASS，exit=0**；
2. **端到端实跑 exit=0**（`demo/` 里 3 张真图 + 1 个坏文件，输出 5849 字节，
   限制校验 0 error / 0 warning）；
3. **独立复算**：把输出里每个 data URI 解回字节重新嗅探，标签全部相符；
   残留本地 src 为空。

第 3 条是关键——它不看脚本自己的报告，只验产物字节。用例还做过**变异验证**：
把 mime 写死回 PNG，反例H 立刻转红，证明用例测的是真东西。

## 7. 包结构与安装

```
Zhouruoying_C4B_wechat-publisher.skill   (ZIP)
├── SKILL.md                      技能说明与触发条件
├── scripts/convert_to_wechat.py  全部逻辑（单文件，含 9 条自检）
├── references/wechat_styles.md   主题调色板与各元素样式推导规则
├── references/wechat_restrictions.md  公众号限制清单
├── references/CHANGELOG-vs-starter.md  相对 starter 的全部改动与证据
└── examples/sample_article.md + sample_output.html  最小示例
```

安装：解包到任意目录，`python3 scripts/convert_to_wechat.py --self-test` 应得 9/9 PASS。

## 8. 边界与已知取舍

| 情况 | 处理 |
|------|------|
| 空文件 | 报错退出，**不产出空 HTML** |
| 非 UTF-8 | 依次尝试 UTF-8 → UTF-8-sig → GBK → GB18030 → Big5 |
| 外部图片 URL | 保留原样并提示先上传微信素材库 |
| 超宽表格 | 暂不特殊处理（微信无横向滚动），建议拆表 |
| 数学公式 | 未支持，建议先渲成 PNG 再插入 |
