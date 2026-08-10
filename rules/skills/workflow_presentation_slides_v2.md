# Presentation Slides Workflow v2 — Image-Free (HTML/SVG/Playwright)

## 元数据

- **类型**: Workflow
- **适用场景**: 制作高质量演示文稿（企业内训、技术分享、keynote），**不依赖任何 image-gen API**
- **前置技能**: [workflow_presentation_slides.md](./workflow_presentation_slides.md)（v1，基于 Gemini Nano Banana Pro）
- **本 skill 的定位**：当你**没有 Gemini API key**，或者 deck 风格本身就是 line-art / 蓝图 / 信息图（Clean Ink、flat design），用这条路替代 v1
- **创建日期**: 2026-05-21
- **决策依据**: [slide_gen_alternatives_survey_20260521.md](../../contexts/survey_sessions/slide_gen_alternatives_survey_20260521.md)

---

## 何时用 v2 而非 v1

| 选 v2（本 skill） | 选 v1（image-gen） |
|---|---|
| 没有 Gemini API key | 有 key |
| 风格：line art、blueprint、flat color、信息图、Clean Ink | 风格：摄影感、绘画感、富纹理 |
| 文字密度高（bullet 多，表格多） | 文字稀疏，靠视觉冲击 |
| 需要快速迭代（改一个字立刻看效果） | 一次出图，少改 |
| 包含真实数据/图表（柱图、线图、流程图） | 概念性插图为主 |
| 预算敏感（$0 vs $0.04+/slide） | 不在意单价 |

**速判**：如果你想做的 deck 80%+ 的内容是 "线条 + 文字 + 图表"，选 v2。

---

## 核心理念

```
v1：LLM 写 prompt → image-gen API 渲染整张图 → PNG → Reveal.js 当背景图
v2：LLM 直接写 HTML/SVG → Reveal.js 直接渲染 → Playwright 截图导出 PNG（如需）
```

**关键差异**：v2 里**每个像素都是 LLM 决定的**，文字是真文字，SVG 是真矢量，可以无限缩放，可以 diff 一行修一个字。

---

## 工具链

| 层 | 工具 | 角色 |
|---|---|---|
| 容器 | **Reveal.js** | slide 播放器（保留 v1 的选择，speaker notes、键盘控制都直接复用） |
| 内容 | **HTML / CSS / 内联 SVG** | LLM 直接编写，文字精确，矢量插图 |
| 图表 | **Mermaid**（LLM 最熟） / D2 / 内联 SVG | 流程图、架构图、序列图 |
| 设计系统 | **`theme.css`**（设计 token） | 颜色、字体、间距全局统一 |
| 导出 PNG | **Playwright**（已有 MCP）或 **Marp CLI** | 4K 静态截图，用于发邮件/微信分享 |
| 服务 | `python -m http.server` 或 `npx http-server` | 本地预览 |

---

## 标准目录结构

```
<deck-name>/
├── index.html              # Reveal.js 入口 + 所有 <section>
├── theme.css               # 设计 token + 自定义样式
├── outline.md              # deck 大纲（稀疏版：标题 + 一句话核心）
├── content.md              # 每张 slide 的完整文字稿（论点 + bullets + 视觉描述 + notes）
├── speak_notes.md          # 演讲稿全文（也直接放进 <aside class="notes">）
├── assets/                 # logo、外部截图、字体
├── exported/               # （可选）Playwright 导出的 PNG
└── README.md               # 主题、目标观众、上次修改日期
```

放在哪：**`contexts/presentations/<deck-slug>/`**。

---

## 工作流程

### Phase 0：明确意图（5 分钟）

写 `outline.md`：
- **目标观众**：技术同事？高管？外部客户？
- **核心论点**：用一句话说完整 deck 要传达什么
- **dual-use 要求**：handout 也能看懂吗？需要多少文字？（参考 v1 的设计哲学）
- **每张 slide 的标题 + 一句话核心**（先列 10-20 张，再砍到 8-12）

### Phase 1：定义 theme.css（10 分钟）

把 Clean Ink 风格固化成 CSS 变量，**整个 deck 只在这里调颜色**：

