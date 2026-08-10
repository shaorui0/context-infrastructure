# Anki 学习 Harness 设计 — 用真实行为日志驱动的偏科纠正闭环

> 日期：2026-05-29 · 状态：设计定稿（未实现）· 已补充人机接口层（engine / state.json / skill / UI）

## 一、初衷（要解决的核心矛盾）

- 这不是"做一个更好的卡组"，而是一个**闭环控制系统（harness）**。
- 核心矛盾：「我每天在做的事」和「我为达成目标必须做的事」之间会悄悄裂开一道缝。
- 展开：设了目标（N2，且不只考过，要真能听能说）→ 每天背卡涌现地训练某些能力 → 但卡组是过去设计的，会**系统性偏科**（今天背的 80 张全是"汉字→意思"，对中国人最舒服最没用；听力 audio-only 三天为 0）→ 自己感觉不到，因为每天都"学了" → 最后 miss target，不是不努力，是方向没人盯着对齐目标。
- Anki 恰好提供闭环两要件：① 自带行为日志（revlog：对错／反应时间／间隔／lapse）= 观测到的真实行为，不是自报；② 开源 + 能 sync = 日志可被程序读、被 agent 每天消费。
- 所以 harness 工作 = 用 Anki 真实日志，持续检测「能力覆盖缺口」，自动把人拨回最性价比的路。"性价比"精确含义：把时间投到边际收益最高的维度（中国人读已强→少投；听-only 和产出是缺口又是考试重头→多投）。

## 二、关键认知：卡的"形式"决定它训练哪种能力

下面这张表是让 Anki 多维训练的核心原语：

| 能力维度 | 卡正面 | 卡反面 | 给中国人的关键点 |
|---|---|---|---|
| 読（识别） | 漢字/书面日语 | 读音+意思 | 天然强，别过度投 |
| 聴-atomic（听词句） | 只有声音，无文字 | 文字+意思 | 必须 audio-only，否则偷看汉字，听觉永远练不出 |
| 説（产出） | 中文意思 | 日语声音+文字 | Anki 只能出题，不能评判说得对不对 |
| 文法（应用） | 含语法点句子/抽规则 | 规则+辨析 | n2_grammar_170 已是现成料 |
| 語感（内化） | （上面任一形式） | — | 不靠新卡，靠反应时间下降度量 |

这对应"意识→潜意识"——内化不需新内容，需要同一张卡反复快速召回直到反应时间下降；Anki revlog 记了每次反应时间，所以语感可测，不是玄学。

## 三、数据模型（不变 + 每天变化）

```
┌─────────────────────────────────────────────────────────────┐
│ L0 — Base Context（慢变，手写）                                │
│  · 目标：N2 @ 2026-07-05（已有 n2_sprint_2026.md）             │
│  · 个人 context：中文母语 → 汉字红利 + 先入为主风险             │
│  · 能力地图：第二节的表                                          │
│  · 大纲：n2_grammar_170 + 词表                                 │
├─────────────────────────────────────────────────────────────┤
│ L1 — Daily Delta（每天变，机器读，不靠自报）← 目前缺的环         │
│  · 从 Anki revlog 拉                                           │
│  · 今天复习每张卡 {对错, 反应时间, 间隔, lapse, tag}            │
├─────────────────────────────────────────────────────────────┤
│ L2 — Derived State（算出来）                                   │
│  · 能力覆盖                                                     │
│  · 掌握度（lapse 率）                                          │
│  · 内化度（反应时间趋势）                                       │
│  · 进度对账（对目标日期超前还是落后）                            │
└─────────────────────────────────────────────────────────────┘
```

注：每张卡带 `ability::` / `dir::` tag，是让 L1 能归因的关键。

## 四、Harness 闭环（每天跑一次）

