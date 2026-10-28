---
name: setup
description: Detects your Python environment and guides you through installing plugin dependencies. Use on first-time setup or when MCP server fails to start.
argument-hint: <blank for full check | "mcp" | "mastering" | "document-hunter">
model: haiku
allowed-tools:
  - Bash
---

Base directory for this skill: ${CLAUDE_PLUGIN_BASE_DIR}

In Codex, read the [shared runtime rules](../../reference/runtime-compatibility.md)
using the loaded skill's path. Resolve the plugin root from that path and use it
in the commands below. Claude Code supplies `CLAUDE_PLUGIN_ROOT`. When presenting
copyable commands, quote the absolute requirements path for the user's shell.

## Your Task

Guide the user through installing bitwize-music plugin dependencies based on their Python environment and requested components.

---

# Setup Assistant

You help users install and verify plugin dependencies.

---

## Step 1: Detect Environment

Run the environment checks in parallel. On native Windows, check the Python
version with `py -3 --version` and use PowerShell for the environment checks.

```bash
# Python version
python3 --version

# Check if externally managed
python3 -c "import sysconfig; print(sysconfig.get_path('purelib'))" 2>&1 | grep -q "/usr" && echo "EXTERNALLY_MANAGED" || echo "USER_MANAGED"

# Check for pipx
command -v pipx >/dev/null 2>&1 && echo "pipx: installed" || echo "pipx: not installed"

# Check for venv support
python3 -m venv --help >/dev/null 2>&1 && echo "venv: supported" || echo "venv: not supported"

# Platform
uname -s
```

---

## Step 2: Check Component Status

**IMPORTANT:** Run these checks **sequentially**, not in parallel. If one check fails, continue with the remaining checks to show complete status.

**CRITICAL:** Always check the venv, not system Python!

```bash
# Set venv path (macOS/Linux/WSL uses bin/python3; native Windows uses Scripts/python.exe)
VENV_PYTHON=~/.bitwize-music/venv/bin/python3
[ -f "$VENV_PYTHON" ] || VENV_PYTHON=~/.bitwize-music/venv/Scripts/python.exe

# Check if venv exists
if [ -f "$VENV_PYTHON" ]; then
    echo "✅ Venv exists at ~/.bitwize-music/venv"

    # Check each component in the venv
    # 2.x serves MCPServer from mcp.server.mcpserver, 1.x serves FastMCP from
    # mcp.server.fastmcp; the server takes either, so probe both (#537).
    "$VENV_PYTHON" -c "import mcp.server.mcpserver" 2>/dev/null || "$VENV_PYTHON" -c "import mcp.server.fastmcp" 2>/dev/null && echo "✅ mcp installed" || echo "❌ mcp not installed (need mcp[cli]>=1.28.1,<3)"
    "$VENV_PYTHON" -c "import matchering; print('✅ matchering installed')" 2>&1 || echo "❌ matchering not installed"
    "$VENV_PYTHON" -c "import boto3; print('✅ boto3 installed')" 2>&1 || echo "❌ boto3 not installed"
    "$VENV_PYTHON" -c "from playwright.sync_api import sync_playwright; print('✅ playwright installed')" 2>&1 || echo "❌ playwright not installed"

    # Check for version drift against requirements.txt
    "$VENV_PYTHON" -c "
import importlib.metadata, pathlib, sys
reqs = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')
stale = []
for line in reqs.splitlines():
    line = line.split('#')[0].strip()
    if not line or '==' not in line:
        continue
    name, _, ver = line.partition('==')
    name = name.split('[')[0].strip()
    try:
        installed = importlib.metadata.version(name)
        if installed != ver:
            stale.append(f'  {name}: {installed} → {ver}')
    except importlib.metadata.PackageNotFoundError:
        stale.append(f'  {name}: missing (needs {ver})')
if stale:
    print('⚠️  Version drift detected:')
    print('\n'.join(stale))
else:
    print('✅ All package versions match requirements.txt')
" "${CLAUDE_PLUGIN_ROOT}/requirements.txt" 2>&1
else
    echo "❌ Venv not found at ~/.bitwize-music/venv"
fi
```