```css
:root {
  --bg: #F0F4F8;        /* 冷浅灰底 */
  --ink: #1C2526;        /* 正文墨色 */
  --navy: #1B3A5C;       /* 线条/strokes/header */
  --grid: #DCE3EA;       /* 极细网格 */
  --orange: #C75B39;     /* 旧范式/问题侧 */
  --teal: #0A6A74;       /* 新范式/方案侧 */
  --accent-yellow: #E8B84A;
  --muted: #5A6470;
  --font-sans: "Inter", "IBM Plex Sans", -apple-system, BlinkMacSystemFont,
               "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  --font-mono: "JetBrains Mono", "SF Mono", "Menlo", monospace;
}

.reveal .slides section {
  background: var(--bg);
  color: var(--ink);
  font-family: var(--font-sans);
  text-align: left;
  padding: 60px 80px;
  /* 关键：把 section 的 base font-size 钉死（默认是 Reveal 的 40px），
     否则 inline `font-size: 0.9em` 在 section 上下文里解析成 36px，所有 muted/footer 全爆。 */
  font-size: 22px;
  line-height: 1.45;
}
.reveal h1 { color: var(--navy); font-weight: 800; font-size: 56px; }
.reveal h2 { color: var(--navy); font-weight: 700; font-size: 40px; }
.reveal h3 { color: var(--navy); font-weight: 600; font-size: 26px; }
.reveal p, .reveal li { font-size: 22px; }
.reveal .accent-orange { color: var(--orange); font-weight: 600; }
.reveal .accent-teal   { color: var(--teal);   font-weight: 600; }
.reveal .muted         { color: var(--muted); }

/* 左右分栏 — 所有 .split-* 变体必须自带 display:grid（见陷阱表） */
.split, .split-1-2, .split-2-1, .split-2-3, .split-3-2 {
  display: grid; gap: 48px; align-items: start;
}
.split     { grid-template-columns: 1fr 1fr; }
.split-1-2 { grid-template-columns: 1fr 2fr; }
.split-2-1 { grid-template-columns: 2fr 1fr; }
.split-2-3 { grid-template-columns: 2fr 3fr; }
.split-3-2 { grid-template-columns: 3fr 2fr; }

/* SVG 安全网：永远不要让 SVG 撑爆 slide 高度（slide canvas 1080） */
.reveal .slides section svg { max-width: 100%; max-height: 620px; height: auto; }

/* 卡片 — 配合 .card-orange / .card-teal 变体 */
.card { background:#fff; border:1px solid var(--grid); border-left:4px solid var(--navy);
        padding:16px 20px; margin:8px 0; }
.card-orange { border-left-color: var(--orange); }
.card-teal   { border-left-color: var(--teal); }
/* 关键：把 card 内所有元素的 font-size 钉死成 18px。
   不写这条的话，<b>/<strong> 不匹配 `.reveal p,li` 选择器，会继承 section 默认（40px）。 */
.card, .card * { font-size: 18px; line-height: 1.4; }
.card h3 { font-size: 20px; }
.card b { font-weight: 700; color: var(--navy); }

/* ⚠️ 重要：DARK 背景的文字自动变白
   任何要把整块 painted 成 navy/orange 的 HTML 区域，套 .on-navy / .on-orange，
   theme 会把整块所有子元素文字自动改成白色（含 <b>、<code>、<a>、SVG text）。
   不写这条的话，agent 必须每个 <p>/<span>/<text> 单独设 color:white，极易漏。 */
.on-navy, .banner-navy   { background: var(--navy);   color:#FFFFFF; padding:14px 24px; border-radius:6px; }
.on-orange, .banner-orange { background: var(--orange); color:#FFFFFF; padding:14px 24px; border-radius:6px; }
.on-navy *, .banner-navy *, .on-orange *, .banner-orange * { color: #FFFFFF; }
.on-navy code, .banner-navy code,
.on-orange code, .banner-orange code { background: rgba(255,255,255,0.18); color:#FFFFFF; }
.on-navy a, .banner-navy a, .on-orange a, .banner-orange a {
  color:#FFFFFF; border-bottom-color: rgba(255,255,255,0.6);
}

/* 锚点 — 自动样式化所有 <a>，让 URL/UID 一目了然且可点 */
.reveal a { color: var(--teal); text-decoration:none; border-bottom:1px dashed var(--teal); }
.reveal a:hover { color: var(--orange); border-bottom-color: var(--orange); }
.reveal a code { background: rgba(10,106,116,0.10); color: var(--teal); border-bottom:none; }

/* SVG defaults.
   ⚠️ 绝对不要加 `svg text { fill: ... }` 规则（连 :where() 都不行）。
   SVG presentation attribute（<text fill="...">）比任何 author CSS 都低优先级，
   一旦全局规则存在，每个 <text fill="#FFFFFF"> 都会被 hijack 成 --ink。
   症状：navy banner 上的白字渲染成黑字（dark-on-dark），肉眼以为是字号问题。
   解法：根本不写这条规则，让 SVG <text> 用 UA 默认黑色；每张图自己设 fill 或 .fill-* 类。 */
svg { stroke: var(--navy); stroke-width: 1.5; fill: none; }
/* ⚠️ <text> inherits the navy stroke above — renders as "dark letterform with
   white halo" on filled boxes (esp. orange/navy nodes in flowcharts).
   Always reset stroke on text. */
svg text { stroke: none; }
svg .fill-navy   { fill: var(--navy);   stroke: none; }
svg .fill-orange { fill: var(--orange); stroke: none; }
svg .fill-teal   { fill: var(--teal);   stroke: none; }
svg .fill-yellow { fill: var(--accent-yellow); stroke: none; }
```