```
        ┌──────────────────────────────────────────────┐
        │                                              │
        ▼                                              │
  ① INGEST                                             │
  读 revlog（AnkiConnect）                              │
        │                                              │
        ▼                                              │
  ② ATTRIBUTE                                          │
  按能力维度归因                                         │
        │                                              │
        ▼                                              │
  ③ DIAGNOSE                                           │
  对账缺口                                              │
        │                                              │
        ▼                                              │
  ④ PLAN                                               │
  按性价比分配明天                                       │
  （+ Anki 干不了的路由出去）                            │
        │                                              │
        ├──────────────┬───────────────                │
        ▼              ▼                               │
  ⑤a 生成/调整         ⑤b 非 Anki 任务处方              │
  Anki 卡              （shadowing / /n2 模式）          │
  复用 build_anki.py /                                  │
  anki_import.py，                                      │
  按缺口选 audio-front 等形式                            │
        │              │                               │
        └──────┬───────┘                               │
               ▼                                        │
            sync ───────────────────────────────────────┘
```

关键点：计划 ④ 的输入是 ②③ 的观测事实，不是意图。"以为在均衡学"但日志说三天没碰听力 → harness 强制把明天配额倾向听力。这就是 harness 让人离目标越来越近的机制。

## 五、能力地图（精确定义）

| id | 中文 | 卡形式（front→back） | 由谁练 | target | JLPT 权重 | 性价比先验 |
|---|---|---|---|---|---|---|
| read_recog | 読·识别 | 书面日语→读音+意思 | Anki | lapse<10%，覆盖全词表 | 中 | 低（天然强，压缩） |
| listen_word | 聴·语句 | 纯声音（无文字）→文字+意思 | Anki | lapse<15% | 高 | 高（缺口） |
| grammar_app | 文法·运用 | 含语法点句子→规则+辨析 | Anki | lapse<15%，覆盖 170 | 高 | 中 |
| listen_passage | 聴·篇章 | — | 非 Anki → /n2 聴解 | 正确率≥70% | 高 | 中 |
| produce | 産出 | 中文→日语声音+文字 | Anki 出题 + shadowing | 只刷量，不评分 | N2 不考 | 暂低 |
| internalization | 内化·语感 | — | 派生指标，非卡 | 反应时间趋势↓ | — | — |

三类维度：

- **卡可练**（read / listen_word / grammar / produce，每卡打 tag 可归因）
- **路由**（listen_passage，Anki 做不了篇章，PLAN 派给 /n2）
- **派生**（internalization，算出来的，不是卡类型）

## 六、Tag 契约

卡在生成时打结构化 tag，`key::value` 约定。例子：

```
n2 ability::listen_word dir::audio_front src::vocab::1042 cohort::2026w22
```

- `ability::X` 绑维度，唯一（每卡恰好一个，否则归因含糊）
- `dir::Y` 卡形式，验证 audio_front 的卡真没文字
- `src::...` 溯源，回链 n2_grammar_170 / 词表
- `cohort::` 何时引入，做留存分析

tag 是连接"能力地图（有哪些维度）"和"归因（按 tag 分桶）"的合同。

## 七、归因 Schema（revlog → 能力桶）

AnkiConnect `getReviewsOfCards` 每条复习给 `{cid, id（复习时刻 ms）, ease（1=Again..4=Easy）, time（反应 ms）, ivl, type}`。

```
revlog 行 ──(join on cid)──▶ notesInfo.tags ──parse──▶ ability::X
                              │ group by (ability, day)
                              ▼
   per (ability, day):
     reviews        = 条数
     fail_rate      = count(ease==1)/reviews      # 掌握度
     median_time_ms = median(time)                # 当前反应速度
     time_trend_7d  = slope(median_time, 7d)       # 内化(应<0)
```

关键洞察：掌握度（fail_rate↓ = 记住）和内化（median_time↓ = 答得越来越快 = 语感）是两个独立信号。总答对但时间不降 = 记住没内化；时间持续降 = 正沉入潜意识。time 字段让这个区分从玄学变可测。

## 八、运行节奏（已拍板：每日自动 + 周度复盘）

```
每日循环（轻，自动）
  晨/晚定时
    → AnkiConnect 读昨日 revlog
    → 按 ability tag 归因
    → "昨天：读 72 / 听-only 0 / 文法 18，听力连续 3 天 = 0"
    → 出今日处方（各维配额 + 新卡 audio-front 优先 + shadowing 句子）
    → 执行

周度复盘（重，周日，对账目标）
    → 七天能力覆盖热力 + 各维 lapse 率 + 反应时间趋势
    → 对账 n2_sprint_2026.md 进度
    → 调下周 base 配额（性价比再平衡）
    → 写回 weakness_log.md
```

