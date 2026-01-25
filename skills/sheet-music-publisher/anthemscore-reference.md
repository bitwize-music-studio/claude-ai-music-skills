# AnthemScore CLI Reference

Complete reference for AnthemScore command-line interface and setup.

## Installation

### Purchase & Download

**Website**: [lunaverus.com](https://www.lunaverus.com/)

**Editions**:
| Edition | Price | Features | CLI Support |
|---------|-------|----------|-------------|
| Lite | $31 | Basic transcription, no editing | ✓ Yes |
| **Professional** | $42 | Full editing, spectrogram view | ✓ Yes (recommended) |
| Studio | $107 | Lifetime updates, priority support | ✓ Yes |

**Free trial**:
- 30 seconds per song
- 100 total transcriptions
- All features available
- No subscription needed

### Platform Support

- Windows (7, 8, 10, 11)
- macOS (10.13+)
- Linux (Ubuntu, Fedora, Arch)

**No subscription** - Buy once, use forever

---

## CLI Executable Locations

### macOS

```bash
/Applications/AnthemScore.app/Contents/MacOS/AnthemScore
```

**Verify installation:**
```bash
ls -l "/Applications/AnthemScore.app/Contents/MacOS/AnthemScore"
```

### Linux

```bash
/usr/bin/anthemscore
/usr/local/bin/anthemscore
```

**Find via PATH:**
```bash
which anthemscore
```

### Windows

```
C:\Program Files\AnthemScore\AnthemScore.exe
C:\Program Files (x86)\AnthemScore\AnthemScore.exe
```

---

## Basic CLI Usage

### Headless Mode (No GUI)

**Required flag**: `-a` or `--headless`

Without this flag, AnthemScore opens GUI. Use `-a` for batch automation.

### Simple Examples

**WAV → PDF only:**
```bash
AnthemScore track.wav -a -p output.pdf
```

**WAV → PDF + MusicXML:**
```bash
AnthemScore track.wav -a -p output.pdf -x output.xml
```

**WAV → PDF + MusicXML + MIDI:**
```bash
AnthemScore track.wav -a -p output.pdf -x output.xml -m output.mid
```

---

## All CLI Flags

### Output Formats

| Flag | Purpose | Example |
|------|---------|---------|
| `-p <file>` | Export PDF | `-p track.pdf` |
| `-x <file>` | Export MusicXML | `-x track.xml` |
| `-m <file>` | Export MIDI | `-m track.mid` |
| `-d <file>` | Save AnthemScore project | `-d track.asdt` |
| `-c <file>` | Save spectrogram CSV | `-c track.csv` |

### Transcription Options

| Flag | Purpose | Values |
|------|---------|--------|
| `-a, --headless` | No GUI (batch mode) | (boolean) |
| `-t` | Treble clef only | (boolean) |
| `-b` | Bass clef only | (boolean) |
| `-w <n>` | Smallest note value | `4`, `8`, `16` (default: 16) |

### Piano Key Range

| Flag | Purpose | Values |
|------|---------|--------|
| `-j <n>` | Lowest piano key | 1-88 (default: 1 = A0) |
| `-k <n>` | Highest piano key | 1-88 (default: 88 = C8) |
| `-r` | Remove notes outside range | (boolean) |
| `-o` | Move notes into range | (boolean) |

**Piano key numbers:**
- 1 = A0 (lowest key)
- 40 = Middle C
- 88 = C8 (highest key)

### Audio Processing

| Flag | Purpose | Example |
|------|---------|---------|
| `-s <ms>` | Start time (milliseconds) | `-s 5000` (skip first 5 sec) |
| `-e <ms>` | End time (milliseconds) | `-e 60000` (stop at 1 min) |
| `-l` | Print audio length and exit | (boolean) |

### Advanced

| Flag | Purpose | Values |
|------|---------|--------|
| `-z <n>` | Thread count | (default: auto) |
| `-n` | Don't find notes | Use with `-c` for spectrogram-only |

---

## Common Use Cases

### Batch Process Directory

```bash
#!/bin/bash
ANTHEMSCORE="/Applications/AnthemScore.app/Contents/MacOS/AnthemScore"

for wav in *.wav; do
  basename="${wav%.wav}"
  echo "Processing: $wav"
  "$ANTHEMSCORE" "$wav" -a -p "$basename.pdf" -x "$basename.xml"
done
```

### Treble Clef Only (Vocal Melody)

```bash
AnthemScore vocal.wav -a -t -p vocal.pdf
```

**Use when:**
- Transcribing vocal melodies only
- High-pitched instruments (flute, violin)
- Simpler output with one staff

### Bass Clef Only

```bash
AnthemScore bass.wav -a -b -p bass.pdf
```

**Use when:**
- Transcribing bass lines only
- Low-pitched instruments (cello, bass guitar)

### Limit to Piano Range

```bash
# Middle C (40) to C6 (76)
AnthemScore track.wav -a -j 40 -k 76 -r -p track.pdf
```

**Use when:**
- Avoiding ghost notes in extreme ranges
- Focusing on playable piano range

### Export MusicXML Only (No PDF)

```bash
AnthemScore track.wav -a -x track.xml
```

**Use when:**
- Planning to edit in MuseScore and export PDF there
- Faster processing (skip PDF rendering)

### Save Project for GUI Editing

```bash
AnthemScore track.wav -a -d track.asdt
```

**Then open in GUI:**
- Adjust sensitivity slider
- Manually correct errors
- Re-export

---

## Transcription Quality

### Accuracy Expectations

| Track Type | Expected Accuracy |
|------------|-------------------|
| Solo voice + piano | 90-95% |
| Acoustic folk/singer-songwriter | 85-90% |
| Clean pop/rock | 75-85% |
| Dense electronic | 60-75% |
| Heavy distortion | 50-70% |

**Factors affecting accuracy:**
- Audio quality (clear > muddy)
- Arrangement density (simple > complex)
- Frequency range (mid-range > extreme)
- Recording quality (studio > live)

### What Transcribes Well

✓ Clear vocal melodies
✓ Simple accompaniment
✓ Acoustic instruments
✓ Piano-based songs
✓ Singer-songwriter
✓ Folk, country, ballads

### What's Challenging

⚠ Polyphonic harmony
⚠ Dense arrangements
⚠ Heavy distortion
⚠ Rapid percussion
⚠ Electronic synth pads
⚠ Extreme frequency content

---

## Performance

### Processing Time

**Typical**: 30-60 seconds per track (3-5 minute song)

**Factors:**
- CPU speed (single-threaded mostly)
- Audio length
- Complexity (dense = slower)
- Output formats (PDF + XML + MIDI = longer)

### Speed Tips

**Faster:**
- Use `-p` only (skip MusicXML/MIDI if not needed)
- Limit key range with `-j`/`-k` flags
- Increase threads with `-z` flag

**Slower (but better):**
- Export all formats for flexibility
- Full piano range (no limits)
- Save project `.asdt` for later editing

---

## Troubleshooting

### "License activation failed"

**Solution**: Run GUI once to activate license

```bash
# macOS - open GUI
open -a AnthemScore

# After activation, CLI will work
```

### "File not found" error

**Check:**
- Full path to AnthemScore executable correct
- WAV file exists and readable
- Output directory exists (create with `mkdir -p`)

### "Transcription produced no notes"

**Possible causes:**
- Note sensitivity too low (can't adjust in CLI)
- Audio file is silent or very quiet
- File format not supported (use WAV, not MP3)

**Solution**: Open in GUI, adjust sensitivity slider, re-export

### Very slow processing

**Check:**
- File is reasonable length (not 30-minute track)
- System isn't under heavy load
- Disk space available

---

## Best Practices

### File Naming

**Good:**
```
01-ocean-of-tears.wav → 01-ocean-of-tears.pdf
track-name.wav → track-name.xml
```

**Bad:**
```
track 1.wav        # Spaces require quoting
FINAL-v2-MASTER.wav # Too long, unclear
```

### Output Organization

```
album/
├── mastered/
│   ├── 01-track.wav
│   └── 02-track.wav
└── sheet-music/
    ├── 01-track.pdf
    ├── 01-track.xml
    └── 02-track.pdf
```

Keep source WAVs separate from sheet music output.

### Batch Processing

**Do:**
- Process entire album at once
- Log output for debugging
- Use consistent naming

**Don't:**
- Process in GUI one-by-one (slow)
- Mix source and output in same folder
- Forget to save MusicXML for editing

### Quality Control

**After batch processing:**
1. Review PDFs for obvious errors
2. Check key signatures (AI detection isn't perfect)
3. Verify playback with MIDI files
4. Identify tracks needing manual polish
5. Edit MusicXML in MuseScore, re-export PDFs

---

## Integration with MuseScore

### Workflow

```
AnthemScore CLI → MusicXML → MuseScore → Polished PDF
```

**Why this workflow:**
- AnthemScore: Fast automated transcription
- MuseScore: Manual corrections and formatting
- Final PDF: Publishing-ready output

### MusicXML Benefits

- Preserves notation data (notes, rests, timing)
- Editable in any notation software
- Better than PDF for corrections
- Smaller file size than .asdt projects

### When to Skip MuseScore

**Skip if:**
- PDFs are "good enough" for reference
- Quick transcription for personal use
- Planning to transcribe by ear anyway

**Don't skip if:**
- Publishing to KDP
- Professional licensing
- Teaching materials
- Accuracy matters

---

## Advanced Techniques

### Stem Separation + Transcription

**For complex arrangements:**

```bash
# 1. Separate stems with Demucs
demucs track.wav

# 2. Transcribe each stem
AnthemScore separated/track/vocals.wav -a -p vocals.pdf -x vocals.xml
AnthemScore separated/track/bass.wav -a -p bass.pdf -x bass.xml

# 3. Combine in MuseScore manually
```

**Benefits:**
- Higher accuracy for dense mixes
- Separate melody from harmony
- Better bass line detection

### Limiting Range to Reduce Noise

```bash
# Remove very high/low notes that are likely errors
AnthemScore track.wav -a -j 21 -k 76 -r -p track.pdf
```

**Piano key reference:**
- 21 = A1 (low A on piano)
- 76 = C6 (two octaves above middle C)

### Custom Note Resolution

```bash
# Don't transcribe notes shorter than eighth notes
AnthemScore track.wav -a -w 8 -p track.pdf
```

**Values:**
- `-w 4` = Quarter notes (slow ballads)
- `-w 8` = Eighth notes (most songs)
- `-w 16` = Sixteenth notes (fast/detailed)

---

## Reference: Piano Key Numbers

| Key | Number | Note |
|-----|--------|------|
| Lowest | 1 | A0 |
| Very low | 21 | A1 |
| Low C | 28 | C2 |
| **Middle C** | **40** | **C4** |
| High | 76 | C6 |
| Very high | 84 | C7 |
| Highest | 88 | C8 |

**Typical vocal ranges:**
- Soprano: 48-79 (C4-G5)
- Alto: 43-74 (G3-D5)
- Tenor: 40-69 (C4-A4)
- Bass: 33-62 (A2-D4)

---

## Getting Help

**CLI help:**
```bash
AnthemScore --help
```

**Official documentation:**
- Website: https://www.lunaverus.com/
- Support: support@lunaverus.com

**Community:**
- Discord server (link on website)
- YouTube tutorials
- User forums