### Phase 2：HTML 骨架（5 分钟）

`index.html`：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>{{DECK TITLE}}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/reveal.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/theme/white.css" id="theme">
  <link rel="stylesheet" href="theme.css">
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
</head>
<body>
  <div class="reveal"><div class="slides">
    <!-- slides 在这里 -->
  </div></div>
  <script src="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/reveal.js"></script>
  <script>
    Reveal.initialize({ width: 1920, height: 1080, margin: 0.04, hash: true });
    mermaid.initialize({ startOnLoad: true, theme: 'base',
      themeVariables: { primaryColor: '#F0F4F8', primaryTextColor: '#1C2526',
        primaryBorderColor: '#1B3A5C', lineColor: '#1B3A5C', fontFamily: 'Inter' }});
  </script>
</body>
</html>
```

### Phase 2.5：写 content.md（文案定稿，**不要 delegate**）

把 outline 里每条一句话**扩展成完整论点 + bullets + 视觉描述 + speaker notes**，但**仍然是纯文字**——不要写 HTML、不要写 SVG。这是 v2 流水线里**唯一一处你必须自己写文案**的地方。

**为什么单独抽这一层**：
- 文案 review 和视觉 review 解耦：先把所有文字定稿，确认论点连贯、措辞统一，再丢给 subagent 渲染
- 重渲染零成本：换主题/换布局/改成 PDF/换语种，重跑 Phase 3 即可，文案不动
- Subagent 一致性更好：它不再"发挥"，只做"翻译"，三组之间措辞漂移显著减少
- Diff 友好：改一个字在 markdown 里就是一行 diff，HTML diff 噪音大
- 主线程（往往是 Opus）擅长写作，subagent（往往是 Sonnet）擅长结构活——分工对齐能力

**何时可以跳过**：deck < 6 张、或纯演示用完全不发 handout、或文案已在调研报告里逐字写好可直接引用。

#### content.md 模板

```markdown
## Slide N: <Title>

**Layout**: split-2-3（左 SVG 右文字）/ single-column / title-slide / table-only
**Core claim**: 一句话，这张 slide 的论点本体
**Bullets**:
- 论点 1 的完整陈述（不是关键词）
- 论点 2 ...
- 论点 3 ...
**Visual**: 描述左/上区视觉——"4 节点横向流程图，节点之间橙色箭头，每节点下方标 dashboard UID"。不画 SVG，只描述
**Data**（可选）: 表格、数字、代码块——逐字写好，subagent 直接搬
**Notes**: 完整 speaker notes，~80-150 词，直接照念
```

#### Phase 3 任务相应变化

Subagent prompt 从"按 outline 起草 slide" 变成"按 content.md 第 N-M 条**翻译**成 HTML/SVG"，硬约束加一条：**文字内容必须逐字来自 content.md，不允许改写/补充/精简**。

##### URL / UID 链接表（必须在 prompt 里给 agent）

Subagent 不会自己把"`p1KqfRAMk`"这种 token 包成 `<a>`，必须显式给 link map：

```
向 agent 提供以下映射规则：

| 输入 token 模式 | 输出 href |
|---|---|
| 完整 URL（如 `vm-mgt-a.dv-api.com/vmui/`） | `https://<URL>` |
| 域名（如 `grafana-mgt.dv-api.com`） | `https://<域名>` |
| Dashboard UID（任何匹配 `^[a-zA-Z0-9_-]{6,32}$` 且 content.md 里被介绍为 dashboard 的 token） | `https://<grafana-host>/d/<UID>` |
| 文件路径、slash command、相对路径 | 保持纯 `<code>`，不加链接 |