周度这环接上 n2_sprint_2026.md 里"每周日错题本复盘"，只是数据源从手动错题本换成 Anki 真实日志。

## 九、三个已拍板的设计决策

- **数据接入：AnkiConnect 插件**（`http://localhost:8765`，跑前探活）。理由：能拿逐条 ease + time，而"内化／语感"维只能靠反应时间趋势度量，正好需要 time。
- **产出盲区：Shadowing 跟读**（不进对账打分，harness 只派量 + 周度诚实标注"产出只刷量无质量信号"）。理由：N2 不考口语，现在搭评测不值，留到考过再加。
- **节奏：每日自动 + 周度复盘**。

## 十、可行性与扩展性

**清楚了吗：是。** 契约闭合：能力地图（维度）↔ tag（每卡绑定）↔ 归因（group-by tag），一个表讲完，无悬空环节。

**目前能不能做到：能，但有一个硬改 + 几个 caveat。**

| 项 | 状态 |
|---|---|
| AnkiConnect 给 ease+time 逐条复习 | ✅ getReviewsOfCards 支持（需较新版，先 version 探测，旧版 fallback cardReviews） |
| join tag 分桶 | ✅ notesInfo 给 tags，纯数据处理 |
| 生成时打 ability::/dir:: tag | ❌ 现在 build_anki.py/anki_import.py 不打——动手前唯一硬改，但很小 |
| 历史无 tag 卡 | ⚠️ 落 unknown 桶，或一次性回填 |
| 内化信号噪声 | ⚠️ time 会被分心拉高→用 median/截尾；每维每天 <~20 条时信号弱 |
| 每日自动 vs AnkiConnect | ⚠️ AnkiConnect 要 Anki 开着→"每日自动"隐含 Anki 常开；真无人值守得 fallback 解析 collection.anki2 |

**扩展性（设计最强处，因为契约是 tag 不是代码）：**

1. **加维度** = 能力地图加一行 + 一个 `ability::` 取值，归因是通用 group-by，零代码改动（如以后加 `ability::kanji_write`）。
2. **换语言**（学韩语）= 同一 harness，只换 L0 base context；①INGEST ②ATTRIBUTE ③DIAGNOSE ④PLAN 全程语言无关——harness 本质是通用"目标 vs 行为对齐器"，日语只是第一个实例。
3. **加模态**（给 listen_passage 配真材料、给 produce 配 AI 评分）= PLAN 路由器加分支，能力地图那行的"路由目标"指过去。
4. **超出 Anki** = 归因本质是"行为日志→能力桶"，任何吐日志的工具（阅读 app、/n2 session log）都能喂同一 ATTRIBUTE 步；Anki 只是第一个最丰富的日志源。
5. **性价比是数据不是代码** = 优先级 = JLPT 权重 × 当前缺口 × 边际收益，全读能力地图；调优 = 改表。

一句话收口：只要 tag 契约立住，加维度／换语言／换日志源都不动核心代码；风险只在内化信号噪声和 AnkiConnect 要求 Anki 常开两点。

## 十一、与现有基建的关系

现状是：生成端 + 训练端齐了，唯独缺反馈端。

| 环节 | 现状 |
|---|---|
| 卡生成/TTS/导入 | ✅ build_anki.py、anki_import.py（双向卡、edge-tts） |
| 训练模式（听说读写） | ✅ /n2 6 模式 + /n2prep 5 模式 |
| 目标/大纲数据 | ✅ n2_sprint_2026.md、n2_grammar_170.md |
| 读 Anki 真实行为日志 | ❌ 完全没有——harness 核心新增 |
| 能力归因+缺口诊断+自动配额 | ❌ 没有 |

收口：这设计不是从零造系统，是补上唯一缺的"反馈端"（①INGEST + ②归因 + ③诊断 + ④配额），把已有生成端和训练端接成闭环。

## 下一步（未实现）

动手时的第一步：给 build_anki.py / anki_import.py 加 `ability::` / `dir::` tag 输出（扩展性和归因都卡在这）；然后写 AnkiConnect ingest + 归因脚本验证逻辑；逻辑稳了再上每日定时。

## 十二、人机接口层：事实 / 判断 / 展示三层切开

