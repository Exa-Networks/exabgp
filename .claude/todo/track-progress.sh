#!/bin/bash
# Progress tracking script for ExaBGP testing implementation
# Usage: ./track-progress.sh [command]

set -e

PROGRESS_FILE=".claude/todo/PROGRESS.md"
TODO_DIR=".claude/todo"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to count completed tasks in a file
count_completed_tasks() {
    local file=$1
    if [ ! -f "$file" ]; then
        echo "0/0"
        return
    fi

    local total=$(grep -c "^- \[ \]" "$file" 2>/dev/null || echo "0")
    local completed=$(grep -c "^- \[x\]" "$file" 2>/dev/null || echo "0")
    echo "$completed/$total"
}

# Function to show overall progress
show_progress() {
    echo -e "${BLUE}=== ExaBGP Testing Implementation Progress ===${NC}\n"

    # Phase 0
    local p0=$(count_completed_tasks "$TODO_DIR/00-SETUP-FOUNDATION.md")
    echo -e "${YELLOW}Phase 0: Foundation Setup${NC}"
    echo -e "  File: 00-SETUP-FOUNDATION.md"
    echo -e "  Progress: $p0"
    echo ""

    # Phase 1.1
    local p1_1=$(count_completed_tasks "$TODO_DIR/01-FUZZ-MESSAGE-HEADER.md")
    echo -e "${YELLOW}Phase 1.1: Message Header Fuzzing${NC}"
    echo -e "  File: 01-FUZZ-MESSAGE-HEADER.md"
    echo -e "  Progress: $p1_1"
    echo ""

    # Phase 1.2
    local p1_2=$(count_completed_tasks "$TODO_DIR/02-FUZZ-UPDATE-MESSAGE.md")
    echo -e "${YELLOW}Phase 1.2: UPDATE Message Fuzzing${NC}"
    echo -e "  File: 02-FUZZ-UPDATE-MESSAGE.md"
    echo -e "  Progress: $p1_2"
    echo ""

    # Phase 1.3
    local p1_3=$(count_completed_tasks "$TODO_DIR/03-FUZZ-ATTRIBUTES.md")
    echo -e "${YELLOW}Phase 1.3: Attributes Fuzzing${NC}"
    echo -e "  File: 03-FUZZ-ATTRIBUTES.md"
    echo -e "  Progress: $p1_3"
    echo ""

    # Test statistics
    echo -e "${BLUE}=== Test Statistics ===${NC}\n"

    if [ -d "tests" ]; then
        local test_files=$(find tests -name "*_test.py" -o -name "fuzz_*.py" 2>/dev/null | wc -l)
        echo -e "Test files: ${GREEN}$test_files${NC}"

        local fuzz_files=$(find tests/fuzz -name "*.py" 2>/dev/null | wc -l)
        echo -e "Fuzzing test files: ${GREEN}$fuzz_files${NC}"

        local test_lines=$(find tests -name "*.py" -exec wc -l {} + 2>/dev/null | tail -1 | awk '{print $1}')
        echo -e "Test code lines: ${GREEN}$test_lines${NC}"
    else
        echo -e "${YELLOW}Tests directory not found${NC}"
    fi
    echo ""
}

# Function to show current coverage
show_coverage() {
    echo -e "${BLUE}=== Current Test Coverage ===${NC}\n"

    if [ ! -d "src" ]; then
        echo -e "${RED}Source directory not found${NC}"
        return
    fi

    if ! command -v pytest &> /dev/null; then
        echo -e "${YELLOW}pytest not installed${NC}"
        return
    fi

    echo "Running coverage analysis..."
    env PYTHONPATH=src pytest --cov=exabgp --cov-report=term-missing --quiet 2>/dev/null || {
        echo -e "${YELLOW}Coverage analysis failed (tests may not be set up yet)${NC}"
    }
}

# Function to mark a task as complete
mark_complete() {
    local phase=$1
    local task=$2

    if [ -z "$phase" ] || [ -z "$task" ]; then
        echo -e "${RED}Usage: $0 complete <phase-file> <task-number>${NC}"
        echo "Example: $0 complete 00-SETUP-FOUNDATION.md 0.1"
        return 1
    fi

    local file="$TODO_DIR/$phase"
    if [ ! -f "$file" ]; then
        echo -e "${RED}File not found: $file${NC}"
        return 1
    fi

    # Use sed to replace [ ] with [x] for specific task
    # This is a simple implementation - may need refinement
    echo -e "${YELLOW}Marking task $task as complete in $phase${NC}"
    echo -e "${YELLOW}Please manually edit the file to mark tasks complete${NC}"
}

# Function to show next steps
show_next() {
    echo -e "${BLUE}=== Next Steps ===${NC}\n"

    # Find first uncompleted task in each phase
    for file in "$TODO_DIR"/*.md; do
        if [[ "$file" == *"README.md" ]] || [[ "$file" == *"PROGRESS.md" ]]; then
            continue
        fi

        local first_incomplete=$(grep -n "^- \[ \]" "$file" 2>/dev/null | head -1)
        if [ -n "$first_incomplete" ]; then
            local line_num=$(echo "$first_incomplete" | cut -d: -f1)
            local task=$(echo "$first_incomplete" | cut -d: -f2-)
            local filename=$(basename "$file")
            echo -e "${YELLOW}$filename${NC}"
            echo -e "  Next: $task"
            echo ""
        fi
    done
}

# Function to generate progress report
generate_report() {
    echo -e "${BLUE}=== Progress Report ===${NC}\n"
    echo "Generated: $(date)"
    echo ""

    show_progress
    echo ""
    show_next
}

# Function to update PROGRESS.md with current stats
update_progress_file() {
    echo -e "${BLUE}Updating PROGRESS.md...${NC}"

    # Update last updated date
    sed -i "s/\*\*Last Updated\*\*:.*/\*\*Last Updated\*\*: $(date '+%Y-%m-%d %H:%M')/" "$PROGRESS_FILE"

    echo -e "${GREEN}PROGRESS.md updated. Please manually update task completions.${NC}"
}

# Main command dispatcher
case "${1:-}" in
    "show"|"")
        show_progress
        ;;
    "coverage")
        show_coverage
        ;;
    "next")
        show_next
        ;;
    "report")
        generate_report
        ;;
    "update")
        update_progress_file
        ;;
    "complete")
        mark_complete "$2" "$3"
        ;;
    "help")
        echo "ExaBGP Testing Progress Tracker"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  show       - Show current progress (default)"
        echo "  coverage   - Run and display test coverage"
        echo "  next       - Show next tasks to work on"
        echo "  report     - Generate full progress report"
        echo "  update     - Update PROGRESS.md timestamp"
        echo "  help       - Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0                    # Show progress"
        echo "  $0 coverage           # Show coverage"
        echo "  $0 next               # Show next tasks"
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac
