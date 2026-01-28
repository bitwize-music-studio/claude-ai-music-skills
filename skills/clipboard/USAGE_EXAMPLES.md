# Clipboard Skill - Usage Examples

Platform-specific examples and troubleshooting for the `/bitwize-music:clipboard` skill.

---

## Platform Detection

The skill auto-detects your platform and uses the appropriate clipboard utility:

| Platform | Utility | Detection |
|----------|---------|-----------|
| macOS | `pbcopy` | Built-in, no install needed |
| Linux | `xclip` | Install: `sudo apt install xclip` |
| Linux (alt) | `xsel` | Install: `sudo apt install xsel` |
| WSL | `clip.exe` | Built-in Windows utility |

---

## Common Use Cases

### Copy Lyrics to Paste into Suno

```bash
/bitwize-music:clipboard lyrics my-album 03
```

Copies the Suno Lyrics Box content for track 03. Paste directly into Suno's lyrics field.

### Copy Style Prompt for Suno

```bash
/bitwize-music:clipboard style my-album 05
```

Copies the Suno Style Box content. Paste into Suno's style/genre field.

### Copy Both for Quick Generation

```bash
/bitwize-music:clipboard all my-album 01
```

Copies Style Box + separator + Lyrics Box. Useful when setting up a new generation.

### Copy Streaming Lyrics for Distributors

```bash
/bitwize-music:clipboard streaming-lyrics my-album 02
```

Copies clean lyrics (no section tags) formatted for DistroKid, TuneCore, etc.

---

## Platform-Specific Commands

### macOS

```bash
# Manual verification (what the skill does internally)
echo "test" | pbcopy
pbpaste  # Should show "test"
```

### Linux with xclip

```bash
# Install if missing
sudo apt install xclip

# Manual verification
echo "test" | xclip -selection clipboard
xclip -selection clipboard -o  # Should show "test"
```

### Linux with xsel

```bash
# Install if missing
sudo apt install xsel

# Manual verification
echo "test" | xsel --clipboard --input
xsel --clipboard --output  # Should show "test"
```

### WSL (Windows Subsystem for Linux)

```bash
# No install needed - uses Windows clipboard
echo "test" | clip.exe
# Paste in any Windows app to verify
```

---

## Troubleshooting

### "No clipboard utility found"

**Linux**: Install xclip or xsel:
```bash
sudo apt install xclip  # Debian/Ubuntu
sudo dnf install xclip  # Fedora
sudo pacman -S xclip    # Arch
```

**WSL**: Ensure you're running from WSL, not native Linux. `clip.exe` should be available.

### "Track not found"

Check your track number and album name:
```bash
# List available tracks
ls ~/music-projects/artists/bitwize/albums/*/my-album/tracks/
```

Track numbers are zero-padded: use `03` not `3`.

### "Content section not found"

The track file may not have the requested section yet. Check the track file:
```bash
# Look for section headings
grep -E "^#{3,4} (Style|Lyrics) Box" ~/path/to/track.md
```

### Clipboard Not Working in SSH

Remote SSH sessions don't have clipboard access. Options:
- Use X11 forwarding: `ssh -X user@host`
- Copy the output manually from the terminal
- Use a clipboard manager that syncs across machines

### Content Gets Truncated

Very long lyrics may hit shell limits. The skill handles this internally, but if issues persist:
- Check the source track file isn't corrupted
- Try copying smaller sections (style vs all)

---

## See Also

- [SKILL.md](SKILL.md) - Full skill documentation
- [/reference/suno/v5-best-practices.md](/reference/suno/v5-best-practices.md) - Suno prompting guide
