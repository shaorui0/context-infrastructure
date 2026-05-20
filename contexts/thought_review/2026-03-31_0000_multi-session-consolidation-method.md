# Session Capture: 多 Session 汇聚方法论

- **日期**: 2026-03-31
- **Session 关键词**: multi-session, consolidation, distillation, AI Agent SRE, knowledge synthesis
- **持续时间**: 短 session（~10 分钟）

---

## 核心想法

- 当多个 Claude Code session 各自探索同一大方向（AI Agent + SRE + 生产级 Agent）的不同切面时，需要一个系统化的汇聚方法
- 全量保存 session 是浪费——80% 是探索性内容，真正有价值的是每个 session 的结晶物
- 正确的做法是两步走：先蒸馏，再合成

## Insights

- **蒸馏优于全量保存**：每个 session 自己做蒸馏效果最好，因为它有完整 context，知道哪些是关键转折点。全量 dump 进下一个 session 会吃掉大量 context window，留给合成思考的空间反而少了
- **蒸馏后的文件通常 200-500 行，5-8 个文件合起来约 2000 行，一个 session 轻松吃下**——这是选择"先蒸馏再合成"而非"全量传递"的实际约束依据
- **汇聚层不是简单拼接，是找上层框架**——要识别跨 session 的共同主题和张力（哪些观点互相支撑，哪些互相矛盾）
- **不要磨平矛盾**——如果两个 session 的观点冲突，保留张力并标注，这本身就是有价值的信号

## 决策与理由

- 选择"蒸馏 → 合成"两步法而非全量保存或直接总结
  - 理由：全量保存太噪声，直接总结会丢失原始 context 中的关键细节
  - 每个 session 的蒸馏 prompt 要求提取 4 项：Core Thesis / Key Insights / Open Questions / Concrete Artifacts
  - 蒸馏原则："宁可漏掉不重要的，不要稀释重要的。如果一个 insight 换个人也能想到，删掉。"

## Open Questions

- 用户当前开了多少个 session？各自的切面具体是什么？
- 蒸馏完之后的合成文档应该放在什么位置？`contexts/` 下的哪个子目录？
- 合成之后是否需要进一步提炼成可行动的 roadmap 或 positioning document？
- 多个 session 指向的共同方向（AI Agent + SRE 生产级系统）是否已经收敛到一个明确的 thesis？

## 原始片段

> 我现在开了一堆 session，Claude Code 的 session，然后每一个感觉都指向了一个地方，虽然有各个不同的切面，但它指向的都是 AI Agent、SRE 关联，然后生产级的 Agent，然后一些概念上的，比如说必要性啊，还有这些东西

> 蒸馏的时候让每个 session 在 Core Thesis 里用一句话回答："这个 session 对'生产级 AI Agent'这个问题的独特贡献是什么？" 这会强迫它找到自己的切面，而不是写一堆泛泛的总结。汇聚层拿到这些切面就能快速建立全景图。

---

## 附：蒸馏 Prompt（可直接复制到其他 session 使用）

```
把这个 session 的内容蒸馏成一个 markdown 文件，保存到
~/work/context-infrastructure/tmp/session_distills/ 下面，
文件名格式：{主题关键词}_{日期}.md

结构要求：
1. **Core Thesis**（1-3 句话，这个 session 最终收敛到的核心观点）
2. **Key Insights**（bullet list，只留不显而易见的洞察，删掉常识）
3. **Open Questions**（这个 session 没解决的、值得继续追的问题）
4. **Concrete Artifacts**（如果产出了框架/模型/代码/清单，原样保留）

原则：宁可漏掉不重要的，不要稀释重要的。如果一个 insight 换个人也能想到，删掉。
```

## 附：合成 Prompt（蒸馏全部完成后使用）

```
读 ~/work/context-infrastructure/tmp/session_distills/ 下所有文件。

这些是我多个独立思考 session 的蒸馏结果，都围绕同一个大方向：
AI Agent + SRE + 生产级 Agent 系统。

任务：
1. 先识别跨 session 的共同主题和张力（哪些观点互相支撑，哪些互相矛盾）
2. 合成一个结构化文档，不是简单拼接，而是找到上层框架
3. 标注哪些是已经收敛的结论，哪些还是假设需要验证
4. 输出到 contexts/ 下一个合适的位置

不要磨平矛盾。如果两个 session 的观点冲突，保留张力并标注。
```
