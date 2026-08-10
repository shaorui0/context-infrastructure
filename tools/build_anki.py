#!/usr/bin/env python3
"""Build Anki .apkg from tmp-out.txt with Japanese TTS audio (Kyoko)."""
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

import genanki

ROOT = Path(__file__).parent
# 输入源:默认 tmp-out.txt(向后兼容)。可用 ANKI_SRC 环境变量覆盖,
# 便于用 fixtures/sample_deck.tsv 等验收。
SRC = Path(os.environ.get("ANKI_SRC", ROOT / "tmp-out.txt"))
OUT_APKG = Path(os.environ.get("ANKI_OUT", ROOT / "n2_vocab_28.apkg"))

# ── tag 校验器接入(producer/tag_validator.py) ─────────────────────────
# 校验器位于 anki-learning-harness/producer/。把它加进 sys.path 以便 import。
_VALIDATOR_DIR = (
    ROOT.parent
    / "work-contexts"
    / "toy-proj"
    / "anki-learning-harness"
    / "producer"
)
if _VALIDATOR_DIR.is_dir():
    sys.path.insert(0, str(_VALIDATOR_DIR))
try:
    import tag_validator  # type: ignore
except Exception:  # 校验器缺失时不阻断旧用法(宽松降级)
    tag_validator = None


def _is_n2_deck(rows) -> bool:
    """启发式:任一行含 ability:: tag → 视为 n2 deck,走严格校验。"""
    return any("ability::" in tags for *_rest, tags in rows)


def _validate_or_abort(rows) -> None:
    """n2 deck 在生成前强制校验;失败则阻断,不生成。非 n2 走宽松模式。"""
    if not _is_n2_deck(rows):
        print("ℹ️  无 ability:: tag,按非-n2 宽松模式跳过严格校验。", flush=True)
        return
    if tag_validator is None:
        print(
            "❌ 检测到 n2 卡(含 ability::)但找不到 tag_validator,拒绝生成。",
            file=sys.stderr,
        )
        sys.exit(1)
    cards = [(f"L{i}", tags.split()) for i, (*_r, tags) in enumerate(rows, 1)]
    violations = tag_validator.validate_cards(cards)
    if violations:
        print(
            f"❌ tag 校验失败 — {len(violations)} 条违规,阻断生成:",
            file=sys.stderr,
        )
        for v in violations:
            print(f"  {v}", file=sys.stderr)
        sys.exit(1)
    print(f"✅ tag 校验通过 — {len(rows)} 张 n2 卡。", flush=True)
AUDIO_DIR = ROOT / ".anki_audio"
AUDIO_DIR.mkdir(exist_ok=True)

VOICE = "Kyoko"

def tts(text: str) -> Path:
    """Generate mp3 for text via macOS `say` + ffmpeg. Cached by hash."""
    h = hashlib.md5(text.encode("utf-8")).hexdigest()[:16]
    mp3 = AUDIO_DIR / f"a_{h}.mp3"
    if mp3.exists():
        return mp3
    aiff = AUDIO_DIR / f"a_{h}.aiff"
    subprocess.run(["say", "-v", VOICE, "-o", str(aiff), text], check=True)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(aiff),
         "-codec:a", "libmp3lame", "-qscale:a", "5", str(mp3)],
        check=True,
    )
    aiff.unlink()
    return mp3

# Note model with auto-play audio on back
MODEL_ID = 1607392319
DECK_ID = 2059400110

model = genanki.Model(
    MODEL_ID,
    "JP Vocab + Audio (rshao)",
    fields=[
        {"name": "Front"},
        {"name": "Back"},
        {"name": "Reading"},
        {"name": "Audio"},
        {"name": "Tags"},
    ],
    templates=[
        {
            "name": "Front → Back",
            "qfmt": '<div class="front">{{Front}}</div>',
            "afmt": (
                '<div class="front">{{Front}}</div><hr id="answer">'
                '<div class="reading">{{Reading}}</div>'
                '<div class="back">{{Back}}</div>'
                '<div class="audio">{{Audio}}</div>'
            ),
        },
        {
            "name": "Back → Front",
            "qfmt": '<div class="back">{{Back}}</div>',
            "afmt": (
                '<div class="back">{{Back}}</div><hr id="answer">'
                '<div class="front">{{Front}}</div>'
                '<div class="reading">{{Reading}}</div>'
                '<div class="audio">{{Audio}}</div>'
            ),
        },
    ],
    css="""
.card { font-family: -apple-system, "Hiragino Sans", sans-serif;
        font-size: 22px; text-align: center; color: #222; background: #fafafa; }
.front { font-size: 30px; font-weight: 600; margin: 12px 0; }
.reading { font-size: 20px; color: #0a7; margin: 8px 0; }
.back { font-size: 18px; color: #444; margin: 10px 0; white-space: pre-wrap; }
.audio { margin-top: 10px; }
hr#answer { border: 0; border-top: 1px solid #ccc; margin: 14px 0; }
""",
)

deck = genanki.Deck(DECK_ID, "N2 Vocab 28 (例句拆解)")
media_files: list[str] = []
seen_audio: set[str] = set()

def parse():
    rows = []
    with SRC.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 4:
                continue
            front, back, reading, tags = parts[0], parts[1], parts[2], parts[3]
            rows.append((front, back, reading, tags))
    return rows

rows = parse()
print(f"Parsed {len(rows)} cards from {SRC.name}", flush=True)
# n2 deck 生成前强制 tag 校验,失败则阻断(契约 tag_schema.md 规则4)
_validate_or_abort(rows)

for i, (front, back, reading, tags) in enumerate(rows, 1):
    # Audio source: prefer Reading (kana). If empty, fall back to Front.
    src_text = reading.strip() or front.strip()
    # Strip parenthetical annotations / slashes for cleaner TTS
    tts_text = re.sub(r"[（(].*?[)）]", "", src_text)
    tts_text = tts_text.replace("／", " ").replace("/", " ")
    tts_text = re.sub(r"\s+", " ", tts_text).strip()
    audio_field = ""
    if tts_text:
        try:
            mp3_path = tts(tts_text)
            fname = mp3_path.name
            if fname not in seen_audio:
                media_files.append(str(mp3_path))
                seen_audio.add(fname)
            audio_field = f"[sound:{fname}]"
        except Exception as e:
            print(f"  ! TTS failed row {i}: {e}", file=sys.stderr)
    note = genanki.Note(
        model=model,
        fields=[front, back, reading, audio_field, tags],
        tags=tags.split(),
    )
    deck.add_note(note)
    if i % 25 == 0:
        print(f"  built {i}/{len(rows)}", flush=True)

pkg = genanki.Package(deck)
pkg.media_files = media_files
pkg.write_to_file(str(OUT_APKG))
print(f"\n✅ wrote {OUT_APKG}  ({len(rows)} notes, {len(media_files)} audio files)")
