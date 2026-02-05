# Go Diff Linter

A Claude Code skill for **differential Go linting** - runs `golangci-lint` only on code that has changed between branches, filtering results to show only issues within modified line ranges.

## Overview

When working on large Go codebases, running linters on the entire project can be:
- **Slow** - Large projects take minutes to lint
- **Noisy** - Pre-existing issues in unchanged code clutter the output
- **Overwhelming** - Hard to focus on what actually matters for your PR

**Go Diff Linter solves this** by:
1. Detecting which files and line ranges you've changed
2. Running linters only on affected packages
3. Filtering output to show only issues in your changes
4. Auto-applying formatters to changed files

## Features

### What It Does

| Feature | Description |
|---------|-------------|
| **Differential Linting** | Runs `golangci-lint` only on packages containing changed files |
| **Line-Range Filtering** | Shows lint issues only within your changed line ranges |
| **Auto-Formatting** | Applies `gofumpt` and `goimports` automatically to changed files |
| **Markdown Reports** | Generates detailed reports for Claude to fix issues |
| **Config Isolation** | Uses its own `.golangci.yaml` for consistent results |

### Enabled Linters

**Essential (always-on):**
- `govet` - Reports suspicious constructs
- `staticcheck` - Advanced static analysis
- `errcheck` - Unchecked error returns
- `ineffassign` - Ineffectual assignments
- `unused` - Unused code detection

**Security:**
- `gosec` - Security vulnerability detection

**Bug Prevention:**
- `bodyclose` - HTTP response body not closed
- `nilerr` - Returning nil error incorrectly
- `sqlclosecheck` - SQL rows/statements not closed
- `contextcheck` - Context not passed correctly
- `rowserrcheck` - SQL `rows.Err()` not checked

**Code Quality:**
- `gocritic` - Code style and correctness
- `revive` - Extensible linter
- `misspell` - Spelling mistakes in code
- `errorlint` - Error handling best practices
- `dupl` - Duplicate code detection
- `goconst` - Magic strings/numbers that should be constants
- `cyclop` - Function complexity analysis

**Auto-Applied Formatters:**
- `gofumpt` - Stricter gofmt with extra rules
- `goimports` - Import ordering and grouping

## Installation

### Requirements

- **Go 1.21+**
- **golangci-lint v2.x** (uses `--output.json.path` and `golangci-lint fmt`)
- **Python 3.10+**
- **jq** (JSON processor)

### Setup

1. Copy the skill to your project's `.claude/skills/` directory:

```bash
mkdir -p /path/to/your/project/.claude/skills
cp -r go-diff-linter /path/to/your/project/.claude/skills/
```

2. Make the scripts executable:

```bash
chmod +x /path/to/your/project/.claude/skills/go-diff-linter/scripts/*.sh
chmod +x /path/to/your/project/.claude/skills/go-diff-linter/scripts/*.py
```

## Usage

### Basic Usage

```bash
# Lint changes compared to develop branch
.claude/skills/go-diff-linter/scripts/run_lint.sh develop

# Lint changes compared to main branch
.claude/skills/go-diff-linter/scripts/run_lint.sh main

# Custom output file
.claude/skills/go-diff-linter/scripts/run_lint.sh develop -o my-report.md
```

### With Claude Code

Simply ask Claude to lint your changes:

```
"Lint my changes against develop"
"Check my PR for lint issues"
"Review my diff for code quality"
```

Claude will automatically invoke this skill when appropriate.

### Workflow

1. **Run the script** against your base branch
2. **Review git status** - formatters are auto-applied
3. **Read the report** at `.golangci-diff/report.md`
4. **Fix issues** listed in the report
5. **Commit** your changes

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        run_lint.sh                               │
│                    (Main orchestrator)                           │
└─────────────────────────────┬───────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│get_diff_ranges│    │ golangci-lint │    │filter_lint_   │
│    .py        │    │   run + fmt   │    │  issues.py    │
└───────┬───────┘    └───────┬───────┘    └───────┬───────┘
        │                    │                    │
        ▼                    ▼                    ▼
   changes.json         lint_output.json      report.md
```

### Pipeline Steps

1. **Extract Changes** (`get_diff_ranges.py`)
   - Runs `git diff -U0 base_branch...HEAD -- *.go`
   - Parses unified diff format
   - Extracts changed line ranges per file
   - Merges overlapping/adjacent ranges
   - Outputs `changes.json`

2. **Run Linters** (`run_lint.sh`)
   - Backs up existing `.golangci.yaml`
   - Copies skill's config for consistency
   - Identifies packages from changed files
   - Runs `golangci-lint run --new-from-rev=<base>`
   - Runs `golangci-lint fmt` on changed files
   - Restores original config

3. **Filter Results** (`filter_lint_issues.py`)
   - Loads lint output and change ranges
   - Separates formatter issues (whole file) from lint issues
   - Filters lint issues to only those in changed ranges
   - Generates Markdown report with:
     - Summary statistics
     - Changed file/line reference
     - Each issue with context and suggested fix

## Output Files

| File | Description |
|------|-------------|
| `.golangci-diff/changes.json` | Changed files and line ranges |
| `.golangci-diff/lint_output.json` | Raw golangci-lint JSON output |
| `.golangci-diff/filtered_issues.json` | Filtered issues (lint + formatter) |
| `.golangci-diff/report.md` | Human/Claude-readable Markdown report |

## Example Report

```markdown
# Go Diff Lint Report

## Summary

- Total issues from linter: 15
- Lint issues in changed lines: 12
- Filtered out (unchanged code): 3
- Formatting: automatically applied

## Changed Files and Line Ranges

- `pkg/handler/api.go`: lines 40-55, 120-145
- `internal/service/user.go`: lines 10-25

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

## Configuration

The skill uses its own `.golangci.yaml` located at `assets/.golangci.yaml`. This ensures:

- **Consistency** - Same linters enabled across all projects using this skill
- **Isolation** - Your project's lint config is not affected
- **Automatic restore** - Original config is backed up and restored after linting

### Customizing Linters

Edit `assets/.golangci.yaml` to enable/disable linters:

```yaml
version: "2"

linters:
  default: none
  enable:
    - govet
    - staticcheck
    # Add or remove linters here

formatters:
  enable:
    - gofumpt
    - goimports
```

## Troubleshooting

### Common Issues

**"No Go file changes detected"**
- Ensure you have uncommitted changes or commits ahead of the base branch
- Verify the base branch name is correct

**"golangci-lint: command not found"**
- Install with: `go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest`
- Or: `brew install golangci-lint`

**"jq: command not found"**
- Install with: `brew install jq` (macOS) or `apt install jq` (Linux)

**Python script errors**
- Ensure Python 3.10+ is installed
- Check with: `python3 --version`

## License

MIT