核心架构动作：在 ENGINE 和接口之间立一个唯一真相源，否则 skill 和 UI 会各算各的、显示不一致的"离目标还有多远"。

```
AnkiConnect (revlog)
        │
        ▼
┌──────────────────────────────────────┐
│ ENGINE  ingest + attribute + diagnose │  纯 Python,确定性,无 LLM,可 cron
└───────────────┬──────────────────────┘
                ▼
          state.json   ◀── 唯一真相源 (L2 derived state)
                │
       ┌────────┼─────────────────┐
       ▼        ▼                 ▼
  [Analyst]  [UI 仪表盘]      (每日 cron 只跑 engine)
  agent skill  读 state.json
  读 state.json  渲染:覆盖/进度/缺口
  → 判断+建议    → 展示 analyst 建议
  → plan.json    → 你 approve
       │              │
       └─► plan.json ◀┘   ← 下一轮 PLAN 读它
```

设计原则：

- ENGINE 产出事实（state.json），Analyst 产出判断（plan.json 建议），UI 是镜头 + 审批闸门。
- 事实只有一个写者（engine 写 state.json），plan 只有一个写者（skill 写 plan.json）。skill 和 UI 都只依赖 state.json 的 schema，互不耦合——避免两边算法出入导致"离目标多远"显示不一致。
- 成本边界：每天定时跑的是纯 Python engine（读 revlog→算 state.json，零 LLM 成本，cron 友好）；只有要"判断和建议"时才调 claude（花 token 换质性诊断）。这是该走的性价比。

## 十三、Agent 交互（headless skill）

对应 ai_agent_cli_guide 路线。一个 skill `/anki_harness`，两种调用：

```bash
# 交互:session 里直接看分析
/anki_harness status

# headless:机器可读,可 cron、可喂 UI、可被别的 agent 消费
claude -p "/anki_harness status" --output-format json
```

skill 分工（关键：它不重新查 raw 数据）：

1. 跑 engine 脚本 → 拿 state.json（确定性部分交给代码）
2. agent 在 state.json 上做判断层（LLM 加价值处）：诊断叙事（例："听力 audio-only 连续3天=0；文法 lapse 降了但 median_time 没降→记住没内化"）+ plan-delta 建议（例："明天 听力+30 / 读-20；本周补 shadowing"）+ 写 plan.json。

模式：status（只诊断）/ plan（出明天处方）/ replan（重新配额）。原则：确定性的留代码，判断的留 agent（与 Opus 工作模式一致）。

## 十四、UI（静态 HTML，只读；三面板）

已拍板：静态本地 HTML，只读，读 state.json/plan.json 渲染；plan 更新不在 UI 里写，走命令行 `/anki_harness replan`（单写者、零服务、复用现有 HTML/design 技能）。

三个面板，正好对应三个问题：

| 用户问的 | UI 面板 | 数据源 |
|---|---|---|
| "我目前走到哪了" | 能力雷达/热力图：各维 lapse 率 + 反应时间（掌握度 vs 内化两条信号） | state.json |
| "我离目标还有多远" | 进度对账/burndown：每维对 n2_sprint_2026.md 目标日的 pace gauge（例："听力按当前速度会 miss 9 天"） | state.json + L0 target |
| "我该不该调 plan，多干啥少干啥" | 建议面板：展示 analyst 的 plan-delta（只读展示）；调整动作回到命令行 /anki_harness replan | plan.json |

收口一句：第三面板把"看不见的缝"画在屏幕上，正面回应最初的恐惧（"我可能会忘记锻炼某些能力"）——想忘也忘不掉。因选了静态只读，approve/改配额的写动作走 skill，UI 不引入第二个 plan 写者。

## 十五、接口层的可行性与扩展性

- 可行性：能。state.json 是新契约（同 tag 契约套路），skill 和 UI 只依赖它的 schema，互不耦合。engine 是纯 Python + AnkiConnect，UI 读 JSON 渲染。
- 扩展性：加一个能力维度 → state.json 多一个 key → UI 多画一根条、skill 多分析一行，两个接口零改动；换语言同理。
- 已拍板决策记录：UI = 静态 HTML 只读；plan 写回走 skill（单写者）。
