# Sheet Music Troubleshooting

Common transcription problems and how to fix them.

---

## AnthemScore Issues

### Transcription Is a Mess (Too Many Notes)

**Symptom**: Sheet music is cluttered with incorrect notes, impossible to play.

**Cause**: Sensitivity too high, dense arrangement, or noisy source audio.

**Fixes**:

1. **Lower sensitivity** - Move slider left until only main melody appears
2. **Use stem separation** - Run `demucs track.wav` first, transcribe `vocals.wav` or `other.wav`
3. **Limit frequency range** - Use `-j` and `-k` flags to focus on specific octaves
4. **Accept limitations** - Some tracks aren't suitable for auto-transcription

```bash
# Limit to middle piano range (middle C area)
$ANTHEMSCORE track.wav -a -j 30 -k 60 -r -p track.pdf
```

---

### Missing Notes

**Symptom**: Important melody notes are not detected.

**Cause**: Sensitivity too low, or notes are masked by other instruments.

**Fixes**:

1. **Raise sensitivity** - Gradually increase until melody appears
2. **Use stem separation** - Isolate the instrument you want
3. **Manual addition** - Add missing notes in MuseScore

---

### Wrong Octave

**Symptom**: Notes appear an octave too high or too low.

**Cause**: Harmonics confused the AI, or low-quality audio.

**Fixes**:

1. **In AnthemScore**: Select notes, drag to correct octave
2. **In MuseScore**: Select notes, press Ctrl/Cmd + Up/Down to shift octave
3. **Verify**: Compare against original audio while editing

---

### Ghost Notes (False Positives)

**Symptom**: Extra notes that aren't in the original recording.

**Cause**: Harmonics, room noise, or compression artifacts detected as notes.

**Fixes**:

1. **Lower sensitivity** - Remove faint detections
2. **Filter short notes** - Set minimum note length to 0.1-0.2 seconds
3. **Manual deletion** - Remove in AnthemScore or MuseScore

---

### Tempo Detection Failed

**Symptom**: Wrong tempo, misaligned bars, notes don't line up with beats.

**Cause**: Complex rhythm, tempo changes, or unconventional time signature.

**Fixes**:

1. **Manual tempo entry** - Click tempo field in AnthemScore, enter correct BPM
2. **Listen to original** - Tap along to determine actual tempo
3. **Fix in MuseScore** - More precise tempo adjustment available

---

## Rhythm Issues

### Notes Have Wrong Duration

**Symptom**: Quarter notes shown as eighths, or vice versa.

**Cause**: Sustained notes with natural decay, or staccato playing interpreted as short notes.

**Fixes in MuseScore**:

1. **Select note**
2. **Use number keys** to change duration:
   - 4 = sixteenth note
   - 5 = eighth note
   - 6 = quarter note
   - 7 = half note
   - 8 = whole note
3. **Tie notes** if needed: Select note, press T

---

### Syncopation Lost

**Symptom**: Off-beat rhythms quantized to on-beat positions.

**Cause**: Aggressive quantization in transcription.

**Fixes**:

1. **Use smallest note value** - Set AnthemScore to 16th notes: `-w 16`
2. **Manual adjustment** - Move notes to correct beat positions in MuseScore
3. **Reference original** - Listen while editing to match feel

---

### Triplets Not Detected

**Symptom**: Triplet rhythms shown as irregular note lengths.

**Cause**: Standard transcription doesn't detect tuplets automatically.

**Fix in MuseScore**:

1. Delete incorrect notes
2. Press N for note input
3. Press Ctrl/Cmd + 3 for triplet mode
4. Enter notes
5. Press Ctrl/Cmd + 3 again to exit triplet mode

---

### Swing Feel Lost

**Symptom**: Swing rhythm transcribed as straight eighths.

**Cause**: Swing is performance style, not easily notated.

**Fixes**:

1. **Add swing text marking** - "Swing" or specific swing ratio
2. **Write as dotted eighth + sixteenth** - More accurate but harder to read
3. **Accept straight eighths** - Performer will add swing naturally

---

## Key Signature Issues

### Wrong Key Signature

**Symptom**: Too many accidentals, key signature doesn't match song.

**Cause**: AI detection isn't perfect, especially for modes or key changes.

**Fix in MuseScore**:

1. Press K (key signature tool)
2. Select correct key
3. Apply to selection or entire piece
4. Notes will be respelled with new key

---

### Modal Music Transcribed Incorrectly

**Symptom**: Dorian, Mixolydian, etc. modes shown with wrong key signature.

**Cause**: AI assumes major/minor; modes are ambiguous.

**Fix**:

1. Choose closest major/minor key signature
2. Use accidentals for modal notes
3. Or: Use key signature that minimizes accidentals

