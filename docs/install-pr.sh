#!/bin/bash
set -e

# Tally PR installer script
# Usage: curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/main/docs/install-pr.sh | bash -s -- <PR_NUMBER> [REPO]
#
# Examples:
#   curl -fsSL https://raw.githubusercontent.com/adriancoman/tally/main/docs/install-pr.sh | bash -s -- 1
#   curl ... | bash -s -- 1 adriancoman/tally
#   TALLY_REPO=adriancoman/tally curl ... | bash -s -- 1
#
# Requires: GitHub CLI (gh) installed and authenticated
#   brew install gh && gh auth login
#
# The script attempts to auto-detect the repository from the download URL.
# If auto-detection fails, you can override by:
#   - Setting TALLY_REPO environment variable
#   - Passing the repo as the second argument

# Auto-detect repository from script URL or use environment variable
# This allows the script to work with forks
detect_repo() {
    # Check if TALLY_REPO is explicitly set (allows override)
    if [ -n "${TALLY_REPO:-}" ]; then
        echo "$TALLY_REPO"
        return
    fi

    # Try to detect from script URL when piped via curl
    # This is challenging because curl may finish before the script runs
    # We'll try multiple methods:
    
    # Method 1: Check shell history (if available and enabled)
    if [ -n "${HISTFILE:-}" ] && [ -r "${HISTFILE:-}" ]; then
        local hist_line
        hist_line=$(tail -5 "$HISTFILE" 2>/dev/null | grep -E 'raw\.githubusercontent\.com' | tail -1 || echo "")
        if [ -n "$hist_line" ] && [[ "$hist_line" =~ raw\.githubusercontent\.com/([^/]+/[^/]+)/ ]]; then
            echo "${BASH_REMATCH[1]}"
            return
        fi
    fi
    
    # Method 2: Check all curl processes for the URL pattern (curl might still be running)
    if command -v ps >/dev/null 2>&1; then
        local curl_procs
        if [[ "$(uname -s)" == "Darwin" ]]; then
            # macOS: check all processes, use -ww for wide output
            curl_procs=$(ps -A -ww -o pid= -o command= 2>/dev/null | grep -i curl || echo "")
        else
            # Linux: check all processes
            curl_procs=$(ps -A -o pid= -o args= 2>/dev/null | grep -i curl || echo "")
        fi
        
        if [ -n "$curl_procs" ]; then
            while IFS= read -r line; do
                if [[ "$line" =~ raw\.githubusercontent\.com/([^/]+/[^/]+)/ ]]; then
                    echo "${BASH_REMATCH[1]}"
                    return
                fi
            done <<< "$curl_procs"
        fi
        
        # Method 3: Walk up the process tree to find the curl command with the URL
        local pid=$PPID
        local max_depth=5
        local depth=0
        
        while [ $depth -lt $max_depth ] && [ -n "$pid" ] && [ "$pid" != "1" ]; do
            local cmd
            # Try different ps formats for different systems (macOS, Linux)
            if [[ "$(uname -s)" == "Darwin" ]]; then
                # macOS: use -ww for wide output to get full command line
                cmd=$(ps -p "$pid" -ww -o command= 2>/dev/null || echo "")
            else
                # Linux: use -o args= or -o cmd=
                cmd=$(ps -p "$pid" -o args= -o cmd= 2>/dev/null | head -1 || echo "")
            fi
            
            if [ -n "$cmd" ]; then
                # Look for raw.githubusercontent.com URL pattern
                if [[ "$cmd" =~ raw\.githubusercontent\.com/([^/]+/[^/]+)/ ]]; then
                    echo "${BASH_REMATCH[1]}"
                    return
                fi
            fi
            
            # Move to parent process
            pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ' || echo "")
            depth=$((depth + 1))
        done
    fi

    # Try to detect from git remote if in a git repository
    if command -v git >/dev/null 2>&1 && git rev-parse --git-dir >/dev/null 2>&1; then
        local remote_url
        remote_url=$(git config --get remote.origin.url 2>/dev/null || echo "")
        if [[ "$remote_url" =~ github\.com[:/]([^/]+/[^/]+)\.git?$ ]] || [[ "$remote_url" =~ github\.com[:/]([^/]+/[^/]+)$ ]]; then
            echo "${BASH_REMATCH[1]}"
            return
        fi
    fi

    # Default fallback
    echo "davidfowl/tally"
}

INSTALL_DIR="${INSTALL_DIR:-$HOME/.tally/bin}"
TMPDIR="${TMPDIR:-/tmp}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

info() { echo -e "${GREEN}==>${NC} $1"; }
warn() { echo -e "${YELLOW}warning:${NC} $1"; }
error() { echo -e "${RED}error:${NC} $1" >&2; exit 1; }

# Check for gh CLI
check_gh() {
    if ! command -v gh &> /dev/null; then
        error "GitHub CLI (gh) is required but not installed.
Install it with:
  macOS:  brew install gh
  Linux:  https://github.com/cli/cli#installation

Then authenticate with: gh auth login"
    fi

    if ! gh auth status &> /dev/null; then
        error "GitHub CLI is not authenticated. Run: gh auth login"
    fi
}

# Detect OS
detect_os() {
    case "$(uname -s)" in
        Linux*)  echo "linux" ;;
        Darwin*) echo "macos" ;;
        *)       error "Unsupported OS: $(uname -s)" ;;
    esac
}

# Detect architecture
detect_arch() {
    case "$(uname -m)" in
        x86_64|amd64)  echo "amd64" ;;
        arm64|aarch64) echo "arm64" ;;
        *)             error "Unsupported architecture: $(uname -m)" ;;
    esac
}

