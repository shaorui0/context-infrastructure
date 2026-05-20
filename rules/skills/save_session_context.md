# Skill: Save Session Context

保存当前 session 的核心上下文——想法、insight、决策、关键发现——到 `contexts/session_captures/` 目录，防止有价值的信息随 session 结束丢失。

## When to Use

- Session 结束前，想把聊出来的核心内容留档
- 跑完一个长 session，里面有不少散落的 insight 想集中保存
- "帮我 save 一下这次的 context"
- "/save-session-context"

## 输出位置

`contexts/daily_records/{YYYY-MM-DD}_{HHMM}_{topic}.md`

日期和时间通过 bash 命令获取：
```bash
date +"%Y-%m-%d_%H%M"
```

## 工作流程

### Step 1: 扫描当前 session

回顾整个对话，提取以下类别的内容（有就提，没有不强求）：

1. **核心想法 / Ideas** — session 中产生的新想法、灵感
2. **Insights** — 关键发现、顿悟时刻、认知更新
3. **决策与理由** — 做了什么决定，为什么
4. **关键讨论** — 重要的讨论要点、争论和结论
5. **待办 / Open Questions** — 未解决的问题、下一步方向
6. **有价值的片段** — 值得保留的原话、类比、框架

### Step 2: 确定主题和文件名

- 用 bash 获取当前日期时间：`date +"%Y-%m-%d_%H%M"`
- 从 session 内容中提炼一个 2-4 词的主题（英文，kebab-case）
- 文件名：`{YYYY-MM-DD}_{HHMM}_{topic}.md`
- 例：`2026-03-31_1430_career-transition-methodology.md`

### Step 3: 写入文件

用以下模板写入：

```markdown
# Session Capture: {主题}

- **日期**: {YYYY-MM-DD}
- **Session 关键词**: {3-5 个关键词}
- **持续时间**: {大致时长，如不确定写"未知"}

---

## 核心想法

{逐条列出，保留原始表达，不过度提炼}

## Insights

{关键发现和认知更新}

## 决策与理由

{做了什么决定，为什么这样决定}

## 关键讨论

{重要的讨论要点}

## Open Questions

{未解决的问题、下一步方向}

## 原始片段

{值得保留的原话、类比、精彩表达，用 blockquote 格式}
```

**关键原则：宁多勿少，宁原始勿提炼。** 这是 save 不是 summarize。保留原始表达和上下文，后续可以再提炼，但丢了就回不来。

### Step 4: 确认保存

- 确认 `contexts/daily_records/` 目录存在
- 写入文件
- 告知用户保存路径和内容概要

## 注意事项

- 不要过度加工，核心是"不漏"而不是"精炼"
- 如果 session 内容很少，一个简短文件就够，不需要填满每个 section
- 空的 section 直接省略，不要写"无"
- 保留用户的原始措辞，特别是类比和框架性表达
- 如果有代码或配置相关的讨论，保留关键代码片段
