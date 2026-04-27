# Skill: N2 日本語トレーニング

## When to Use

User says "/n2", "日语训练", "N2 练习", or wants to practice JLPT N2 Japanese.

Trigger with mode: `/n2 会話`, `/n2 文法`, `/n2 読解`, `/n2 語彙`, `/n2 模試`, `/n2 素材`

No mode specified → ask user to choose, show the mode menu.

## Prerequisites

- None (pure conversational skill)
- Optional: Anki flashcard skill for vocab export (`/anki`)

## Core Design Principle

N2 tests decoding speed, not knowledge. The bottleneck is recognition latency.
All training modes target the pipeline: signal → recognition → parsing → meaning → decision.

For Chinese speakers: grammar parsing is relatively easy (similar structures, kanji advantage).
Training weight should skew toward vocabulary recognition (35%) and listening/reading throughput (35%).

---

## Output Rule (All Modes)

All modes that generate content MUST write output to a file, not just display in conversation.

- Output directory: `./tmp/`（relative to current working directory, create if not exists）
- File naming: `N2_<mode>_<YYYYMMDD_HHmm>.md`
  - 会話 → `N2_kaiwa_20260412_2300.md`
  - 文法 → `N2_bunpou_20260412_2300.md`
  - 読解 → `N2_dokkai_20260412_2300.md`
  - 語彙 → `N2_goi_20260412_2300.md`
  - 模試 → `N2_moshi_<section>_20260412_2300.md`（section = vocab/grammar/reading/listening/mixed）
  - 素材 → `N2_sozai_20260412_2300.md`
- File structure: questions/content first, answers/explanations at file end
- After writing the file, display the file path and a brief summary in conversation

---

## TTS Audio (All Modes)

Japanese text-to-speech via edge-tts + afplay. All modes support audio output.

### Setup
```bash
EDGE_TTS="/Users/rshao/work/context-infrastructure/.venv/bin/edge-tts"
# Voices: ja-JP-NanamiNeural (female), ja-JP-KeitaNeural (male)
```

### Usage Pattern
```bash
# Generate and play
$EDGE_TTS --text "日本語テキスト" --voice ja-JP-NanamiNeural --rate=-10% \
  --write-media ./tmp/tts_output.mp3 && afplay ./tmp/tts_output.mp3

# Speed control: --rate=-20% (slow/練習), --rate=+0% (normal/本番), --rate=+10% (fast/上級)
```

### Per-Mode Audio Behavior

| Mode | Audio behavior | Voice |
|------|---------------|-------|
| 会話 | AI の各返答を自動朗読 | Nanami |
| 文法 | 例文を朗読（パターン提示時） | Nanami |
| 読解 | 文章の朗読はオプション（ユーザーが「読んで」と言ったら） | Nanami |
| 語彙 | ターゲット文を朗読 | Nanami |
| 模試 聴解 | **音声を先に再生 → 質問を表示**（真考シミュレーション） | 男=Keita, 女=Nanami |
| 素材 | 抽出した重要文を朗読 | Nanami |

### 模試 聴解 Audio Flow (Critical)
聴解 section は音声が核心。テキストを先に見せてはいけない。

1. Generate audio for each dialogue (split by speaker, use Keita for 男 and Nanami for 女)
2. Play audio FIRST (user listens)
3. Show question text + options (NO dialogue transcript yet)
4. User answers
5. After answering: show transcript + explanation
6. Offer replay: 「もう一度聞く？」

Audio files saved to: `./tmp/N2_moshi_listening_<date>/` (one mp3 per question)

### Audio File Storage
When generating audio, save mp3 files alongside the .md output:
- Single files: `./tmp/N2_<mode>_<date>_audio/Q01.mp3`, `Q02.mp3`, ...
- 聴解 dialogues: `./tmp/N2_moshi_listening_<date>/Q01_male.mp3`, `Q01_female.mp3`, `Q01_full.mp3`

---

## Mode Menu

Display this when user triggers `/n2` without specifying mode:

```
N2 トレーニング — モード選択

1. 会話  — N2 レベルで自由会話（文法・語彙を自然に訓練）
2. 文法  — 文法パターン発見（例文から法則を見抜く）
3. 読解  — N2 レベル読解 + 理解問題（興味のある話題で生成）
4. 語彙  — 語彙コンテキスト訓練（文脈の中で意味を即答）
5. 模試  — N2 模擬試験（セクション別 10 問）
6. 素材  — 日本語素材を分析 → 学習ポイント抽出 → Anki 連携可
```

