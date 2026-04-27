# AI/LLM 行业"学得慢不如不学"—— 深度调研报告

**调研日期**：2026-04-17
**调研方法**：4 维度并行 sub-agent 调研 + 交叉验证
**覆盖范围**：英文圈（HN / X / 个人博客 / paper）+ 中文圈（知乎 / B站 / 独立博客 / 官媒）

---

## TL;DR

"学得慢不如不学"这个说法在**表层**是对的，在**底层**是错的，而多数焦虑的人搞不清自己在哪一层。

- **如果你学的是**：LangChain 0.x 的 API、某个 prompt hack 模板、某个 AutoGPT fork、某个 vendor 的 UI 操作 —— 确实"学了就被淘汰"，这部分说法成立。
- **如果你学的是**：Transformer/attention 原理、eval 方法论、error analysis 流程、检索系统、分布式系统、软件工程基本功、数据直觉、写作与提炼 —— 跨越 3 年、5 年、10 年都不会过时。

**问题不是"要不要学"，是"学哪一层"。** 被淘汰的不是学得慢的人，是把全部精力投在最表层的人。

中文圈还有一个特殊陷阱：焦虑营销产业链（"35 岁 + AI + 百万年薪"漏斗）把"学不过来"的情绪包装成付费课程，让很多人在**学 vs 不学**的伪命题上消耗判断力。这份报告最后一节会拆解这个陷阱。

---

## 一、"学得慢不如不学"的语境 —— 这个观点在哪些情境下为真

这个观点在英文和中文圈都有大量支持者。但拆解后会发现，他们吐槽的对象几乎都是**同一层**：快速变化的具体 framework / 工具 / prompt 技巧，而不是底层知识。

### 1.1 Framework 层的共识：LangChain 现象

Octomind 团队在 HN 上的一篇文章（2024-06）被 discuss 上千次：

> "Most LLM applications require nothing more than string handling, API calls, loops, and maybe a vector DB if you're doing RAG. You don't need several layers of abstraction and a bucketload of dependencies to manage basic string interpolation, HTTP requests, and for/while loops."
>
> "LangChain always looked like an answer in search of a question, a collection of abstractions that don't do much except making a simple thing more complex."

