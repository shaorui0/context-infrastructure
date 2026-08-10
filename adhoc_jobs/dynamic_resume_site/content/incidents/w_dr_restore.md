# META
id: w-dr-restore
kicker_en: RECOVERY
kicker_cn: 恢复
title_en: Restoring 5.2 billion rows without touching prod
title_cn: 不接触生产，恢复 52 亿行
sub_en: A restore drill that corrected its own premise and made RPO explicit for the first time.
sub_cn: 一场纠正了自身前提的恢复演练，第一次把 RPO 写成显式数字。
domains: [data, incident]

# EN

## Correcting the premise

The initial plan assumed rows expired by the database's TTL could be recovered from the live volume. That assumption was wrong, and proving it wrong was the first deliverable: this engine's TTL delete physically unlinks the data parts, and no S3 tiering existed to catch them. Nothing recoverable remained on the live system — and experimenting on a live disk to confirm that would have been risk without payoff.

## The recovery architecture

What did exist was an immutable daily EBS snapshot series of the production volumes. The restore path: materialize a snapshot to a **brand-new, independent volume**, attach it to a **separate database instance**, and verify there. No attach/detach on any live disk, no connection to any production system at any point. The blast radius was not "managed" — it was structurally zero, provable from the design before execution.

## Verified, with numbers

The restored dataset came up live and queryable: **5.198 billion rows / 4.07 TiB**. A full `count(*)` completed in **50 s**; a full-table cold aggregation in **83 s**. A restore is not a restore until you have queried it — a mounted volume proves storage, not data.

## Honest boundaries

Two limits, named on purpose. The implied RPO is roughly 24 hours — that is what a daily snapshot series gives you, and nobody had written it down as an SLA before this drill made it visible. And this was a one-off drill proving the path works at full scale, not yet a scheduled DR program. Both gaps are now explicit, which is the difference between a gap and a surprise.

> The most useful output of a restore drill is rarely the data. It is the corrected assumptions and the numbers (RPO, restore time) that nobody had been forced to state before.

# CN

## 纠正前提

最初的方案假设被数据库 TTL 过期的行能从在线卷上找回。这个假设是错的，而证明它错就是第一份交付物：这个引擎的 TTL 删除会物理 unlink 数据 part，也不存在能接住它们的 S3 分层。在线系统上没有任何可恢复的东西，而在在线磁盘上做实验来确认这一点，是只有风险没有收益。

## 恢复架构

真实存在的是生产卷的不可变每日 EBS 快照序列。恢复路径：把快照物化成一块**全新的独立卷**，挂到一个**独立的数据库实例**上，在那里验证。全程不对任何在线磁盘做 attach/detach，任何时刻不连接任何生产系统。爆炸半径不是「被管理」，而是结构性为零，执行前即可从设计证明。

## 用数字验证

恢复出的数据集在线可查：**51.98 亿行 / 4.07 TiB**。全量 `count(*)` 用时 **50 秒**；全表冷聚合 **83 秒**。没被查询过的恢复不算恢复：挂上的卷证明的是存储，不是数据。

## 诚实的边界

两条边界，刻意点名。隐含 RPO 约 24 小时：每日快照序列就给你这么多，而在这次演练之前没人把它写成 SLA。这是一次证明路径可行的一次性演练，还不是有日程的 DR 制度。两个缺口现在都是显式的，这正是「缺口」与「意外」的区别。

> 恢复演练最有用的产出很少是数据本身，而是被纠正的假设，和那些此前没人被迫写下的数字（RPO、恢复时长）。
