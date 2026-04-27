# 日本 AI Agent Ops 工作岗位调研报告

**调研日期：** 2026-03-31
**调研方法：** 4个并行 sub-agent，交叉验证
**信息来源：** TokyoDev、Japan-Dev、Glassdoor、各公司官方求人页面、日本 METI 数据

---

## 核心结论

> **"AI Agent Ops" 作为独立职位在日本基本不存在。** 当前市场还处于「谁来构建 Agent」阶段，远未到「谁来运营 Agent」。入场路径几乎只有一条：以 **LLM Engineer / AI Agent Engineer** 工程师身份进入，在工程角色内嵌入运营职能。

---

## 一、职位名称：日本实际叫什么

"AI Agent Ops" 这个词在日本求人市场几乎找不到。对应的实际职位名称：

| 日本语タイトル | 英語タイトル | 定位 |
|---|---|---|
| AIエージェントエンジニア | AI Agent Engineer | Agent 系统设计+实现 |
| LLMエンジニア | LLM Engineer | LLM 选型/RAG/API 集成 |
| 生成AIエンジニア | Generative AI Engineer | LLM 应用开发，偏产品 |
| MLOpsエンジニア | MLOps Platform Engineer | ML 基础设施/推理/监控 |
| AIアーキテクト | AI / Modernization AI Architect | 全栈架构设计 |

**AgentOps（可观测性/评估/成本优化）** 已被识别为差异化技能，但作为独立职位名称尚未定型。在求职时出现于"Nice to have"一栏而非职位标题。

