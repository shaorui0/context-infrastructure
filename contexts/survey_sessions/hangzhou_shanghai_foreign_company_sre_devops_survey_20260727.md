# 上海/杭州外企 SRE/DevOps 招聘调研

**调研日期**：2026-07-27
**调研目的**：对照瑞哥当前简历（`work-contexts/career/profile/resume.tex`），列出上海/杭州地区**外资企业**（排除阿里/腾讯/字节/网易/美团等中国本土公司）当前招聘 SRE / DevOps / Platform Engineer / Infrastructure Engineer 岗位的公司清单，附招聘 URL。
**方法**：4 个独立调研维度并行搜索（上海云计算/企业软件大厂、杭州外资公司、金融科技/支付类外企、招聘平台交叉验证补漏），互有重叠以发现交叉印证和矛盾点。

## 候选人匹配基准（简历摘要）

Rui Shao，约 4 年专职经验（2022 硕士毕业，此前 Tencent/ByteDance/App Annie/Baidu 实习），当前 DataVisor（反欺诈 SaaS，美国总部）Senior SRE（此前 Intel Cloud SDE）。核心技能：Kubernetes（50 集群，1.24→1.29 升级）、AWS（6 region，600+ 节点）、可观测性（VictoriaMetrics + Grafana + Loki，~1.2M series）、数据平台（ClickHouse、Apache Doris/StarRocks）、Jenkins/Ansible CI-CD、Go/Python、20+ P1/P2 on-call、多活流量切换系统。

---

## 核心结论（先说结论）

1. **上海是主战场，杭州岗位池极薄。** 四个独立调研维度都印证了这一点：SAP、Amazon 官方招聘系统按"Hangzhou"筛选均返回 **0 条**结果；猎聘"杭州外资企业招聘"聚合页（约 40 条）里没有一条 SRE/DevOps/Infra 岗位；多数外资在华工程枢纽（HSBC、DBS、ThoughtWorks、eBay、Ubisoft、EA、Riot）都落在上海/广州/西安/成都，唯独不落杭州。
2. **最强信号：SAP 上海。** 8 个月内多次开出 Senior SRE / Senior DevOps 岗位（虽然当前查到的两条正式岗位已关闭，但说明团队活跃、值得设 job alert 持续追踪），另有一条 2026-07-10 发布的 System Reliability Engineer Intern 岗位仍在开放，JD 技术栈（Docker/K8s/Prometheus/Grafana/Terraform/Go）与简历高度重合。
3. **结构最对口：Airwallex（空中云汇）上海。** 全球总部 + 中国工程团队的结构与 DataVisor 几乎一致（都是海外总部反欺诈/支付类 SaaS，中国团队做基础设施）,当前有 DevOps Engineer 和 SRE 两个在招岗位，技术栈（K8s/AWS/GCP/容器化/分布式监控）匹配度全场最高。
4. **新发现的一个垂直领域：外资游戏工作室（上海）。** Ubisoft、EA 都在上海常年招聘 SRE，这是"云计算大厂"和"金融科技"两个预设分类之外、被交叉验证维度独立发现且被官方招聘页+第三方数据源共同证实的稳定招聘方向。
5. **杭州唯一两条待核实线索**：MicroStrategy（杭州分公司 DevOps 工程师，猎聘页面日期存在矛盾，需确认是否仍在招）、DHL 敦豪（BOSS 直聘标题含"杭州"但因页面渲染问题未能确认地点/岗位性质）。

---

## 一、上海 — 强信号，当前有匹配岗位

