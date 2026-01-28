# Album Ideas - Status Values

Reference for status tracking in the `/bitwize-music:album-ideas` skill.

---

## Status Values

| Status | Meaning | When to Use |
|--------|---------|-------------|
| **Pending** | Idea captured, not yet started | Initial brainstorm, backlog items |
| **In Progress** | Actively being worked on | Album directory created, writing/generating |
| **Complete** | Finished and released (or archived) | Album released on platforms |

---

## Status Workflow

```
                    ┌─────────────┐
                    │   Pending   │
                    │  (backlog)  │
                    └──────┬──────┘
                           │
              /new-album creates directory
                           │
                           v
                    ┌─────────────┐
                    │ In Progress │
                    │  (working)  │
                    └──────┬──────┘
                           │
              Album released on platforms
                           │
                           v
                    ┌─────────────┐
                    │  Complete   │
                    │ (archived)  │
                    └─────────────┘
```

---

## Detailed Status Descriptions

### Pending

The idea exists only in IDEAS.md. No album directory created yet.

**Typical state:**
- Title and concept captured
- Genre identified
- Maybe some notes or inspiration sources
- No tracks written, no research started

**Move to In Progress when:**
- You run `/bitwize-music:new-album [title] [genre]`
- Album directory structure is created
- Ready to begin the 7 planning phases

### In Progress

Album directory exists and work is actively happening.

**Typical state:**
- Album README created with concept
- Some or all tracks drafted
- May be generating in Suno
- May be mastering audio

**Move to Complete when:**
- Album status in README is "Released"
- `release_date` is set in album frontmatter
- Available on streaming platforms

### Complete

Album is finished and released (or intentionally archived without release).

**Typical state:**
- All tracks finalized
- Audio mastered
- Released on SoundCloud/distributors
- Or: Deliberately shelved/abandoned

---

## Status Commands

### List All Ideas by Status

```bash
/bitwize-music:album-ideas list
```

Shows ideas organized by Pending, In Progress, Complete.

### Update Status Manually

```bash
/bitwize-music:album-ideas status "Album Title" in-progress
/bitwize-music:album-ideas status "Album Title" complete
/bitwize-music:album-ideas status "Album Title" pending
```

### Check Specific Idea

```bash
/bitwize-music:album-ideas show "Album Title"
```

---

## Automatic Status Updates

The skill suggests status updates at key workflow points:

1. **After `/new-album`**: Prompts to move idea to "In Progress"
2. **After release**: Can manually mark as "Complete"

Status sync between IDEAS.md and album README is manual - the two files track different things:
- IDEAS.md: Brainstorming/backlog tracking
- Album README: Detailed album status (Concept, In Progress, Complete, Released)

---

## Best Practices

- **Capture liberally**: Add ideas when inspiration strikes, even half-formed ones
- **Review periodically**: Check Pending list every few sessions
- **Keep Complete lean**: Archive or remove old completed entries
- **Use notes field**: Add research leads, inspiration sources, collaborator ideas

---

## See Also

- [SKILL.md](SKILL.md) - Full skill documentation
- [/templates/ideas.md](/templates/ideas.md) - IDEAS.md template