— [Why we no longer use LangChain (HN)](https://news.ycombinator.com/item?id=40739982)

更早的一次讨论（HN 2023-07），高赞评论（minimaxir）：

> "I spent a month working with LangChain and coming to the conclusion that it's just easier to make my own Python package than it is to hack LangChain to fit my needs... The current implementations of the ReAct workflow and prompt engineering are based on InstructGPT (text-davinci-003), and are extremely out of date... Debugging a LangChain error is near impossible, even with verbose=True."

— [Langchain Is Pointless](https://news.ycombinator.com/item?id=36645575)

Roborhythms 的 2026 综述一针见血：

> "Frequent interface changes made LangChain feel unreliable for projects where stability is critical, with early adopters vividly remembering the churn and 'upgrade anxiety'... frequent API changes and breaking releases within the 0.x lifecycle meaning that using LangChain in production requires constant attention to upgrades, migrations, and refactors."

— [LangChain Is Quietly Losing Developers](https://www.roborhythms.com/langchain-losing-developers-2026/)

**这是 framework 层"学了就被淘汰"的真实案例。** 但注意：批评者并不是在否认"学 LLM 编程"本身没价值，他们是在说"学一个会频繁 breaking change 的 framework 没价值"。

### 1.2 "Prompt Engineering 已死" 的真实含义

Santiago Valdarrama（ML 教育者）2025 年在 LinkedIn 上的帖子：

> "Prompt engineering is dead. Context engineering is the new king. I've talked to many people building agents, and most are duct-taped together using a bunch of services..."

— [LinkedIn post](https://www.linkedin.com/posts/svpino_prompt-engineering-is-dead-context-engineering-activity-7404550996703465472-Q0eA)

Conner Ardman：

> "In 2023, prompt engineering was an art form — people learned to 'hack' model behavior with clever phrasing. But in 2025, the frontier has shifted to context orchestration... I see prompt engineering less as a permanent job title, and more as a transitional skill."

— [LinkedIn post](https://www.linkedin.com/posts/connerardman_i-was-wrong-about-prompt-engineering-activity-7352018740714143744-kkE4)

**关键观察**：他们说的不是"别学提示词"，而是"别把它当永久技能"。这和"别学 HTML wrangling，要学 web development"是同一个 pattern。表层操作会被抽象掉，但**更高抽象层次的思考（context engineering, orchestration）继续存在**。

### 1.3 具体 Framework 是否值得学

Owain Lewis（The AI Engineer newsletter, 2026-01）：

> "AI framework hell is real. Every week, a new AI framework arrives... Here's what nobody tells you: you don't need any of these. The provider SDKs (OpenAI, Anthropic, Google) are powerful enough on their own... I call this framework tax."

— [AI Frameworks Worth Learning in 2026](https://newsletter.owainlewis.com/p/ai-frameworks-worth-learning-in-2026)

Ebenezer Don（2026-02）：

> "If you're learning agent frameworks as your entry point into agent engineering, you're learning a very specific abstraction layer that's probably going to change dramatically. **The pattern of agent matters, the frameworks don't.**"
>
> "Finetuning is high effort, high maintenance and the model you fine-tune today might be obsolete in 3 months when a better base model comes out."

— [Don't Waste 2026 Learning the Wrong AI Skills (YouTube)](https://www.youtube.com/watch?v=D6S7PMlQdh8)

**这类观点的共同结构是**：X 会过时 → 别把 X 当学习目标 → 要学 X 背后的 pattern。**它不是"别学"，是"别在 X 这一层学"。**

### 1.4 中文圈的特殊形态：AI 培训智商税

中文圈的"学得慢不如不学"被产业化了 —— 焦虑营销矩阵把它包装成付费课程。

中国经济网调查（2024-12）记录学员"可儿"的亲历：

> "AI 没学明白，先学会知识付费了。"
>
> "学完后我发现，其实大部分 AI 应用操作没有想象中复杂……我只能去视频网站搜索免费教程，自己研究一会儿也能学会了。"
>
> "我感觉自己就像哑巴吃黄连，有苦说不出。如果让我重来一次，我绝对不会选择花费近一千块钱报名课程。"

— [AI 培训：逆袭"神器"还是"割韭菜"陷阱？](http://tech.ce.cn/yw/202412/16/t20241216_39235757.shtml)

知乎上高赞"程序员转型 AI"回答几乎全部绑定"知乎知学堂大模型公开课"引流（见 [这篇](https://zhuanlan.zhihu.com/p/1954205355207779797) 为典型），这是平台分成机制造成的系统性扭曲。

**李一舟现象**是这个产业链的符号：199 元"清华博士 AI 课"—— 被封杀后又换马甲复出（[知乎文章](https://zhuanlan.zhihu.com/p/2017662869131536017)）。

这里的"学得慢不如不学"被重写成："你学得慢 → 焦虑 → 买我的速成课"。**中文圈的特殊陷阱不是"学还是不学"，而是"你是不是在被焦虑营销当作流量收割"。**

---

## 二、为什么多数情况它是错的 —— 不变量的存在

把具体 framework 的生命周期误当作整个领域的生命周期，是这个观点最大的逻辑漏洞。AI/LLM 领域确实有一层"不变量"，被多位有长期实绩的研究者反复验证。

### 2.1 Karpathy：学 fundamentals，不要抽象

Karpathy 的 Zero-to-Hero 课程设计本身就是一次公开表态：

> "We start with the basics of backpropagation and build up to modern deep neural networks, like GPT. In my opinion language models are an excellent place to learn deep learning, even if your intention is to eventually go to other areas like computer vision because **most of what you learn will be immediately transferable**."

— [Zero to Hero](https://karpathy.ai/zero-to-hero.html)

DeepLearning.AI 采访中他直接表态：

> "It's really important to not abstract away things. **You need to have a full understanding of the whole stack.**"

— [Heroes of Deep Learning](https://www.deeplearning.ai/blog/hodl-andrej-karpathy/)

他在 Twitter 上总结的 "expert formula"：

> "(1) iteratively take on concrete projects and accomplish them depth wise, learning 'on demand' (**ie don't learn bottom up breadth wise**) (2) teach/summarize everything you learn in your own words (3) only compare yourself to younger you, never to others"

— [karpathy.ai/tweets](https://karpathy.ai/tweets.html)

**关键**：Karpathy 本人从 2022 年开始持续产出 nanoGPT / micrograd / build-nanogpt / llm.c / State of GPT —— 这些材料在 2024/2025/2026 都没过时，因为它们教的是**transformer 原理**而非具体 framework API。这是对"学了就过时"论最有力的实绩反驳。

### 2.2 Simon Willison：追前沿，但沉淀概念

Simon 每年年底写的 "things we learned about LLMs" 系列是 LLM 生态的权威编年史。他本人每天花大量时间在 LLM 的 jagged frontier 上，但他做的不是追 tool，而是提炼**可命名、可迁移的概念**：

> "The lethal trifecta, my one attempted coinage of the year that seems to have taken root. Context rot... for the thing where model output quality falls as the context grows longer during a session. Context engineering as an alternative to prompt engineering that helps emphasize how important it is to design the context you feed to your model."

— [2025: The year in LLMs](https://simonwillison.net/2025/Dec/31/the-year-in-llms/)

**lethal trifecta、context rot、context engineering** —— 这些概念跨 model / 跨 framework 不变，因为它们描述的是 LLM 本身的不变属性。

### 2.3 swyx：AI 工程 90% 是传统软件工程

Shawn Wang（swyx）的公开立场：

> "I actually also think that **AI engineering is 90% traditional software engineering**, and you should learn all the software engineering fundamentals before you tackle the AI stuff."

— [Scrimba Podcast E146](https://podcast.scrimba.com/146/transcript)

> "The more I build in this space, the more I realize that you just cannot do anything interesting unless you can write software to orchestrate the [AI] systems, and then use the systems to write software."

— [The New Stack interview](https://thenewstack.io/ai-engineer-summit-wrap-up-and-interview-with-co-founder-swyx/)

**换句话说**：10 年写代码的功力 + 1 年学 LLM ≫ 1 年写代码 + 10 年追最新 framework。

### 2.4 Hamel Husain：Evals 是永恒的功夫

Hamel 的立场最直接：

> "the teams who succeed barely talk about tools at all. Instead, they obsess over measurement and iteration."
>
> "Error analysis — the single most valuable activity in AI development and consistently the highest-ROI activity."
>
> "**This is the 'tools trap'** — the belief that adopting the right tools or frameworks will solve your AI problems."

— [A Field Guide to Rapidly Improving AI Products](https://hamel.dev/blog/posts/field-guide/)

> "I've seen many successful and unsuccessful approaches to building LLM products. I've found that unsuccessful products almost always share a common root cause: **a failure to create robust evaluation systems**."

— [Your AI Product Needs Evals](https://hamel.dev/blog/posts/evals/)

**Eval / error analysis 这层功夫，从传统 ML 到 LLM 到未来的 AGI，都是核心。** Framework 可以换，模型可以换，但"看数据、写 eval、做 error analysis"这个 craft 不换。

### 2.5 Eugene Yan：Patterns 而非 Products

Eugene 在《Patterns for Building LLM-based Systems》里的立场：

> "How important evals are to the team is a major differentiator between folks rushing out hot garbage and those seriously building products."
>
> "**RAG applies mature and simpler ideas from the field of information retrieval to support LLM generation.**"
>
> "Data... is one of the few moats for LLM products."

— [llm-patterns](https://eugeneyan.com/writing/llm-patterns/)

**关键**：他指出 RAG 本质上是几十年的 IR 研究在 LLM 时代的再利用 —— 这就是"不变量"的一个典型例子。学 IR 基础的人，每出一个新 RAG 架构都是"哦原来是 BM25 + rerank 的新变种"；没学 IR 基础的人，每出一个新架构都是"又要从头学"。

### 2.6 Chip Huyen：基础会留下

Chip Huyen 在 *AI Engineering* 一书和访谈中的核心观点：

> "To get good at AI engineering, focus on the basics. Understand what an LLM is (and how it works), how to evaluate them, how to use RAG, what finetuning is, and how to optimize inference. **All of these techniques are foundational, and will remain important in a few years' time as well.**"

— 访谈摘要，[The AI Engineering Stack (Pragmatic Engineer)](https://newsletter.pragmaticengineer.com/p/ai-engineering-with-chip-huyen)

### 2.7 中文圈的反叙事锚点：李沐、苏剑林

中文圈不是没有反焦虑的声音，只是这些声音被营销流量淹没。

**李沐**（B 站"跟李沐学 AI"111.5 万粉丝）的《用随机梯度下降来优化人生》：

> "要有目标。短的也好，长的也好。就跟随机梯度下降需要有个目标函数一样。"
>
> "目标要大。不管是人生目标还是目标函数，你最好不要知道最后可以走到哪里。"
>
> "不要纠结于最完美的方向和步子。前期的徘徊是必要的 —— 如果一开始就找到最优解，后期反而会乏力。"

— [知乎专栏](https://zhuanlan.zhihu.com/p/414009313)

**苏剑林**（kexue.fm，十余年独立博客，月更一手数学推导）—— 他本人几乎不参与"学得快被淘汰"这类讨论。他的存在本身就是反证：中文 AI 圈公认最硬核的独立研究者，走的是"窄、深、慢"路线，没被任何 framework/model 换代淘汰过。

**宝玉**（baoyu.io）《既然 AI 越来越聪明，那么学习提示词不是浪费时间吗？》：

> "很多人觉得 AI 越来越强，提示词工程迟早过时。但这就像当年说'学英语没用'一样，把'自己用不上'等同于'没价值'。真正的提示词工程不是背咒语，而是把需求想清楚、说明白 —— 这件事永远不会过时。"

— [baoyu.io](https://baoyu.io/)

---

## 三、不变量清单 —— 学了不会被淘汰的东西

基于上面多源交叉验证，汇总"值得长期投入"的 6 类不变量。这份清单本身就是一个判断工具 —— 你投入的每一份时间，应该都能 map 到这 6 类之一。

### 不变量 1：模型原理

- Backprop / gradient flow
- Attention / transformer 架构
- Pretraining / SFT / RLHF / DPO / GRPO 的 pipeline 本质
- Tokenization / embedding 空间
- Decoding 策略与采样

**为什么不变**：从 GPT-2 到 GPT-4 到 Claude 4 到 Llama 4，参数量、数据、tricks 都在变，但 transformer + SGD + next-token prediction 这个基本盘从 2017 年至今没变。

**怎么学**：nanoGPT、micrograd、build-nanogpt、llm.c 这些都是 Karpathy 准备好的不变量学习材料。从零实现一次 GPT 之后，后面所有 model 细节都是"某个位置的变种"。

### 不变量 2：评估与测量

- Error analysis（先看数据，再写 eval）
- Task-specific evals（不是用通用 benchmark）
- 统计显著性、confidence interval
- Regression detection
- Feedback flywheel 设计

**为什么不变**：任何 AI 系统在部署后都需要被测量，否则无法改进。model 再强也需要 eval；prompt 再好也需要 eval；agent 再自主也需要 eval。

**怎么学**：Hamel 的 [Evals Field Guide](https://hamel.dev/blog/posts/evals-faq/) 和付费课程是当前最好的材料。

### 不变量 3：检索与数据

- BM25、稠密检索、rerank 的 IR 基础
- Chunking、embedding、index 设计
- 数据质量 > 算法（所有 ML 团队都认可）
- Transfer learning / finetuning 的 when-to-use 判断

**为什么不变**：RAG 只是 IR + LLM 的组合；下一代架构大概率还是 IR + 某种 model 的组合。**学 IR 基础的人不会被任何 RAG 变种淘汰。**

### 不变量 4：软件工程基本功

- 分布式系统（尤其对瑞哥 SRE 背景直接迁移）
- API 设计、抽象能力
- Debugging 与可观测性
- 系统思维（latency、throughput、bottleneck）
- 测试、版本控制、CI/CD

**为什么不变**：swyx 的 "AI engineering is 90% traditional SWE" 是最硬的论据。任何 AI 系统最终都要被部署、被监控、被调试、被迭代 —— 这些都是传统 SWE。

### 不变量 5：实验与迭代能力

Karpathy 明确命名的能力：

> "raw experimental throughput - **the ability to babysit a large number of experiments at once**, staring at plots and tweaking/re-launching what works."
>
> "When you sort your dataset descending by loss you are guaranteed to find something unexpected, strange and helpful."

— [A Recipe for Training Neural Networks](https://karpathy.github.io/2019/04/25/recipe/)

**为什么不变**：ML 的 empirical 本质决定了"快速运行实验、读懂结果、调整假设"这个循环永远是核心。这是为什么 PhD 训练在 AI 领域仍有溢价。

### 不变量 6：写作、提炼、教学

- 写博客（Eugene Yan、Simon Willison、Lilian Weng 的做法）
- Learn in public（swyx 倡导）
- 用自己的话总结 / 教学（Karpathy 的 expert formula 第二条）

Eugene Yan 引 Sönke Ahrens：

> "Writing is not what follows research, learning, or studying. It is **the medium of all this work**."

— [eugeneyan.com/writing/reading-note-taking-writing](https://eugeneyan.com/writing/reading-note-taking-writing/)

**为什么不变**：写作是思考的压力测试，是学习的 consolidation step，也是你在任何新领域建立 reputation 的最低成本方式。Model 再强也不会替你写出你的判断。

---

## 四、"值不值得学"的 4 条判断信号

给定一个新概念 / 新 paper / 新 framework，怎么判断要不要投入？四条信号：

### 信号 1：convergent evolution（多人独立重新发现）

多个独立来源、从不同角度得到相同结论 = 底层真实。

**例子**：LangChain abstraction 过度 这个结论，Octomind（生产实践）、HN 社区（开发者使用）、Roborhythms（事后分析）、多位独立开发者都独立得出，且从不同角度 —— 这就是强信号。

**反例**：某个新 framework 的价值如果只有 vendor 自己的 marketing 在说，那是弱信号。

### 信号 2：能否 map 回已有 fundamentals

> "RAG applies mature and simpler ideas from the field of information retrieval to support LLM generation."

— Eugene Yan

能还原到 IR、统计、系统、SWE 这些老学科的概念 → 值得学，因为你同时在强化 fundamentals。

**反例**：一个无法 map 回任何老学科、纯粹是某个 vendor 创造的新词 → 警惕是 marketing 包装。

### 信号 3：paper / 理论支撑 vs pure marketing

Chollet 的 intelligence/skill 区分有 Algorithmic Information Theory 支撑；Karpathy 的 pipeline 对应 InstructGPT paper；Eugene 的 patterns 都引用 NLP/IR 文献。

**对比**：很多"agentic framework"、"X 天速成 AI"完全没有 paper 支撑，属于 marketing 层。

### 信号 4：发明者是研究者还是 marketing team

Hamel Husain 的原话：

> "the teams who succeed barely talk about tools at all. Instead, they obsess over measurement and iteration."

**判断维度**：发明者 / 推广者有没有 shipped-model 实绩？有没有长期 track record？还是只在社交媒体上造势？Karpathy / Chollet / Howard / Hamel / Simon / Eugene / Chip 都有多年实绩；相反，很多"XX 天学会 AI"的讲师没有任何 production 经验。

---

## 五、具体学习策略 —— 5 条强共识

从 Karpathy / Howard / Hamel / Yan / swyx 的公开写作里抽出 5 条**多源一致**的策略（任何一条都至少有 3 个独立来源支持）：

### 策略 1：深度 > 宽度（4 小时长窗口）

Karpathy 原话：

> "**Learning is not supposed to be fun.** It doesn't have to be actively not fun either, but the primary feeling should be that of effort."
>
> "Close those tabs with quick blog posts. Consider the opportunity cost of snacking and seek the meal — the textbooks, docs, papers, manuals, longform."
>
> "Allocate a **4 hour window**. Don't just read, take notes, re-read, re-phrase, process, manipulate, learn."

— [karpathy.ai/tweets](https://karpathy.ai/tweets.html)

**落地**：与其每天刷 10 条 AI Twitter，不如每周留 1 个 4 小时长窗口读一篇 paper 或啃一段源码。

### 策略 2：项目拉动 > 课程铺垫（on-demand learning）

Karpathy 的 expert formula 第一条：

> "iteratively take on concrete projects and accomplish them depth wise, learning 'on demand' (**ie don't learn bottom up breadth wise**)"

Jeremy Howard 的 top-down 哲学：

> "I start by showing how to use a complete, working, very usable, state-of-the-art deep learning network to solve real-world problems... And then we gradually dig deeper and deeper into understanding how those tools are made."

— [course.fast.ai](https://course.fast.ai/)

**落地**：不要"先学数学再学 ML 再学 DL 再学 LLM"这种 bottom-up 路径。找一个你真的想做的项目，遇到什么补什么。

### 策略 3：从零实现是 fundamentals 的必经之路

Karpathy 反复强调并用 nanoGPT / micrograd / llm.c 示范。核心价值：

> "Because the code is so simple, it is very easy to hack to your needs, train new models from scratch, or finetune pretrained checkpoints."

— [github.com/karpathy/nanoGPT](https://github.com/karpathy/nanoGPT)

**落地**：学 LLM 的一个不可替代环节就是**从零写一个** —— 不一定要训大模型，micrograd 级别 + nanoGPT 级别的一次 implementation 足够。

### 策略 4：写作 / 教学 / learn in public

swyx 的核心立场：

> "Don't judge your results by 'claps' or retweets or stars or upvotes"
>
> "the biggest beneficiary of you trying to help past you is **future you**"
>
> "have a habit of creating **learning exhaust**"

— [swyx.io/learn-in-public](https://www.swyx.io/learn-in-public)

Eugene Yan：

> "Writing is both a multiplayer and single-player game... it's single-player because when you write, you're learning, thinking deeply, and clarifying your thoughts, and you always win the single-player game."

— [eugeneyan.com](https://eugeneyan.com/writing/reading-note-taking-writing/)

**落地**：每学完一个东西，用自己的话写一篇笔记 / 博客 / 内部分享。输出质量 = 理解深度的 upper bound。

### 策略 5：学不变量而非当前框架

Hamel 的 eval craft、Eugene 的 LLM patterns、Karpathy 的 backprop/attention 原理 —— 这些都是"model 怎么变都需要的东西"。

**落地**：选择投入方向时问自己 —— 如果明年出现一个更强的 base model、或一个完全替代 LangChain 的新框架，我这次学的东西还剩多少？如果剩得少，投入要谨慎。

---

## 六、反模式 —— 尤其中文圈需要警惕的 5 个陷阱

### 反模式 1：追新 framework → 每个都浅尝

信息化时代最大的陷阱是"看起来在学，其实在消费"。Karpathy 直接命名：

> "If you are consuming content: are you trying to be entertained or are you trying to learn?"

### 反模式 2：囤教程当安慰剂（"buying courses as anxiety relief"）

买了不看、看了不做 —— 知识付费的本质是缓解焦虑，不是学习。中国经济网采访的学员"可儿"就是典型。

### 反模式 3：bottom-up 系统学习

很多人"学 AI"先买本数学书从头看，书没看完就放弃了。Karpathy 明确反对这种路径："don't learn bottom up breadth wise"。

### 反模式 4：Eval-driven development 的伪方法论

这个有点反直觉 —— 看起来很对的东西其实有陷阱。Hamel 原话：

> "Eval-driven development (writing evaluators before implementing features) sounds appealing but creates more problems than it solves... Unlike traditional software where failure modes are predictable, LLMs have infinite surface area for potential failures. You can't anticipate what will break. **A better approach is to start with error analysis. Write evaluators for errors you discover, not errors you imagine.**"

— [Should I practice eval-driven development?](https://hamel.dev/blog/posts/evals-faq/should-i-practice-eval-driven-development.html)

### 反模式 5：中文圈独有 —— 焦虑营销漏斗

这是中文圈的结构性陷阱，值得单独讲。模式：

> **年龄焦虑（35 岁）+ 性别焦虑（宝妈）+ 收入锚点（百万年薪） → "不学就被淘汰"情绪 → 免费体验课 → 付费课程 → 发现免费教程都能学会**

中新网直接定性（2024-02）：

> "不学 AI 马上失业？拒绝 AI 培训课程'贩卖焦虑'"

— [chinanews.com.cn](https://www.chinanews.com.cn/sh/2024/02-26/10169945.shtml)

**识别信号**：
- 文案强调"30 天学会"、"百万年薪"、"风口"、"错过就晚了"
- 讲师缺乏 shipped-model 实绩 / 长期 track record
- 课程大纲 = 知乎 / B 站免费教程的目录重排
- 有强变现漏斗（免费课 → 299 课 → 2999 课 → 2w+ 咨询）

---

## 七、中英文圈的结构性差异

这是维度 4 调研中浮现出来的**独特发现**，值得单独留意。

**英文圈的焦虑** ≈ 个人存在价值焦虑
- "我的技能会不会被淘汰"
- "我读不完所有 paper"
- "HN 每天 10 个新 tool，我是不是 FOMO"
- 主要风险：追新停不下来 / FOMO

**中文圈的焦虑** ≈ 被经济结构抛弃焦虑
- "35 岁要不要转 AI"
- "不学大模型要被裁员"
- "百万年薪在招，我怎么还没去"
- 主要风险：被焦虑营销收割 / 学速成班

**推论**：两种人群需要不同的解药。
- 英文圈需要：**节制**（Karpathy 的"关掉 tab，读长文"、Simon 的"沉淀可命名概念"）
- 中文圈需要：**识别 + 远离焦虑营销产业链**（看到"35 岁 + 百万年薪 + 速成"关键词立即关闭）

瑞哥作为跨两个圈子的用户，两种风险都要提防。

---

## 八、结论与行动建议

### 8.1 Reframe "不被淘汰"这个问题

错误的提问：**"我学哪个 framework / 哪个 model / 哪个 tool 不会过时？"**

正确的提问：**"我每一次投入，在这个具体对象过时之后，我还剩下什么？"**

前者是 tool-centric 思维，必然焦虑 —— 因为 tool 肯定会过时。
后者是 skill-centric 思维，可以反脆弱 —— 因为 fundamentals 不会过时，而且每一次追前沿都在强化 fundamentals。

### 8.2 最小可执行清单

**本周做一件事**：打开一个文本文件，写下"我的不变量清单"—— 你打算长期投入的 3-5 个 fundamentals 是什么？（参考第三章 6 类）

**本月做一件事**：选一个 4 小时长窗口 + 一个具体项目，强制关闭社交媒体。要么啃一段 nanoGPT 源码 + 自己注释一遍，要么找一个真实任务跑通 eval 循环。

**本季度做一件事**：写一篇长文（博客 / 内部分享 / 知乎专栏都行），主题是你这个季度最深的一个 fundamental 顿悟。写作是学习的压力测试。

**长期纪律**：每次看到一个新 framework / 新概念，用第四章的 4 条信号过一遍。过不去 2 条的直接忽略，省下的时间投入 fundamentals。

### 8.3 对 SRE + AI 交叉方向的具体建议

（因为你目前的方向是 AI/LLM + SRE，这里直接针对你）

**你已有的不变量**（强）：
- 分布式系统（天然对应 AI infra 的 inference serving / RAG stack / agent orchestration）
- 可观测性（eval 的底层哲学和 metrics/logs/traces 同构）
- Overload / SLI-SLO / availability（AI 系统的 production 问题 80% 是传统 SRE 问题）
- 调试与根因分析（对应 Hamel 的 error analysis）

**应该补齐的**（高 ROI）：
1. **Transformer/LLM 原理一次**（nanoGPT + State of GPT 视频，一个长假搞定）
2. **Eval craft**（Hamel 的材料 + 你实际在某个 agent 项目上做一次 error analysis）
3. **RAG fundamentals = IR 基础**（BM25 + rerank + eval，不要学 framework 先学原理）
4. **Agent 控制理论**（你 `contexts/thought_review/` 下已经有 agentic control theory 的思考，这是正确方向）

**不要补的**（低 ROI）：
- LangChain / LlamaIndex / CrewAI 这类 framework 的深度用法 —— 用 provider SDK（Anthropic / OpenAI）直接写就够了
- 具体 prompt 模板库
- 追每一个新 agent framework

你的 SRE 背景是罕见的不变量资本。AI agent ops / agent infra / agent 可靠性这个方向，是"你的 fundamentals × AI 趋势"的正交交集，值得重投入（这也是你 OBSERVATIONS.md 和 thought_review 里已经在走的方向）。

---

## 九、一句话收尾

> 不是"学得慢不如不学"，是**"别在错的那一层学"**。
>
> 不变量很少，但每一个都足够养活一辈子。
> 表层很多，但每一个都活不过三年。
>
> 选择权在你。

---

## 附录：关键信源索引

### 英文一手（高可信）
- Andrej Karpathy: [karpathy.ai](https://karpathy.ai/) / [Zero to Hero](https://karpathy.ai/zero-to-hero.html) / [A Recipe for Training NN](https://karpathy.github.io/2019/04/25/recipe/) / [nanoGPT](https://github.com/karpathy/nanoGPT)
- Simon Willison: [simonwillison.net](https://simonwillison.net/) / [2025 年度总结](https://simonwillison.net/2025/Dec/31/the-year-in-llms/)
- Hamel Husain: [hamel.dev/evals](https://hamel.dev/blog/posts/evals/) / [Field Guide](https://hamel.dev/blog/posts/field-guide/)
- Eugene Yan: [eugeneyan.com](https://eugeneyan.com/) / [LLM Patterns](https://eugeneyan.com/writing/llm-patterns/)
- Chip Huyen: [AI Engineering (O'Reilly)](https://www.oreilly.com/library/view/ai-engineering/9781098166298/)
- François Chollet: [On the Measure of Intelligence](https://arxiv.org/abs/1911.01547)
- Jeremy Howard / fast.ai: [course.fast.ai](https://course.fast.ai/)
- swyx: [learn in public](https://www.swyx.io/learn-in-public)

### 批判方（表层"学了就过时"的案例）
- [Why we no longer use LangChain (Octomind)](https://www.octomind.dev/blog/why-we-no-longer-use-langchain-for-building-our-ai-agents)
- [HN: LangChain Is Pointless](https://news.ycombinator.com/item?id=36645575)
- [LangChain Is Quietly Losing Developers](https://www.roborhythms.com/langchain-losing-developers-2026/)
- [AI Frameworks Worth Learning in 2026](https://newsletter.owainlewis.com/p/ai-frameworks-worth-learning-in-2026)

### 中文一手（反叙事锚点）
- 李沐《用随机梯度下降来优化人生》: [zhihu](https://zhuanlan.zhihu.com/p/414009313)
- 苏剑林 科学空间: [kexue.fm](https://spaces.ac.cn/)
- 宝玉: [baoyu.io](https://baoyu.io/)
- 李rumor NLP 路线: [zhihu](https://www.zhihu.com/tardis/sogou/qus/27529154)

### 中文圈批判性声音（反割韭菜）
- [中国经济网：AI 培训"割韭菜"陷阱](http://tech.ce.cn/yw/202412/16/t20241216_39235757.shtml)
- [中新网：拒绝 AI 培训课程"贩卖焦虑"](https://www.chinanews.com.cn/sh/2024/02-26/10169945.shtml)
- [吉林网：警惕以新技术贩卖焦虑](https://piyao.cnjiwang.com/jrpy_py/202502/3924085.html)
- [掘金：真正免费的 Prompt 学习路径](https://juejin.cn/post/7586957587076661298)