### SAP（思爱普，德国）
- 上海研发中心确认（浦东张江 201203）
- **System Reliability Engineer Intern - Shanghai**（发布于 2026-07-10，当前 Active）：https://jobs.sap.com/job/Shanghai-SAP-China-iXp-Intern-System-Reliability-Engineer-Intern-Shanghai-201203/1413714333/ （注：实习岗，非面向 4 年经验候选人，但 JD 要求 Docker/K8s、Prometheus/Grafana、Terraform、Python/Go，说明团队技术栈高度匹配）
- Senior Site Reliability Engineer（已关闭，约 2025-11-18 发布）：https://jobs.sap.com/job/Shanghai-Senior-Site-Reliability-Engineer-201203/1268880801/
- Site Reliability Engineer（已关闭，约 2025-11-19 发布）：https://jobs.sap.com/job/Shanghai-Site-Reliability-Engineer-201203/1268880201/
- Senior DevOps Engineer for Cloud Infrastructure Engineering and Automation（已关闭）：https://jobs.sap.com/job/Shanghai-Senior-DevOps-Engineer-for-Cloud-Infrastructure-Engineering-and-Automation-201203/1175231801/
- **匹配点**：K8s、可观测性、云基础设施自动化经验完全对口
- **建议**：8 个月内密集开出多个 Senior SRE/DevOps 岗，团队活跃，建议在 jobs.sap.com 设置 job alert 持续跟踪

### Airwallex 空中云汇（澳大利亚/香港，支付出海）
- 上海（黄浦区）确认有 Engineering 团队
- DevOps Engineer | Shanghai：https://www.liepin.com/job/1935338459.shtml （⚠️页面同时出现"2022年"与"90天前发布"矛盾字样，需人工核实是否为过期缓存）
- SRE | Shanghai：https://www.liepin.com/job/1940113875.shtml （要求 K8s、AWS/GCP、Docker、分布式系统监控，金融背景/Go 为加分）
- Senior Software Engineer, Infrastructure & Productivity | Shanghai：https://careers.airwallex.com/job/1b9a80ed-c6fa-4e84-a9ca-2bf8d62a7d7b/senior-software-engineer-infrastructure-productivity/ （偏 AI-agent 基础设施，Kafka/K8s，需补 Python/TS）
- Staff Software Engineer, Infrastructure & Productivity | Shanghai：https://careers.airwallex.com/job/ab89a8da-c743-4165-b154-2f1eab958950/staff-software-engineer-infrastructure-productivity/ （8 年经验门槛较高）
- 官方职位列表：https://careers.airwallex.com/jobs?team=Engineering&location=Shanghai
- **匹配点**：与 DataVisor 结构最相似的公司（海外总部支付/风控 SaaS + 中国工程团队），本轮调研结构最对口

### Ubisoft 育碧（法国，游戏）
- Senior Site Reliability Engineer：https://jobs.smartrecruiters.com/Ubisoft2/743999786379414-senior-site-reliability-engineer
- Site Reliability Engineer – AI Platform：https://www.ubisoft.com/en-us/company/careers/search/744000109658600-site-reliability-engineer-ai-platform
- 上海全部职位列表：https://www.ubisoft.com/en-us/company/careers/search?cities=Shanghai
- **匹配点**：SRE title 完全对口，游戏在线服务基础设施与 K8s/监控经验高度相关

### Electronic Arts / EA（美国，游戏）
- 官方职位搜索（按 Shanghai 筛选）：https://jobs.ea.com/en_US/careers/SearchJobs
- Glassdoor 显示上海共 46 个 EA 职位，含 Site Reliability Engineer
- **交叉印证**：Ubisoft + EA 同时在上海招 SRE，说明"外资游戏工作室"是稳定的招聘垂直领域

### AWS / 亚马逊云科技（美国）
- BOSS 直聘聚合页（约 19 个相关职位，需人工逐条核实真伪）：https://www.zhipin.com/zhaopin/b9de88135731b1a11XF_2Ni1FQ~~/
- 官方地区职位入口：https://www.amazon.jobs/en/location/shanghai-china
- **匹配点**：K8s + AWS 多 region + 可观测性经验高度契合，但需人工二次核实新鲜度

### Tesla（美国，汽车/临港 Gigafactory）
- Site Reliability Engineer, Fleet Net：https://www.tesla.com/careers/search/job/site-reliabilityengineerfleetnet-72152
- **匹配点**：SRE title，车队后端服务可用性方向

