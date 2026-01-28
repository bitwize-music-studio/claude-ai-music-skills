# Project History

Brief history and design philosophy of the bitwize-music plugin.

---

## Origins

The bitwize-music plugin started as a personal workflow for creating AI-generated music albums using Suno and Claude. What began as a collection of prompts and templates evolved into a structured system for managing the entire album creation process.

The core insight: AI music generation isn't just about prompting - it's about workflow. Managing concepts, research, lyrics, generation attempts, mastering, and release requires organization that scales.

---

## Version Milestones

### v0.1.0 - Foundation
Initial release with core skills: lyric-writer, researcher, suno-engineer, album-conceptualizer. Established the template-based approach and track file format.

### v0.5.0 - Infrastructure
Major infrastructure additions:
- Config system (`~/.bitwize-music/config.yaml`)
- Path separation (content, audio, documents)
- Import skills (audio, track, art)
- Test framework
- Sheet music publisher

### v0.7.0 - Customization
Override system introduced:
- User-customizable files in `{content_root}/overrides/`
- Plugin updates don't overwrite user preferences
- 10 skills support overrides

### v0.8.0 - Workflow Polish
Album ideas tracking, clipboard skill, workflow documentation extracted to reference files. CLAUDE.md refactored for performance.

### v0.12.0 - Onboarding
Focus on new user experience:
- Resume skill for finding albums
- Troubleshooting guide
- Getting Started checklist
- Common Mistakes sections in skills

### v0.13.0 - Promo Videos
Social media integration:
- Promo video generation
- 9 visualization styles
- Album sampler videos
- Cloud upload support

---

## Design Decisions

### Why Markdown Files?

Markdown is:
- Human-readable without special tools
- Version-controllable with git
- Editable in any text editor
- Parseable by Claude

Track files as markdown means your lyrics and prompts are never locked in a proprietary format.

### Why Separate Content from Plugin?

Early versions mixed plugin code with user content. This caused problems:
- Plugin updates overwrote user files
- Git conflicts on every update
- Unclear what was "mine" vs "template"

The current architecture keeps plugin code in one place and user content in another. Update the plugin freely; your albums stay untouched.

### Why Config Outside Plugin Directory?

`~/.bitwize-music/config.yaml` lives outside the plugin because:
- Same location whether plugin is installed or cloned
- Plugin updates can't overwrite config
- Easy to back up separately
- Standard Unix convention (dotfiles in home)

### Why Override Files Instead of Config Fields?

Originally, customization meant adding config fields: `custom_pronunciation_path`, `custom_lyrics_style_path`, etc. This doesn't scale.

Override files use convention over configuration:
- Put `pronunciation-guide.md` in overrides → skill uses it
- No new config field needed per customization
- Self-documenting (filename = what it overrides)
- Future-proof for new overrides

### Why Human Verification for Sources?

AI can fetch and summarize sources, but can't verify accuracy at the level required for true-story albums. The verification step ensures:
- Sources actually exist and say what's claimed
- Quotes are accurate
- No fabricated details slip through

This is a deliberate friction point. Music about real events carries responsibility.

---

## Philosophy

### Tools, Not Magic

The plugin doesn't try to fully automate album creation. It provides tools that make the human-AI collaboration more efficient:
- Templates reduce boilerplate
- Skills encode best practices
- Validation catches common mistakes
- But creative decisions stay with you

### Explicit Over Implicit

The plugin is verbose about what it's doing and why. Status tracking, checkpoint messages, and validation feedback keep you informed. Surprises are bad in creative workflows.

### Iterate and Improve

Skills update themselves when they learn new things:
- Pronunciation specialist adds to the guide
- Suno engineer updates best practices
- Model updater keeps skills current

The system gets smarter over time.

---

## Contributing

See [/CONTRIBUTING.md](/CONTRIBUTING.md) for guidelines on:
- Adding new skills
- Updating documentation
- Running tests
- Creating pull requests

---

## See Also

- [SKILL.md](SKILL.md) - About skill documentation
- [/CHANGELOG.md](/CHANGELOG.md) - Detailed version history
- [/README.md](/README.md) - Project overview
- [bitwizemusic.com](https://www.bitwizemusic.com/) - Artist website
