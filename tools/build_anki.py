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
SRC = ROOT / "tmp-out.txt"
OUT_APKG = ROOT / "n2_vocab_28.apkg"
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