### Kong Inc.（美国，API 网关基础设施软件）
- Software Engineer (DevOps) | Shanghai：https://cn.linkedin.com/jobs/view/software-engineer-devops-shanghai-at-kong-inc-4119572540
- **匹配点**：DevOps title，基础设施软件公司背景，非"云计算大厂"分类下容易被漏掉的一家

### Roche 罗氏（瑞士，制药，Roche Innovation Center Shanghai）
- AI Platform Engineer：https://careers.roche.com/global/en/job/ROCHGLOBAL202605113541EXTERNALENGLOBAL/AI-platform-engineer
- **匹配点**：Platform Engineer title；提示"外资制药研发中心"也可能是被忽略的方向（目前仅一家样本，证据强度中等）

### PayPal（美国，跨境支付）
- 官方中国地点页确认 Shanghai 办公室：https://careers.pypl.com/locations/china/
- Site Reliability Engineer Intern | Shanghai：https://www.linkedin.com/jobs/view/site-reliabliity-engineer-intern-at-paypal-4197597821 （要求 Python/Bash、AWS/GCP/Azure、IaC、chaos engineering，技术方向高度匹配，**但为实习岗**）

---

## 二、上海 — 有中国团队，但当前查无匹配岗位（建议持续关注）

| 公司 | 总部 | 证据 | 说明 |
|---|---|---|---|
| Microsoft 微软 | 美国 | https://careers.microsoft.com/v2/global/en/locations/shanghai.html | 上海研发中心存在，未确认具体 SRE/DevOps 在招 |
| Oracle 甲骨文 | 美国 | 杨浦创智天地研发中心（非官方来源） | 官方 SRE/DevOps 岗多要求美国身份，需人工核实上海岗位 |
| IBM | 美国 | https://www.liepin.com/city-sh/zpibm/ | 猎聘上海专场，未见 SRE/DevOps 精确匹配 |
| VMware / Broadcom | 美国 | 上海研发中心历史信息（2011 年设立） | 未找到可验证的当前 SRE/DevOps 岗位 |
| Red Hat 红帽 | 美国 | 上海分公司工商注册确认（2007 年） | OpenShift/K8s 核心厂商，岗位未能确认（官网 JS 渲染受限，建议人工核实） |
| Salesforce | 美国 | 上海法律实体确认（浦东世纪大道） | 上海办公室以销售/客户成功为主，无 SRE/DevOps 证据 |
| Dell 戴尔 | 美国 | 上海办公地点确认（长宁路） | 当前 5 条在招岗位均为制造/测试/销售，无匹配 |
| Mastercard | 美国 | 历史上确认有上海 DevOps 团队 | 官方 Shanghai 专属招聘页当前显示 "No results" |
| Adyen | 荷兰 | 官方确认"10 年上海团队" | 团队性质是客户对接（Sales/Implementation），非核心研发；当前岗位均为 Implementation/Technical Support，非 SRE/DevOps |
| Bloomberg 彭博 | 美国 | 官方确认近 300 人在沪京两地 | 当前预筛选链接显示 "No jobs found" |

---

## 三、杭州 — 结论：外资 SRE/DevOps 岗位池极度稀薄

四个调研维度独立印证了这一结论：SAP、Amazon 官方招聘系统按"Hangzhou"筛选均为 **0 条**；Bosch 官方校招城市列表明确不含杭州；猎聘"杭州外资企业招聘网"（约 40 条职位）里全是销售/工艺研发（非 IT）/质控/医药代表，没有一条 SRE/DevOps/Platform/Infra；Michael Page（专做外企猎头）全站 DevOps 岗位仅 1 条且在上海。

### 待人工核实的两条线索

