# META
id: w-g-slo
kicker_en: EVOLUTION
kicker_cn: 我的进化
title_en: From Labeling CPU to Designing SLOs: Relearning What Monitoring Is
title_cn: 从标 CPU 到设计 SLO：一个 SRE 对监控的重新理解
sub_en: The junior version of me split metrics horizontally — system vs application — and thought monitoring was done once the CPU curve was on a dashboard. The turn was learning to design top-down: different stakeholders care about different things, each has a different SLO and a different dashboard, and a dashboard exists to answer a question.
sub_cn: junior 时期的我把指标横着切：system 与 application，以为把 CPU 标到 dashboard 上监控就做完了。真正的转折是学会从上往下设计：不同主体关心不同的指标，每个主体的 SLO 不同、dashboard 不同，而 dashboard 存在的意义是回答问题。
domains: [obs]

# EN

## What this is about

I did not really start to understand SLOs from reading the Google SRE book. I started to understand them because my seat changed — from a demo environment at Intel to production at DataVisor. This is the record of the single most important shift in that move: monitoring is not about surfacing metrics, it is about designing downward from "who cares about what." That shift is also the line along which I judge my own move from junior to senior.

## When the SLO became real

In a demo environment, an SLO is a concept. The system dies, you restart it, nobody actually loses anything. "99.9% availability" is a number on a slide, and emotionally it is hollow.

In production there is a real customer standing behind it, and that is when it lands:

- An **SLA is a promise** — the line you signed your name to in front of a customer.
- It is the **concretization** of stability: the abstract word "stable" gets translated into "monthly availability ≥ 99.9%, or there is compensation."
- Infrastructure gets pushed to the front. It used to hide behind the product; now its jitter turns **directly** into the customer's loss, the customer's phone call, the customer's churn.

Once you owe something to a customer, the SLO stops being jargon and becomes a kind of pressure. Everything real I understand about SLOs grew out of that pressure.

## The junior mistake: cutting metrics horizontally

I used to understand monitoring like this: two categories, **system metrics** (CPU, memory, disk, network) and **application metrics** (QPS, error rate, latency). Collect them all, put them on a dashboard, monitoring is done.

Looking back, the error is that this is a **horizontal split**. It classifies metrics by which layer of the system they live on, not by who needs them and what question they answer. The result:

- The dashboard is full of CPU curves, but no one can tell from one screen whether the customer is being affected right now.
- Every metric is green while the customer is complaining — because what is green is the host, and what hurts is the request.
- When something breaks the dashboard does not help, because it was not built to answer a question, it was built to collect everything collectable.

A horizontally-cut monitoring setup is instrument-hoarding, not monitoring design.

## The senior turn: design top-down

The real approach is **top-down**, pushing down from the topmost layer, from the user's point of view. The core is one sentence: **different stakeholders care about different metrics.**

- **Customer / business:** did my request succeed, was it fast enough, did the data land today? This is the SLA/SLO layer.
- **Service owner:** which endpoint is burning error budget, which dependency is dragging? This is the golden-signals layer.
- **On-call:** what is broken right now, at which layer, how do I stop the bleeding? This is the diagnostic-chain layer.
- **Platform / capacity:** is there enough resource to last into next quarter? Only here do CPU and memory finally take the stage.

CPU is not unimportant; it belongs to the bottom stakeholder. Putting it on the top layer for the customer to see is a layering error.

Three consequences follow:

1. **Each stakeholder has a different SLO.** The customer's SLO is availability and latency; the capacity team's "target" is utilization and headroom. Do not use one set of metrics to pretend to serve everyone.
2. **Each stakeholder has a different dashboard.** One panel serves one stakeholder and answers one class of question. The customer-facing panel should not have CPU on it; the on-call panel should not be a single overall availability number.
3. **A dashboard exists to answer a question**, not to display data. Before building one, ask: whose question does this answer? A curve that answers no one's question is noise.

## The growth line

Put the two states side by side and the shift is clear:

| | Junior me | Senior me |
|---|---|---|
| What monitoring is | surface every metric you can collect | design downward from stakeholders and questions |
| How to classify | horizontal: system vs app | vertical: who cares, what question |
| SLO | a number on a slide | a promise to a customer, with pressure behind it |
| Dashboard | a wall of data | answering a specific question for a specific stakeholder |
| Where CPU sits | the most prominent first screen | a lower-layer metric for the capacity stakeholder |

I no longer treat "putting CPU on a screen" as monitoring. Monitoring is first working out who is looking and what they need to answer, then deciding what to measure, how to display it, and for whom. The moment that order reversed was the moment I knew my understanding of SLOs and of monitoring design had finally crossed the line from junior.

