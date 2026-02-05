#!/usr/bin/env python3
"""
Extract changed line ranges from git diff between base branch and current HEAD.
Outputs JSON with file paths and their changed line ranges.
"""

import argparse
import json
import re
import subprocess
import sys
from typing import TypedDict


class FileChanges(TypedDict):
    file: str
    ranges: list[tuple[int, int]]  # (start_line, end_line) inclusive


def get_diff_output(base_branch: str) -> str:
    """Get unified diff output from git."""
    result = subprocess.run(
        ["git", "diff", "-U0", f"{base_branch}...HEAD", "--", "*.go"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def parse_diff_ranges(diff_output: str) -> list[FileChanges]:
    """Parse git diff output and extract changed line ranges."""
    files: dict[str, list[tuple[int, int]]] = {}
    current_file: str | None = None

    # Pattern for file header: +++ b/path/to/file.go
    file_pattern = re.compile(r"^\+\+\+ b/(.+\.go)$")
    # Pattern for hunk header: @@ -old_start,old_count +new_start,new_count @@
    hunk_pattern = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

    for line in diff_output.splitlines():
        file_match = file_pattern.match(line)
        if file_match:
            current_file = file_match.group(1)
            if current_file not in files:
                files[current_file] = []
            continue

        hunk_match = hunk_pattern.match(line)
        if hunk_match and current_file:
            start_line = int(hunk_match.group(1))
            count = int(hunk_match.group(2)) if hunk_match.group(2) else 1

            if count > 0:  # Only additions/modifications, not pure deletions
                end_line = start_line + count - 1
                files[current_file].append((start_line, end_line))

    # Merge overlapping/adjacent ranges and build result
    result: list[FileChanges] = []
    for file_path, ranges in files.items():
        if not ranges:
            continue
        merged = merge_ranges(ranges)
        result.append({"file": file_path, "ranges": merged})

    return result


def merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping or adjacent line ranges."""
    if not ranges:
        return []

    sorted_ranges = sorted(ranges, key=lambda x: x[0])
    merged: list[tuple[int, int]] = [sorted_ranges[0]]

    for start, end in sorted_ranges[1:]:
        last_start, last_end = merged[-1]
        # Merge if overlapping or adjacent (within 1 line)
        if start <= last_end + 2:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))

    return merged


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract changed line ranges from git diff"
    )
    parser.add_argument(
        "base_branch",
        help="Base branch to compare against (e.g., main, develop)",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file path (default: stdout)",
    )
    args = parser.parse_args()

    try:
        diff_output = get_diff_output(args.base_branch)
        changes = parse_diff_ranges(diff_output)

        output = json.dumps(changes, indent=2)

        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
            print(f"Wrote changes to {args.output}", file=sys.stderr)
        else:
            print(output)

    except subprocess.CalledProcessError as e:
        print(f"Git error: {e.stderr}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
