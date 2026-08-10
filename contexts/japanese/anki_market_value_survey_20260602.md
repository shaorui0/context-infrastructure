# Anki 深度调研：使用广度 · 市场价值 · 用户粘性 · 生态商业价值

> 调研日期：2026-06-02（附录 1/2 于 2026-06-03 追加）
> 方法：4 个独立 sub-agent 并行调研 4 个有重叠的维度（使用广度 / 市场价值 / 粘性 / 生态商业），主 agent 交叉验证 + 撰写。所有数字附 URL，并按【确凿】/【第三方估算】/【传闻待核】三级标注可信度。
> 附录：在主调研基础上追加两次专项深挖——**附录 1：Duolingo 估值逻辑对照**、**附录 2：AnKing/AnkiHub 定价与营收拆解**。

---

## 核心结论（先读这一段）

**Anki 是间隔重复（SRS）赛道事实上的"基础设施"，渗透率与粘性都属极端档位，但本体几乎零商业化——价值没有被本体捕获，而是外溢给了围绕它做内容/社区的第三方（AnkiHub/AnKing）。2026 年 2 月本体移交给 AnkiHub，正是这一结构性矛盾走到极限的标志性事件。**

四个面的一句话判断：

1. **使用广度**：累计下载量 ~千万级（AnkiDroid 10M+，桌面同量级），活跃用户约 200 万级；最深的垂直是**美国医学生——2024 年 86.2% 用过、66.5% 每日使用**，9 年内从 31%(2015) 翻了近 3 倍。
2. **市场价值**：本体年营收量级仅数百万美元（一人支配，靠 iOS app $24.99 买断），却处在一个能撑起 Quizlet（$1B 估值 / $139M ARR）、Duolingo（$5.19B 市值）的赛道里——**市场地位与商业捕获严重背离**。
3. **用户粘性**："**幸存者偏差型超强粘性**"——高学习曲线 + 老旧 UI 在前端筛掉大量新人，但翻过门槛的用户被三重护城河锁死（算法真实收益 + 多年复习历史无法迁移 + 习惯/沉没成本），千日级 streak 是社区常态。
4. **生态商业价值**：**唯一被验证跑通规模化的打法是 AnkiHub/AnKing**——靠"占住美国医学生 USMLE 备考、把免费内容做成行业标准"赚钱，护城河是社区与标准 deck 的网络效应，**不是技术**。卖工具（add-on / AI 生卡）几乎不成立。

---

## 维度一：使用广度（Usage Breadth）

### 1.1 用户规模

最可信的一手数字来自 **Anki 作者 Damien Elmes（dae）本人**在官方论坛的回答：