---

### Key Change Not Detected

**Symptom**: Song modulates but key signature doesn't change.

**Fix in MuseScore**:

1. Click on barline where key changes
2. Press K
3. Select new key
4. Check "Show courtesy" for warning accidentals

---

## Time Signature Issues

### Wrong Time Signature

**Symptom**: Measures don't align with musical phrases.

**Cause**: Unusual time signature not detected correctly.

**Fix in MuseScore**:

1. Press T (time signature tool)
2. Select correct time signature
3. Apply at beginning of piece or specific measure
4. May need to reflow notes manually

---

### Mixed Meters Not Detected

**Symptom**: Song alternates between 4/4 and 3/4 but shown as one signature.

**Fix in MuseScore**:

1. Add time signature changes at each meter change
2. Select measure, press T, choose signature
3. Check "Show courtesy" for advance warning

---

### Pickup Measure Issues

**Symptom**: First measure has wrong beat count (anacrusis/pickup).

**Fix in MuseScore**:

1. Right-click first measure
2. Measure Properties
3. Set "Actual duration" to pickup length
4. Uncheck "Exclude from measure count" if desired

---

## MuseScore Editing Tips

### Quick Navigation

| Action | Shortcut |
|--------|----------|
| Next measure | Ctrl/Cmd + Right |
| Previous measure | Ctrl/Cmd + Left |
| Beginning | Ctrl/Cmd + Home |
| End | Ctrl/Cmd + End |
| Play/Stop | Space |

---

### Note Entry

| Action | Shortcut |
|--------|----------|
| Note input mode | N |
| Rest | 0 |
| Dot | . |
| Tie | T |
| Sharp | Up arrow |
| Flat | Down arrow |
| Octave up | Ctrl/Cmd + Up |
| Octave down | Ctrl/Cmd + Down |

---

### Common Edits

**Delete note/rest**: Select, press Delete

**Change duration**: Select note, press number key (4-8)

**Add chord tone**: In note input, click additional note or type letter

**Copy/paste**: Ctrl/Cmd + C, Ctrl/Cmd + V

**Undo**: Ctrl/Cmd + Z (unlimited)

---

### Adding Dynamics

1. Select note or passage
2. Go to Palette (F9 if not visible)
3. Expand Dynamics
4. Double-click desired marking (pp, p, mp, mf, f, ff)

---

### Adding Articulations

1. Select note
2. Go to Palette
3. Expand Articulations
4. Double-click desired marking (staccato, accent, tenuto)

---

### Page Layout Fixes

**Cramped measures**:
- Format > Style > Measure
- Increase "Spacing" value

**Page breaks**:
- Select barline
- Add > Breaks & Spacers > Page Break

**System breaks** (force new line):
- Select barline
- Add > Breaks & Spacers > System Break

---

## Export Issues

### PDF Looks Different Than Screen

**Cause**: Screen view doesn't match print layout.

**Fix**: Switch to "Page View" (View menu) before exporting to see true layout.

---

### PDF Text Is Missing

**Cause**: Fonts not embedded.

**Fix in MuseScore**:
- File > Export
- Select PDF
- Ensure "Embed fonts" is checked

---

### XML Won't Import to Another Program

**Cause**: MusicXML version incompatibility.

**Fix**: Export as MusicXML 3.1 (most compatible) rather than compressed format.

---

## Workflow Problems

### "File Won't Open" in AnthemScore

**Cause**: Unsupported format or corrupted file.

**Fixes**:
1. Convert to WAV if not already
2. Check file isn't corrupted (plays in media player?)
3. Ensure 16 or 24-bit depth (not 32-bit float)

---

### Processing Takes Forever

**Cause**: Very long track or complex audio.

**Fixes**:
1. Use `-s` and `-e` flags to process only a section
2. Increase thread count: `-z 8`
3. Process sections separately and combine

```bash
# Process first minute only
$ANTHEMSCORE track.wav -a -s 0 -e 60000 -p track_part1.pdf
```

---

### Out of Memory

**Cause**: Very long or high-sample-rate audio.

**Fixes**:
1. Downsample to 44.1kHz before processing
2. Split long tracks into sections
3. Close other applications

---

## Quick Reference

| Problem | Quick Fix |
|---------|-----------|
| Too many notes | Lower sensitivity |
| Missing notes | Raise sensitivity |
| Wrong octave | Ctrl+Up/Down in MuseScore |
| Wrong rhythm | Use number keys (4-8) |
| Wrong key | Press K, select correct key |
| Wrong time sig | Press T, select correct time |
| Dense arrangement | Use stem separation first |
| Won't transcribe well | Some tracks aren't suitable |
