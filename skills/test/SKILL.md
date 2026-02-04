---
name: test
description: Runs automated tests to validate plugin integrity across 14 categories. Use before creating PRs, after making changes to skills or templates, or to verify plugin health.
argument-hint: [all | config | skills | templates | workflow | suno | research | mastering | sheet-music | release | consistency | terminology | behavior | quality | quick]
model: claude-haiku-4-5-20251001
context: fork
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
---

## Your Task

**Input**: $ARGUMENTS

Run automated tests to validate plugin integrity. Execute each test methodically and report results clearly.

**Default**: Run all tests if no argument provided.

---

# Plugin Test Suite

You are the plugin's automated test runner. Execute each test, track pass/fail, and report actionable results.

## Quick Automated Tests (`/test quick`)

For fast automated validation, run the Python test runner:

```bash
python3 tools/tests/run_tests.py
```

This covers:
- **skills** - YAML frontmatter validation, required fields, model references
- **templates** - Required templates exist, template structure
- **references** - Suno reference docs, mastering docs
- **links** - Internal markdown link validation
- **terminology** - Deprecated terms, path variable consistency
- **consistency** - Skill count, version sync, .gitignore entries
- **config** - Config file structure and documentation

Run specific categories:
```bash
python3 tools/tests/run_tests.py skills templates
python3 tools/tests/run_tests.py --verbose  # Debug mode
```

The Python runner is faster and catches common issues. For deep behavioral tests, use the full test suite below.

## Output Format

```
════════════════════════════════════════
CATEGORY: Test Category Name
════════════════════════════════════════

[PASS] Test name
[FAIL] Test name
       → Problem: what's wrong
       → File: path/to/file:line
       → Fix: specific fix instruction

────────────────────────────────────────
Category: X passed, Y failed
────────────────────────────────────────
```

At the end:
```
════════════════════════════════════════
FINAL RESULTS
════════════════════════════════════════
config:       X passed, Y failed
skills:       X passed, Y failed
templates:    X passed, Y failed
...
────────────────────────────────────────
TOTAL:        X passed, Y failed, Z skipped
════════════════════════════════════════
```

---


# TEST CATEGORIES

All test definitions are in [test-definitions.md](test-definitions.md).

14 categories: config, skills, templates, workflow, suno, research, mastering, sheet-music, release, consistency, terminology, behavior, quality, e2e.

Read that file before running tests to understand what each test checks.

---

# RUNNING TESTS

## Commands

| Command | Description |
|---------|-------------|
| `/test` or `/test all` | Run all tests |
| `/test quick` | Run Python test runner (fast automated checks) |
| `/test config` | Configuration system tests |
| `/test skills` | Skill definitions and docs |
| `/test templates` | Template file tests |
| `/test workflow` | Album workflow documentation |
| `/test suno` | Suno integration tests |
| `/test research` | Research workflow tests |
| `/test mastering` | Mastering workflow tests |
| `/test sheet-music` | Sheet music generation tests |
| `/test release` | Release workflow tests |
| `/test consistency` | Cross-reference checks |
| `/test terminology` | Consistent language tests |
| `/test behavior` | Scenario-based tests |
| `/test quality` | Code quality checks |
| `/test e2e` | End-to-end integration test |

## Quick Tests via Python Runner

For rapid validation during development, use the Python test runner directly:

```bash
# Run all automated tests
python3 tools/tests/run_tests.py

# Run specific categories
python3 tools/tests/run_tests.py skills templates

# Verbose mode for debugging
python3 tools/tests/run_tests.py --verbose

# No color output (for CI/logs)
python3 tools/tests/run_tests.py --no-color
```

Categories available in Python runner:
- `skills` - Frontmatter, required fields, model validation
- `templates` - Template existence and structure
- `references` - Reference doc existence
- `links` - Internal markdown links
- `terminology` - Deprecated terms check
- `consistency` - Version sync, skill counts
- `config` - Config file validation

## Adding New Tests

When bugs are found:
1. Identify which category the test belongs to
2. Add a test that would have caught the bug
3. Run `/test [category]` to verify test fails
4. Fix the bug
5. Run `/test [category]` to verify test passes
6. Commit both the fix and the new test

**Rule:** Every bug fix should add a regression test.

---

# EXECUTION TIPS

- Use Grep with `output_mode: content` and `-n` for line numbers
- Use Glob to find files by pattern
- Use Read to check file contents
- Use Bash sparingly (YAML/JSON validation)
- Report exact file:line for failures
- Provide specific, actionable fix instructions
- Group related tests for readability
- Skip tests gracefully if prerequisites missing