**MicroStrategy / Strategy（美国，杭州分公司）**
- DevOps 开发运维工程师：https://www.liepin.com/job/1944789613.shtml （黄龙万科中心 A 座，20-40k·13薪）
- ⚠️ 抓取到发布日期 2023-06-06，但页面显示"90天前更新"，存在矛盾，很可能是常年挂着的过期岗位，需自行确认是否仍在招
- 匹配点：任职要求含 Ruby/Bash/Python、Linux、Cloud/容器、Jenkins CI/CD，与简历技能栈重合度最高的一条杭州线索

**DHL 敦豪（德国，物流）**
- BOSS 直聘：https://m.zhipin.com/zhaopin/3978266a539829ab03F-3tu0Fw~~ （标题含"杭州"，描述含"服务端技术方案设计"/"架构规划设计"/"性能优化"，疑似技术岗）
- ⚠️ 因页面 JS 渲染问题未能确认地点是否确实是杭州（BOSS 直聘常把多城市岗位聚合展示），需人工打开核实
- 官方渠道仅明确的杭州岗位是"快递员-国际快件（萧山）"，非技术岗

### 结构对口但地点在上海、非杭州的公司（供扩大搜索半径参考）

- **Airwallex**（详见第一节）——与候选人当前雇主结构最像的公司，只是团队在上海
- **ACI Worldwide**（支付/反欺诈软件，美国）——确认在陆家嘴金融广场设有技术运营团队：https://www.aciworldwide.com/about-aci/careers/technology-operations ，未拿到具体岗位链接，但方向高度相关，建议直接查该公司官网 China 岗位

---

## 四、交叉验证与矛盾点

1. **Hangzhou 稀缺性 —— 强交叉印证**：4 个独立维度（云计算大厂官方系统查询、猎聘聚合页人工浏览、猎头网站扫描、泛化关键词搜索）互相独立地得出同一结论，没有一个维度找到确凿反例。可信度高。
2. **SAP 信号 —— 交叉印证**：「上海云计算/企业软件」维度和「平台交叉验证」维度都独立发现 SAP 上海团队活跃招聘 SRE/DevOps，且发布时间跨度覆盖 8 个月，说明不是偶然的单条岗位，而是持续性需求。
3. **Airwallex —— 双重发现**：「金融科技」维度和「杭州」维度都独立提到 Airwallex（后者是作为"结构最对口但不在杭州"的反例提出），两条线索互相佐证了该公司团队和岗位的真实性。
4. **游戏行业新垂直 —— 需要谨慎的边界案例**：调研中还发现 Riot Games 上海工作室常年招聘，但 Riot Games 自 2015 年起已被腾讯 100% 全资收购，股权上已不属于外资，尽管品牌/文化仍是美系，**本报告不将其计入外企清单**，仅作为边界案例提示。
5. **矛盾点：猎聘/BOSS 直聘发布日期不可靠**。至少两条记录（Airwallex DevOps、MicroStrategy）出现"页面日期"与"平台显示的更新时间"矛盾，说明这类平台上的老岗位可能被系统性地"刷新"展示为近期在招，**所有猎聘/BOSS 直聘来源的链接都建议求职前亲自打开确认是否仍开放**。

---

## 五、方法论局限（如实说明）

- 4 个调研 agent 在本次 session 中共享同一个 WebSearch 配额池（200 次/session），中途配额耗尽后被迫改用 WebFetch 直接抓取官网静态 HTML。多数外企官方招聘系统（Workday、SmartRecruiters、Greenhouse、公司自建 SPA）是纯前端 JS 渲染，WebFetch 抓不到执行筛选后的职位列表——**很多"未找到"结论的真实原因是工具链够不到动态内容，不等于岗位确实不存在**。凡标注"未能确认""建议人工核实"的条目，建议用真实浏览器登录对应招聘系统按城市筛选一遍。
- 猎聘/BOSS 直聘对具体公司名有时做脱敏处理（"某知名公司""科技金融公司"），这类结果因无法确认是否为外资已被排除或标注为存疑。
- 完全查无中国大陆证据、已排除的公司（不再赘述细节）：ServiceNow、Workday、Atlassian、Splunk、New Relic、GitLab、Visa、Stripe、Worldpay、FIS、Marqeta、LexisNexis Risk Solutions、Experian、Riskified、Forter、Coupa、Klarna、WorldFirst、Equifax、TransUnion、Feedzai、Sift、Kount、GBG、Trulioo、Nasdaq、ICE、Rapyd、Nium、Thunes、Synchrony Financial、FICO、SAS Institute、NICE Actimize、Finastra、Temenos。
- 对照基准：候选人当前雇主 DataVisor 官方全球招聘（Workable，18 个在招职位）集中在 Mountain View/Toronto/Vancouver/Calgary/Tokyo/Ireland/US，**无任何 Shanghai/Hangzhou 岗位**——中国团队的招聘大概率走内部推荐渠道，未走公开招聘平台，这本身也是一个值得注意的行业现象（外资在华工程团队常见的隐性招聘方式）。