输出格式：`<a href="..." target="_blank"><code>UID</code></a>`
```

Subagent self-check 必须包括 "[ ] 每个 UID 在 X 个位置都包了 `<a>`，URL 共 Y 处都包了 `<a>`"，否则容易漏掉表格 / 卡片里的 UID。

##### 内容里出现 "navy banner" / "white text on dark" 时

Agent prompt 里要给死指令：「**任何 dark 背景必须用 `<div class="on-navy">` 或 `<div class="on-orange">` 包裹，不要在内部手动设 `color:white` 或 `fill:#FFFFFF`**」。这条规则配合 theme.css 里的 `.on-navy *` 让整块所有子元素（含 `<b>`、`<a>`、`<code>`）自动继承白色，agent 不需要逐元素处理。

### Phase 3：并行起草 slides（最大加速点）

**这是 subagent 介入的关键点。** 把 outline 里的 N 张 slide 切成 2-3 组，每组派一个 background agent 草拟 HTML。

#### 拆分原则

- **按 deck 章节拆**，不要按"奇偶序号"或"中间砍一刀"——同一章节内的 slide 风格、词汇、SVG 主题强相关，分给同一个 agent 一致性更好
- 一个 agent **≥3 张、≤6 张**，少于 3 张不值得并行，多于 6 张超出 agent 上下文舒适区
- 并行度 ≤3（更多就开始有协调成本）

#### Agent 任务模板

每个 background agent 的 prompt 必须包含：

1. **完整的 `theme.css` 内容**（粘贴，不要让 agent 读文件——文件可能正在被你改）
2. **该组每张 slide 的 outline 条目**（标题 + 核心论点 + 期望的视觉元素）
3. **明确的输出格式**：返回**纯 HTML `<section>...</section>` 数组**，不要 markdown 包裹，不要 commentary。每个 section 包含：
   - 标题（`<h2>`）
   - 主体（推荐 `.split` 左右布局）
   - 内联 SVG 或 Mermaid 图（**必须用 theme.css 里的 CSS 变量颜色**）
   - `<aside class="notes">` speaker notes（中文或英文按 deck 决定）
4. **硬约束**：
   - 文字必须是 deck outline 的实际论点（不是 placeholder）
   - 不要用否定句型（参考 v1 skill 的对照表）
   - SVG 用 stroke 而非 fill 优先，符合线条美学
   - 不要引用外部图片资源（除非 outline 明确指定 `assets/xxx.png`）
5. **不要 background agent 修改 `theme.css`**——主线程统一管理

#### 派 agent 示例

```python
# 主线程串行：写 outline.md + theme.css + index.html 骨架
# 然后并行：

task(category="deep", run_in_background=True,
     description="Draft slides 1-4 (intro + problem)",
     prompt="""
     [theme.css 全文]
     [outline 1-4 全文]
     输出：4 个 <section>...</section>，按 outline 顺序。
     [硬约束 1-5]
     """)

task(category="deep", run_in_background=True,
     description="Draft slides 5-8 (Path A details)",
     prompt="...")

task(category="deep", run_in_background=True,
     description="Draft slides 9-12 (Path B + recommendation)",
     prompt="...")

# 等三个 agent 全部返回，主线程做最后的拼装 + 一致性 review
```

> **关于 background agent 的细节**（什么时候用、并行度、轮询禁令等），见 [workflow_parallel_subagents.md](./workflow_parallel_subagents.md)。

### Phase 4：拼装 + 一致性 review（10-20 分钟，主线程必须自己做）

主线程拿到 3 组 HTML 后：

1. **直接粘进 `index.html`**（注意 section 顺序按 outline）
2. **本地起服务**：`python3 -m http.server 8000` 或写一个 `serve.sh`。
   - **不要直接用 `file://` 打开** — Chrome 会因 CORS 拒绝加载 `theme.css` / Mermaid / Reveal.js 子资源
3. **自动尺寸验证**（最便宜的捉 bug 方法，建议每次都做）：
   - 用 Playwright MCP 打开 deck，跑这段 JS：
   ```js
   () => Array.from(document.querySelectorAll('.reveal .slides > section')).map((s, i) => {
     s.style.display = 'block';
     const h = s.scrollHeight;
     s.style.display = '';
     return { n: i+1, h, overflow: h > 1080 };
   })
   ```
   - 任何 `overflow:true` 都意味着该 slide 被 Reveal.js 自动缩小了，需要修。常见原因：SVG `width:100%` 但没有 `max-height`、split 网格塌成单列（见陷阱表）。