---

## Mode 1: 会話 (Conversation)

### Goal
Build fluency through interactive conversation at N2 level. Train grammar + vocab + context inference simultaneously.

### Execution

1. Ask user for topic preference, or pick from: tech/AI, Japanese workplace culture, daily life, current events, hobbies
2. Start conversation in Japanese at N2 level
3. Rules during conversation:
   - Use N2-level grammar patterns naturally (rotate through target patterns)
   - Vocabulary within N2 range, occasionally introduce N2 edge words in context
   - When user makes an error: do NOT interrupt the flow. Instead, naturally reformulate the correct version in your next reply (recasting technique). Only give explicit correction if the error is structural or repeated.
   - Every 4-5 exchanges, introduce one new grammar pattern or vocabulary item in context
   - Maintain natural conversation flow; this is not a classroom drill
   - After each AI reply, generate TTS audio and play it (edge-tts → afplay). This reinforces phonetic mapping while conversing.

4. At session end (user says "終わり", "结束", or "done"), provide a summary:

```
📊 Session Summary
- 新出語彙: [list words encountered]
- 文法パターン: [patterns used]
- 修正ポイント: [errors and corrections]
- 次回の課題: [suggested focus for next session]

→ Anki 導出？（/anki で闪卡生成可能）
```

### File Output
Session end 时将完整对话记录 + summary 写入 `./tmp/N2_kaiwa_<date>.md`。文件结构: 对话全文 → session summary → Anki export candidates。

### Difficulty Calibration
- If user responds mostly in Chinese/English → lower to N3-N2 boundary
- If user responds fluently → push toward N2-N1 boundary
- Adapt within the session, not between sessions

---

## Mode 2: 文法パターン (Grammar Pattern Discovery)

### Goal
Train grammar recognition through pattern discovery, not rule memorization. User sees examples and extracts the rule themselves.

### Execution

1. Select one N2 grammar pattern (from ~200 key patterns)
2. Present 4 example sentences using that pattern, with context variety:

```
以下の文に共通する文法パターンは何でしょう？

① 技術が進歩するにつれて、新しい課題が生まれる。
② 年を取るにつれて、体力が落ちてきた。
③ 日本語を勉強するにつれて、日本文化にも興味が出てきた。
④ プロジェクトが進むにつれて、要件が変わっていった。
```

3. Wait for user's response
4. Provide feedback:
   - If correct: confirm, expand with nuance (register, similar patterns, common mistakes)
   - If partial: guide toward the missing piece
   - If wrong: give one more example as hint before explaining

5. After explanation, present 2 discrimination sentences:

```
使い分け：どちらが正しい？

A. 練習するにつれて、上手になった。
B. 練習するたびに、上手になった。

→ 両方正しいが、ニュアンスの違いは？
```

6. After 5 patterns, provide a recap:

```
📊 文法パターン Session
- 正答: 3/5
- 苦手パターン: ～にしたがって vs ～につれて
- 復習推奨: [specific patterns]
```

### File Output
开始时即创建 `./tmp/N2_bunpou_<date>.md`。文件结构: 全部 pattern 例文 + 使い分け問題（前半）→ 各 pattern 解説 + session recap（后半）。

### Pattern Pool Selection
Prioritize patterns that:
- Appear frequently in N2 exams
- Have easily confused similar patterns (e.g., ～につれて vs ～にしたがって vs ～とともに)
- Are structurally different from Chinese equivalents (harder for Chinese speakers)

---

## Mode 3: 読解チャレンジ (Reading Challenge)

### Goal
Train reading throughput: extract information quickly from N2-level text. Material generated on topics the user actually cares about.

### Execution

1. Ask user for topic preference: tech/AI, business, Japanese society, science, workplace
2. Generate a passage (300-500 characters) at N2 level:
   - Natural Japanese, not textbook style
   - Contains 3-5 N2 vocabulary items and 2-3 N2 grammar patterns
   - Has a clear argument or information structure

3. After passage, present 3 comprehension questions in N2 exam style:

