# Deck Outline: Beyond Nano Banana Pro

**Audience**: 自己 + 未来读这份调研报告的人
**Core argument**: Clean Ink 风格的 slide 根本不需要 image-gen API；HTML/SVG + Playwright 是更快更便宜更可控的方案。
**Tone**: 工程师 deck，dense but legible，handout & presentation 双用
**Source**: `contexts/survey_sessions/slide_gen_alternatives_survey_20260521.md`

---

## Slides

### S1 — Title
- **Header**: Beyond Nano Banana Pro
- **Subtitle**: Slide 生成方案选型 · 2026-05-21
- **Visual**: 大字标题 + 副标题；右下角小 SVG（一只 banana 线条画 + 一根斜杠划过——"告别 banana"）

### S2 — The Problem
- **Header**: 起点：没 Gemini key
- **Core argument**: 当前 nbp_slides 工作流依赖 `gemini-3-pro-image-preview`；没有 key 整条流水线断了。
- **Visual**: 左侧 SVG 现有流水线（prompt → Gemini → PNG → Reveal.js），中间断点（红叉）。右侧文字：3 点症状（无 key、无法迭代、无法 4K 放大）

### S3 — TL;DR
- **Header**: 两条路，优先 Path A
- **Visual**: 左右分栏对比表
  - Path A：HTML/SVG + Playwright | $0、200ms 迭代、像素级文字、CSS 强制一致
  - Path B：fal.ai 聚合 API | $0.03–0.09、15–30s、有限分辨率、跨 slide 漂移
- **底部一句话**：Clean Ink 本质是 line art，正是 SVG 强项

### S4 — Why Path A Fits Clean Ink
- **Header**: Clean Ink ≈ SVG 的语言
- **Core**: Clean Ink 的五个特征（冷灰底、海军蓝线条、flat color、sans-serif、blueprint 感）逐一映射到 SVG/CSS 的原生能力
- **Visual**: 左侧 SVG demo（用 Clean Ink 配色画一个工程图纸感的小插图：齿轮、量角器、网格），右侧 5 行映射（特征 → 实现）

### S5 — Path A Toolchain
- **Header**: Path A 工具链
- **Visual**: Mermaid 流程图：outline.md → theme.css → Claude 写 HTML/SVG → Reveal.js 直接演 → Playwright 导出 PNG（可选）
- **底部**：你已有的 = Reveal.js + Playwright MCP + chrome-devtools MCP。需要新增的 = 0

### S6 — Path A Trade-offs（核心说服 slide）
- **Header**: Path A vs v1（image-gen）
- **Visual**: 6 行对比表（成本/迭代/文字/一致性/可编辑性/插图丰富度），每行 Path A 大幅领先（除最后一项），最后一项 Clean Ink 风格用不到
- **结论**：在你的场景里没有任何维度是输的

### S7 — When You Still Need Image-Gen
- **Header**: Path B：何时仍然需要图像生成
- **Core**: 三种场景 → 摄影感封面图 / 绘画级插图 / 真实人物/物品（即使如此也是少数 slide）
- **Visual**: 三个小卡片，每个一行场景 + SVG icon（camera / brush / portrait）

### S8 — Path B Lineup（fal.ai）
- **Header**: 一把钥匙：fal.ai
- **Visual**: 4 行模型对比表（Seedream 4.5 / Recraft V3 / Ideogram 3.0 / FLUX 1.1 Pro Ultra），列：强项 / 分辨率 / 价格
- **底部**：单一 `FAL_KEY` 解锁，比 Replicate 便宜 30-50%

### S9 — Path B via MCP
- **Header**: 通过 MCP 接入 Claude Code
- **Core**: `raveenb/fal-mcp-server` 配置片段 + Claude Code 直接 tool-call 出图
- **Visual**: 左侧 JSON 配置代码块，右侧调用流程小图（Claude → MCP → fal.ai → 600+ models）

### S10 — Cross-Validation
- **Header**: 三个 agent 的独立共识
- **Visual**: 6 行 ✓ 表格 + 一行明确说"无显著矛盾"
- **底部**：调研方法论：3 个 background agent 独立并行 + 强制 overlap

### S11 — Action Plan
- **Header**: 三步走
- **Visual**: Mermaid 时间线
  - Today (1h)：挑一张典型 slide，HTML+SVG 试一下
  - If gaps：注册 fal.ai，装 fal-mcp-server，hybrid
  - Land：沉淀进 `workflow_presentation_slides_v2.md`
- **底部**：这份 deck 本身就是 v2 skill 的第一个产出

### S12 — End / Meta
- **Header**: This deck was made with v2
- **Core**: 自指的 closing slide：本 deck 12 张全部 HTML/SVG/Mermaid，零 image-gen 调用，2 个 background subagent 并行起草，Opus 主线程一致性把关
- **Visual**: 一个小 SVG（齿轮组合）+ deck 元数据（slide 数 / API 调用数 / 总迭代时间）