4. **CSS 缓存陷阱**：改了 `theme.css` 之后浏览器看不到变化？因为 `<link href="theme.css">` 命中了浏览器缓存。两个解法任选：
   - 链接加版本戳：`<link href="theme.css?v=2">`，每次改递增
   - 浏览器 `Cmd+Shift+R` 强刷
5. **一致性检查清单**：
   - [ ] 字号大小一致（h2 都是同尺寸？bullet 都是同尺寸？）
   - [ ] SVG 风格统一（stroke width 没有混用 1px / 2px / 3px）
   - [ ] 配色严格走 theme.css 变量（grep `#[0-9A-F]{6}` 看有没有硬编码漏网）
   - [ ] 每张 slide 文字内容是论点而非占位
   - [ ] speaker notes 都补齐了
6. **逐张过一遍人眼**——这是质量门禁，**不能 delegate**

### Phase 5：导出 PNG（按需）

如果要发邮件 / 群里发 / 打印，再走这一步：

```bash
# 选项 A：Playwright MCP（你已有）
# 主线程让 Playwright 导航到 ?slide=N，逐张截图
# viewport 3840×2160，deviceScaleFactor=2 出 4K

# 选项 B：Marp 风格 CLI（需重写为 Marp 格式，不推荐）

# 选项 C：用 reveal.js 自带的 ?print-pdf 模式导 PDF
# Chrome 打开 index.html?print-pdf，CMD+P 保存 PDF
```

Playwright 导出脚本示例（保存为 `exported/screenshot.js`）：

```js
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 },
                                       deviceScaleFactor: 2 });
  const slideCount = parseInt(process.argv[2] || '12');
  await page.goto('http://localhost:8000/');
  await page.waitForTimeout(500);
  for (let i = 1; i <= slideCount; i++) {
    await page.goto(`http://localhost:8000/#/${i-1}`);
    await page.waitForTimeout(300);
    await page.screenshot({ path: `exported/slide_${String(i).padStart(2,'0')}.png`,
                            fullPage: false });
  }
  await browser.close();
})();
```

---

## SVG 速查卡（最常用的几个模式）

### 1. 对比卡（Before vs After）
```html
<svg viewBox="0 0 400 200">
  <rect x="10" y="10" width="180" height="180" class="fill-orange" opacity="0.15"/>
  <rect x="210" y="10" width="180" height="180" class="fill-teal" opacity="0.15"/>
  <text x="100" y="105" text-anchor="middle" font-size="18" class="fill-navy">Before</text>
  <text x="300" y="105" text-anchor="middle" font-size="18" class="fill-navy">After</text>
</svg>
```

### 2. 流程图（节点 + 箭头）
```html
<svg viewBox="0 0 600 100">
  <rect x="10" y="20" width="120" height="60" rx="8"/>
  <rect x="240" y="20" width="120" height="60" rx="8"/>
  <rect x="470" y="20" width="120" height="60" rx="8"/>
  <path d="M130 50 L240 50" marker-end="url(#arrow)"/>
  <path d="M360 50 L470 50" marker-end="url(#arrow)"/>
  <defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" class="fill-navy"/></marker></defs>
</svg>
```

### 3. 比例条
```html
<svg viewBox="0 0 400 30">
  <rect x="0" y="5" width="280" height="20" class="fill-teal"/>
  <rect x="280" y="5" width="120" height="20" class="fill-orange"/>
  <text x="140" y="20" text-anchor="middle" fill="white" font-size="12">70%</text>
</svg>
```

### 4. Mermaid 流程图
```html
<pre class="mermaid">
flowchart LR
  A[Prompt] --> B{Has API?}
  B -->|Yes| C[Image-gen]
  B -->|No| D[HTML/SVG]
  D --> E[Playwright PNG]
