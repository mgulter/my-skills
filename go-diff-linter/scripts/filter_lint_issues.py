#!/usr/bin/env python3
"""
Filter golangci-lint JSON output to only show issues within changed line ranges.
Generates a Markdown report for Claude to review and fix manually.
"""

import argparse
import json
import os
import sys
from typing import TypedDict


class LintIssue(TypedDict, total=False):
    FromLinter: str
    Text: str
    Severity: str
    SourceLines: list[str]
    Pos: dict  # Contains Filename, Line, Column
    Replacement: dict  # Contains NewLines for suggested fix


class FilteredOutput(TypedDict):
    lint_issues: list[LintIssue]  # Only in changed ranges
    formatter_issues: list[LintIssue]  # All formatter issues (whole file)
    stats: dict


FORMATTER_LINTERS = {"gofmt", "gofumpt", "goimports"}

# Linter descriptions for better context
LINTER_INFO = {
    "gosec": "Security issue",
    "bodyclose": "HTTP response body not closed",
    "nilerr": "Returning nil error incorrectly",
    "sqlclosecheck": "SQL rows/stmt not closed",
    "contextcheck": "Context not passed correctly",
    "rowserrcheck": "SQL rows.Err() not checked",
    "gocritic": "Code style/correctness suggestion",
    "revive": "Code quality issue",
    "misspell": "Spelling mistake",
    "errorlint": "Error handling issue",
    "dupl": "Duplicate code detected",
    "goconst": "Magic string/number should be const",
    "cyclop": "Function complexity too high",
    "gofmt": "Formatting (gofmt)",
    "gofumpt": "Formatting (gofumpt)",
    "goimports": "Import ordering",
}


def load_changes(changes_file: str) -> dict[str, list[tuple[int, int]]]:
    """Load changed ranges from JSON file into a lookup dict."""
    with open(changes_file) as f:
        changes = json.load(f)

    lookup: dict[str, list[tuple[int, int]]] = {}
    for entry in changes:
        file_path = entry["file"]
        ranges = [tuple(r) for r in entry["ranges"]]
        lookup[file_path] = ranges

    return lookup


def is_in_changed_range(
    line: int,
    ranges: list[tuple[int, int]],
) -> bool:
    """Check if a line number falls within any of the changed ranges."""
    for start, end in ranges:
        if start <= line <= end:
            return True
    return False


def filter_issues(
    lint_output: dict,
    changes: dict[str, list[tuple[int, int]]],
) -> FilteredOutput:
    """Filter lint issues to only those in changed ranges."""
    issues = lint_output.get("Issues") or []

    lint_issues: list[LintIssue] = []
    formatter_issues: list[LintIssue] = []

    stats = {
        "total_issues": len(issues),
        "filtered_lint_issues": 0,
        "formatter_issues": 0,
        "skipped_issues": 0,
    }

    for issue in issues:
        linter = issue.get("FromLinter", "")
        pos = issue.get("Pos", {})
        filename = pos.get("Filename", "")
        line = pos.get("Line", 0)

        # Formatter issues apply to whole file
        if linter in FORMATTER_LINTERS:
            formatter_issues.append(issue)
            stats["formatter_issues"] += 1
            continue

        # Lint issues only if in changed range
        if filename in changes:
            if is_in_changed_range(line, changes[filename]):
                lint_issues.append(issue)
                stats["filtered_lint_issues"] += 1
            else:
                stats["skipped_issues"] += 1
        else:
            stats["skipped_issues"] += 1

    return {
        "lint_issues": lint_issues,
        "formatter_issues": formatter_issues,
        "stats": stats,
    }


