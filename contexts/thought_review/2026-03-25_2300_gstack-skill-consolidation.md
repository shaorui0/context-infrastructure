# gstack 整合与 Skill 体系精简

**日期**：2026-03-25
**来源**：Claude Code 对话

## 关键结论

- gstack (Garry Tan) 的 28 个开发流程 skill 通过 git submodule 整合进 context-infrastructure，与自建 skill 统一管理于 `rules/skills/`
- 自建 SKILL.md 技能从 11 个精简到 4 个（blogs-writer, critical-thinking, red-team, oncall_checklister），删除的 skill 要么可被 gstack 替代，要么可被一句 prompt 替代
- Skill 质量判定标准确立：specificity（一致可重复）、uniqueness（裸 prompt 做不到）、actionability（产出具体制品）、usage frequency（实际使用频率）、prompt engineering quality

## 思维与偏好

- **统一管理优先**：所有 skill 实体放 `context-infrastructure/rules/skills/`，`~/.claude/skills/` 只放 symlink。理由是 git tracked + 单一真实源 + 换机器可恢复
- **第三方工具用 submodule**：gstack 保持自己的 git clone（submodule），保留 `gstack-upgrade` 能力。不删 `.git`，不做死副本
- **果断砍 skill**：对"听起来有用但实际不用"的 skill 零容忍。industry_sensitivity_loop 14 个月没更新直接删；output-expression-corrector 零独特价值直接删；first-principles 和 prompt-fixer 提取精华为 axiom 后删
- **dev-runner vs gstack 的判断**：当 gstack 已覆盖完整 dev pipeline（plan → review → qa → ship → deploy → canary → retro），dev-runner 的 OpenSpec 概念虽然独特但从未真正使用过，果断删除

## 工作上下文

- gstack submodule 位置：`rules/skills/gstack/`（git remote: github.com/garrytan/gstack）
- 升级方式：`cd rules/skills/gstack && git pull` 或 `/gstack-upgrade`
- 新增 axioms：X07（第一性原理约束清单，提取自 first-principles skill）、X08（Prompt 质量标准，提取自 prompt-fixer skill）
- de_ai_blog_refactor 的 D01-D10 规则已合入 blogs-writer Stage 06（`stages/06_final.md`）
- `~/.claude/skills/` 最终结构：gstack symlink + 4 个自建 skill symlink + gstack setup 创建的 28 个相对 symlink

## 可复用方法

- **Skill 审计流程**：用 3 组并行 subagent 审计 11 个 skill，每组 3-4 个，按 5 维度评分，产出 KEEP/REMOVE/MERGE 建议表。总耗时约 1 分钟
- **Skill 精简模式**：删除前先提取有价值的碎片（checklist → axiom，规则集 → 合入其他 skill 的 stage），避免知识丢失
- **gstack 三条哲学可内化**：(1) Boil the Lake — AI 让完整实现的边际成本趋零，不走捷径 (2) Search Before Building — 先搜再建 (3) Build for Yourself — 真实问题 > 假想通用性
- **gstack 标准工作流链**：`/office-hours` → `/plan-ceo-review` → `/plan-eng-review` → 写代码 → `/review` → `/qa` → `/ship` → `/land-and-deploy` → `/canary` → `/retro`
