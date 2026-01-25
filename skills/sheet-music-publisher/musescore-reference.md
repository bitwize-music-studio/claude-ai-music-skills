# MuseScore Polish Reference

Techniques for editing and polishing sheet music transcriptions in MuseScore.

## Installation

### Download & Install

**Website**: [musescore.org](https://musescore.org/)

**Cost**: Free, open source

**Supported platforms:**
- Windows (7, 8, 10, 11)
- macOS (10.12+)
- Linux (AppImage, Ubuntu/Debian, Fedora, Arch)

**Current versions:**
- MuseScore 4 (latest, recommended)
- MuseScore 3 (stable, still supported)

**No account required** for basic use. Optional MuseScore.com account for cloud features.

---

## Opening AnthemScore Output

### Import MusicXML

**File → Open**
- Navigate to `.xml` or `.musicxml` file
- MuseScore auto-detects format
- Import settings usually correct (accept defaults)

**First review:**
- Play through (Space bar)
- Check key signature
- Check time signature
- Verify tempo marking

---

## Essential Corrections

### Key Signature

**Problem**: AI often guesses wrong, especially for modes or key changes

**Fix**:
1. Select measure where key change should occur
2. **Edit → Key Signature** (or press `K`)
3. Choose correct key from palette
4. Apply to: "All staves" or "Just this staff"

**Tip**: If fundamentally wrong key (e.g., C major instead of A minor), you may need to transpose the entire score.

### Time Signature

**Problem**: AI can misinterpret syncopation as different time signature

**Fix**:
1. Select measure
2. **Edit → Time Signature** (or press `T`)
3. Choose correct time signature
4. Apply: "From this measure onward" or "Just this measure"

**Common fixes:**
- 4/4 mistaken for 2/4 (or vice versa)
- Swing feel transcribed as triplets in 4/4

### Tempo Marking

**Problem**: Often missing or incorrect BPM

**Fix**:
1. Select first measure (or where tempo changes)
2. **Add → Text → Tempo Marking**
3. Type tempo (e.g., "♩ = 120" or "Moderate")
4. MuseScore auto-converts text to symbols

**Standard terms:**
- Largo (40-60 BPM)
- Adagio (60-80 BPM)
- Moderato (90-110 BPM)
- Allegro (120-140 BPM)

---

## Note Corrections

### Wrong Note Pitches

**Fix individual notes:**
1. Click note to select
2. Press **Up/Down arrow** to move by half-step
3. Press **Ctrl/Cmd + Up/Down** to move by octave

**Fix chords:**
1. Click one note in chord
2. Shift + click other notes to select all
3. Arrow keys move entire selection

### Wrong Note Durations

**Shortcuts (with note selected):**
- `5` = Quarter note
- `6` = Eighth note
- `7` = Sixteenth note
- `4` = Half note
- `3` = Whole note
- `.` = Dotted note (toggle)

**Visual guide:**
- ♩ = Quarter note (`5`)
- ♪ = Eighth note (`6`)
- ♬ = Sixteenth note (`7`)
- 𝅗𝅥 = Half note (`4`)

### Adding Missing Notes

**Enter note input mode:**
1. Press `N` (or click note input icon)
2. Click staff where note should go
3. Type letter name (A-G)
4. Use Up/Down arrows to adjust octave
5. Use number keys for duration (4-7)
6. Press Esc when done

### Deleting Wrong Notes

1. Click note to select
2. Press **Delete** or **Backspace**
3. May need to add rests to complete measure

---

## Rest Corrections

### Incomplete Measures

**Problem**: Measure shows "duration error" (doesn't add up to time signature)

**Fix**:
1. Select measure
2. **Tools → Regroup Rhythms** (auto-fixes common issues)
3. Or manually add rests to complete

**Add rests:**
- Press `0` (zero) in note input mode
- Or: Delete a note, rest auto-inserted

### Simplify Rest Notation

**Problem**: Multiple short rests instead of one long rest

**Fix**:
- **Tools → Regroup Rhythms** (auto-consolidates)
- Manually: Delete short rests, add longer rest

---

## Formatting & Layout

### Page Breaks

**Add page break:**
1. Select barline where break should occur
2. **Add → Breaks & Spacers → Page Break**
3. Or: Press **Ctrl/Cmd + Return**

**Best practices:**
- Break at natural pause (end of verse, chorus)
- Avoid awkward page turns (mid-phrase)

### System Breaks (Line Breaks)

**Add system break:**
1. Select barline
2. **Add → Breaks & Spacers → System Break**
3. Or: Press **Return**

**Use when:**
- Separating sections (verse, chorus)
- Improving readability
- Controlling measures per line

### Spacing

**Increase/decrease space:**
- **Format → Style → Measure → Measure spacing**
- Increase for crowded measures
- Decrease to fit more on page

**Manual adjustments:**
- Select measure
- **Format → Stretch**
- Adjust to taste

---

## Performance Markings

### Dynamics

**Add dynamics:**
1. Select note or measure
2. **Add → Dynamics** (or press `Ctrl/Cmd + E`)
3. Choose from palette: *p*, *mp*, *mf*, *f*, *ff*, crescendo, etc.

**Common dynamics:**
- *pp* = Very soft
- *p* = Soft
- *mp* = Medium soft
- *mf* = Medium loud
- *f* = Loud
- *ff* = Very loud

**Hairpins (crescendo/diminuendo):**
- Select notes
- Click crescendo `<` or diminuendo `>` in palette
- Drag to adjust length

### Articulations

**Add articulation:**
1. Select note
2. Double-click articulation in palette
   - Staccato (dot above note)
   - Accent (`>`)
   - Tenuto (line)
   - Fermata (pause)

**Shortcuts:**
- `.` = Staccato
- `Shift + S` = Slur

### Pedal Markings (Piano)

**Add pedal line:**
1. Select note where pedal starts
2. **Lines → Pedal** (from palette)
3. Drag line to where pedal ends
4. Displays: "Ped." ... "*" (release)

---

## Lyrics (Optional)

**Add lyrics:**
1. Select first note of phrase
2. Press **Ctrl/Cmd + L**
3. Type syllable, press **Space** for next note
4. Press **-** (hyphen) for multi-syllable word
5. Esc when done

**Verses:**
- Ctrl/Cmd + L = Verse 1
- Add → Text → Lyrics → Verse 2 (etc.)

---

## Cleanup Tasks

### Beaming

**Problem**: Eighth notes beamed incorrectly (or not beamed)

**Fix**:
1. Select notes
2. **Format → Beam** → Choose beam style
   - Beam together
   - Break beam
   - Auto

**Best practice**: Beam by beat in 4/4 time

### Ties vs. Slurs

**Tie**: Connects same note across barline (held)
**Slur**: Connects different notes (phrasing)

**Add tie:**
1. Select first note
2. Press `+` (plus key)

**Add slur:**
1. Select first note
2. Press `S`
3. Drag to last note

### Remove Ghost Notes

**Problem**: AI transcribed noise as notes

**Fix**:
1. Play through, listen for wrong notes
2. Compare to original audio
3. Delete notes that aren't in original

---

## Title & Credits

### Score Properties

**Edit → Score Properties**

**Fields:**
- **Work Title**: Song name (no track number!)
- **Composer**: Artist name
- **Lyricist**: If different from composer
- **Copyright**: © Year Artist Name

**These appear:**
- On first page
- In PDF metadata
- In printed scores

### Header/Footer

**Format → Style → Header, Footer**

**Customize:**
- Page numbers
- Title on every page
- Copyright notice

---

## Export to PDF

### Export Settings

**File → Export → PDF**

**Settings:**
- Resolution: **300 DPI** (print quality)
- Page size: Letter (US) or A4 (international)
- All pages or range

**File naming:**
- Use clean title (no track numbers)
- E.g., `ocean-of-tears.pdf` not `01-ocean-of-tears.pdf`

---

## MuseScore CLI (For Automation)

### Batch PDF Export

**macOS:**
```bash
/Applications/MuseScore\ 4.app/Contents/MacOS/mscore -o output.pdf input.xml
```

**Linux:**
```bash
mscore -o output.pdf input.xml
```

**Batch process:**
```bash
for xml in *.xml; do
  mscore -o "${xml%.xml}.pdf" "$xml"
done
```

### Find MuseScore Executable

**Common locations:**
- macOS 4: `/Applications/MuseScore 4.app/Contents/MacOS/mscore`
- macOS 3: `/Applications/MuseScore 3.app/Contents/MacOS/mscore`
- Linux: `/usr/bin/musescore` or `which mscore`
- Windows: `C:\Program Files\MuseScore 4\bin\MuseScore4.exe`

---

## Keyboard Shortcuts Reference

### Navigation
- **Space**: Play/pause
- **Home**: Jump to start
- **End**: Jump to end
- **Page Up/Down**: Scroll score

### Note Input
- **N**: Toggle note input mode
- **A-G**: Enter note by letter
- **0**: Enter rest
- **4-7**: Note duration (whole, half, quarter, eighth)
- **. (dot)**: Toggle dotted note

### Editing
- **Ctrl/Cmd + C**: Copy
- **Ctrl/Cmd + V**: Paste
- **Ctrl/Cmd + X**: Cut
- **Delete**: Delete selection
- **Ctrl/Cmd + Z**: Undo
- **Ctrl/Cmd + Y**: Redo

### Pitch
- **Up/Down arrows**: Pitch by half-step
- **Ctrl/Cmd + Up/Down**: Pitch by octave

### Articulations
- **.**: Staccato
- **S**: Slur
- **+**: Tie

### Layout
- **Return**: System break
- **Ctrl/Cmd + Return**: Page break
- **K**: Key signature
- **T**: Time signature

---

## Common Fixes Checklist

**After importing from AnthemScore, check:**

- [ ] Key signature correct
- [ ] Time signature correct
- [ ] Tempo marking added
- [ ] All measures complete (no duration errors)
- [ ] Note pitches accurate (compare to audio)
- [ ] Note durations correct
- [ ] Beaming appropriate
- [ ] Dynamics added (at minimum: p, mf, f)
- [ ] Articulations added (staccato, accents)
- [ ] Page breaks at sensible locations
- [ ] Title/composer in score properties (no track numbers!)
- [ ] Copyright notice added
- [ ] Playback sounds correct (Space bar test)

---

## Quality Standards

### Minimum Viable

- Correct notes (mostly)
- Readable layout
- Title and composer
- Basic structure

### Publishing Ready

- Clean, professional notation
- Correct key/time signatures
- Dynamics and articulations
- Proper formatting
- Copyright notice
- Page turns at natural breaks
- Playable by intermediate pianist

---

## Troubleshooting

### "MuseScore won't open XML file"

**Check:**
- File extension is `.xml` or `.musicxml` (not `.mid`)
- File isn't corrupted (try opening in text editor - should see XML tags)
- Using MuseScore 3+ (older versions may not support MusicXML 3.0)

### "Playback sounds wrong"

**Check:**
- Instrument assigned correctly (piano?)
- Soundfont loaded (MuseScore → Preferences → I/O)
- MIDI device configured

**Fix:**
- Don't trust playback 100% - compare to original audio
- Playback is for verification only

### "Notes are in wrong clef"

**Fix:**
1. Right-click staff
2. **Staff/Part Properties**
3. Change clef to treble or bass
4. Apply

### "Can't export PDF - error"

**Check:**
- Disk space available
- Output directory exists and writable
- MuseScore has permissions
- No special characters in filename

---

## Learning Resources

**Built-in handbook:**
- Help → Handbook (comprehensive guide)

**Video tutorials:**
- MuseScore YouTube channel
- Search: "MuseScore piano tutorial"

**Community:**
- MuseScore.org forums
- Discord server
- Facebook groups

---

## Best Practices

### Workflow

1. **Import** MusicXML from AnthemScore
2. **Play through** - identify obvious errors
3. **Fix structure** - key sig, time sig, tempo
4. **Correct notes** - compare to original audio
5. **Add markings** - dynamics, articulations
6. **Format** - page breaks, spacing
7. **Properties** - title, composer, copyright
8. **Export PDF** - 300 DPI, clean filename
9. **Save project** - keep `.mscz` for future edits

### Save Your Work

**File → Save** (or Ctrl/Cmd + S)

**Save as `.mscz` format** - This is MuseScore's native format, editable later.

**Keep both:**
- `.mscz` - Source file (editable)
- `.pdf` - Deliverable (publishing-ready)

### Version Control

**For significant changes:**
- Save numbered versions: `track-v1.mscz`, `track-v2.mscz`
- Or use git for `.mscz` files (they're ZIP archives, version-friendly)

---

## Integration with Sheet Music Workflow

### Position in Workflow

```
WAV → AnthemScore → MusicXML → MuseScore → Final PDF
                                    ↑
                              You are here
```

### When to Polish

**Always polish if:**
- Publishing to KDP or selling
- Professional licensing package
- Teaching materials

**Maybe polish:**
- Personal reference sheets
- Quick transcriptions for learning

**Skip polish if:**
- Just need rough notation
- Time-constrained
- Audio quality was poor (transcription too messy)

---

## Quick Reference Card

| Task | Action |
|------|--------|
| Play/pause | Space |
| Note input | N |
| Add dynamic | Ctrl/Cmd + E |
| Add lyrics | Ctrl/Cmd + L |
| Pitch up/down | Arrow keys |
| Octave up/down | Ctrl/Cmd + Arrow |
| Staccato | . (period) |
| Slur | S |
| Tie | + (plus) |
| Key signature | K |
| Time signature | T |
| Page break | Ctrl/Cmd + Return |
| System break | Return |
| Undo | Ctrl/Cmd + Z |
| Save | Ctrl/Cmd + S |
| Export PDF | File → Export → PDF |