def generate_markdown_report(
    filtered: FilteredOutput,
    changes: dict[str, list[tuple[int, int]]],
) -> str:
    """Generate a Markdown report for Claude to read and fix issues."""
    lines = []
    lines.append("# Go Diff Lint Report")
    lines.append("")
    lines.append("This report contains only lint issues within **changed line ranges**.")
    lines.append("Issues in unchanged code have been filtered out.")
    lines.append("")

    # Stats summary
    stats = filtered["stats"]
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total issues from linter: {stats['total_issues']}")
    lines.append(f"- Lint issues in changed lines: {stats['filtered_lint_issues']}")
    lines.append(f"- Filtered out (unchanged code): {stats['skipped_issues']}")
    lines.append(f"- Formatting: automatically applied")
    lines.append("")

    # Changed ranges for context
    lines.append("## Changed Files and Line Ranges")
    lines.append("")
    for filepath, ranges in changes.items():
        range_strs = [f"{s}-{e}" for s, e in ranges]
        lines.append(f"- `{filepath}`: lines {', '.join(range_strs)}")
    lines.append("")

    # Lint issues (grouped by file)
    if filtered["lint_issues"]:
        lines.append("## Lint Issues (Must Fix)")
        lines.append("")
        lines.append("These issues were found in the line ranges you modified.")
        lines.append("")

        # Group by file
        by_file: dict[str, list[LintIssue]] = {}
        for issue in filtered["lint_issues"]:
            filename = issue.get("Pos", {}).get("Filename", "unknown")
            if filename not in by_file:
                by_file[filename] = []
            by_file[filename].append(issue)

        for filename, issues in by_file.items():
            lines.append(f"### `{filename}`")
            lines.append("")

            for issue in issues:
                pos = issue.get("Pos", {})
                line_num = pos.get("Line", 0)
                col = pos.get("Column", 0)
                linter = issue.get("FromLinter", "unknown")
                text = issue.get("Text", "")
                source_lines = issue.get("SourceLines", [])
                replacement = issue.get("Replacement", {})

                linter_desc = LINTER_INFO.get(linter, linter)

                lines.append(f"**Line {line_num}:{col}** - [{linter}] {linter_desc}")
                lines.append("")
                lines.append(f"> {text}")
                lines.append("")

                if source_lines:
                    lines.append("Current code:")
                    lines.append("```go")
                    for i, src_line in enumerate(source_lines):
                        # Show line number context
                        actual_line = line_num + i
                        lines.append(f"{actual_line}: {src_line}")
                    lines.append("```")
                    lines.append("")

                if replacement and replacement.get("NewLines"):
                    lines.append("Suggested fix:")
                    lines.append("```go")
                    for new_line in replacement["NewLines"]:
                        lines.append(new_line)
                    lines.append("```")
                    lines.append("")

                lines.append("---")
                lines.append("")

    # Formatter note
    lines.append("## Formatting")
    lines.append("")
    lines.append("Formatters (gofumpt, goimports) have been **automatically applied** to all changed files.")
    lines.append("")

    # Instructions for Claude
    lines.append("## Fix Instructions")
    lines.append("")
    lines.append("1. Open each file with `view` tool")
    lines.append("2. Fix the issues above in order (use `str_replace`)")
    lines.append("3. For formatter issues, run `gofumpt -w` and `goimports -w`")
    lines.append("4. Only modify the specified lines, do not touch other code")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Filter golangci-lint output by changed line ranges"
    )
    parser.add_argument(
        "lint_output",
        help="Path to golangci-lint JSON output file",
    )
    parser.add_argument(
        "changes_file",
        help="Path to changes JSON file from get_diff_ranges.py",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file path for filtered JSON",
    )
    parser.add_argument(
        "--report",
        help="Output Markdown report for Claude",
    )
    parser.add_argument(
        "--human",
        action="store_true",
        help="Output human-readable format to stdout",
    )
    args = parser.parse_args()

    with open(args.lint_output) as f:
        lint_output = json.load(f)

    changes = load_changes(args.changes_file)
    filtered = filter_issues(lint_output, changes)

    # Always save filtered JSON for reference
    work_dir = os.path.dirname(args.lint_output)
    json_output_path = args.output or os.path.join(work_dir, "filtered_issues.json")
    with open(json_output_path, "w") as f:
        json.dump(filtered, f, indent=2)

    # Generate Markdown report if requested
    if args.report:
        report = generate_markdown_report(filtered, changes)
        with open(args.report, "w") as f:
            f.write(report)
        print(f"Report saved to: {args.report}", file=sys.stderr)

    # Human readable output
    if args.human:
        print("=" * 60)
        print("LINT ISSUES (in changed ranges)")
        print("=" * 60)
        for issue in filtered["lint_issues"]:
            pos = issue.get("Pos", {})
            print(f"{pos.get('Filename')}:{pos.get('Line')}:{pos.get('Column')} "
                  f"[{issue.get('FromLinter')}] {issue.get('Text')}")

        print("\n" + "=" * 60)
        print("FORMATTER ISSUES (whole file)")
        print("=" * 60)
        for issue in filtered["formatter_issues"]:
            pos = issue.get("Pos", {})
            print(f"{pos.get('Filename')}:{pos.get('Line')} "
                  f"[{issue.get('FromLinter')}] {issue.get('Text')}")

        print("\n" + "=" * 60)
        print("STATS")
        print("=" * 60)
        for key, value in filtered["stats"].items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
