#!/usr/bin/env sh
set -eu

TARGET_DIR="."
INIT_GIT=0
GITHUB_REPO=""
TEMPLATE_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ERRORS=0
WARNINGS=0

warn() {
  WARNINGS=$((WARNINGS + 1))
  printf '[WARN] %s\n' "$1" >&2
}

error() {
  ERRORS=$((ERRORS + 1))
  printf '[ERROR] %s\n' "$1" >&2
}

usage() {
  cat <<'EOF'
Usage: ./init-agents.sh [--target-dir DIR] [--init-git] [--github-repo OWNER/NAME]
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --target-dir)
      TARGET_DIR=$2
      shift 2
      ;;
    --init-git)
      INIT_GIT=1
      shift
      ;;
    --github-repo)
      GITHUB_REPO=$2
      INIT_GIT=1
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      error "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

backup_path_if_exists() {
  path=$1
  if [ ! -e "$path" ] && [ ! -L "$path" ]; then
    return
  fi
  backup_path="$path.backup"
  rm -rf "$backup_path"
  cp -R "$path" "$backup_path"
  printf '  Backup created: %s\n' "$backup_path"
}

copy_top_level_item() {
  rel=$1
  src="$TEMPLATE_ROOT/$rel"
  dst="$TARGET_DIR/$rel"
  if [ ! -e "$src" ]; then
    warn "Skipping missing template path: $rel"
    return
  fi
  mkdir -p "$(dirname "$dst")"
  backup_path_if_exists "$dst"
  cp -R "$src" "$dst"
  printf '  Copied %s\n' "$rel"
}

ensure_claude_skills_symlink() {
  mkdir -p "$TARGET_DIR/.claude"
  skills_path="$TARGET_DIR/.claude/skills"
  backup_path_if_exists "$skills_path"
  if ln -s "../.agents/skills" "$skills_path"; then
    printf '  Linked .claude/skills -> ../.agents/skills\n'
  else
    error "Failed to create .claude/skills symlink."
  fi
}

ensure_line_entries() {
  file_path=$1
  template_path=$2
  header=$3
  mkdir -p "$(dirname "$file_path")"
  [ -f "$file_path" ] || : > "$file_path"

  tmp_file=$(mktemp)
  cp "$file_path" "$tmp_file"
  added=0

  while IFS= read -r line || [ -n "$line" ]; do
    trimmed=$(printf '%s' "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    case "$trimmed" in
      ''|'#'*)
        continue
        ;;
    esac
    if ! grep -Fqx "$trimmed" "$tmp_file"; then
      if [ "$added" -eq 0 ]; then
        if [ -s "$tmp_file" ]; then
          printf '\n' >> "$tmp_file"
        fi
        if ! grep -Fqx "$header" "$tmp_file"; then
          printf '%s\n' "$header" >> "$tmp_file"
        fi
        added=1
      fi
      printf '%s\n' "$trimmed" >> "$tmp_file"
    fi
  done < "$template_path"

  if ! cmp -s "$file_path" "$tmp_file"; then
    cp "$tmp_file" "$file_path"
    rm -f "$tmp_file"
    return 0
  fi

  rm -f "$tmp_file"
  return 1
}

ensure_gitignore_entries() {
  if ensure_line_entries "$TARGET_DIR/.gitignore" "$TEMPLATE_ROOT/.gitignore-template" "# Workflow template entries"; then
    printf '  Merged workflow entries into .gitignore\n'
  else
    printf '  .gitignore already contains workflow entries\n'
  fi
}

ensure_gitexclude_entries() {
  if ensure_line_entries "$TARGET_DIR/.git/info/exclude" "$TEMPLATE_ROOT/exclude_template" "# Workflow local-only files"; then
    printf '  Updated .git/info/exclude\n'
  else
    printf '  .git/info/exclude already contains workflow entries\n'
  fi
}

github_ssh_url() {
  https_url=$1
  case "$https_url" in
    https://github.com/*)
      slug=${https_url#https://github.com/}
      slug=${slug%.git}
      slug=${slug%/}
      printf 'git@github.com:%s.git\n' "$slug"
      ;;
    *)
      return 1
      ;;
  esac
}

mkdir -p "$TARGET_DIR"
TARGET_DIR=$(CDPATH= cd -- "$TARGET_DIR" && pwd)