---

## 六、给候选人的实操建议（仅外企范围）

1. **优先级排序**：Airwallex（结构最对口）> SAP（信号最强最活跃）> Ubisoft/EA（游戏 SRE 新赛道，如果对游戏行业开放）> AWS/Kong/Tesla/Roche（值得投递但需人工核实新鲜度）。
2. **如果搜索半径严格限定杭州**：岗位池非常薄，MicroStrategy 和 DHL 两条线索都需要先自行打开链接确认是否仍开放，不要预期能在杭州找到大量外资 SRE/DevOps 机会。
3. **如果能接受上海通勤/搬迁**：搜索空间会明显打开，尤其是 Airwallex、ACI Worldwide 这类与 DataVisor 业务结构相邻的公司。
4. **持续监控入口**（可定期人工刷新）：
   - 猎聘「上海外企招聘网」：https://www.liepin.com/city-sh/zpwaiqi/
   - 猎聘「杭州外企招聘网」：https://www.liepin.com/city-hz/zpwaiqi/
   - 猎聘「上海基础设施 SRE 招聘网」：https://www.liepin.com/city-sh/zpjcsssre5a9j/

---

## 七、补充调研（2026-07-27）：不限外企，就杭州而言的选择性

**调研目的**：上文已证实杭州外企 SRE/DevOps 岗位池极薄，本节评估"放开到中国本土公司"后杭州本身的选择广度。3 个并行维度：杭州头部科技公司（阿里/蚂蚁/网易/海康等）、杭州本地风控/反欺诈同类公司（对齐 DataVisor 业务）、招聘平台整体量级扫描。

### 核心结论

1. **放开到本土公司后，杭州选择性明显变大**——阿里云、蚂蚁集团各自有多个并行团队独立招聘 SRE（容器服务、弹性计算、云平台、网络方向各自成岗），这是外企范围内完全看不到的密度。
2. 但**杭州 SRE/DevOps 这个精确 title 的岗位密度，即便放开本土公司，仍明显薄于上海**——同一关键词在智联招聘上，上海首页返回 10 条不同岗位，北京 6 条，杭州则掺杂大量重复的猎头代招/无关噪音（充电桩运维、光伏运维值班员等），实质软件/云平台方向的岗位是"稀释后的少数"。这与外企维度的结论方向一致：**杭州整体（不分内外资）都不是 SRE/DevOps 岗位密度最高的城市，上海才是**。
3. **匹配度最高的具体岗位**：有赞（Youzan）「SRE运维工程师（基础架构方向）」——原文直接点名 Kubernetes 集群规划/升级/容量管理，与简历经验一一对应。
4. **业务方向最契合的公司**：同盾科技、顶象科技（杭州本地风控/反欺诈 SaaS，与 DataVisor 业务结构几乎一致），但两家当前公开可查的具体 SRE/DevOps 岗位较少，更适合走内推渠道而非海投。
5. **需警惕的噪音**：不少"SRE/DevOps"标题的岗位实际是猎头/外包公司代招（大连弗斯特、四川科航、外企德科、山东华科等），同一岗位在不同关键词搜索下反复出现，说明招聘平台的"职位数"会高估真实雇主数量。