</pre>
```

---

## 常见陷阱

| 陷阱 | 对策 |
|---|---|
| Background agent 每个都自己发明配色 | Prompt 里强制只允许引用 `var(--xxx)` |
| Mermaid 渲染前 section 高度塌缩 | 给 mermaid 容器一个 `min-height` |
| 文字溢出 1920×1080 | Reveal.js 自动缩放，但 SVG 内部要预留 padding |
| 中文字符宽度计算和英文不同 | font-family fallback 包含 `system-ui` 让浏览器选 |
| Subagent 返回带 markdown 围栏 ```html | Prompt 里明确"return raw HTML, no fence" |
| 一致性 review 被跳过 | 主线程**必须**逐张过——这是 v2 的质量护城河 |
| **`.split-2-3` 等变体只覆盖 columns，没 `display:grid`** | 把所有 `.split-*` 选择器合并写 `display:grid`，见 Phase 1 theme.css。**症状**：SVG 占满全宽、网格塌成单列、Reveal.js 自动缩小到 0.7-0.8x、整张 slide 看起来"飘"在中间 |
| **SVG `width:100%` 在宽列里渲染成 1400×1400** | theme.css 加 `section svg { max-height: 620px; }` 兜底 |
| **改 CSS 后浏览器不更新** | `<link href="theme.css?v=N">` 版本戳；或 `Cmd+Shift+R` |
| **直接 `open index.html`（file://）不工作** | 必须 `python3 -m http.server`；写 `serve.sh` 一键启动 |
| **SVG `<text fill="#FFFFFF">` 渲染成黑字（dark-on-dark bug）** | **绝对不要**在 theme.css 写 `svg text { fill: ... }` 或 `:where(svg text)`。SVG presentation attribute 比任何 author CSS 都低优先级，全局 fill 规则会 hijack 所有 `fill="..."` 属性。把 svg text 的 fill 留给 UA 默认（黑色），需要白字时 SVG 自己 `fill="#FFFFFF"` 或加 `.fill-*` 类。**症状**：白底 navy box 上的标题肉眼看是深色，computedStyle 验证 `getComputedStyle(t).fill === "rgb(28,37,38)"` 即使 attr 是 `#FFFFFF`。|
| **SVG `<text>` 渲染成"深色字 + 白色描边"（halo bug）** | `svg { stroke: var(--navy) }` 全局规则会被 `<text>` 继承，每个字符都画一圈 1.5px navy 描边。fill 是对的（白），但 stroke 把白色 fill 当镂空，肉眼看就是深色字。**症状**：填充 orange/navy 的节点上文字像被"打孔"。**修法**：theme.css 加 `svg text { stroke: none; }`。和 fill 不同 — 给 text 加 stroke 几乎从来不是 deck 真实意图，这条规则 hijack 没副作用。|
| **HTML dark 块上 `<b>` / `<a>` / `<code>` 颜色不跟 parent** | 用 `.on-navy` / `.on-orange` 包裹整块，theme 自动让所有子元素文字白；不要逐子元素手动设色（agent 必漏） |
| **section 默认 font-size = 40px，所有 inline `0.9em` 全爆** | theme.css 里 `.reveal .slides section { font-size: 22px }`；同理 `.card, .card * { font-size: 18px }` 钉死卡片内字号，防止 `<b>` 继承 section 默认 |
| **URL / Dashboard UID 渲染成纯文字不可点** | theme.css 加 `.reveal a { color: var(--teal); border-bottom: 1px dashed }` 自动样式；Subagent prompt 必须带显式 link map（见 Phase 2.5）|
| **Playwright 取尺寸时 `position:static !important` 后 scrollWidth 虚高（2080 而非 1920）** | 是测量伪影（强制 static 解除了 Reveal 的 width 约束）。只看 `scrollHeight > 1080` 是否真溢出，宽度数字忽略 |
| **content.md 文案有错 → 全 deck 多处不一致** | content.md 是 single source of truth。修一处即可，重跑 Phase 3 subagent，HTML 重新翻译。**不要**直接改 generated HTML，下次再重渲会被覆盖 |

---

## 与其他 skill 的关系

- [workflow_presentation_slides.md](./workflow_presentation_slides.md) v1 — 当你需要摄影/绘画风格时仍然用 v1
- [workflow_parallel_subagents.md](./workflow_parallel_subagents.md) — Phase 3 并行起草的底层心法
- [bestpractice_markdown_html_conversion.md](./bestpractice_markdown_html_conversion.md) — 如果 deck 的原始素材是长 markdown 报告，先按这个流程转
- [share_report.md](./share_report.md) — deck 完成后想发布到 web，走这条路

---

## 起步模板

新建 deck 时，复制以下命令：

```bash
DECK=my_deck_name
mkdir -p contexts/presentations/$DECK/{assets,exported}
cd contexts/presentations/$DECK
# 然后让 Claude 按 Phase 0-4 推进
```
