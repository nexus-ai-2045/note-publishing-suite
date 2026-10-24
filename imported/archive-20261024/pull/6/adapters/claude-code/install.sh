#!/bin/bash
# Claude Code 用 pointer skill installer
# 使い方: bash adapters/claude-code/install.sh [WORKSPACE_ROOT]
#   PACKAGE_ROOT  = この repo の絶対 path (自動検出)
#   WORKSPACE_ROOT = 記事 drafts / data 台帳 / scripts を持つ作業 repo (省略時 = PACKAGE_ROOT)
set -eu
umask 077
PACKAGE_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORKSPACE_ROOT="${1:-$PACKAGE_ROOT}"
DEST="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
escape_sed_replacement() {
  printf '%s' "$1" | sed 's/[\\&|]/\\&/g'
}
PACKAGE_ROOT_SED=$(escape_sed_replacement "$PACKAGE_ROOT")
WORKSPACE_ROOT_SED=$(escape_sed_replacement "$WORKSPACE_ROOT")
mkdir -p "$DEST"
for d in "$PACKAGE_ROOT"/adapters/claude-code/*/; do
  name=$(basename "$d")
  if [ -L "$DEST/$name" ]; then
    echo "NG: installed pointer directory must not be a symlink: $DEST/$name" >&2
    exit 1
  fi
  mkdir -p "$DEST/$name"
  tmp_pointer=$(mktemp "$DEST/$name/.SKILL.md.XXXXXX")
  sed -e "s|{{PACKAGE_ROOT}}|$PACKAGE_ROOT_SED|g" \
      -e "s|{{WORKSPACE_ROOT}}|$WORKSPACE_ROOT_SED|g" \
      "$d/SKILL.md" > "$tmp_pointer"
  chmod 644 "$tmp_pointer"
  mv -f "$tmp_pointer" "$DEST/$name/SKILL.md"
  echo "installed: $DEST/$name/SKILL.md"
done
python3 "$PACKAGE_ROOT/scripts/skill_pointer_check.py" \
  --installed-root "$DEST" \
  --json
echo "OK: 次の Claude Code セッションから note 系トリガで発火します"