### 杭州头部科技公司（阿里系/网易/海康/有赞等）

| 公司 | 岗位 | URL | 匹配点 | 薪资 |
|---|---|---|---|---|
| 阿里云 | 容器服务 SRE 技术专家（杭州/北京） | https://www.zhipin.com/job_detail/fdafb6a9630fe27e1HB60t65F1JY.html | ACK 容器平台，对口 K8s 50 集群升级+可观测性经验 | 未公开 |
| 阿里云 | 弹性计算灵骏稳定性 SRE 专家 | https://careers.aliyun.com/off-campus/position-detail?positionId=100000523026 | 大规模 AI 算力集群稳定性，对口 20+ P1/P2 on-call 经验 | 未公开 |
| 阿里云 | 云平台 SRE（杭州） | https://careers.aliyun.com/off-campus/position-detail?positionId=2005203005 | 多区域云基础设施运维 | 未公开 |
| 蚂蚁集团 | 基础设施高可用 SRE（西湖区） | https://m.liepin.com/job/1961747789.shtml | 多活流量切换、20+ P1/P2 incident response 直接对口 | 30-50k·15薪 |
| 蚂蚁集团 | 基础设施数据智能 SRE | 同上链接 | ClickHouse/Doris 宽表工程+可观测性强相关 | 30-60k·16薪 |
| 蚂蚁集团 | SRE 专家-国内【平台工程】（3-5年） | https://www.zhipin.com/job_detail/c914f97af6675e621HF63Ny4EFpS.html | 全站基础架构，对口 50 集群+可观测性平台经验 | 未公开 |
| 网易 | 高级运维研发工程师（SRE，滨江） | https://m.liepin.com/a/76438521.shtml | SRE 岗名直接对口 | 20-40k·16薪 |
| 网易 | 高级/资深运维开发、云计算运维（官方专题页） | https://hr.163.com/zc | 云计算运维直接对口 K8s+AWS+可观测性 | 需登录查看 |
| 海康威视/萤石 | 基础设施运维工程师（杭州） | https://talent.hikvision.com/home/socity/position?postId=72D33C5449756A3ECB1C149B410AF853 | Python/Go+Ansible+公私有云，高度吻合 | 未公开 |
| 海康威视/萤石 | 运维工程师（2026-07-14 更新） | https://talent.hikvision.com/home/socity/position?postId=91E98AF1717E4214093BB67EB33B4C34 | 容器化部署（Docker/K8s）+多环境运维 | 未公开 |
| **有赞 Youzan** | **SRE运维工程师（基础架构方向）——本轮匹配度最高** | https://www.zhipin.com/zhaopin/b5b678c4e40f0ac00XR_29q_ | 原文直接点名 K8s 集群规划/部署/运维/容量管理 | 15-30K |
| 有赞 Youzan | 大数据运维工程师 | https://m.zhipin.com/zhaopin/e863fb4729d6fa631nd82t68Fw~~ | ClickHouse/Doris 宽表运维经验相关 | 15-25K·14薪 |
| 每日互动/个推 | 大数据运维工程师（西湖区） | https://m.liepin.com/job/1979721723.shtml | 680亿装机量级数据平台，与数据平台经验相关 | 15-30k·14薪 |
| 群核科技/酷家乐 | 后端开发工程师（DevOps方向） | https://www.zhipin.com/job_detail/f70b5d2bec21900e03x83925EltU.html | DevOps 平台+AI结合运维，对口 CI/CD+Go/Python（⚠️base城市需核实，牛客网另一相似岗位base在成都） | 未公开 |

大华股份：未找到可验证的杭州 SRE/运维开发岗位（建议人工登录 job.dahuatech.com 核实）。

### 杭州本地风控/反欺诈同类公司（业务方向对齐 DataVisor）