来源：[aiagent-jp.com](https://www.aiagent-jp.com/blog/ai-agent-engineer-salary.html)、[tokyodev.com](https://www.tokyodev.com/companies/legalon-technologies/jobs/ai-engineer-agent)

---

## 二、核心技能栈

### 必须（几乎所有职位）
- **Python**（绝对标配）
- **LangChain / LangGraph**（Agent 框架）
- **RAG + Vector DB**（Pinecone / Weaviate / ChromaDB / FAISS）
- **Cloud**：AWS / GCP / Azure 至少一个
- **LLM API**（OpenAI / Anthropic Claude / Gemini）

### Agent 特化职位额外要求
- **CrewAI、AutoGen**（多 Agent 协作）
- **MCP（Model Context Protocol）**
- **LangSmith**（观测/评估）
- **Prompt Engineering**（CoT / few-shot / role assignment）

### MLOps 方向额外要求
- Kubernetes（CKA 认证加分）
- KubeFlow / MLFlow
- Terraform / IaC、CI/CD 管道
- 模型监控、推理集群管理

### 与传统 ML 工程师的根本区别

| 维度 | 传统 ML 工程师 | AI Agent / LLM 工程师 |
|---|---|---|
| 核心框架 | PyTorch / TensorFlow / scikit-learn | LangChain / LangGraph / LlamaIndex |
| 基础设施感 | GPU 集群、MLflow | Vector DB、API 编排、非确定性处理 |
| 数学要求 | 线代/微积分必须 | 理解概念即可（fine-tuning 除外） |
| 运营挑战 | 模型漂移、再训练管道 | 非确定性、成本管理、安全、评估设计 |

来源：[zenn.dev AI Agent Skills 2025](https://zenn.dev/taku_sid/articles/20250409_ai_agent_skills)、[a-x.inc LLM Engineer Guide](https://a-x.inc/blog/llm-engineer)

---

## 三、薪资水平

### 正社员年收（日本市场）

| 级别 | 通用 AI 工程师 | AI Agent / LLM 专精 | 生成 AI 工程师（2026） |
|---|---|---|---|
| 入门（0-2年） | ¥450M~600M | ¥400M~550M | ¥700M~1,000M |
| 中级（3-5年） | ¥700M~1,000M | ¥550M~800M | ¥1,200M~2,200M |
| 高级（5年+） | ¥1,200M~2,000M | ¥800M~1,200M | ¥2,500M~4,500M |
| 专家级 | — | ¥1,200M~2,000M+ | ¥5,000M+（CTO 级） |

**AI Agent 特化溢价：比同级通用 AI 工程师高 30~50%**

来源：[aiagent-jp.com](https://www.aiagent-jp.com/blog/ai-agent-engineer-salary.html)、[geekly.co.jp](https://www.geekly.co.jp/column/cat-position/ai_engineer_annual_salary/)、[bunkai-work.jp](https://bunkai-work.jp/%E3%80%902026%E5%B9%B4%E6%9C%80%E6%96%B0%E3%80%91%E7%94%9F%E6%88%90ai%E3%82%A8%E3%83%B3%E3%82%B8%E3%82%A2%E3%81%AE%E5%B9%B4%E5%8F%8E%E7%9B%B8%E5%A0%B4%EF%BD%9C1500%E4%B8%87%E8%B6%85%E3%81%88/)

### 外资 vs 日系差距

| 公司类型 | 年薪相场 | 备注 |
|---|---|---|
| 外资 Big Tech（Google等） | ¥800M~1,500M+（均值 ¥1,918M） | 能力主义，市场基准联动 |
| 外资咨询（McKinsey/BCG） | ¥800M~1,600M | 零年功序列 |
| 日系大手企业 | ¥500M~900M | 年功序列，晋升慢 |
| 国内 AI 初创（独角兽候选） | ¥400M~1,500M + SO | 股票期权弥补基础薪资差 |

**日本 vs 美国差距约 4.5 倍**。Anthropic/OpenAI 美国工程师 TC $300K~550K（约 ¥4,400M~8,000M）。

来源：[miraie-group.jp](https://miraie-group.jp/sees/article/detail/AI_engineer_nenshu)、[comm.relance.jp](https://comm.relance.jp/blog/ai-engineer-career-strategy-20m-jpy/)、[jobsbyculture.com Anthropic Comp](https://jobsbyculture.com/blog/anthropic-compensation-2026)

### 自由职业市场
- 正社员 AI 工程师平均：¥558M
- 自由职业 AI 工程师平均：¥999M~1,020M（月单价 ¥79M~85M）
- MLOps / 生成 AI 专案最高：¥150M+/月

---

## 四、主要招聘企业

### 重点投资 AI Agent 的公司（按投入力度排序）

#### 🔴 Exawizards（エクサウィザーズ）— AI Agent 投入最深
- **类型**：日系上市公司，东京
- **AI Agent 方向**：Sales AI Agent（营业自动化）、HR Tech AI Agent、企业生成 AI 平台「exaBase Studio」
- **公开职位数**：8~10个以上（市场最多）
- **薪资**：¥6.5M~¥13.1M
- **⚠️ 语言**：**全职位要求日语 N1，仅限日本居住者**
- 链接：[tokyodev.com/companies/exawizards](https://www.tokyodev.com/companies/exawizards)

#### 🔴 LegalOn Technologies — 最高薪资，部分英语 OK
- **类型**：日系法律 AI 初创，与 OpenAI 联合开发
- **AI Agent 方向**：自主法务/合同 AI Agent
- **薪资**：¥7.7M~**¥19M**（全市场最高区间）
- **语言**：
  - Senior AI Engineer - Agent：**英语 Business Level，日语不需要**，支持海外应聘
  - Backend AI Agent Engineer：需 JLPT N2
- 链接：[tokyodev.com/companies/legalon-technologies](https://www.tokyodev.com/companies/legalon-technologies/jobs/ai-engineer-agent)
- **注**：高薪职位已 close，关注新开职位

#### 🟡 JAPAN AI（Geniee 子公司）— AI Agent 框架技术前线
- **类型**：2023年创立初创，上市 Geniee 旗下
- **AI Agent 方向**：AI Agent Framework 开发、多 Agent 系统、「JAPAN AI AGENT」无代码平台
- **需求背景**：「AI Agent 领域研究·大规模开发加速，紧急增员」
- 链接：[japan-dev.com/jobs/geniee/geniee-aisenior-backend-engineer-ai-agent-framework](https://japan-dev.com/jobs/geniee/geniee-aisenior-backend-engineer-ai-agent-framework-36fhb2)

#### 🟡 PKSHA Technology（パークシャ）— Agent 产品最完整
- **类型**：日系上市 AI SaaS，与 Microsoft Japan 合作
- **产品**：PKSHA ChatAgent、VoiceAgent、AI Agents Studio（2025年）
- **⚠️ 语言**：全职位基本日语必须，外国人窗口很窄

#### 🟢 Money Forward — 英语友好日系大企
- **类型**：日系上市金融科技
- **AI Agent 方向**：「AI Agent Platform」为核心业务
- **薪资**：¥7M~¥15M
- **语言**：**英语 Fluent/Business 必须，日语 Conversational 为加分项**
- 链接：[japan-dev.com/jobs/money-forward/money-forward-ai-solution-engineer-h8hkgz](https://japan-dev.com/jobs/money-forward/money-forward-ai-solution-engineer-h8hkgz)

#### 🟢 Cookpad — 最高薪资 + 无日语要求
- **类型**：日系上市（料理平台）
- **AI Agent 方向**：Conversational AI（moment by Cookpad）
- **薪资**：¥13M~**¥25M**（市场最高上限）
- **语言**：**日语不需要**
- 链接：[japan-dev.com](https://japan-dev.com/ml-data-science-jobs-in-japan)

#### 其他英语友好选项
| 公司 | 类型 | 特点 |
|---|---|---|
| Mercari（メルカリ） | 日系上市 | 50国员工，英语公司语言 |
| Rakuten（楽天） | 日系大企 | 英语公司语言，GenAI/LLM 开发 |
| AI Robot Association (AIRoA) | 初创 | VLA/机器人×Agent，海外应聘可，最高¥30M |

---

## 五、外国人/英语背景的现实

### 英语可工作的窗口真实存在，但相对狭窄

- 日本 AI 职位中约 **15~25%** 可纯英语工作
- **英语 OK 的类型**：外资日本分部、初创、Money Forward / Mercari / Rakuten 等英语化转型的日系企业
- **日语必须的类型**：Exawizards、PKSHA、大多数传统日企

推荐求职平台：
- [tokyodev.com/jobs/no-japanese-required](https://www.tokyodev.com/jobs/no-japanese-required)
- [hipstarters.com](https://www.hipstarters.com/no-japanese-required-english-only-jobs-in-japans-ai-space-and-it-sectors/)
- [japan-dev.com](https://japan-dev.com/ml-data-science-jobs-in-japan)（Apply from Abroad 筛选）

### 签证情况（2026年更新）
- **主要类型**：技術・人文知識・国際業務ビザ（技人国）
- **2026年新变化**：学历与职务实质对应要求更严（计算机专业→实际做技术工作）
- **东京最低月薪门槛**：¥230,000/月
- **周期**：offer 到抵达约 **6个月**，建议早启动
- 高度専門職ビザ（积分制）：最短 1 年可申请永住

来源：[oysterhr.com Japan Visa 2026](https://www.oysterhr.com/library/japan-work-visa-requirements)、[modernlivingjapan.com 2026 Visa Changes](https://modernlivingjapan.com/en/blog/2026-visa-changes-japan)

### 远程工作现状
- 全远程（Full remote）：约 20~25%
- 部分远程（Partial remote）：约 50~60%（主流）
- 全到岗：约 20%
- 时区说明：JST（UTC+9）对欧美有时差壁垒，对亚洲无问题

---

## 六、日本 AI 人才缺口数字

| 数据来源 | 缺口数字 | 时间节点 |
|---|---|---|
| 日本 METI（经产省） | **IT人才缺口 79万人** | 2030年预测 |
| METI AI 专项 | AI 专职人才缺口 **9万人** | 2025年 |
| METI AI 专项 | AI 人才缺口扩至 **12万人** | 2030年预测 |
| IPA（信息处理推进机构） | **约50%企业**将"AI人才不足"列为 DX 最大障碍 | 2023年白皮书 |
| 全球对比 | 日本 **85% 雇主**难以填补技术岗位（全球最高比例） | 2026年 |

来源：[metaintro.com Japan Tech Jobs Boom 2026](https://www.metaintro.com/blog/japan-tech-jobs-boom-ai-engineering-talent-reshaping-workforce-2026)、[ptsjapan.co.jp IT Talent Shortage](https://www.ptsjapan.co.jp/en/japan-it-talent-shortage-2030_en/)

---

## 七、与中美市场横向对比

| 维度 | 美国 | 中国 | 日本 |
|---|---|---|---|
| AI Agent Ops 独立岗位 | 已出现，有独立职位名 | 有 Prompt 工程师/Agent 运营，数量多 | **极少，基本嵌入工程师职能** |
| 岗位成熟度 | 高 | 中 | 低（仍在"谁来建"阶段） |
| 英语可工作比例 | ~100% | 极低（中文主导） | 约 15~25% |
| 中级 AI 工程师年薪（USD） | $160K~$240K | $54K~$79K | $60K~$100K |
| 远程友好度 | 高 | 中（偏到岗） | 中低（hybrid 主流） |

---

## 八、结论与建议

### 如果目标是「做 AI Agent Ops」：

1. **当前不存在独立岗位**，不要用"Agent Ops"搜索——用 "LLM Engineer"、"AI Agent Engineer"、"MLOps Engineer" 搜索
2. **以工程师身份入场**，在工程角色内承担 Agent 运营/评估/可观测性职能（embedded ops）
3. **1-2 年内这个岗位有望独立出现**——生成 AI 大规模落地后运营成本显现，会催生专职 Agent Ops 岗

### 如果语言是障碍（英语背景）：

**推荐路径**（优先级排序）：
1. LegalOn Technologies（技术最前沿，薪资最高，有英语岗历史）
2. Money Forward（英语友好，AI Agent 战略明确）
3. Cookpad（无日语要求，薪资最高 ¥25M，但产品方向偏 Conversational AI）
4. Mercari / Rakuten（英语环境好，AI 专化度偏低）
5. AI Robot Association（海外应聘可，方向是 VLA/机器人）

### 薪资预期（中级工程师，3-5年经验，日本市场）：
- **日系企业**：¥700M~¥1,200M
- **外资/国际化日企**：¥1,000M~¥1,800M
- **自由职业**：¥80M~¥100M/月（¥960M~¥1,200M/年）

---

*报告生成：2026-03-31 | 调研工具：Tavily Advanced Search | 输出位置：contexts/survey_sessions/*
