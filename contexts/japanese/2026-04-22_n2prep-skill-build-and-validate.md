# Session Capture: /n2prep skill — 搭建与真实验证

- **日期**: 2026-04-22
- **Session 关键词**: n2-prep, anti-laziness-gate, parallel-subagent, solidity-gate, skill-orchestration
- **持续时间**: ~2h

---

## 核心想法

- **两个 skill 分层**：`/n2`（已有，交互式单题/短会话）vs `/n2prep`（本次新建，长周期备考编排）。不要把两者糅进同一 skill——职责边界清晰，"/n2 是 5-20 分钟练一下，/n2prep 是 1-3 小时完整备考"。
- **反偷懒的关键是"出卷 agent 和验卷 agent 必须分离"**：一个 agent 自己验自己必然徇私。用户一开始就点明"LLM 喜欢偷懒，最后比如收尾需要判定生成的卷子比较'扎实'了"，整个设计围绕这个前提构建。
- **扎实度门禁的证据门槛**：门禁 agent 的 critique 必须附"题号 + 引文"，不允许"看起来还行"这种空洞评价。prompt 里写死"你的 critique 如果空洞会被二次审查发现"。
- **3 轮回流硬上限**：防止死循环，3 轮仍不过就交付带 critique，让人工取舍。不能让机器无限打磨。
- **代理指标代替真实 JLPT 量表分数**：JLPT 等化量表分数本地没法复现，用原始正答率 / 1-pass 率 / recognition latency 代理。60% 有戏、75%+ 稳过（经验映射）。

## Insights

- **门禁不是装饰——在真实 LLM 下真的抓到了偷懒**。Round 1 gate 精准抓出：
  - 問12「経済家」非日语自然词（解说自己都写"应为経済学者/評論家"，等于自承 key 不地道）
  - 問13「スマートフォン化社会」搭配生硬（固定搭配是「情報化社会/少子化社会」）
  - 問11 干扰项「未賛成」「無賛成」是伪造词，3/4 可一眼淘汰
  - 这不是预想的偷懒模式，是真实 sub-agent 在约束下仍然暴露的质量问题。
- **对 N2 补什么模块**（不止 corpus + Anki）：
  1. **Shadowing（影子跟读）** 最高 ROI，直接治聴解"听得懂但跟不上"
  2. **限时阅读训练**，読解瓶颈是速度不是理解
  3. **弱点台帳按 pattern 聚合而非按题**，才能发现"～につれて / ～にしたがって 反复混淆"这种模式
  4. **写作/口语产出**（可选），N2 不考但能产出比能识别牢固 3 倍
  - 不建议加：漢字单独训练（中文母语者近白送）、敬語深挖（N2 考察有限）。
- **每日 Anki 30 note 上限是认真的**，超出进候补池。防止一下甩 100 张过载。
- **Anki deck 用双冒号分层**：`N2_prep::YYYYMMDD` 自动按天成子 deck。
- **对 Opus 的任务分配**：主设计 + 质量把关自己做，调研/实现派 sub-agent。这次 Opus 自己写了 SKILL.md、4 个 prompt 和 3 个 runner，派 sub-agent 验证了出卷 → 门禁 → 回流 → 再门禁的完整闭环。

## 决策与理由

| 决策 | 选择 | 理由 |
|---|---|---|
| 官方 scope 调研 | **不现在跑**，stub 知识文件 + TODO | 不阻塞 skill 搭建；真要用时 Phase 0 触发 |
| 触发词 | `/n2prep` | 与现有 `/n2` 正交，不侵入 |
| Runner 语言 | Python | 状态管理 + 计时 + 结果汇总，bash 不合适 |
| 门禁最大回流 | 3 轮 | 防死循环 + 强制收敛 |
| 每日 Anki 上限 | 30 note | 防过载；用户明确选 30 而非 20 |
| Shadowing | v1 就做 | 用户说"一起做"，不延 v2 |
| 全局注册方式 | symlink | 学现有 anki_japanese_flashcard 的 pattern |
| SKILL 放哪 | `archives/skills/n2_exam_prep/` | 含脚本的 skill 用 archives 惯例 |