| 公司 | 岗位 | URL | 匹配点 |
|---|---|---|---|
| 同盾科技（现"小盾未来"） | 运维工程师 | https://www.zhipin.com/zhaopin/e37193136e575e291XV40ti4/ | Linux/容器/CI-CD/监控告警，与 K8s、Jenkins/Ansible、Prometheus 经验重合（⚠️需人工核实是否仍在招） |
| 同盾科技 | 海外运维工程师 | https://app.mokahr.com/su/x0oZf | 官方 Moka 门户确认杭州坐标，但薪资区间指向校招定级 |
| **恒生电子——本轮验证最扎实、匹配度最高的公司** | 运维开发工程师 | https://www.zhipin.com/zhaopin/63579281c143df9433x73g~~ | 公有云产品自动化部署平台+云产品运维支撑，直接对应 Jenkins/Ansible+云平台运维+on-call 经验；公司内部设"运维服务部"，联合中国信通院发布过《证券行业分布式核心系统SRE运维白皮书》，证明有成体系 SRE 团队 |
| 恒生电子 | 持续追踪入口 | https://m.liepin.com/company/857922 | 职位数39+，搜索快照中曾出现"云原生K8S运维工程师" |
| 玖章算术（NineData，云原生数据库管理） | 云数据库架构师 | https://ninedata.cloud/joinus | 与 ClickHouse/Doris 背景相关，但偏产品架构/售前，非纯 SRE/DevOps |
| 顶象科技（业务安全/风控SaaS，杭州研发分部） | AI平台Java研发工程师 | https://www.dingxiang-inc.com/job/55 | 业务方向（反欺诈SaaS）与 DataVisor 高度契合，非纯运维岗，建议长期关注/内推；官方招聘页（11个在招，6个base杭州）：https://www.dingxiang-inc.com/job |

排除（无杭州团队或业务不匹配）：瑞莱智慧、天冕信息、简知科技（疑似记录有误）、白骑士科技、云徙科技（数字中台非风控）、51信用卡（业务收缩，仅一个合规岗）、挖财（P2P清退后大幅收缩）、氪信科技杭州分部（仅算法岗）。

### 整体量级扫描发现的其他公司

| 公司 | 行业 | 信号 |
|---|---|---|
| 涂鸦智能 (Tuya) | IoT云平台，杭州总部 | BOSS直聘公司页 254 个职位在招，需人工用"运维/SRE"筛选：job.tuya.com |
| 子不语网络科技 | 跨境电商（杭州上市公司） | BOSS直聘 58 个在招职位 |
| 电魂网络 | 手游（杭州上市公司） | 主动招聘中，约9-19条职位 |

### 方法论说明（延续第五节的局限）

同样受限于本 session 共享的 WebSearch 配额耗尽，后半程改用 WebFetch/Tavily。多数猎聘/BOSS直聘详情页 JS 动态渲染，无法 100% 验证时效性，标注"需人工核实"的条目请求职前亲自打开确认。此外确认了一个新噪音模式：**不少标题为"SRE/DevOps"的岗位实际是猎头/外包公司代招**（如山东华科代招阿里云职位、外企德科代招某未披露外企职位），并非目标公司直接发布，检索时容易高估真实雇主数量。

### 结论：外企 vs 不限外企，如何选

- **如果只看杭州**：不限外企能显著打开选择面（阿里系多个并行 SRE 团队、有赞、恒生电子都是扎实信号），比外企范围内几乎为零要好得多。
- **但即便不限外企，杭州的 SRE/DevOps 精确岗位密度仍薄于上海**——这是本轮和上一轮调研共同印证的结论，城市本身的机会基数是硬约束，不因内外资放开而改变排名。
- **最值得先投的三个具体目标**：有赞（技术栈匹配度最高）、蚂蚁集团基础设施 SRE（薪资与规模最大）、恒生电子（业务方向金融科技+验证最扎实）。同盾/顶象作为反欺诈业务对口首选，但建议走内推而非海投，因为公开岗位少。
