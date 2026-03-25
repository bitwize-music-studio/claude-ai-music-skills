# Troubleshooting

## Config Not Found

**Problem:** "Config not found at ~/.bitwize-music/config.yaml"

**Solution:**
```bash
mkdir -p ~/.bitwize-music
cp config/config.example.yaml ~/.bitwize-music/config.yaml
nano ~/.bitwize-music/config.yaml  # edit with your settings
```

Or use the interactive config tool:
```
/bitwize-music:configure
```

## Album Not Found When Resuming

**Problem:** `/bitwize-music:resume my-album` can't find the album

**Possible causes:**
1. **Wrong album name** — album names are case-sensitive. Try `/bitwize-music:resume` (without name) to see all albums
2. **Wrong path in config** — check `paths.content_root` in `~/.bitwize-music/config.yaml`
3. **Album in wrong location** — albums must be in: `{content_root}/artists/{artist}/albums/{genre}/{album}/`

## Path Resolution Issues

**Problem:** Files created in wrong locations, "path not found" errors

**The rule:** Always read `~/.bitwize-music/config.yaml` first to get paths. Never assume or hardcode.

```
{content_root}/artists/{artist}/albums/{genre}/{album}/    # Content
{audio_root}/artists/{artist}/albums/{genre}/{album}/      # Audio (mirrored)
{documents_root}/artists/{artist}/albums/{genre}/{album}/  # Documents (mirrored)
```

## Python Dependency Issues (Mastering)

**Problem:** Mastering fails with import errors

**Solution:**
```bash
python3 -m venv ~/.bitwize-music/venv
~/.bitwize-music/venv/bin/pip install -r requirements.txt
```

## Playwright Setup (Document Hunter)

**Problem:** `/bitwize-music:document-hunter` fails with browser errors

**Solution:**
```bash
pip install playwright
playwright install chromium
```

## Plugin Updates Breaking Things

**Common causes:**
1. Config schema changed — compare your config with `config/config.example.yaml`
2. Template changes — existing albums may use old format
3. Skill renamed or removed — check [CHANGELOG.md](../CHANGELOG.md)

## Skills Not Showing Up

**Check:**
1. Plugin installed correctly: `/plugin list`
2. Skill files exist: `ls ~/.claude/plugins/bitwize-music@claude-ai-music-skills/skills/`
3. Try restarting Claude Code

## Still Stuck?

[Open an issue](https://github.com/bitwize-music-studio/claude-ai-music-skills/issues) with:
- What you tried to do
- What happened (error messages, unexpected behavior)
- Your OS and Claude Code version
- Relevant config (redact personal info)