## 关键讨论

- **用户点题"LLM 喜欢偷懒"**：这句驱动了整个门禁设计。不是事后补的安全网，是第一天就画在架构图上的核心组件。
- **"还缺什么？对于我备考 n2"**：用户主动问 gap，说明备考思维里"靠语料堆"本身有不安感。回答 shadowing + timed reading + weakness pattern-log + optional writing 四项。
- **"完整验证过真实可用"**：用户对"完成"的定义高——不是"代码能跑"，是"端到端真实 sub-agent 链路走通，并在真实 LLM 偷懒模式下能抓到问题"。这驱动了 round 1 → RETRY → round 2 → PASS 的真实闭环验证，而不是 unit test 糊弄。

## 验证过程中的真实数据

**反偷懒循环真的 converge 了**：
- v1: 28 题生成，自报"无偷懒" → 门禁打回 3 题
- v2: 精准修改 3 题，其他 25 题原样保留 → 门禁 PASS
- 修复的具体内容：
  - 問11: 大賛成（再/猛/大/初 都是合法接頭辞，不再是伪造词）
  - 問12: 登山家（替代 経済家，职业称呼合媒体语境）
  - 問13: 少子化社会（替代 スマートフォン化社会，固化搭配）

**发现的真 bug（3 个）**：
1. `avg_time_sec` 在 0.0 时误报 null（`if avg_time` 对 0 为假）→ `is not None` 修复
2. `listening.py` transcript 正则吞 `- 解说:` 前缀行 → lookahead 加 `[-*]?\s*` 修复
3. `run_shadowing.py` stdin EOF 时 crash → try/except EOFError 修复

## Open Questions / 下一步

- [ ] 跑 `workflow_deep_research_survey` 调研 jlpt.jp 官方 scope，产出 `contexts/survey_sessions/n2_exam_spec_<date>.md`，蒸馏回 `rules/knowledge/n2_exam_spec.md`，把 `status: STUB` 改 VERIFIED
- [ ] **第一次真实使用**：`/n2prep daily` 跑一次完整小流量（15 题 + 30 Anki + 5 分钟 shadowing），验证 Phase 0-7 整条链在**人类交互**下的体感（目前只验了 sub-agent + pipe 自动化）
- [ ] v2 限制：听力单声线。真正男女轮转需要按 speaker 分段合成 + 拼接（pydub / ffmpeg），edge-tts 不支持单次切声线
- [ ] 可选 Mode 7：写作/口头产出（用户未明确要，但 ROI 高，备用）

## 原始片段

> "搞个skill，理解n2范围、难度，从官网。注册到全局，几个subagent（避免偷懒）..."
>
> 开场就把"注册到全局"和"避免偷懒"并列成硬要求——不是后来补的。

> "配合我那个读音的工具，写一个脚本，能够跑起来对应的听力。"
>
> "读音工具" = 已有的 edge-tts + afplay。用户假设这个是基础设施，不要重造。

> "需要考虑llm 喜欢偷懒，最后比如收尾需要判定生成的卷子比较'扎实'了"
>
> 这句话是整个 solidity gate 的 origin。"扎实"是用户的词，直接用到 `gate_check.md` prompt 里（扎实度门禁 / Solidity Gate）。

> "决策按你建议的来 / 5. 30 / 6 一起"
>
> 用户决策风格：对已经权衡过的建议快速 yes，只在数字（30 vs 20）和 scope（shadowing 一起）上做二元选择。不纠结无关紧要的细节。

> "完整验证过真实可用"
>
> "完整验证"不是"写了 test"——在这次语境里，意味着"派真实 sub-agent 跑完 出卷 → 门禁 → 回流 → 再门禁 的闭环"。