```
問1（内容理解）：筆者が最も言いたいことは何か。
  A. ...
  B. ...
  C. ...
  D. ...

問2（詳細理解）：「〜」とあるが、それはなぜか。
  A. ...
  B. ...
  C. ...
  D. ...

問3（推論）：この文章から推測できることは何か。
  A. ...
  B. ...
  C. ...
  D. ...
```

4. After user answers, provide:
   - Correct answers with explanation (in Chinese for clarity)
   - Structural analysis of the passage: how the argument is built
   - Key vocabulary and grammar from the passage
   - Offer to generate Anki cards for vocabulary encountered

### File Output
开始时即创建 `./tmp/N2_dokkai_<date>.md`。文件结构: 文章 + 問題（前半）→ 正解 + 解説 + 語彙リスト（后半）。

### Passage Generation Rules
- Avoid textbook-style "safe" topics. Use real-world content the user would actually want to read
- Include opinion/argument passages (主張理解 style) and information retrieval passages (情報検索 style)
- Occasionally include charts or structured data for 情報検索 practice (describe in text)

---

## Mode 4: 語彙コンテキスト (Vocabulary in Context)

### Goal
Train vocabulary recognition speed. Not definition recall, but meaning-in-context recognition.

### Execution

Present 10 questions, one at a time. Each question: one sentence with a target word, user picks the meaning.

```
Q1. 彼の提案は会議で却下された。

「却下」の意味に最も近いものはどれか。
A. 承認された
B. 拒否された
C. 延期された
D. 修正された
```

Question design rules:
- Target word must be N2 level
- Sentence context should allow inference even if word is unknown (tests context inference ability)
- Distractors must be plausible in the sentence structure
- Mix question types:
  - 文脈規定 (meaning from context): 5 questions
  - 言い換え類義 (paraphrase/synonym): 3 questions
  - 用法 (correct usage): 2 questions

### File Output
开始时即创建 `./tmp/N2_goi_<date>.md`。文件结构: 全 10 題（前半）→ 正解 + session summary（后半）。

After 10 questions:

```
📊 語彙 Session: 7/10
- 即答（<3秒）: 5問
- 考えて正解: 2問
- 不正解: 3問 → [list words]

→ 不正解の語彙を Anki に追加？（/anki）
```

---

## Mode 5: 模擬試験 (Mock Exam)

### Goal
N2-style exam questions. Calibrate test-taking strategy and identify weak areas.

### Section Selection

Ask user to choose section, or default to mixed:

```
模擬試験 — セクション選択

A. 文字・語彙（漢字読み・表記・語形成・文脈規定・言い換え・用法）
B. 文法（文法形式判断・文の組み立て・文章の文法）
C. 読解（短文理解・中文理解・統合理解・長文理解・情報検索）
D. 聴解（テキストベース：課題理解・ポイント理解・即時応答）
E. 総合（全セクション混合）
```

### Section A: 文字・語彙 (10 questions)

Question type distribution:
- 漢字読み × 2: underlined kanji, pick correct reading
- 表記 × 1: underlined hiragana, pick correct kanji
- 語形成 × 1: word formation (prefix/suffix)
- 文脈規定 × 3: word meaning from context
- 言い換え × 2: paraphrase
- 用法 × 1: correct sentence using the word

Format per question:
```
問1.（漢字読み）
友人の不注意で貴重な資料が紛失した。
「紛失」の読み方として最も適当なものを選べ。
A. ふんしつ
B. ふんしゅつ
C. ぶんしつ
D. ふんしち
```

### Section B: 文法 (10 questions)

Question type distribution:
- 文法形式の判断 × 5: pick correct grammar form to complete sentence
- 文の組み立て × 3: reorder scrambled sentence parts (★ position)
- 文章の文法 × 2: pick correct word/phrase for blank in a paragraph

Format for 文の組み立て:
```
問6.（文の組み立て）
次の文の ★ に入る最も適当なものを選べ。

経験が ＿＿ ＿＿ ★ ＿＿ わけではない。
A. あるからといって
B. 必ずしも
C. 成功する
D. 豊富で

（★ に入るものは？）
```

### Section C: 読解 (10 questions across passage types)

Generate 3 passages:
- 短文 (150-200 chars) → 2 questions
- 中文 (400-500 chars) → 4 questions
- 長文 (600-800 chars) → 4 questions

Follow the same rules as Mode 3 (Reading Challenge) for passage generation.

### Section D: 聴解 (10 questions, audio-first)

