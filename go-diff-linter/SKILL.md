---
name: go-diff-linter
description: |
  Differential Go linting - run golangci-lint only on changed code between branches.
  Use this skill when:
  - User wants to lint only changed Go code (not entire codebase)
  - User mentions "lint my changes", "check my PR", "review diff", "lint against main/develop"
  - User wants to fix lint issues only in modified code without touching unchanged functions
  - User needs to compare branches and find lint issues in the diff
  This skill filters lint output to show only issues within changed line ranges. Formatters are automatically applied to changed files.
---

# Go Diff Linter

Lint only the code you changed, not the entire codebase. Formatters are applied automatically, Claude fixes lint issues manually.

## Quick Start

```bash
# Run linting and auto-format for changes vs develop branch
.claude/skills/go-diff-linter/scripts/run_lint.sh develop

# Report saved to .golangci-diff/report.md
```

## What It Does

1. **Extracts changed files** - Gets diff between your branch and base branch
2. **Runs linters** - Only on packages containing changed files (avoids unrelated errors)
3. **Filters issues** - Keeps only issues within changed line ranges
4. **Auto-formats** - Applies gofumpt and goimports to all changed files
5. **Generates report** - Markdown report for Claude to fix remaining lint issues

## Workflow

### Step 1: Run the Script

```bash
.claude/skills/go-diff-linter/scripts/run_lint.sh <base_branch> [-o report.md]
```

Example:
```bash
.claude/skills/go-diff-linter/scripts/run_lint.sh develop
.claude/skills/go-diff-linter/scripts/run_lint.sh main -o my-report.md
```

### Step 2: Review Changes

Formatters are applied automatically. Check with:
```bash
git status
git diff
```

### Step 3: Fix Lint Issues

Read the report: `.golangci-diff/report.md`

Report contains:
- Changed files and line ranges
- Each lint issue: file, line, linter, description, current code, suggested fix

Fix each issue using the Edit tool. **Only modify lines specified in the report.**

## Config

Always uses skill's `assets/.golangci.yml` for consistent linting (project config is temporarily backed up and restored).

**Enabled Linters:**
- Essential: govet, staticcheck, errcheck, ineffassign, unused, typecheck
- Security: gosec
- Bug prevention: bodyclose, nilerr, sqlclosecheck, contextcheck, rowserrcheck
- Code quality: gocritic, revive, misspell, errorlint, dupl, goconst, cyclop

**Auto-applied Formatters:**
- gofumpt (with extra-rules)
- goimports

## Key Behaviors

| Type | Scope | Action |
|------|-------|--------|
| Lint issues | Changed lines only | Claude manually fixes |
| Formatting | Changed files | **Auto-applied** |
| Unchanged code | Skip | Never touch |

## Example Report Output

```markdown
## Summary

- Total issues from linter: 15
- Lint issues in changed lines: 12
- Filtered out (unchanged code): 3
- Formatting: automatically applied

## Lint Issues (Must Fix)

### `pkg/handler/api.go`

**Line 42:5** - [gosec] Security issue
> G104: Errors unhandled

Current code:
```go
42: json.Unmarshal(data, &result)
```

Suggested fix:
```go
if err := json.Unmarshal(data, &result); err != nil {
    return err
}
```
```

## Requirements

- Go 1.21+
- golangci-lint v2.x (uses `--output.json.path` and `golangci-lint fmt`)
- Python 3.10+
- jq
