---
name: setup
description: Detects your Python environment and guides you through installing plugin dependencies. Use on first-time setup or when MCP server fails to start.
argument-hint: <blank for full check | "mcp" | "mastering" | "document-hunter">
model: claude-haiku-4-5-20251001
allowed-tools:
  - Bash
---

Base directory for this skill: ${CLAUDE_PLUGIN_BASE_DIR}

## Your Task

Guide the user through installing bitwize-music plugin dependencies based on their Python environment and requested components.

---

# Setup Assistant

You help users install and verify plugin dependencies.

---

## Step 1: Detect Environment

**Run these checks in parallel:**

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

Based on user's request (or check all if no argument):

### MCP Server (required for fast state queries)

```bash
python3 -c "import mcp; print('✅ mcp installed')" 2>&1 || echo "❌ mcp not installed"
python3 -c "import yaml; print('✅ pyyaml installed')" 2>&1 || echo "❌ pyyaml not installed"
```

### Mastering Tools (optional)

```bash
python3 -c "import matchering; print('✅ matchering installed')" 2>&1 || echo "❌ matchering not installed"
python3 -c "import pyloudnorm; print('✅ pyloudnorm installed')" 2>&1 || echo "❌ pyloudnorm not installed"
python3 -c "import scipy; print('✅ scipy installed')" 2>&1 || echo "❌ scipy not installed"
```

### Document Hunter (optional)

```bash
python3 -c "from playwright.sync_api import sync_playwright; print('✅ playwright installed')" 2>&1 || echo "❌ playwright not installed"
command -v playwright >/dev/null 2>&1 && echo "✅ playwright CLI: installed" || echo "❌ playwright CLI: not installed"
```

---

## Step 3: Show Installation Commands

**Always use the unified venv approach** — it works on all platforms and is automatically detected by the plugin.

```bash
# Create unified venv (if it doesn't exist)
python3 -m venv ~/.bitwize-music/venv

# Install ALL plugin dependencies
~/.bitwize-music/venv/bin/pip install -r ${CLAUDE_PLUGIN_ROOT}/requirements.txt

# Set up document hunter browser
~/.bitwize-music/venv/bin/playwright install chromium
```

**That's it!** The plugin automatically detects and uses `~/.bitwize-music/venv`. No configuration needed.

**Works on:**
- ✅ Linux (externally-managed Python)
- ✅ macOS
- ✅ Windows (WSL)
- ✅ All other systems

---

## Step 4: Installation Guide

Present a clear, simple installation guide:

1. **Environment detected**: [Python version, Platform]
2. **Missing components**: [list what needs to be installed]
3. **Installation commands**:
   ```bash
   python3 -m venv ~/.bitwize-music/venv
   ~/.bitwize-music/venv/bin/pip install -r ${CLAUDE_PLUGIN_ROOT}/requirements.txt
   ~/.bitwize-music/venv/bin/playwright install chromium
   ```
4. **After installation**:
   - Restart Claude Code to reload the plugin
   - MCP server should show as running in `/plugin` status
   - Run `/bitwize-music:setup` again to verify

---

## Step 5: Verify Installation (if requested)

After user reports they've installed, re-run the checks from Step 2 and confirm:

✅ **MCP server**: Ready
✅ **Mastering tools**: [Ready | Not installed (optional)]
✅ **Document hunter**: [Ready | Not installed (optional)]

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
- [❌] MCP server (required)
- [✅] Mastering tools
- [❌] Document hunter

### Installation

Run these commands to set up the unified venv:

```bash
# Create venv
python3 -m venv ~/.bitwize-music/venv

# Install everything
~/.bitwize-music/venv/bin/pip install -r ${CLAUDE_PLUGIN_ROOT}/requirements.txt

# Set up browser for document hunting
~/.bitwize-music/venv/bin/playwright install chromium
```

**After installation:**
1. Restart Claude Code
2. MCP server will automatically use the venv
3. Run `/bitwize-music:setup` to verify

The plugin automatically detects `~/.bitwize-music/venv` — no configuration needed!
```

---

## Remember

- **Be specific** - show exact commands for their environment
- **Prioritize user install** for externally-managed Python
- **Explain what each component does** so they can decide what to install
- **Test commands work** before suggesting them
- **Clear next steps** after installation
