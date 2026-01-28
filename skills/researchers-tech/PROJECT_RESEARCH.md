# Tech Project Research Guide

Find project histories, developer communications, and technical documentation.

---

## GitHub Research

### Repository History
```bash
# View commit history
git log --oneline --since="2000-01-01" --until="2005-12-31"

# Find first commit
git log --reverse --oneline | head -1

# Commits by author
git log --author="[name]" --oneline
```

### GitHub Web Interface
- **Commits tab**: Full history with messages
- **Releases**: Version history with notes
- **Issues**: Community discussions, bug reports
- **Pull Requests**: Code review discussions
- **Insights > Contributors**: Who contributed when

### Finding Developer Information
- Profile page: github.com/[username]
- Email in commits (often visible)
- README contributor lists
- CONTRIBUTORS or AUTHORS files

---

## Mailing List Archives

### Major List Archives
| Project | Archive URL |
|---------|-------------|
| Linux Kernel | lkml.org |
| Debian | lists.debian.org |
| GNU | lists.gnu.org |
| Apache | mail-archives.apache.org |
| Python | mail.python.org/archives |

### Search Strategies
```
"[topic]" site:lists.debian.org
"[author name]" site:lkml.org
"[project] announcement" mailing list
```

### What to Find
- **Original announcements**: "I'm releasing..."
- **Design decisions**: "We decided to..."
- **Conflicts**: Heated debates, departures
- **Personal statements**: Philosophy, motivation

---

## Usenet and Historical Forums

### Google Groups (Usenet)
**URL**: groups.google.com

Historical Usenet archives including:
- comp.os.linux.*
- alt.* groups
- Early internet discussions

### Slashdot
**URL**: slashdot.org

- Tech news discussion since 1997
- Search archives for historical reactions
- Developer comments in discussions

### Hacker News
**URL**: hn.algolia.com (searchable archive)

- Tech community discussions
- Founders often participate
- Product announcements

---

## Conference Talks

### Finding Talks
```
"[person]" OR "[project]" site:youtube.com conference OR talk
"[project]" linux.conf.au OR FOSDEM OR DebConf
"[person]" keynote [year]
```

### Major FOSS Conferences
| Conference | Focus |
|------------|-------|
| linux.conf.au | Linux, open source |
| FOSDEM | European FOSS |
| DebConf | Debian |
| PyCon | Python |
| KubeCon | Kubernetes, cloud native |

### Extracting from Talks
- Note timestamps for specific quotes
- Check for official transcripts
- Slides often posted separately
- Q&A often most revealing

---

## Project Documentation

### Finding Historical Docs
- **Wayback Machine**: web.archive.org/web/*/[project-url]
- **Official wikis**: Often have history pages
- **DistroWatch**: distrowatch.com for Linux distros
- **Wikipedia**: Version history sections

### Key Documents
| Document | Contents |
|----------|----------|
| README | Project purpose, philosophy |
| CHANGELOG | Version history, features |
| AUTHORS | Contributor credits |
| HISTORY | Project timeline |
| FAQ | Common questions, design decisions |

---

## Timeline Construction

### Key Dates to Find
1. **Project start**: First commit, announcement
2. **Major releases**: Version numbers, dates
3. **Governance changes**: Leadership, foundation
4. **Forks**: When, why, by whom
5. **Acquisitions**: If applicable
6. **End of life**: If abandoned

### Sources by Date Type
| Date Type | Best Source |
|-----------|-------------|
| First release | Mailing list announcement, git history |
| Version releases | CHANGELOG, DistroWatch |
| Acquisitions | Press releases, SEC filings |
| Forks | Fork announcement, media coverage |
| Project death | Final commit, announcement |

---

## Researching Forks

### Why Forks Happen
- Philosophical differences
- Governance disputes
- Technical direction
- Licensing changes
- Maintainer burnout

### Finding Fork History
- Original project's mailing list
- Fork announcement post
- Media coverage at time
- Wikipedia "History" sections

### Fork Drama (Lyric Gold)
- Who left, who stayed
- What sparked the split
- Community reactions
- How it resolved

---

## Developer Profiles

### Tech-Specific Sources
- **GitHub profile**: Contributions, projects
- **Personal blog**: Philosophy, updates
- **Conference talks**: Speaking history
- **Podcast appearances**: Interviews

### Search Patterns
```
"[name]" "[project]" interview OR podcast
"[name]" blog OR writes
"[name]" conference OR talk OR keynote
```

---

## Archiving Tech Sources

### Git Repositories
```bash
# Clone full history
git clone --mirror [repo-url]
```

### Mailing List Posts
- Archive.org for list archives
- Save individual message URLs
- Screenshot critical posts

### Websites
- Wayback Machine save
- Archive.today backup
- Screenshot key pages

---

## For Lyrics

### Tech Terms That Work
| Term | Meaning | Lyric Use |
|------|---------|-----------|
| Fork | Project split | "Forked the code" |
| Commit | Code change | "First commit" |
| Upstream | Original project | "Send it upstream" |
| Maintainer | Project steward | "Solo maintainer" |
| Rolling release | Continuous updates | "Rolling release" |
| Kernel | OS core | "Down to the kernel" |

### Numbers for Authenticity
- Commit counts
- Years maintained
- Contributor counts
- Version numbers
- Download/user counts
