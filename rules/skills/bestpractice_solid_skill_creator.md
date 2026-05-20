# Solid Skill Creator（工程化写 Skill）

## 元数据

- **类型**: BestPractice
- **适用场景**: 写一个新的 skill / 重写凭感觉写的旧 skill / 评估 skill 质量
- **创建日期**: 2026-05-20
- **来源**: 2026-05-20 session — 分析 `workflow_deep_research_survey.md` 为什么能逼出 agent 深度

---

## 核心命题

> **Skill 不是教 agent 怎么做好,是堵住 agent 怎么做差。**

凭感觉写的 skill 是**正面表述的方法论**(请深入、请全面、请认真);
工程化的 skill 是**反向编码的失败模式防御网**(没写 URL 就过不了、没贴原文就过不了)。

形容词 agent 可以糊弄,产物可以 grep。**好 skill 的判别标准:agent 偷懒会在哪一步被卡住?答得上来,才是工程化的 skill。**

---

## 工程化 Skill 的 5 个动作

### 1. 先列失败模式,不是先列步骤

凭感觉:"调研要深入、要全面、要客观。"
工程化:先问"agent 在这个任务上最常以什么方式失败?"

- 总结代替原文 → 失去可验证性
- 只搜正面 → 偏差
- 单线程深挖 → context 污染
- 单点信息 → 没有交叉验证

**每个失败模式 → 对应一条结构约束。** Skill 里的每条规则都应该能回答:"它在防哪个失败?"

### 2. 用可观察的产物代替形容词

凭感觉:"请深入。"
工程化:"返回 URL + 原文摘录(不是总结)。"

形容词无法验证、agent 可以糊弄;产物可以 grep。

Skill 里出现 **深入 / 全面 / 认真 / 仔细 / 充分** 这类词,都要翻译成具体产物:
- 文件路径 / 字段名 / Markdown 链接格式 / 行数下限 / 表格列 / 截图 / 原文 blockquote

### 3. 设计冗余而不是分工

凭感觉:"3 个 agent 各调研一个维度,拼起来就是全貌。"
工程化:"维度之间 ≥50% overlap,因为我要的不是覆盖率,是矛盾。"

**冗余 = 交叉验证 = 信号源。** 工程化的 skill 知道:**单一来源 = 不可信**,所以主动制造重复劳动。

参见 `workflow_deep_research_survey.md` 的 50% overlap 规则、`bestpractice_multi_agent_analysis.md` 的并行交叉验证模式。

### 4. 把 Prompt 工程外化成 Skill 工程

- Prompt = 临时火力(本次对话用一次)
- Skill = 持久火力(以后每次都生效)

**判断分水岭:同一个失败模式下周还会遇到吗?**
- 会 → 写成 skill,不是在 prompt 里救场
- 不会 → 留在 prompt 里就好

### 5. 列陷阱表(反向规约)

Skill 末尾的"陷阱与对策"表是工程化痕迹的判别器。

它承认 skill **不是写给完美 agent 的,而是写给会走捷径的 agent 的**。每一条陷阱 = 过去踩过的坑反向编码成的约束。

**没有陷阱表的 skill 通常是凭感觉写的。**

陷阱表的内容来自:
- 自己写 skill 时主动逆向推演(agent 会怎么偷懒?)
- 实际 agent 失败后的回流(参考 [[workflow_agent_failure_taxonomy]])

---

## Skill 工程化骨架

```markdown
# Skill 名称

## 元数据
- 类型 / 适用场景 / 输出位置 / 创建日期

## 核心原则(3-5 条,每条对应一个失败模式)
- 不是"请认真",是"必须返回 X"

## 工作流程(Phase 1..N)
每个 Phase 必须有:
- 目标(一句话)
- 操作(具体步骤)
- 输出物(可观察、可 grep)

## 强制产物规范
- URL 格式 / 字段名 / 行数下限 / Markdown 模板
- 反例:"❌ 没有 URL 的引用"

## 子 Agent 调用模板(如涉及)
- category / tools / run_in_background 显式指定
- prompt 模板里点名"必须返回 X、不需要写文件"

## 陷阱与对策表
| 陷阱 | 对策 |
| --- | --- |
| Agent 会偷懒方式 X | 结构约束 Y |
```

---

## 自检三问(写完 skill 必跑)

1. **如果 agent 偷懒,在哪一步会被卡住?**
   答不上 = 没有强制点 = 凭感觉。

2. **这条规则在防哪种失败?**
   答不上 = 这条规则没必要 = 装饰,删掉。

3. **如果删掉这条规则,产出会变差吗?变差在哪?**
   答不出 = 删掉。

三问通不过 = skill 还没工程化,回去重写。

---

## 参考样本

### ✅ 工程化 Skill 标杆

- [`workflow_deep_research_survey.md`](./workflow_deep_research_survey.md) — 5 个结构约束(overlap / 原文摘录 / URL 留存 / 反正面偏差关键词 / 并行后台),每个都对应一个具体偷懒路径。
- [`bestpractice_multi_agent_analysis.md`](./bestpractice_multi_agent_analysis.md) — Topic 分割 + 50% 重叠的冗余设计。
- [`bestpractice_staged_approach.md`](./bestpractice_staged_approach.md) — 隔离-处理-验证三阶段,每阶段产出物明确。

### 拆解:为什么 `workflow_deep_research_survey` 能逼出深度

| 失败模式 | 结构约束 |
| --- | --- |
| Agent 用总结代替原文 | 强制"返回 URL + 原文摘录" |
| 维度太干净,各 agent 各说各话 | 强制 ≥50% overlap |
| 单 agent context 污染 | 多 agent 并行 `run_in_background=true` |
| SEO 默认偏正面 | 主动搜 "criticism / scam / overpriced" |
| 引用无法追溯 | 所有数据/评价必须带 URL |

**关键洞察:这个 skill 没有任何一句话喊"请深入",但它让 agent 没法不深入。**

---

## 陷阱与对策

| 陷阱 | 对策 |
| --- | --- |
| Skill 里写满"请认真/请仔细/请深入" | 每个形容词翻译成可观察产物;通不过的删掉 |
| 规则只有正面表述,没有反例 | 每条规则后面加 "❌ 反例" 或 "陷阱" 行 |
| 没有陷阱表 | 自问"agent 会怎么偷懒?",至少列 3 条 |
| Skill 看起来很全但落不了地 | 跑自检三问,删掉无强制点的章节 |
| 把一次性 prompt 写成 skill | 问"下周还会遇到吗",不会就别写 |
| 子 agent 调用模板含糊(没指定 tools/category) | 显式写 category、tools、run_in_background;参考 [[workflow_parallel_subagents]] |
| 产出物只有"一份报告" | 拆到字段级:报告必须包含哪些 section、每个 section 必须有什么字段 |
| Skill 写完没人用 | 在 INDEX.md 写一行能让未来 agent 触发的 description(场景关键词) |

---

## 与其他 Skill 的关系

- **失败模式来源** → [[workflow_agent_failure_taxonomy]](agent 失败回流到 skill 陷阱表)
- **并行调用骨架** → [[workflow_parallel_subagents]](子 agent 调用模板的标准写法)
- **冗余设计参考** → [[bestpractice_multi_agent_analysis]](50% overlap 的具体落地)
- **AI 编程心法** → [[bestpractice_ai_programming_mindset]](可验证性原则,skill 工程化的母原则)
