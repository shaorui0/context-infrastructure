# 日语 Anki Decks — 个人语料库

我自己的日语学习闪卡语料，**corpus-as-code**：语料以 Python 生成器的 `CARDS` 列表形式长期沉淀，改一条/加一条直接编辑列表再跑，产物（csv/apkg）落到 `out/`。

## 设计

- 每条 note → **两张卡**：认读（日语+语音 → 中文/拆解）+ 回忆（中文 → 日语+语音）
- 语音：edge-tts `ja-JP-NanamiNeural`（自然女声，语速 -10%，仿《大家的日语》deck）
- 打包/导入脚本复用 skill：`~/.claude/skills/anki_japanese_flashcard/anki_import.py`
- guid 按 front 文本固定 → 增量导入去重，不会重复建卡

## 生成器

| 文件 | Deck 名 | 内容 |
|------|---------|------|
| `gen_daily_conversation.py` | 日语日常口语 | 篮球/日常实用句 + 口语连接词/相槌（源自 tmp.txt + 高频接续词） |
| `gen_personal_top100.py` | 日语·我的场景100 | 基于个人 context 提炼的 TOP 100 句/场景（在日生活、行政、租房、工作、社交） |

## 用法

```bash
cd /Users/rshao/work/context-infrastructure

# 1. 生成 CSV（编辑生成器里的 CARDS 列表后重跑即可）
.venv/bin/python contexts/japanese/anki_decks/gen_daily_conversation.py

# 2. 生成 TTS 语音 + 打包 .apkg + 触发 Anki 导入
.venv/bin/python ~/.claude/skills/anki_japanese_flashcard/anki_import.py \
  --csv contexts/japanese/anki_decks/out/daily_conversation.csv \
  --deck "日语日常口语" \
  --audio \
  --output contexts/japanese/anki_decks/out/daily_conversation.apkg \
  --open
```

## 扩充语料

直接往对应生成器的 `CARDS` 列表追加 `(front, reading_kana, meaning, structure_html, expand_html, tags)` 元组：
- `reading_kana`：纯假名，无汉字无括号（TTS 用）
- `tags`：空格分隔，含来源 + 场景，用于在 Anki 里按场景筛选练习
- 内嵌引号用日文「」，别用 ASCII 双引号（会破坏 Python 字符串）
