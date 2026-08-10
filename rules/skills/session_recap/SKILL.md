---
name: session_recap
description: |
  session 停了很久回来，想知道「我们解决了哪些问题、现在讨论到哪、下一步该干什么」，但不想重读整个对话；或者要从一堆旧 session 里翻出某个做到一半的活儿。
  Trigger: user says "/session_recap" or asks about # Skill: Session Recap（断点续接）.
---

# Skill: Session Recap（断点续接）

**适用场景**: session 停了很久回来，想知道「我们解决了哪些问题、现在讨论到哪、下一步该干什么」，但不想重读整个对话；或者要从一堆旧 session 里翻出某个做到一半的活儿。

## When to Use

- "这个 session 我们做了啥 / 讨论到哪了"
- "上次那个 XXX 做到哪一步了" / "捡回上下文" / "断点续接"
- "/session_recap"
- 长 session 被 compact 过，你自己的 context 里已经缺了前半段
- 打开一个几天没动的 session，第一句话就该先跑这个

**与 `/save_session_context` 的区别**：save 是**往外写**（把 session 内容存档到 `contexts/`），recap 是**往回读**（从 transcript 重建 session 骨架）。两者可串联：先 recap，再 save。

## 工具

`tools/session_recap.py` —— 从 `~/.claude/projects/<project-slug>/<session-id>.jsonl` 提取骨架。
它只做**机械提取**（谁说了什么 → 做了哪些动作 → 改了哪些文件 → 任务板状态），**不做总结**。总结是你的活。

```bash
cd /Users/rshao/work/context-infrastructure

python3 tools/session_recap.py --list -n 10        # 列出当前项目最近 10 个 session
python3 tools/session_recap.py --list --all-projects -n 15   # 跨项目
python3 tools/session_recap.py <session-id>        # 提取指定 session
python3 tools/session_recap.py latest              # 最近活动的那个
python3 tools/session_recap.py <path/to/x.jsonl>   # 直接给文件
python3 tools/session_recap.py <id> --full         # 不截断、不省略回合（很大，慎用）
python3 tools/session_recap.py <id> --cwd /path/to/other/repo   # 换项目定位
```

输出包含：session 元信息（跨度、闲置多久、compact/打断次数）、按人类回合切分的时间线（人类说了什么 + 工具统计 + 关键动作 + Claude 当回合结论）、任务板最终状态、最后一次 ExitPlanMode 计划、改过的文件清单。

## 工作流程

### Step 1: 确定目标 session

**默认是「当前这个 session」。** 当前 session id 就写在 scratchpad 路径里：
`/private/tmp/claude-*/<project-slug>/<SESSION-ID>/scratchpad` —— 直接从 system prompt 里的 scratchpad 路径取那一段 UUID，不要猜。

其他情况：
- 用户指名某个旧活儿（"上次搞 Doris 那个"）→ 先 `--list`（必要时 `--all-projects`），按标题/开场白匹配；有歧义就把候选列给用户挑，别乱选
- 用户没说清楚且当前 session 很短 → 用 `--list` 让他挑

### Step 2: 跑提取，读输出

```bash
python3 tools/session_recap.py <session-id> > "$SCRATCHPAD/recap.md" && wc -c "$SCRATCHPAD/recap.md"
```

大 session（>40KB）先落盘再 Read，别直接吞 stdout。

**即使这个 session 还在你的 context 里，也以 transcript 提取为准。** 被 compact 过的部分你只有二手印象，transcript 才是一手证据。

### Step 3: 写 briefing（这是交付物）

固定七段，中文，结论先行，**总长控制在一屏半以内**：

```markdown
## 一句话
{这个 session 到底在干什么 —— 一句，不要复读标题}

## 已经落地的
{做完并且有证据的事。每条带证据：文件路径 / 命令 / 数字。3-6 条}

## 停在哪
{最后一个回合在干什么，为什么停 —— 被打断？在等你回答？还是自然停了？
 如果 transcript 里有 ⏸ 大间隔或「被用户打断」标记，明确指出来}

## 未完成 / 下一步
{任务板里 pending / in_progress 的项 + 时间线里明确说了要做但没做的事}

## 关键决策与约束
{定下来的口径、试过发现不行的路、不能再踩的坑。防止续跑时走回头路}

## 需要你拍板的
{transcript 里悬而未决、必须人来决定的问题。没有就写「无」}

## 续跑指令
{一段可以直接复制粘贴的 prompt，让新 session 无缝接上}
```

## 硬规则

1. **「说要做」≠「做完了」**。只有出现对应的 Edit/Write/Bash 动作证据才算落地；只在正文里承诺过的，写成「声称要做，transcript 里没看到动作」。
2. **不许编**。transcript 里看不出来的就写「看不出」。尤其是被省略的回合，不要脑补内容。
3. **不贴原文**。briefing 是提炼，不是转载。需要细节时给出「回合号 + 怎么查」（`--full` 或直接 grep transcript）。
4. **闲置时长要说**。>3 天的 session，提醒代码/环境可能已经漂移（分支、依赖、集群状态），续跑前先验证现状。
5. **subagent 的内部对话不在 transcript 主线里**（脚本已跳过 sidechain），briefing 里只写主线派了什么 agent、拿回什么结论。
6. 用户要存档 → 转 `save_session_context`，别在这里重新发明。