printf 'Copying workflow files to %s...\n' "$TARGET_DIR"
copy_top_level_item ".workflow"
copy_top_level_item ".opencode/commands"
copy_top_level_item ".agents"
ensure_claude_skills_symlink
copy_top_level_item ".spec"
copy_top_level_item "AGENTS.md"
copy_top_level_item "CLAUDE.md"

ensure_gitignore_entries

CREATED_GIT_REPO=0
if [ "$INIT_GIT" -eq 1 ] || [ -d "$TARGET_DIR/.git" ]; then
  if ! command -v git >/dev/null 2>&1; then
    error "git is not installed or not in PATH."
  else
    printf '\n=== Git Setup ===\n'
    old_pwd=$(pwd)
    cd "$TARGET_DIR"

    if [ ! -d .git ] && [ "$INIT_GIT" -eq 1 ]; then
      if git init >/dev/null 2>&1; then
        CREATED_GIT_REPO=1
        printf '  Initialized git repository\n'
      else
        error "Failed to initialize git repository."
      fi
    elif [ -d .git ]; then
      printf '  Git repository already exists\n'
    fi

    if [ -d .git ]; then
      ensure_gitexclude_entries
    fi

    if [ "$CREATED_GIT_REPO" -eq 1 ]; then
      if [ -n "$(git status --porcelain -- .gitignore 2>/dev/null || true)" ]; then
        git add -- .gitignore >/dev/null 2>&1 || error "Failed to stage .gitignore for initial commit."
        if git commit -m "chore: initialize git repository" >/dev/null 2>&1; then
          printf '  Created initial commit for .gitignore\n'
        else
          warn "Failed to create initial commit. Configure git user.name and user.email if needed."
        fi
      else
        printf '  No tracked initialization changes to commit\n'
      fi
    fi

    if [ -n "$GITHUB_REPO" ]; then
      printf '\n=== GitHub Repository Setup ===\n'
      if ! command -v gh >/dev/null 2>&1; then
        error "GitHub CLI (gh) is not installed or not in PATH."
      elif ! gh auth status >/dev/null 2>&1; then
        error "GitHub CLI is not authenticated. Run: gh auth login"
      else
        repo_url=$(gh repo view "$GITHUB_REPO" --json url -q .url 2>/dev/null || true)
        if [ -z "$repo_url" ]; then
          printf '  Creating GitHub repository: %s (private)...\n' "$GITHUB_REPO"
          if gh repo create "$GITHUB_REPO" --private >/dev/null 2>&1; then
            repo_url=$(gh repo view "$GITHUB_REPO" --json url -q .url 2>/dev/null || true)
            printf '  Repository created: %s\n' "$repo_url"
          else
            error "Failed to create GitHub repository."
          fi
        else
          printf '  Repository already exists: %s\n' "$repo_url"
        fi

        if [ -n "$repo_url" ]; then
          existing_remote=$(git remote get-url origin 2>/dev/null || true)
          ssh_url=$(github_ssh_url "$repo_url" 2>/dev/null || true)
          if [ -z "$existing_remote" ]; then
            if git remote add origin "$repo_url" >/dev/null 2>&1; then
              printf '  Added remote '\''origin'\'': %s\n' "$repo_url"
            else
              error "Failed to add remote 'origin'."
            fi
          elif [ "$existing_remote" = "$repo_url" ] || { [ -n "$ssh_url" ] && [ "$existing_remote" = "$ssh_url" ]; }; then
            printf '  Remote '\''origin'\'' already set: %s\n' "$existing_remote"
          else
            warn "Existing remote 'origin' differs from requested repository. Leaving it unchanged: $existing_remote"
          fi
        fi
      fi
    fi

    cd "$old_pwd"
  fi
fi

printf '\n'
if [ "$ERRORS" -gt 0 ]; then
  printf 'Initialization completed with errors.\n'
elif [ "$WARNINGS" -gt 0 ]; then
  printf 'Initialization completed with warnings.\n'
else
  printf "Initialization complete. Project at '%s' is ready.\n" "$TARGET_DIR"
fi

printf 'Next steps:\n'
printf '  1. Open the project in your editor\n'
printf '  2. Start OpenCode and run /specify-design\n'
printf '  3. Start Claude Code and run /specify-design\n'
printf '  4. For Codex, start codex in the project and invoke repo skills with $specify-design\n'
if [ "$INIT_GIT" -eq 0 ]; then
  printf '  5. Re-run with --init-git if you want this script to initialize git\n'
fi

if [ "$ERRORS" -gt 0 ]; then
  exit 1
fi
