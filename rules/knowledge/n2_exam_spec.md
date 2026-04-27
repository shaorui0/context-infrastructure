---
name: n2_exam_spec
description: JLPT N2 官方考试 scope 参考（题型/题量/时间/通过线/词汇语法规模）。供 /n2prep skill 加载。
last_updated: 2026-04-22
status: STUB — 尚未调研，先用兜底常识
source_urls: []
---

# JLPT N2 Exam Spec (Reference)

> ⚠️ **本文件是 stub**。内容是凭常识写的兜底版本，未经官方调研验证。
>
> **TODO**: 运行 `workflow_deep_research_survey`，调研对象：
>
> - 官方 scope: https://www.jlpt.jp/e/about/levelsummary.html
> - 题型分布: https://www.jlpt.jp/e/samples/sample12.html
> - 通过线: https://www.jlpt.jp/e/guideline/results.html
> - 词汇/语法规模: N2 公式语法表、词汇表
>
> 产出 `contexts/survey_sessions/n2_exam_spec_<date>.md`，带完整 URL 引用原文。然后蒸馏回本文件，更新 `last_updated`、`status: VERIFIED`、`source_urls`。

---

## 本地 prep 使用的规格（兜底）

### 总体

- 试卷时长：105 min (言語知識 + 読解) + 50 min (聴解)
- 总分：180 分（每 section 60 分，量表化 scaled score）
- 通过线：每 section ≥19/60 且总分 ≥90/180

### 言語知識（文字・語彙） ~28 题

| 题型 | 题数（真实） | 本地 prep |
|---|---|---|
| 漢字読み | 5 | 5 |
| 表記 | 5 | 5 |
| 語形成 | 3 | 3 |
| 文脈規定 | 7 | 7 |
| 言い換え類義 | 5 | 5 |
| 用法 | 5 | 3 |

### 言語知識（文法） ~20 题

| 题型 | 题数 |
|---|---|
| 文法形式の判断 | 12 |
| 文の組み立て | 5 |
| 文章の文法 | 3 |

### 読解 ~15 题

| 题型 | 文章数 | 题数/文章 | 字符数下限 |
|---|---|---|---|
| 短文 | 2 | 1 | 150 |
| 中文 | 3 | 2 | 400 |
| 統合理解 | 1 | ~3 | — |
| 長文 | 1 | 4 | 600 |
| 情報検索 | 1 | 3 | 300 |

本地 prep 简化：省略統合理解，合计 15 题。

### 聴解 ~30 题（本地压缩到 20）

| 题型 | 真实题数 | 本地 prep |
|---|---|---|
| 課題理解 | 5 | 5 |
| ポイント理解 | 6 | 6 |
| 概要理解 | 5 | 4 |
| 即時応答 | 11 | 5 |
| 統合理解 | 3 | 0（省略） |

### 词汇/语法规模（待验证）

- N2 词汇量：约 6,000（累计）
- N2 语法 pattern：约 200（N2 核心）+ N3 残余

### 代理指标 → 真实通过率映射（经验）

| 本地 composite | 真实考试预期 |
|---|---|
| ≥ 75% | 稳过（160+/180） |
| 65% - 75% | 大概率过（100-140） |
| 55% - 65% | 临界（有风险） |
| < 55% | 不建议裸考 |

---

## 更新约定

调研完成后：
1. 更新 frontmatter: `status: VERIFIED`, `last_updated: <date>`, `source_urls: [...]`
2. 每项数据后附 URL
3. 本 TODO 段落删除