# CN

## 这篇想说什么

我真正开始懂 SLO，不是因为读了 Google SRE 那本书，而是因为换了个位置：从 Intel 的 demo，到 DataVisor 的 production。这篇记录这个转变里最核心的一件事：监控不是把指标标出来，而是从「谁在关心什么」往下设计。这也是我判断自己从 junior SRE 迈向 senior 的那条线。

## 一、SLO 是什么时候变「真」的

在 demo 环境里，SLO 是个概念。系统挂了，重启就好，没人真的因此损失什么。所谓「可用性 99.9%」是 PPT 上的数字，感性上是空的。

到了 production，背后站着一个真实的客户。这时候才明白：

- **SLA 是一个承诺**，是你对客户签字画押的那条线。
- 它是系统稳定性的**具象化**：抽象的「稳定」被翻译成「月度可用性 ≥ 99.9%，否则赔偿」。
- infra 被推到了前台。以前它躲在业务后面，现在它的抖动**直接**变成客户的损失、客户的电话、客户的流失。

对客户有责任、有承诺，这件事一旦成立，SLO 就不再是术语，而是一种压力。我对 SLO 的所有真正理解，都是从这个压力里长出来的。

## 二、junior 的错误：把指标横着切

我曾经这样理解监控：分两类，**system metrics**（CPU、内存、磁盘、网络）和 **application metrics**（QPS、错误率、延迟）。把它们都采下来，标到 dashboard 上，监控就算做完了。

现在看，这个划分错在它是一个**水平切分**。它按「指标长在系统的哪一层」来分类，而不是按「谁需要它、用它回答什么问题」来分类。结果就是：

- dashboard 上摆满了 CPU 曲线，但没人能从一屏里看出「客户现在有没有在受影响」。
- 一堆指标都绿，客户却在投诉，因为绿的是主机，痛的是请求。
- 出事时 dashboard 帮不上忙，因为它不是为回答问题建的，是为「把能采的都采上」建的。

横切的监控，本质是仪表堆砌，不是监控设计。

## 三、senior 的转向：从上往下做

真正的做法是 top-down，从最上层、从 user 的视角往下推。核心是一句话：**不同的主体关心不同的指标。**

- **客户 / 业务**：我的请求成功吗？够快吗？数据当天到了吗？这是 SLA/SLO 层。
- **服务 owner**：哪个接口在烧 error budget？哪个依赖在拖后腿？这是服务黄金信号层。
- **on-call / 值班**：现在哪里坏了、坏在哪一层、怎么止血？这是排障链路层。
- **平台 / 容量**：资源够不够撑到下个季度？这才轮到 CPU、内存这些系统指标登场。

CPU 不是不重要，而是它属于最下面那个主体。把它摆到最上层给客户看，是层级错位。

由此推出三条：

1. **每个主体的 SLO 不同。** 客户的 SLO 是可用性和延迟；容量团队的「目标」是利用率和余量。别用一套指标假装服务所有人。
2. **每个主体的 dashboard 不同。** 一块面板服务一个主体、回答一类问题。给客户看的面板上不该有 CPU；给 on-call 看的面板不该只有一条总可用率。
3. **dashboard 的存在意义是回答问题**，不是展示数据。建之前先问：这块板要回答谁的什么问题？答不上来的曲线，就是噪声。

## 四、这条成长线

把这两种状态并排放，转变就很清楚了：

| | junior 的我 | senior 的我 |
|---|---|---|
| 监控是什么 | 把能采的指标标出来 | 从主体和问题往下设计 |
| 怎么分类 | 横切：system vs app | 纵切：谁关心、答什么问题 |
| SLO | PPT 上的数字 | 对客户的承诺，有压力 |
| dashboard | 数据展示墙 | 为特定主体回答特定问题 |
| CPU 的位置 | 最显眼的第一屏 | 容量主体的下层指标 |

我不再把「标出 CPU」当作监控。监控是先想清楚谁在看、他要回答什么，再决定标什么、怎么标、给谁看。这个顺序反过来的那一刻，我知道我对 SLO、对监控设计的理解，终于从 junior 迈过了那条线。

# SOURCES
- 原始博客草稿（作者本人，hexo blog）：work-contexts/toy-proj/blog-system/source/_posts/2026-07-20_slo-top-down-monitoring_zh.md
- 站点版处理：CN 去除破折号（站点惯例）；补 EN 平行版本；内容与原文一致，未添加新事实
- 关联站点内容：可观测性域（SLI/SLO 设计）、V1 视角页「运营监控是核心、建设监控是专家项」、告警治理页（不能指导行为的告警是噪声，与「答不上问题的曲线是噪声」同构）