# Get the latest successful workflow run for a PR
get_workflow_run_id() {
    local repo="$1"
    local pr_number="$2"

    # Get the head SHA of the PR
    local head_sha
    head_sha=$(gh api "repos/${repo}/pulls/${pr_number}" --jq '.head.sha')

    if [ -z "$head_sha" ]; then
        error "Could not find PR #${pr_number}"
    fi

    info "PR #${pr_number} head commit: ${head_sha:0:7}"

    # Find the latest successful workflow run for this commit
    local run_id
    run_id=$(gh api "repos/${repo}/actions/workflows/pr-build.yml/runs?head_sha=${head_sha}&status=success" \
        --jq '.workflow_runs[0].id')

    if [ -z "$run_id" ] || [ "$run_id" = "null" ]; then
        error "No successful build found for PR #${pr_number}.
Check https://github.com/${repo}/pull/${pr_number}/checks"
    fi

    echo "$run_id"
}

main() {
    local pr_number="$1"
    local repo_override="$2"

    if [ -z "$pr_number" ]; then
        error "Usage: $0 <PR_NUMBER> [REPO]

Example: $0 42
Example: $0 42 adriancoman/tally

The repository will be auto-detected from the download URL when possible.
You can also set TALLY_REPO environment variable or pass it as the second argument."
    fi

    # Determine repository: argument > env var > auto-detect > default
    local REPO
    if [ -n "$repo_override" ]; then
        REPO="$repo_override"
    elif [ -n "${TALLY_REPO:-}" ]; then
        REPO="${TALLY_REPO}"
    else
        REPO=$(detect_repo)
    fi

    check_gh

    # Show which repository is being used
    if [ -n "$repo_override" ]; then
        info "Using repository from argument: ${REPO}"
    elif [ -n "${TALLY_REPO:-}" ]; then
        info "Using repository from TALLY_REPO: ${REPO}"
    elif [[ "$REPO" != "davidfowl/tally" ]]; then
        info "Auto-detected repository: ${REPO}"
    else
        warn "Could not auto-detect repository, using default: ${REPO}"
        warn "If this is wrong, set TALLY_REPO or pass repo as second argument:"
        warn "  TALLY_REPO=adriancoman/tally curl ... | bash -s -- $pr_number"
        warn "  curl ... | bash -s -- $pr_number adriancoman/tally"
    fi

    info "Installing tally from PR #${pr_number}..."

    OS=$(detect_os)
    ARCH=$(detect_arch)
    PLATFORM="${OS}-${ARCH}"

    info "Detected: ${PLATFORM}"

    # Get workflow run ID
    RUN_ID=$(get_workflow_run_id "$REPO" "$pr_number")
    info "Found workflow run: ${RUN_ID}"

    # Download artifact
    DOWNLOAD_PATH="${TMPDIR}/tally-pr-$$"
    mkdir -p "$DOWNLOAD_PATH"

    ARTIFACT_NAME="tally-${PLATFORM}"
    info "Downloading ${ARTIFACT_NAME}..."

    if ! gh run download "$RUN_ID" -R "$REPO" --name "$ARTIFACT_NAME" -D "$DOWNLOAD_PATH"; then
        error "Failed to download artifact. The build may still be in progress.
Check https://github.com/${REPO}/actions/runs/${RUN_ID}"
    fi

    # Extract
    info "Extracting..."
    unzip -q "${DOWNLOAD_PATH}/${ARTIFACT_NAME}.zip" -d "${DOWNLOAD_PATH}"

    # Install
    mkdir -p "$INSTALL_DIR"
    mv "${DOWNLOAD_PATH}/tally" "${INSTALL_DIR}/tally"
    chmod +x "${INSTALL_DIR}/tally"

    # Cleanup
    rm -rf "$DOWNLOAD_PATH"

    # Verify installation
    info "Successfully installed tally from PR #${pr_number}!"
    "${INSTALL_DIR}/tally" version

    # Add to PATH if not already there
    if [[ ":$PATH:" != *":${INSTALL_DIR}:"* ]]; then
        add_to_path
    fi
}

# Detect shell and add to appropriate config file
add_to_path() {
    local shell_name
    shell_name=$(basename "${SHELL:-/bin/bash}")

    local config_file=""
    local path_line=""

    case "$shell_name" in
        bash)
            if [[ -f "$HOME/.bashrc" ]]; then
                config_file="$HOME/.bashrc"
            elif [[ -f "$HOME/.bash_profile" ]]; then
                config_file="$HOME/.bash_profile"
            else
                config_file="$HOME/.bashrc"
            fi
            path_line='export PATH="$HOME/.tally/bin:$PATH"'
            ;;
        zsh)
            config_file="${ZDOTDIR:-$HOME}/.zshrc"
            path_line='export PATH="$HOME/.tally/bin:$PATH"'
            ;;
        fish)
            config_file="${XDG_CONFIG_HOME:-$HOME/.config}/fish/config.fish"
            path_line='fish_add_path $HOME/.tally/bin'
            ;;
        *)
            # Fallback to .profile for other POSIX shells
            config_file="$HOME/.profile"
            path_line='export PATH="$HOME/.tally/bin:$PATH"'
            ;;
    esac

    # Create config file directory if needed
    mkdir -p "$(dirname "$config_file")"

    # Check if already added
    if [[ -f "$config_file" ]] && grep -q "/.tally/bin" "$config_file" 2>/dev/null; then
        return
    fi

    # Add to config file
    echo "" >> "$config_file"
    echo "# Added by tally installer" >> "$config_file"
    echo "$path_line" >> "$config_file"

    info "Added tally to PATH in $config_file"
    echo ""
    echo "Restart your terminal or run:"
    echo "  source $config_file"
}

main "$@"
