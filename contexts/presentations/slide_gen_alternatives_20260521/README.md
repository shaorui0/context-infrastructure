# Beyond Nano Banana Pro · Slide 生成方案选型

**Date**: 2026-05-21
**Audience**: self · 调研报告的读者
**Slides**: 12
**Built with**: [`workflow_presentation_slides_v2`](../../../rules/skills/workflow_presentation_slides_v2.md)
**Source**: [`contexts/survey_sessions/slide_gen_alternatives_survey_20260521.md`](../../survey_sessions/slide_gen_alternatives_survey_20260521.md)

## 看 deck

**必须起一个本地 HTTP server**（Reveal.js 通过 fetch 加载子资源，直接 `open index.html`（file://）部分浏览器会因 CORS 拒绝加载 `theme.css` / Mermaid 等）。

最简单：

```bash
cd contexts/presentations/slide_gen_alternatives_20260521
./serve.sh           # 默认 :8765
./serve.sh 9000      # 自定义端口
```

或者直接：

```bash
python3 -m http.server 8765
```

然后浏览器打开 `http://localhost:8765/`。

- 方向键 / 空格：翻页
- `S`：speaker notes 模式
- `F`：全屏
- `Esc`：缩略图概览
- `?print-pdf`：进入 PDF 打印模式，CMD+P 存成 PDF

**注意**：改了 `theme.css` 后浏览器会缓存。要么用 `Cmd+Shift+R` 硬刷新，要么把 `index.html` 里 `theme.css?v=N` 的版本号 +1。

## 导出 PNG（可选）

```bash
# 用 Playwright（需先 `pip install playwright && playwright install chromium`）
# 或者直接 Chrome → http://localhost:8765/?print-pdf → CMD+P 存 PDF
```

## 文件

```
index.html      # Reveal.js 主文件，12 个 <section>
theme.css       # Clean Ink 设计 token + 全局样式（含 ?v=N 防缓存）
outline.md      # deck 大纲（每张 slide 的核心论点）
serve.sh        # 一键起本地服务
README.md       # 本文件
assets/         # （目前为空，无外部资源依赖）
exported/       # （目前为空，可放 Playwright 导出的 PNG）
```

## 元数据

- 0 个 image-gen API 调用
- 2 个 background subagent 并行起草（slides 1-6 / 7-12）
- Opus 主线程：outline + theme.css + 一致性 review + 拼装
- 端到端约 15 分钟
