#!/usr/bin/env bash
#
# go-diff-linter: Run golangci-lint only on changed code
#
# Usage: run_lint.sh <base_branch> [-o output_file]
#
# This script:
# 1. Gets changed line ranges between base_branch and HEAD
# 2. Runs golangci-lint with --new-from-rev flag
# 3. Filters lint issues to only those in changed ranges
# 4. Outputs a report for Claude to review and fix manually
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
WORK_DIR="${WORK_DIR:-.golangci-diff}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

usage() {
    echo "Usage: $0 <base_branch> [-o output_file]"
    echo ""
    echo "Arguments:"
    echo "  base_branch   Base branch to compare against (e.g., main, develop)"
    echo "  -o            Output report file path (default: .golangci-diff/report.md)"
    echo ""
    echo "Examples:"
    echo "  $0 main"
    echo "  $0 develop -o lint-report.md"
    exit 1
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Parse arguments
if [[ $# -lt 1 ]]; then
    usage
fi

BASE_BRANCH="$1"
OUTPUT_FILE="$WORK_DIR/report.md"

shift
while [[ $# -gt 0 ]]; do
    case $1 in
        -o)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        *)
            usage
            ;;
    esac
done

# Create work directory
mkdir -p "$WORK_DIR"

# Step 1: Get changed line ranges
log_info "Getting changed files and line ranges (base: $BASE_BRANCH)..."
python3 "$SCRIPT_DIR/get_diff_ranges.py" "$BASE_BRANCH" -o "$WORK_DIR/changes.json"

# Check if there are any changes
if [[ ! -s "$WORK_DIR/changes.json" ]] || [[ "$(cat "$WORK_DIR/changes.json")" == "[]" ]]; then
    log_info "No Go file changes detected between $BASE_BRANCH and HEAD"
    exit 0
fi

log_info "Changed files:"
jq -r '.[].file' "$WORK_DIR/changes.json" | sed 's/^/  - /'

# Step 2: Always use skill's config for consistent linting
log_info "Using skill's .golangci.yaml config..."
if [[ -f ".golangci.yaml" ]]; then
    mv ".golangci.yaml" "$WORK_DIR/.golangci.yaml.backup"
    RESTORE_CONFIG=true
else
    RESTORE_CONFIG=false
fi
cp "$SKILL_DIR/assets/.golangci.yaml" ".golangci.yaml"

# Step 3: Get unique packages from changed files
log_info "Extracting packages from changed files..."
PACKAGES=$(jq -r '.[].file' "$WORK_DIR/changes.json" | xargs -I{} dirname {} | sort -u | sed 's|^|./|' | tr '\n' ' ')
log_info "Packages to lint: $PACKAGES"

# Step 4: Run golangci-lint
log_info "Running golangci-lint with --new-from-rev=$BASE_BRANCH..."

# golangci-lint v2 uses --output.json.path instead of --out-format
# Run only on changed packages to avoid typecheck errors in unrelated code
eval "golangci-lint run --new-from-rev=$BASE_BRANCH --output.json.path=$WORK_DIR/lint_output.json --issues-exit-code=0 $PACKAGES" 2>&1 || true
log_info "golangci-lint completed"

# Step 5: Run formatters (golangci-lint v2 runs formatters separately)
log_info "Applying formatters (gofumpt, goimports) to changed files..."
CHANGED_FILES=$(jq -r '.[].file' "$WORK_DIR/changes.json" | tr '\n' ' ')
eval "golangci-lint fmt -E gofumpt -E goimports $CHANGED_FILES" 2>&1 || true
log_info "Formatters applied"

# Step 6: Generate report for Claude
log_info "Generating report..."
python3 "$SCRIPT_DIR/filter_lint_issues.py" \
    "$WORK_DIR/lint_output.json" \
    "$WORK_DIR/changes.json" \
    --report "$OUTPUT_FILE"

# Restore original config if it existed
rm -f ".golangci.yaml"
if [[ "$RESTORE_CONFIG" == "true" ]]; then
    mv "$WORK_DIR/.golangci.yaml.backup" ".golangci.yaml"
fi

# Show summary
LINT_COUNT=$(jq '.lint_issues | length' "$WORK_DIR/filtered_issues.json" 2>/dev/null || echo "0")

echo ""
if [[ "$LINT_COUNT" -gt 0 ]]; then
    log_warn "Found $LINT_COUNT lint issues in changed code"
    log_info "Formatters have been automatically applied to changed files"
    log_info "Report saved to: $OUTPUT_FILE"
    log_info "Claude should read this report and fix the lint issues manually"
    exit 1
fi

log_info "No lint issues in changed code!"
log_info "Formatters have been automatically applied to changed files"
exit 0
