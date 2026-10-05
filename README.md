# C4B — 公众号文章生成技能（wechat-publisher）

把「Markdown 文章 → 微信公众号可直接粘贴的 HTML」这条链路，做成一个**零依赖、可自检、可复现**的本地技能，并用它真实产出一篇公众号文章。

| 项 | 值 |
|---|---|
| 挑战 | C4B 公众号文章生成技能（`ch-20260717031440-bp05rs`） |
| 提交身份 | Zhouruoying |
| 技能包 | `Zhouruoying_C4B_wechat-publisher.skill`（ZIP，7 项，33799 字节） |
| 运行环境 | Python 3.12，**零第三方依赖**，全程本地、无网络 |
| 本仓库内容 | 技能源码 + 交付文档 + 可复现证据（不是只交一个包） |

---

## 一、它解决什么问题

在 Markdown 里排版工整的一篇文章，复制进公众号编辑器经常直接崩掉：标题样式丢失、代码块变成一排小方块、图片裂开、表格错位。原因不是编辑器差，而是**公众号只吃一份受限的 HTML 子集**：不允许 `script`/`style`/`iframe`/`div`，样式只能内联，图片要能被内联或外链到微信自己的域名。

这个技能把「手工试错」变成一条确定性管线：Markdown（或 `.docx`/`.html`）进去，**可粘贴 HTML** 出来，并在输出前用一套硬规则自检，不合格就让进程带着非零退出码失败——而不是把问题留到「发出去才发现」。

## 二、技能能力

| 能力 | 为什么有用 |
|---|---|
| 4 套主题 `--theme`（default/blue/warm/minimal） | 技术文、叙事文、观点文气质不同；改一组色值即可换肤，样式全部由调色板推导 |
| Callout 高亮框（`> [!TIP]` 等 4 类） | 长文靠视觉锚点提留存；颜色固定不随主题，形成稳定语义 |
| 自动目录 / 标题头 / 页脚版权 | 微信内不能跳锚点，目录靠位置记忆发挥作用 |
| 中英混排优化 | 中英文、数字间自动加空格，半角标点转全角——中文排版最影响观感、手工调最费时的一项 |
| 图片 base64 内联 | 直接复制进编辑器不丢图 |
| 图片类型按**魔数**判定 | 不信扩展名，标签跟着真实字节走（PNG/JPEG/GIF），不认识的一律降级为提示行而不是静默丢弃 |
| SVG 主动拦截 | 微信会**静默丢** SVG，不拦就是「发出去才发现图没了」 |
| 校验器自证 | 自检里包含一条「校验器必须能抓到违规」的用例，防止校验器变成永远通过的摆设 |
| `--self-test` 自检套件 | 9 条用例（1 正例 + 8 否定用例），让技能可被**独立验证**，而不是靠作者口头保证 |
| `--report` 运行报告 | 输出字数/字节/图片数/违规项 JSON，机器可读证据 |

## 三、安装与使用

```bash
# 解包（.skill 是 ZIP）
unzip Zhouruoying_C4B_wechat-publisher.skill -d wechat-publisher
cd wechat-publisher

# 自检：应得 9/9 PASS，退出码 0
python3 -B scripts/convert_to_wechat.py --self-test

# 转换一篇文章
python3 -B scripts/convert_to_wechat.py 我的文章.md -o 输出.html --theme blue --report 报告.json
```

拿到输出后：浏览器打开 HTML → Ctrl+A → Ctrl+C → 粘进公众号编辑器即可，样式与图片都跟着走。

## 四、复现证据（不靠口述，靠命令与退出码）

1. **技能自检** 9/9 PASS，`exit=0` → `logs/selftest.log`
2. **端到端**：`Zhouruoying_C4B_文章源文件.md`（1922 字符）→ `Zhouruoying_C4B_output.html`（10706 字节），
   源编码 utf-8，限制校验 **0 error / 0 warning**，`exit=0` → 报告见 `Zhouruoying_C4B_文章_报告.json`
3. **本地提交预检**（复用 C4 的 submit-preflight 技能，`--challenge C4B`）→ `logs/preflight.log` / `logs/preflight.summary.json`
4. **包 ↔ 盘一致性**：`.skill` 内 7 个载荷文件 sha256 与源码目录逐一 MATCH（见 `Zhouruoying_C4B_AI日志.md`）

## 五、与评分维度的对应

| 维度 | 分 | 本仓库的对应物 |
|---|---|---|
| contentQuality | 25 | `Zhouruoying_C4B_文章源文件.md` + `_output.html`：一篇完整的真实文章（痛点 → 原理 → 做法 → 能力 → 自检 → 经验 → 上手） |
| distribution | 20 | 真实发布：链接见 `Zhouruoying_C4B_文章链接.md`；技能本身可被他人一行命令独立复现 |
| artifactCompleteness | 15 | 技能包 + 技能说明 + 教学说明 + 拿来说明 + 文章 + AI 日志 + AAR + 自评，齐备且命名统一 |
| aiUsage | 20 | `Zhouruoying_C4B_AI日志.md`：采纳 / 修改 / 驳回三类判定表 + 失败记录 + 原始输出 |
| reflectionQuality | 20 | `Zhouruoying_C4B_AAR.md`：卡点、突破（魔数判定）、与 AI 协作的判定与失误 |

## 六、边界（明确不做）

- **不做发布**：技能只产出「可粘贴 HTML」，发布由人在公众号后台完成——这是平台与权限边界，不是能力缺口。
- **不做图片美化/裁剪**：只做内联与尺寸约束，不代改内容。
- **不追新主题**：4 套覆盖主要文体，再多是维护负担。
- **不做 Word 深度支持**：`.docx` 走文本 + 基础样式提取，复杂版式（文本框、公式）不保证。

## 七、目录结构

```
.
├── README.md                            ← 本文件
├── .gitignore / .preflight-ignore
├── Zhouruoying_C4B_wechat-publisher.skill   ← 技能包（交付物）
├── Zhouruoying_C4B_技能源码/                 ← 技能源码（与包内一致）
│   ├── SKILL.md
│   ├── scripts/convert_to_wechat.py         ← 全部逻辑 + 9 条自检
│   ├── references/                          ← 微信限制、主题样式、与 starter 的差异清单
│   ├── examples/                            ← 官方示例文章与输出
│   └── demo/                                ← 演示素材（GIF/JPG/PNG 与损坏文件）
├── Zhouruoying_C4B_技能说明.md / _教学说明.md / _拿来说明.md
├── Zhouruoying_C4B_文章源文件.md → _output.html（+ _文章_报告.json）
├── Zhouruoying_C4B_文章链接.md              ← 真实发布链接
├── Zhouruoying_C4B_AI日志.md / _AAR.md / _项目自评.md
└── logs/                                ← 自检与预检证据（人读 + 机读）
```

---

*作者：Zhouruoying ｜ 挑战：C4B 公众号文章生成技能 ｜ 技能包：`Zhouruoying_C4B_wechat-publisher.skill`*