All components are installed together in the venv via requirements.txt.

---

## Step 3: Show Installation Commands

Use the shared venv and show the block for the user's shell. In Codex, use the
resolved absolute path to `requirements.txt` in the `-r` argument.

**macOS, Linux, and WSL**

```bash
python3 -m venv "$HOME/.bitwize-music/venv"
"$HOME/.bitwize-music/venv/bin/python3" -m pip install -r "${CLAUDE_PLUGIN_ROOT}/requirements.txt"
"$HOME/.bitwize-music/venv/bin/python3" -m playwright install chromium
```

**Windows PowerShell**

```powershell
py -3 -m venv "$env:USERPROFILE\.bitwize-music\venv"
& "$env:USERPROFILE\.bitwize-music\venv\Scripts\python.exe" -m pip install -r "$env:CLAUDE_PLUGIN_ROOT\requirements.txt"
& "$env:USERPROFILE\.bitwize-music\venv\Scripts\python.exe" -m playwright install chromium
```

The plugin automatically detects the venv in `~/.bitwize-music/venv` or
`%USERPROFILE%\.bitwize-music\venv` on native Windows.

---

## Step 3.5: Optional — Suno Server and Audio Player

Neither is needed for the plugin to work. Mention them once, after the required components are sorted.

**Suno MCP server** — lets `/bitwize-music:generate`, `/bitwize-music:listen` and `/bitwize-music:import-audio --from-suno` reach the user's Suno account. In Claude Code, check the `suno` section of `health_check()` when available. If configured, show its name and scope. To add a missing server, use:

```bash
claude mcp add --transport http suno https://api.suno.com/mcp
```

Then `/mcp` in a session to sign in. `--scope user` on the command makes it available in every project, not only this one. The plugin does not ship this server; without it those skills fall back to the clipboard flow, and session start shows these instructions until it is added (`generation.suno_mcp_reminder: false` in the config hides them).

In Codex, check the current session's MCP settings or run `codex mcp list` from
the music workspace using the same profile. Report the registered Suno server's
name, or link to [Suno's setup instructions](https://help.suno.com/en/articles/14551425)
if it is absent.

**Audio player** — lets `/bitwize-music:listen` play audio in the terminal. Any one of `mpv` (recommended), `ffplay` (part of ffmpeg) or macOS's built-in `afplay`:

```bash
command -v mpv ffplay afplay   # shows which are installed
brew install mpv               # macOS
sudo apt install mpv           # Debian/Ubuntu/WSL
winget install mpv             # Windows
```

---

## Step 4: Installation Guide

Present a clear, simple installation guide:

1. **Environment detected**: [Python version, Platform]
2. **Missing components**: [list what needs to be installed]
3. **Installation commands**: Show the matching commands from Step 3 with the installed requirements path.
4. **After installation**:
   - Start a new session in the active host to reconnect MCP
   - In Claude Code, check `/plugin` status; in Codex, check the plugin's MCP connection
   - Invoke the installed `setup` skill again to verify, using the host's skill syntax

---

## Step 5: Verify Installation (if requested)

After user reports they've installed, re-run the checks from Step 2 and confirm:

✅ **MCP server**: Ready
✅ **Audio mastering**: Ready
✅ **Cloud uploads**: Ready
✅ **Document hunter**: Ready

**Next steps**: Run `/bitwize-music:configure` to set up your workspace paths.

---

## Output Format

Use clear sections with checkboxes for status:

```markdown
## bitwize-music Setup

### Environment
- Python: 3.12.3
- System: Linux

### Component Status
- [❌] MCP server
- [❌] Audio mastering
- [❌] Cloud uploads
- [❌] Document hunter

### Installation

[Copyable Step 3 commands for the user's shell]

**After installation:**
1. Start a new session in the active host
2. Check the plugin's MCP connection
3. Invoke the installed `setup` skill again to verify

```

---

## Remember

- **Be specific** - show exact commands for their environment
- **Prioritize user install** for externally-managed Python
- **Explain what each component does** so they can decide what to install
- **Test commands work** before suggesting them
- **Clear next steps** after installation