Uses edge-tts to generate real audio. Flow mimics actual N2 listening exam.

**Execution flow per question:**

1. Generate dialogue audio (Keita for 男, Nanami for 女), save to `./tmp/N2_moshi_listening_<date>/`
2. Play audio via afplay (user listens, no transcript visible)
3. Display question + options only:
```
問1.（課題理解）
質問：男の人はこの後まず何をしますか。
A. 部長の会議が終わるのを待つ
B. メールで書類を送る
C. 課長に書類を見せる
D. 外出先で部長に会う
```
4. User answers
5. Show transcript + explanation in answers section at file end
6. Offer 「もう一度聞く？」 to replay

**Dialogue example (internal, for audio generation):**
```
男：すみません、この書類、部長に確認してもらいたいんですが。
女：部長は今会議中で、3時に終わる予定です。でも、その後すぐ外出されるそうです。
男：じゃあ、メールで送っておいた方がいいですかね。
女：そうですね。でも急ぎなら、課長に先に見てもらうこともできますよ。
```

**Speed progression:** Q1-Q3 at --rate=-10% (slow), Q4-Q7 at --rate=+0% (normal), Q8-Q10 at --rate=+10% (fast)

### Output Rules (all sections)

- Output all questions first, answers at file end (same as AWS prompt pattern)
- File name format: `N2_moshi_<section>_<YYYYMMDD_HHmm>.md`（section = vocab/grammar/reading/listening/mixed）
- Save to: `./tmp/`

Answer format:
```
問1:
- 正解: B
- 解説: [1-2 sentences, in Chinese for clarity]
- キーポイント: [grammar pattern or vocabulary note]

（問2-10 同形式）
```

### Strict Prohibitions (same spirit as AWS prompts)
- No teaching tone in questions
- No obvious giveaway wording
- All distractors must be plausible
- No questions testable by elimination of absurd options
- Grammar questions must test boundary cases, not textbook examples
- Reading passages must require actual comprehension, not keyword matching

---

## Mode 6: 素材マイニング (Content Mining)

### Goal
Extract learning points from Japanese content the user provides. Bridge real consumption to structured learning.

### Execution

1. User provides Japanese text (article, transcript, manga dialogue, email, etc.)
2. Analyze and output:

```
📊 素材分析

【難易度】N2-N1（推定）

【語彙ピックアップ】（N2 レベル以上）
- 却下（きゃっか）— 拒否・不承認 [N2]
- 懸念（けねん）— 心配・不安 [N2]
- 見込み（みこみ）— 予想・期待 [N2]

【文法パターン】
- ～にもかかわらず（第3段落）— 逆接の強調。「～のに」より硬い表現
- ～ざるを得ない（第5段落）— 「～しなければならない」のフォーマル版

【構文分析】（最も複雑な文を1つ選んで分解）
原文: 技術革新が急速に進む中、従来の方法に固執するあまり、本来得られるはずだった成果を逃してしまう企業も少なくない。
分解:
  技術革新が急速に進む中 → 状況設定
  従来の方法に固執するあまり → 原因（～あまり = 过度～导致）
  本来得られるはずだった成果を → 目的語（はずだった = 本应）
  逃してしまう企業も少なくない → 主述（～てしまう = 遗憾结果, 少なくない = 不少）

【Anki 導出】
→ /anki で上記語彙＋例文を闪卡化可能
```

### File Output
分析结果写入 `./tmp/N2_sozai_<date>.md`。文件结构: 原文引用 → 語彙ピックアップ → 文法パターン → 構文分析 → Anki candidates。

3. If user says "Anki" or "/anki", hand off extracted vocab to Anki flashcard skill

---

## Difficulty Calibration Across Modes

All modes share a calibration principle:

- Start at solid N2 level
- If user scores >80% → push toward N1 boundary
- If user scores <50% → pull back toward N3-N2 boundary
- Adapt within the session based on performance
- Always note the difficulty shift in session summary

## Integration with Anki Skill

Any mode that surfaces vocabulary can feed into `/anki`:
- 会話 session summary → vocab list → Anki
- 文法 patterns with example sentences → Anki
- 読解 passage vocabulary → Anki
- 語彙 missed words → Anki
- 素材 extracted vocabulary → Anki

When user requests Anki export, format the vocab list as input for the Anki flashcard skill, then invoke `/anki`.
