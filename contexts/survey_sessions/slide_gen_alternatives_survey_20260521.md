# Slide 生成：Gemini Nano Banana Pro 替代方案调研

**调研日期**: 2026-05-21
**背景**: 当前 [nbp_slides](https://github.com/grapeot/nbp_slides) 工作流依赖 `gemini-3-pro-image-preview` 把每张 slide 渲染成一整张图。用户没有 Gemini API key，想找替代方案——MCP、其他 image-gen API、或彻底换路线。
**风格约束**: Clean Ink — 冷浅灰底 (#F0F4F8)、海军蓝线条、flat color、sans-serif、工程图纸感、~40% 插图 / ~60% 可读文字、需支持 4K。

---

## 核心结论（先看这个）

**两条路并存，强烈建议优先走 Path A。**

| | Path A：HTML/CSS/SVG + Playwright | Path B：换一个 image-gen API |
|---|---|---|
| 每张成本 | **$0** | $0.03–$0.09 |
| 迭代速度 | **~200ms** | 15–30s |
| 文字渲染 | **像素级完美** | 都会偶尔出错 |
| 风格一致性 | **CSS 强制统一** | 跨 slide 漂移 |
| 改一个字 | **改一行 HTML** | 重新生成整张图 |
| 适合 Clean Ink 风格？ | **几乎为之量身定做** | 可以但是性价比低 |
| 你已有的能力 | **Playwright MCP + chrome-devtools MCP 已就位** | 还得开新账号、买 credit |

**Clean Ink 本质上就是 line art + flat fills + 衬线无的 sans-serif**——这正是 SVG/HTML 的强项，不是 raster image 的强项。把图像生成留给"摄影感封面图"那种 1-2 张特殊场合，主体 deck 全部走 HTML。

---

## Path A：HTML/SVG + Playwright（推荐）

### 工具链

```
Reveal.js（你已经在用）
  + Claude 直接写每张 slide 的 <section> HTML
  + 内联 <svg> 画线条插图
  + Mermaid / D2 画流程图、架构图
  + Playwright MCP 截图导出 4K PNG
```

### 工作流程

1. **定义 `theme.css`**——把 Clean Ink 的设计 token 沉淀下来：
   - `--bg: #F0F4F8`
   - `--ink: #1C2526`
   - `--navy: #1B3A5C`（线条/strokes）
   - `--orange: #C75B39`（旧范式/问题侧）
   - `--teal: #0A6A74`（新范式/方案侧）
   - 字体 `Inter` / `IBM Plex Sans`
   - 1px stroke 默认
2. **每张 slide = 一个 `<section>`**：左右分栏（左 SVG / Mermaid 插图，右 2-4 行核心文字），完全可被 Reveal.js 直接播放，不需要导出也能演示。
3. **导出 PNG**：
   - `npx http-server` 起本地服务
   - Playwright MCP → 导航到 `?slide=N` → `take_screenshot`，viewport 3840×2160 + `deviceScaleFactor=2`
   - 或者更简单：直接 `marp --images png deck.md` 一行命令
4. **复用现有 skill**：`rules/skills/workflow_presentation_slides.md` 加一个 "image-free mode" 分支即可。

### 同类参考实现（都可直接借鉴）

| Repo | 说明 |
|---|---|
| [ryanbbrown/revealjs-skill](https://github.com/ryanbbrown/revealjs-skill) | Claude Code skill，CSS 变量主题，自动溢出检测 |
| [zl190/md-slides](https://github.com/zl190/md-slides) | Markdown → slides + 图表 |
| [bluedusk/html-slides](https://github.com/bluedusk/html-slides) | 富组件库（flip cards、code blocks、架构流程） |
| [autonomee.ai 博客](https://autonomee.ai/blog/reveal-presentations-generate-slide-decks-from-claude-code/) | Claude Code → Reveal.js 端到端走通 |

### 备选纯命令行方案

- **[Marp CLI](https://github.com/marp-team/marp-cli)**：`marp --images png deck.md` → `deck.001.png ...` 一行搞定，零配置，v4 用 headless Chrome。最适合"我就要 PNG 输出文件"的场景。
- **[Slidev](https://sli.dev/guide/exporting)**：`slidev export --format png --per-slide`，Vue 组件强大，theming 比 Reveal.js 现代。

### 图表/插图选型（按 Clean Ink 匹配度）

| 工具 | 适配度 | 备注 |
|---|---|---|
| **Claude 直接写 inline SVG** | ★★★★★ | 你的风格就是线条+flat fill，SVG 原生表达 |
| **Mermaid** | ★★★★ | Claude 训练数据最多，写得最流畅，token 比 Excalidraw JSON 省 ~24× |
| **D2** | ★★★ | 默认更好看，但 LLM 不如 Mermaid 熟 |
| **mermaid-to-excalidraw** | ★★★★ | 如果想要手绘蓝图感，[excalidraw/mermaid-to-excalidraw](https://github.com/excalidraw/mermaid-to-excalidraw) 直接转 |

> Token 效率分析：[dev.to: Analyzing the Best Diagramming Tools for the LLM Age](https://dev.to/akari_iku/analyzing-the-best-diagramming-tools-for-the-llm-age-based-on-token-efficiency-5891)

### 这条路的唯一短板

照片级/绘画级插图做不出来。但 Clean Ink 风格本来就排除了照片，所以**这个"短板"在你的场景里损失为零**。

---

## Path B：换一个 image-gen API

如果还是想保留"一张图渲染整页"的工作流，下面是排序：

### B.1 单一 fal.ai key 解锁全部（最优）

**注册一个 fal.ai 账号，拿 `FAL_KEY` 一把钥匙开多个模型**，按 slide 类型分流。fal.ai 比 Replicate 便宜 30–50%、985+ endpoints。

| 模型 | 强项 | 分辨率 | 价格/张 |
|---|---|---|---|
| **[Seedream 4.5](https://fal.ai/learn/devs/seedream-v4-5-vs-v4-0)** | "Dense text rendering"、最接近 Nano Banana Pro 的全幅渲染体验 | **2048×2048**（>1080p） | $0.04 |
| **[Recraft V3](https://fal.ai/models/fal-ai/recraft/v3/text-to-image)** | "First to offer image generation with text of any size and length"——长多行正文唯一可靠选项；支持品牌参考图 | ~1K（需放大） | $0.04 raster / $0.08 vector |
| **[Ideogram 3.0](https://developer.ideogram.ai/api-reference/api-reference/generate-v3)** | "Highly accurate text rendering, from single words to multi-line layouts" | ≤1536px | $0.03 Turbo / $0.09 Quality |
| **[FLUX 1.1 Pro Ultra](https://fal.ai/models/fal-ai/flux-pro/v1.1-ultra)** | 真 4MP（4K 级）、文字尚可但密集小字会错 | 4MP | $0.06 |

**建议组合**：主体 deck 用 **Seedream 4.5**（分辨率 + 文字均衡），文字特别密的章节标题页用 **Recraft V3** 或 **Ideogram 3.0 Quality**。

> 来源汇总：[Seedream v4.5 vs v4.0](https://fal.ai/learn/devs/seedream-v4-5-vs-v4-0)、[Recraft V3 on fal](https://fal.ai/models/fal-ai/recraft/v3/text-to-image)、[Segmind: Ideogram 3.0 API](https://www.segmind.com/models/ideogram-3/api)、[BFL FLUX 1.1 Pro Ultra](https://bfl.ai/models/flux-pro-ultra)、[TeamDay fal.ai vs Replicate 2026](https://www.teamday.ai/blog/fal-ai-vs-replicate-comparison)

### B.2 排除项

- **OpenAI gpt-image-1**：max 1536px，**塞不进 1920×1080 crisp 输出**，pass。
- **Qwen-Image-2.0-Pro**：质量可以，但走 Alibaba Cloud Model Studio 鉴权摩擦大。

### B.3 通过 MCP 调用（让 Claude Code 直接出图）

如果选 Path B，建议套一层 MCP，让 Claude Code 直接 tool-call 出图：

| MCP Server | 模型 | Key 需求 |
|---|---|---|
| **[raveenb/fal-mcp-server](https://github.com/raveenb/fal-mcp-server)** ⭐推荐 | 600+ via fal.ai（Seedream / Recraft / Ideogram / Flux 全在内） | `FAL_KEY` 一个搞定 |
| [PierrunoYT/fal-ideogram-v3-mcp-server](https://github.com/PierrunoYT/fal-ideogram-v3-mcp-server) | 只有 Ideogram v3 | `FAL_KEY` |
| [lansespirit/image-gen-mcp](https://github.com/lansespirit/image-gen-mcp) | gpt-image / dall-e / Imagen 4 | `OPENAI_API_KEY` |
| ~~[shinpr/mcp-image](https://github.com/shinpr/mcp-image)~~ | Nano Banana Pro/2 | **要 `GEMINI_API_KEY`——你正是因为没这个才来调研，所以不适用** |
| ~~[GongRzhe/Image-Generation-MCP-Server](https://github.com/GongRzhe/Image-Generation-MCP-Server)~~ | 已 archived 2026-03 | 避免 |

`raveenb/fal-mcp-server` 安装：

```json
{
  "mcpServers": {
    "fal-ai": {
      "command": "uvx",
      "args": ["--from", "fal-mcp-server", "fal-mcp"],
      "env": { "FAL_KEY": "..." }
    }
  }
}
```

> 来源：[raveenb/fal-mcp-server](https://github.com/raveenb/fal-mcp-server)、[punkpeye/awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers)

---

## 交叉验证：三个 agent 的共识

| 共识点 | Image-gen API agent | MCP agent | HTML/SVG agent |
|---|---|---|---|
| Anthropic 没有原生图像生成 | ✓ | ✓ 明确确认 | — |
| Gemini Nano Banana Pro 是当前文字渲染最强的之一 | ✓ | ✓ | — |
| 想换 image-gen 时，**fal.ai 是唯一合理的多模型聚合器** | ✓ | ✓（推荐 fal-mcp-server） | — |
| Ideogram / Recraft 文字渲染优于 Flux | ✓ | ✓ | — |
| OpenAI gpt-image 分辨率太低，不适合 4K slide | ✓ 明确指出 | — | — |
| **Clean Ink 风格根本不需要 raster image** | — | — | ✓ 强论点 |

**矛盾**：无显著矛盾，三个 agent 在各自领域结论独立、互补。

---

## 行动建议（给 N=1 的你）

**第一步（今天，1 小时）**：把 `outline_visual.md` 里挑一张最典型的 slide，让 Claude 用 HTML + inline SVG 写出来，Playwright MCP 截图看效果。如果文字+插图都达标——你已经不需要 image-gen API 了。

**第二步（如果 SVG 表达不了某些插图）**：注册 fal.ai 账号，装 `raveenb/fal-mcp-server`，**只用它出那些 SVG 表达不了的画面**，其余仍走 HTML/SVG。

**第三步**：把这套 hybrid 流程沉淀到 `rules/skills/workflow_presentation_slides.md` 的 "image-free mode" 分支。

---

## 引用清单

- [nbp_slides repo](https://github.com/grapeot/nbp_slides)
- [Slidev Exporting](https://sli.dev/guide/exporting) · [Slidev CLI](https://sli.dev/builtin/cli)
- [marp-team/marp-cli](https://github.com/marp-team/marp-cli) · [Marp CLI v4](https://github.com/orgs/marp-team/discussions/542)
- [ryanbbrown/revealjs-skill](https://github.com/ryanbbrown/revealjs-skill)
- [zl190/md-slides](https://github.com/zl190/md-slides)
- [bluedusk/html-slides](https://github.com/bluedusk/html-slides)
- [autonomee.ai: Claude → Reveal pipeline](https://autonomee.ai/blog/reveal-presentations-generate-slide-decks-from-claude-code/)
- [excalidraw/mermaid-to-excalidraw](https://github.com/excalidraw/mermaid-to-excalidraw)
- [Token efficiency for LLM diagramming](https://dev.to/akari_iku/analyzing-the-best-diagramming-tools-for-the-llm-age-based-on-token-efficiency-5891)
- [Best AI Diagram Tools 2026](https://nimbalyst.com/blog/best-ai-diagram-tools-2026/)
- [fal.ai Seedream v4.5 vs v4.0](https://fal.ai/learn/devs/seedream-v4-5-vs-v4-0)
- [fal.ai Recraft V3](https://fal.ai/models/fal-ai/recraft/v3/text-to-image)
- [Segmind: Ideogram 3.0 API](https://www.segmind.com/models/ideogram-3/api)
- [Ideogram developer docs](https://developer.ideogram.ai/api-reference/api-reference/generate-v3)
- [BFL FLUX 1.1 Pro Ultra](https://bfl.ai/models/flux-pro-ultra)
- [fal.ai FLUX 1.1 Pro Ultra](https://fal.ai/models/fal-ai/flux-pro/v1.1-ultra)
- [OpenAI gpt-image-1 model card](https://developers.openai.com/api/docs/models/gpt-image-1)
- [Qwen Image API (PiAPI)](https://piapi.ai/qwen-image)
- [TeamDay fal.ai vs Replicate 2026](https://www.teamday.ai/blog/fal-ai-vs-replicate-comparison)
- [raveenb/fal-mcp-server](https://github.com/raveenb/fal-mcp-server)
- [shinpr/mcp-image](https://github.com/shinpr/mcp-image)
- [lansespirit/image-gen-mcp](https://github.com/lansespirit/image-gen-mcp)
- [PierrunoYT/fal-ideogram-v3-mcp-server](https://github.com/PierrunoYT/fal-ideogram-v3-mcp-server)
- [TamerinTECH/claude-code-generate-images-mcp](https://github.com/TamerinTECH/claude-code-generate-images-mcp)
- [punkpeye/awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers)