> "AnkiDroid has had 10M+ over the course of its life; the desktop version is in the same ballpark."
> —— [Anki Forums: Anki downloads statistics](https://forums.ankiweb.net/t/anki-downloads-statistics/28788)（一手，**确凿**）

即 AnkiDroid 累计下载 10M+，桌面版「同量级」。注意这是**生命周期累计下载**，不是活跃用户。

- **AnkiDroid**：Google Play **4.7 星 / 162K reviews**，第三方口径 10M+ installs（[Google Play](https://play.google.com/store/apps/details?id=com.ichi2.anki)，与 dae 说法一致）。
- **AnkiMobile（iOS，唯一收入来源）**：Sensor Tower 估算美区约 **30k 下载/月、~$700k 收入/月**，售价 **$24.99 一次性买断**，长期位列美区付费 iOS app 前十（[Sensor Tower](https://app.sensortower.com/overview/373493387?country=US)，**第三方估算**）。
- **活跃用户**：约 **200 万级**（growjo 等数据库估算，[growjo Anki](https://growjo.com/company/Anki)，**第三方估算**）。
- **AnkiWeb 注册用户总数**：官方**从不公开**，多轮搜索无结果。任何"确切数字"几乎必为传闻。
- **FSRS 算法校准样本**（一个有趣的活跃度下界锚点）：默认参数基于约 **727 million reviews / ~10,000 用户**（[fsrs-benchmark](https://github.com/ankitects/fsrs-benchmark)）——说明至少上万名用户活跃到愿意上传复习数据。

### 1.2 核心人群

**医学生是渗透最深的垂直，且有学术文献支撑（多源印证，可信度高）：**

> "86.2% of surveyed students reported some Anki use and 66.5% used it daily."（2024 study）
> "31% of students... reported using Anki as a study resource."（2015 study）
> —— [Wikipedia: Anki](https://en.wikipedia.org/wiki/Anki_(software))（已由主 agent 直接 WebFetch 确认，参考 [45]/[43]）

单校实证（2021 调查，[PMC10176558](https://pmc.ncbi.nlm.nih.gov/articles/PMC10176558/)）独立印证：

> "139 (84%) reporting using Anki for at least one semester" / "92 (66%) completed their reviews... on a daily basis"

→ 全国口径 86.2%/66.5% 与单校 84%/66% **几乎完全吻合，两份独立来源互证**，渗透率 9 年内大幅上升。

医学生社区外溢到国际：专门讨论医学院 Anki 的论坛**注册活跃用户 109,000 > 全美在校医学生 89,000**（[Wikipedia](https://en.wikipedia.org/wiki/Anki_(software)) 引用）。

**第二大人群是语言学习者**（日语 kanji/词汇、Refold、Core 10k 等），人群确凿存在但无类似医学生的量化调查，**规模仅定性**。编程/法学院/考研等为长尾，无硬数据。

### 1.3 地理与平台分布

**本维度最薄弱处**。无官方国别/平台拆分。碎片信息：欧美为主力付费市场（Sensor Tower），医学生口径以美国 USMLE 体系为中心。平台上多数用户**跨平台使用**（桌面/平板建卡 + 移动碎片复习），iOS 是变现端而非用户量最大端。

### 1.4 增长趋势

证据偏定性，但方向一致指向**稳定增长，无下滑信号**：医学生渗透率纵向 31%→86.2%；产品持续投入（2025 云同步 + 移动端重做）；付费生态扩张（AnKing 75 万次更新）；行业大盘顺风；r/Anki **194k members** 活跃社区。Google Trends 精确曲线本轮未抓到。

---

## 维度二：市场价值（Market Value）

### 2.1 Anki 自身：个人项目，不是公司

Anki 由 Damien Elmes 于 ~2006 年创建（最初为自学日语），桌面版 AGPL v3+ 开源。**桌面 + AnkiDroid + AnkiWeb 全免费，AnkiMobile（iOS）$24.99 买断是整个生态唯一收入来源。**

> "The iOS app is the sole source of income for Damien, who develops, hosts and supports the entire Anki ecosystem for free."
> —— [Hacker News id=7540530](https://news.ycombinator.com/item?id=7540530)（开发者本人，**确凿**）

**收入量级**：Sensor Tower 估算美区 ~$700k/月（年化 ~$8.4M 美区表面值）。⚠️ **可信度中**：算法推算非财报，且同一来源给出的"英国 $900k、西班牙 $600k"量级不自洽（英国不可能超美国），明显是二手转引误读。**报告只采"美区约 $700k/月"并标为估算**；更稳妥的表述是"年营收量级数百万至千万美元、由一人/极小团队支配"。

### 2.2 赛道天花板：竞品对标

| 竞品 | 路线 | 营收 / 估值 / 用户 | 可信度 |
|---|---|---|---|
| **Quizlet** | 闭源 freemium | 估值 **$1B**；2025 ARR **$139M**（2024 $80M）；50–60M MAU；累计融资 $62M | 中高（[GetLatka](https://getlatka.com/companies/quizlet)） |
| **Duolingo** | 上市公司 | 2025 营收 **$1.03B**；市值 **~$5.19B**（2026-06）；Q3'25 单季 $271.7M（+41%） | 高（[SEC 8-K](https://www.sec.gov/Archives/edgar/data/0001562088/000162828025049514/q3fy25duolingo9-30x25share.htm) / [companiesmarketcap](https://companiesmarketcap.com/duolingo/marketcap/)） |
| **Memrise** | 闭源 freemium | 2024 营收 ~**$13.3M（连续第三年下滑）**；7200 万注册；累计融资 $25M | 中（[Business of Apps](https://www.businessofapps.com/data/memrise-statistics/)） |
| **RemNote** | 闭源 freemium | Seed **$3.5M（2021）无后续**；100 万+学生；营收未披露 | 中（[Crunchbase](https://www.crunchbase.com/organization/remnote)） |
| **SuperMemo World** | 算法鼻祖 | 年营收 ~$2.2M / 22 人 | 中（Crunchbase/Growjo） |
| **Anki（本体）** | 开源 + 第三方生态 | ~200 万活跃用户；估算年营收 **< $5M**（主要靠 iOS 买断）；**零外部投资人** | 估算 |

### 2.3 市场规模（口径混乱，可信度低）

各家市场报告对"闪卡 app 市场"给出 **$0.5B–2.5B / CAGR 9–15%** 的区间（[WiseGuy](https://www.wiseguyreports.com/reports/flashcard-app-market)、[Business Research Insights](https://www.businessresearchinsights.com/market-reports/flashcard-app-market-124828)）。这些是付费报告引流页、口径不统一、有机器生成嫌疑，**只能作区间参考**。

### 2.4 市场价值悖论

一个被 ~70% 美国医学生当每日刚需、全球千万级下载、生态繁荣的工具，本体商业化只有"免费开源 + 一个 $24.99 的 iOS app"，由**一个人维护了 19 年**。价值被捕获的比例极低——但这是 Damien 的**主动设计选择**（拒绝 VC、避免 enshittification），而非市场不认可。价值确实存在，只是被外溢给了第三方（AnkiHub/AnKing），见维度四。

---

## 维度三：用户粘性（User Stickiness）

### 3.1 粘性证据：多年 streak 是社区常态

> "I have been using Anki for **more than 8 years almost every day (have a streak of several thousand days now)** for 15-40 minutes each day."
> —— [r/Anki](https://www.reddit.com/r/Anki/comments/pmovkn/longtime_anki_and_diminishing_returns_or_the)

> "I lost my **1480 day Anki streak**... In April of last year I lost my **4 year long Anki streak for Japanese**."
> —— [r/languagelearning](https://www.reddit.com/r/languagelearning/comments/1r62i29/i_lost_my_1480_day_anki_streak_and_it_was_the)

社区里"1000 days streak"、"1168 days streak"、"6 years and 22 days" 等帖反复出现；**千日级 streak 的丢失会被当作值得发帖哀悼的"事件"**——本身就是粘性强度的反向指标。医学生每日投入 1–2 小时是常态。r/Anki **194k members**，高活跃（[GummySearch](https://gummysearch.com/r/Anki/)）。

### 3.2 粘性来源：三重护城河

- **(A) 算法锁定（FSRS）**：2023.11 起默认算法从 SM-2 换成 FSRS。在 500M+ 复习记录基准上，**达到同等记忆保持率所需复习量比 SM-2 少 20–30%**，对 99.5% 用户回忆预测更准（[Anki FAQ](https://faqs.ankiweb.net/what-spaced-repetition-algorithm)、[srs-benchmark](https://github.com/open-spaced-repetition/srs-benchmark)）。切换到别的工具 = 回忆效率立刻下降。
- **(B) 数据/历史沉淀（最硬的护城河）**：FSRS 精度来自**你自己积累几年的复习历史**，历史越长拟合越准。换工具 = 丢掉个性化模型。医学生常用全套 AnKing deck（**30,000+ 卡**）+ 自建，体量 + 多年评分历史构成极高退出成本。
- **(C) 习惯/沉没成本**：

> "Although a 1000-day streak sounds like a lack of freedom, I do believe the opposite is true. Religiously keeping up with Anki reviews has significantly reduced my workload these last few years."
> —— [r/Anki 1000天帖](https://www.reddit.com/r/Anki/comments/1rfis6v/1000_days_streak_here_is_my_experience)

### 3.3 网络效应与生态

- **Add-on 市场**：AnkiWeb 列有 **1,600+ add-ons**（AnkiConnect、Image Occlusion、Review Heatmap 等）。但⚠️**关键反差**——一位 100+ add-on 作者指出：

> "Even the most popular Add-ons only reach **less than 1% of all Anki users**... Anki for desktop and AnkiDroid have at least 4 to 10 million users... the leaderboard of popular add-ons currently has only about **1700 active users**."
> —— [Anki Forums](https://forums.ankiweb.net/t/idea-for-new-anki-addon-platform/68264?page=2)

→ **深度定制是少数硬核用户的护城河，不是大众粘性来源**。这条直接连到维度四（卖工具不成立）。

- **共享 deck 网络效应**：AnKing Step Deck 成北美医学生事实标准，新人直接装 → 越多人用越是标准 → 进一步绑定平台。

### 3.4 粘性的反面（真实存在的风险）

- **学习曲线陡峭 = 头号流失原因**：流失主要发生在头一两周。

> "People download Anki... get overwhelmed, and quit before the system ever starts working... because the system asks too much of them up front."
> —— [RemNote blog](https://www.remnote.com/blog/best-anki-alternatives)

- **UI 老旧**：社区直言"Anki's UI/UX is not anywhere near the quality of a 'Silicon Valley app'"，新人求"像 ChatGPT app 那样简洁现代"。
- **老用户后期"戒断"**：复习堆积 + 边际收益递减，1480 天用户断签后"I just felt free"，称自己曾"addicted to it"。**这种粘性既是优势也是用户自己意识到的负担。**
- **转投替代品**：方向主要是 RemNote（笔记+卡片一体）、Quizlet（上手快、现成卡）；也有从 RemNote 回流 Anki 的反向案例。

---

## 维度四：围绕 Anki 做产品的商业价值（Ecosystem & Commercial Value）

### 4.1 唯一跑通规模化的玩家：AnkiHub / AnKing（同一拨人）

**最关键的事实：AnkiHub 与 AnKing 是同一拨人。** AnkiHub 由 Nick Flint（即 The AnKing）和 Andrew Sanchez 于 **2022 年**创立（[CB Insights: AnKing](https://www.cbinsights.com/company/anking)）。

- **AnkiHub**：核心订阅 **$5/月**（deck 免费，协作/同步功能需订阅；提供奖学金）。**已盈利、无外部投资人**（[AnkiHub FAQ](https://www.ankihub.net/faq)、[byteiota](https://byteiota.com/anki-transferred-to-ankihub-open-source-at-risk/)）。

> "Since Anki and AnkiHub are profitable, there's no pressure to squeeze users for revenue... the existing $5/month model is already profitable."

- **AnKing**：起家于**免费 YouTube 教程 + 免费 Step Deck**（USMLE 行业标准，**30,000+ 卡、100,000+ 医学生、300K+ 下载、75 万次社区更新**），上层叠加多条付费线：Anki Mastery Course、VIP Membership、1-on-1 Tutoring、Pre-med Course（[theanking.com](https://www.theanking.com/)）。具体标价未公开披露。
- **商业模式精髓**：免费内容做获客 + "行业标准"地位 → 付费课程/会员/平台变现。**护城河是社区地位 + 标准 deck 的网络效应，不是技术。** 关键在锁定"医学生"这个高付费意愿 + 高焦虑 + 标准化考试（USMLE）的垂直市场。

### 4.2 历史性事件：本体被生态最大玩家"收编"（2026-02）

> "In 2026, Damien announced he would be gradually transitioning business operations and open source stewardship to AnkiHub."
> —— [Wikipedia](https://en.wikipedia.org/wiki/Anki_(software))（参考 [39]，已 WebFetch 确认）

移交理由：单人维护 19 年 burnout 不可持续；AnkiHub 承诺核心永久开源、不拿 VC、"no enshittification"、定价不变。**但隐含利益冲突**（社区担忧）：

> "AnkiHub already sells paid add-ons and premium tiers, creating a direct conflict of interest: the company makes more money if the free version gets worse."
> —— [byteiota](https://byteiota.com/anki-transferred-to-ankihub-open-source-at-risk/)

缓释因素：无 VC = 无指数增长压力，$5/月已盈利。

### 4.3 卖工具几乎不成立：add-on 变现天花板

**Glutanimate**（Image Occlusion 等 60+ add-on 作者，**百万级总下载**）靠 Patreon/Ko-Fi 打赏维生：**3,991 total members，仅 179 paid members**（付费转化 ~4.5%）（[Glutanimate Patreon](https://www.patreon.com/glutanimate/about)）。

> "Juggling all of these projects while also being a medical student and funding my studies by myself has been an incredibly challenging experience."

→ 百万下载量的核心工具作者只有 179 个付费支持者——**铁证：开源免费本体对"卖工具"的商业化压制极强。能赚钱的不是工具，是内容 + 社区 + 垂直市场。**

### 4.4 AI 生卡赛道：护城河近零

anki-decks.com（$60–144/年）、AnkiAI、Jungle AI、Ankify、StudyCards AI 等一堆 freemium 产品，均未披露营收，且**两头被挤**：上有 ChatGPT/Claude 直接生成，下有免费开源 add-on（用户自带 API key 在 Anki 里直接调 LLM）。技术壁垒近乎为零。

⚠️ **混淆陷阱**：**AnkiApp / AlgoApp**（Admium Corp.，闭源订阅制）与官方 Anki **毫无关系**——是付费生态里冒名的"李鬼"。

### 4.5 卖 deck：合法但有社区伦理摩擦

Damien Elmes 明确表态**允许卖 deck**，但开源社区对"把免费共享内容收费"有道德摩擦（[Anki Forums](https://forums.ankiweb.net/t/is-there-a-way-to-sell-my-decks-for-a-fee/17315)、[Tower of Babelfish](https://www.towerofbabelfish.com/cms/a-quick-note-on-anki-decks-and-the-tricky-issue-of-money/)）。

---

## 交叉验证：矛盾点与可信度核对

工作流故意让 4 个维度重叠，以下是交叉发现：

| 交叉点 | 多源情况 | 结论 |
|---|---|---|
| **医学生 86.2%/66.5% daily** | 维度 1/2/3/4 全部引到 + Wikipedia 一手确认 + PMC 单校 84%/66% 独立印证 | **高可信，采用** |
| **AnkiMobile ~$700k/月** | 维度 1、2 都引 Sensor Tower；维度 2 指出英国/西班牙数字自相矛盾 | 仅采美区一条，**标为估算** |
| **AnkiHub 定价** | 维度 2/3/4 一致 **$5/月**；维度 1 另见 $6/$10/$450 终身 tier | 主线用 $5/月（官方 FAQ），tier 为细分项 |
| **AnkiHub = AnKing 同一拨人** | 维度 4 单独挖到（CB Insights） | **关键事实**，其他维度未触及，单源但权威 |
| **AnKing 30K 卡 / 100K 学生 / 300K 下载** | 维度 1/3/4 一致 + Wikipedia 确认 300K | **高可信** |
| **add-on 触及率 <1% / 179 付费** | 维度 3（<1% 触及）+ 维度 4（179 付费）互相印证 | **高可信**，构成"卖工具不成立"核心论据 |
| **AnkiHub 员工数** | CB Insights "2–10" vs byteiota "35" | **冲突待核**，谨慎引用 |
| **AnkiHub 实际订阅数/月营收** | 全部维度均**无官方数据** | 仅能量级推断（$5 × 数万医学生 → 年营收数百万级），**非事实** |

**最薄弱、需谨慎的三块**：(1) AnkiWeb 注册总用户数（官方铁口不公开）；(2) 精确地理/平台分布；(3) AnkiHub/AnKing 真实营收。这三项任何"确切数字"几乎必为推算或传闻。

---

## 结论与建议：围绕 Anki 做产品到底值不值得？

### 商业判断

1. **本体不赚钱是设计选择，不是市场不认可。** Anki 站在一个能撑起 $1B（Quizlet）、$5B（Duolingo）的赛道里，渗透率与粘性都是顶级，但创始人主动选择了开源 + 单一买断、拒绝 VC。**价值真实存在，只是被外溢给了第三方。**

2. **唯一被验证的赚钱路径 = 垂直内容 + 社区标准，不是工具。** AnkiHub/AnKing 盈利到能反向接管本体，靠的是"占住美国医学生 USMLE 这个高付费意愿垂直 + 把免费内容做成行业标准 + 协作 deck 网络效应"。对照之下，Glutanimate 百万下载只有 179 付费支持者——**纯工具/add-on 在开源免费本体下几乎无法商业化。**

3. **AI 生卡是红海陷阱。** 护城河近零，上有大模型官方能力、下有免费开源 add-on 双面夹击。除非绑定具体垂直场景（如医学/法考的高质量结构化内容），否则难以建立壁垒。

4. **格局已变：最大玩家拿到了平台控制权。** 2026.2 移交后，AnkiHub 既是最大商业玩家又是本体维护者。对其他第三方而言，这意味着平台风险显著上升（利益冲突、潜在收编）。

### 对"围绕 Anki 创业"的具体启示

- ✅ **可做**：锁定一个高付费意愿垂直人群（医学/法考/CFA/语言考证），做**高质量结构化内容 + 社区 + 持续更新**，把自己做成该垂直的"事实标准 deck"——这是 AnKing 验证过的唯一规模化路径。
- ⚠️ **慎做**：纯工具型 add-on / 通用 AI 生卡 / 又一个闪卡 app——开源免费本体 + 大模型会持续压制定价空间。
- 🚫 **高风险**：与 AnkiHub 直接竞争平台/协作层，或押注于"Anki 官方不会自己做"的功能。

### 一句话

> **Anki 的商业价值不在"工具"本身，而在它创造的"被锁定的高价值垂直人群"——谁能为某个这样的人群提供持续更新的权威内容并把它做成标准，谁就能赚到 Anki 没去捕获的那部分价值。这正是 AnKing 做到、而无数 add-on 作者和 AI 生卡创业者没做到的事。**

---

*报告基于 2026-06-02 的公开信息。营收/估值类数字多为第三方估算，引用时请回溯原始 URL 核实。AnkiHub 接管 Anki 本体处于早期阶段，生态格局仍在演变。*

---

# 附录 1：Duolingo 估值逻辑对照——为什么同赛道两种物种

> 追加于 2026-06-03。回答"多邻国和 Anki 不一样在哪、为什么估值这么高"。数据为财报口径（经 StockTitan/财经媒体转引，SEC 直链抓取受限）；市值/倍数为第三方 2026-05-07 口径。

## 一句话

> **Anki 卖的是"效果"，Duolingo 卖的是"持续回来"。** 同样是超强粘性，在 Duolingo 变成可估值的订阅复利现金流，在 Anki 只是"用户很忠诚但不掏钱"。资本市场给的不是"语言学习"的估值，是"高增长 + 高毛利 + 强留存的消费订阅机器"的估值。

## 重要修正：Duolingo 估值已从"梦想期"大幅压缩

它**曾经**估值极高，但 2025 Q4 财报后**单日暴跌 ~14%**（尽管营收创纪录），因为 DAU 增速衰减曲线被市场看穿：

| 季度 | DAU | YoY 增速 |
|---|---|---|
| Q4 2023 | 26.9M | **+65%**（峰值） |
| Q3 2024 | 37.2M | +54% |
| Q3 2025 | 50.5M | +36% |
| Q4 2025 | 52.7M | +30% |
| Q1 2026 | 56.5M | **+21%** |

管理层亲口承认 **"top-of-funnel growth has been about flat"**（[StockTitan 8-K Q1 2026](https://www.stocktitan.net/sec-filings/DUOL/8-k-duolingo-inc-reports-material-event-6974ab47316e.html)、[TIKR: stock drop 14%](https://www.tikr.com/blog/duolingo-just-beat-earnings-so-why-did-the-stock-drop-14)）。当前 **P/S 仅 4.82x、forward P/E 43x**（trailing P/E 13x 被一次性税收益扭曲，失真）。所以准确说法是："为什么曾经那么高、现在被压到接近 IPO 水平"。

## 高估值的数字支撑（叠乘逻辑）

1. **高增长**：营收仍 +30%+（FY2025 破 $1.1B）。
2. **高毛利**：**73.0%**（Q1 2026）；⚠️ 近期被 AI/hosting 成本小幅拖累。
3. **强现金生成**：**FCF margin 50.6%**（Q1 2026 FCF $147.8M），Adj. EBITDA margin 28.6%，净现金 $1B+。
4. **复利订阅**：**12.5M 付费用户（+21%）**，占 MAU **~9.1%**，**订阅占收入 86%**。
5. **留存被产品化**：**DAU/MAU = 41.1%**（创新高），1000 万+ 用户 streak 超 1 年。
6. **多引擎**：订阅 + Duolingo English Test（切托福/雅思高毛利 B2B）+ 广告。
7. **AI 叙事**：Duolingo Max（GPT-4，月付 $29.99）+ 内容产能 2 年提升 ~10x。
- **Bear case**：漏斗停滞 + 2026 定为 "investment year"（主动牺牲利润换增长）+ 通用 LLM 可能直接替代语言学习需求。
- 来源：[TopTier Strategy 估值拆解](https://toptierstrategy.com/blog/duolingo-valuation-2026-complete-breakdown)、[companiesmarketcap](https://companiesmarketcap.com/duolingo/marketcap/)、[Seeking Alpha bull](https://seekingalpha.com/article/4876748-duolingo-this-high-quality-business-remains-deeply-misunderstood-by-the-market)、[Investing.com bear/bull](https://www.investing.com/analysis/duolingos-ai-push-the-bear-and-bull-case-for-the-stock-price-200661860)

## 与 Anki 的本质区别

| | **Anki** | **Duolingo** |
|---|---|---|
| 物种 | 开源工具 / 基础设施 | 上市消费订阅资产 |
| 用户 | 高动机硬核（医学生） | 大众低动机（"想学坚持不了"） |
| 设计目标 | 记忆**效率**（FSRS 省 20–30% 复习） | **留存被产品化**（streak/energy/排行榜） |
| 变现 | 一次性 $24.99，大多免费 | 订阅复利（86% 收入）+ DET + 广告 |
| 粘性性质 | 用户**自驱**的 SRS，无游戏化锁定 | 把 churn 主动**工程化**降下来 |
| 估值 | 无可估值现金流 | $5B+（DAU 资产 × 高毛利 × 复购 × 增长） |

三个最关键差异：(1) **留存来源**——Anki 是用户自己撞出来的（效果+数据沉淀），Duolingo 把留存当产品设计；(2) **现金流结构**——用 10 年的 Anki 医学生一分钱不多付，用 3 年的 Duolingo 用户按月持续付费，同样忠诚一个产生复利一个不产生，这是 $5B vs $0 估值的根因；(3) **增长杠杆**——Anki 靠口碑+社区标准无营销引擎，Duolingo 有 Duo 猫头鹰+TikTok 病毒营销+A/B 测试增长机器。

---

# 附录 2：AnKing / AnkiHub 定价矩阵与营收量级

> 追加于 2026-06-03。回答"AnKing 靠垂直内容赚了多少、产品模式如何"。**定价基本全查实；营收/订阅人数官方零披露，只能给带假设的区间估算。**

## 赚了多少：估算 $3–6M/年（推算，非事实）

前提：AnKing/AnkiHub 是私人公司、零 VC、从不披露财报。CB Insights / Growjo / ZoomInfo 全部查无有效营收数据。下面是基于 [付费基数 × 已查实价格] 的推算。盘子：美国在校+备考医学生约 80–100K，有效 ARPU ≈ $6/月（$72/年）。

| 情景 | 付费活跃订阅 | AnkiHub 订阅年收入 |
|---|---|---|
| 保守 | 20,000 | ~$1.4M |
| 中性 | 40,000 | ~$2.9M |
| 乐观 | 70,000 | ~$5.0M |

加课程/VIP/tutoring 长尾，**全公司总营收中性约 $3–6M/年**。支撑量级的**确凿事实**：已盈利、自举无外部投资人、团队十几到几十人、**2025-01 McGraw Hill 官宣合作**（把 Boards & Beyond / First Aid 深链进 Step Deck）、2026-02 接管 Anki 本体治理。没有证据支持 8 位数营收。

> 参照：这个量级与 Anki 本体 AnkiMobile 收入（~$700k/月美区估算）是同一数量级——印证"价值外溢给第三方，且第三方赚的和本体差不多"。

## 产品模式：免费内容做行业标准 → 实时更新订阅变现

**① 漏斗顶端（免费获客 + 锁定行业标准）**：The AnKing YouTube（~61.5K 订阅）+ 完全免费的 Step Deck（300K+ 下载，30K+ 卡，100K+ 医学生）→ 成 USMLE 备考事实标准。

**② 中段变现（关键转化点）**：deck 免费，但"持续协作更新的 deck"要订 AnkiHub。

| AnkiHub 档位 | 价格 | 含什么 |
|---|---|---|
| Free | $0 | 入门 deck |
| **Core** | **$6/mo**（年付 $66） | 全部 deck 含 Step Deck + 实时协作更新 |
| Premium | $10/mo | + AI 功能（Smart Search、Chatbot） |
| Lifetime | $450 | 一次性买断 |

> 旧定价（$5/mo、$55/yr、$240 lifetime）仍在部分页面残留——是新旧两套并存，AnkiHub 已涨价。Step Deck / MCAT Deck 无独立订阅，绑在 AnkiHub Core 上。这是**收入主力**（唯一经常性订阅收入）。
> 来源：[ankihub.net](https://www.ankihub.net/)、[/step-deck](https://www.ankihub.net/step-deck)、[/faq](https://www.ankihub.net/faq)

**③ 高端变现（高毛利长尾）**：
- **Anki Mastery Course**：**$119** 一次性（8 节课 + Palace Butler 一键装 50+ add-on）（[courses.theanking.com](https://courses.theanking.com/mastery-course)）
- **VIP Membership**：4 档 Bronze $5 / Silver $10 / Gold $15 / Platinum $20 每月（年付 -15%），按答疑支持等级分层（[theanking.com/vip](https://www.theanking.com/vip)）
- **Med School 录取课**：$100
- **1-on-1 Tutoring**：确认存在，单价 JS 动态加载未抓到

## 护城河：数据网络效应，不是技术

1. **协作 deck 的数据网络效应**：海量医学生提交修订 → maintainer 审核合并 → deck 越用越准越新 → 单用户离开零议价权。
2. **切换成本**：学生把整个 USMLE 备考建在 Step Deck tag 体系 + 实时更新上，换 deck = 重建学习系统。
3. **机构背书**：McGraw Hill 深链。
4. **治理终局**：2026-02 接管 Anki 本体 = 从"最大内容方"升级为"平台治理者"，护城河从内容层下沉到平台层。

## 与三条主线的呼应

- **vs Glutanimate（卖工具）**：百万下载只有 179 付费 → 卖工具不成立；AnKing 卖的是"垂直内容 + 社区标准"。
- **vs Duolingo（附录 1）**：都跑通"免费获客 + 订阅复利"；不同在 Duolingo 是大众市场自建引擎，AnKing 寄生在 Anki 开源生态、靠垂直内容做网络效应。
- **vs Anki 本体**：AnKing 赚的是 Anki 主动不去捕获的那部分价值——这正是全报告主线"价值外溢"的最终落点。

*附录数据基于 2026-06-03 公开信息。营收为推算，定价以公开页面原文为准（除 tutoring 单价、精确员工数未查实）。*
