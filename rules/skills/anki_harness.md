---
name: anki_harness
description: 学习对齐引擎(anki-learning-harness)的"判断层"入口——读 engine 产出的 state.json,做质性诊断(缺口/记住没内化/领先/盲区)并写明日处方 plan.json。三模式 status/plan/replan。Use when user says "/anki_harness"、"学习复盘"、"anki harness"、"看学习状态"、"今天该学啥"、"出处方"、"重新配额",或在 N2/Anki 对齐引擎上下文里要诊断学习行为偏差。
---

# Skill: anki_harness — 学习对齐引擎判断层(全局封装)

> **这是薄封装。** 真正的实现与权威说明在项目内:
> `work-contexts/toy-proj/anki-learning-harness/skill/anki_harness/SKILL.md`
> 全新 session 第一步:读那份 SKILL.md 拿铁律与 plan.json 形状,本文件只负责把你带到那里 + 给最短可执行路径。

## 项目位置(从 workspace 根 `/Users/rshao/work/context-infrastructure/` 出发)

| 角色 | 路径 |
|---|---|
| 项目根 | `work-contexts/toy-proj/anki-learning-harness/` |
| 权威 SKILL(必读) | `work-contexts/toy-proj/anki-learning-harness/skill/anki_harness/SKILL.md` |
| 引擎(纯 Python,产 state.json,**不归本 skill 写**) | `work-contexts/toy-proj/anki-learning-harness/engine/run.py` |
| analyst(确定性预处理,你的判断锚点) | `work-contexts/toy-proj/anki-learning-harness/skill/anki_harness/analyst.py` |
| 工作目录 / 产出 plan.json | `work-contexts/toy-proj/anki-learning-harness/skill/anki_harness/` |
| fixtures(开发/验收用) | `work-contexts/toy-proj/anki-learning-harness/fixtures/state.sample.json`、`plan.sample.json` |

## 分工铁律(细节见项目 SKILL.md §0)

- **engine 是 state.json 唯一写者**;**本 skill 是 plan.json 唯一写者**。绝不互抢写。
- **不重查 raw、不重算事实**:mastery / latency / forecast / 配额边际收益都由 engine 算进 state.json,你只在事实之上做**判断**。
- **确定性归 analyst.py**(缺口排序、内化分类、ahead 判定、card_dir 合法性),**判断归你**(诊断叙事、权衡、动机、盲区诚实标注)。

## 三模式

| 模式 | 触发 | 产出 |
|---|---|---|
| `status` | "看状态" / "学习复盘" / 只想诊断 | 诊断叙事(headless 时输出 JSON 的 `diagnosis` 段),不出处方 |
| `plan` | "今天该学啥" / 出处方 | 写 `plan.json`(诊断 + 明日 plan-delta) |
| `replan` | 改了预算/目标后"重新配额" | 按新 target 重排,覆盖 `plan.json` |

## 最短执行路径

```bash
# 0) 必读权威 SKILL(全新 session 第一步)
#    work-contexts/toy-proj/anki-learning-harness/skill/anki_harness/SKILL.md

# 1) 拿 state.json:集成态用 engine 当日 cron 产物;开发/验收态直接用 fixture
#    (本 skill 不跑引擎逻辑、不查 AnkiConnect)
# 若需重新生成开发态 state:
python work-contexts/toy-proj/anki-learning-harness/engine/run.py \
  --source fixture --out /tmp/state.json

# 2) 跑 analyst 拿预处理脚手架(确定性,零判断)——在 skill 工作目录里跑
python work-contexts/toy-proj/anki-learning-harness/skill/anki_harness/analyst.py \
  --state work-contexts/toy-proj/anki-learning-harness/fixtures/state.sample.json

# 3) 基于 analyst 的 ranked_abilities/flags/card_dir_contract 写诊断叙事
#    plan/replan 再写 plan-delta → 落到
#    work-contexts/toy-proj/anki-learning-harness/skill/anki_harness/plan.json
#    (结构严格对齐 fixtures/plan.sample.json)
```

## Headless 用法(被 cron / UI / 别的 agent 消费)

```bash
claude -p "/anki_harness status"  --output-format json   # 只诊断,机器可读
claude -p "/anki_harness plan"    --output-format json   # 出处方,写 plan.json
claude -p "/anki_harness replan"  --output-format json   # 改预算后重新配额
```

输入(state.json)、输出(plan.json)都走文件,不靠管道传核心数据;plan.json 落本地、git diff 可审计、零外传。

## 关键约束(违反会被下游阻断,完整见项目 SKILL.md §2–§5)

- 出卡(`amount_cards>0`)的 `card_dir` 必须取 `analyst.py` 给的 `card_dir_contract[ability]`(tag 契约 FROZEN v1),取别值=违约,会被 producer tag_validator 拦。
- 无质量信号维(`blind_spots`)**不出卡**,只排 shadowing,并在 `notes` 诚实标注盲区。
- `state.meta.degraded==true` 时在 `notes` 标注降级、对缺信号维更保守(倾向 keep)。
- plan.json 写完不直接改 state.json;`state.latest_recommendation` 回填由 engine 下次 cron 做。
