#!/bin/bash
# Claude Code 用 pointer skill installer
# 使い方: bash adapters/claude-code/install.sh WORKSPACE_ROOT
#   PACKAGE_ROOT  = この repo の絶対 path (自動検出)
#   WORKSPACE_ROOT = 記事 drafts / data 台帳 / scripts を持つ作業 repo (明示指定必須)
set -euo pipefail
umask 077
PACKAGE_ROOT="$(cd "$(dirname "$0")/../.." && pwd -P)"
WORKSPACE_ROOT="${1:-}"
RUNTIME="${NOTE_SKILL_RUNTIME:-claude}"
case "$RUNTIME" in
  claude) DEST="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}" ;;
  codex) DEST="${CODEX_SKILLS_DIR:-${CODEX_HOME:-$HOME/.codex}/skills}" ;;
  *) echo "NG: unknown NOTE_SKILL_RUNTIME: $RUNTIME" >&2; exit 1 ;;
esac
# 壊れた正本から配布しない。既存の共通検査を利用する。
python3 "$PACKAGE_ROOT/scripts/skill_pointer_check.py" --json
PACKAGE_ROOT_POINTER="$PACKAGE_ROOT"
WORKSPACE_ROOT_POINTER="$WORKSPACE_ROOT"
DEST_POINTER="$DEST"
if command -v cygpath >/dev/null 2>&1; then
  WORKSPACE_ROOT="$(cygpath -u "$WORKSPACE_ROOT")"
  DEST="$(cygpath -u "$DEST")"
  PACKAGE_ROOT_POINTER="$(cygpath -w "$PACKAGE_ROOT")"
  WORKSPACE_ROOT_POINTER="$(cygpath -w "$WORKSPACE_ROOT")"
  DEST_POINTER="$(cygpath -w "$DEST")"
elif command -v wslpath >/dev/null 2>&1; then
  WORKSPACE_ROOT="$(wslpath -u "$WORKSPACE_ROOT")"
  DEST="$(wslpath -u "$DEST")"
  PACKAGE_ROOT_POINTER="$PACKAGE_ROOT"
  WORKSPACE_ROOT_POINTER="$WORKSPACE_ROOT"
  DEST_POINTER="$DEST"
fi
if [ "$RUNTIME" = codex ] || [ "$RUNTIME" = claude ]; then
  if [ "$#" -ne 1 ] || [ ! -d "$WORKSPACE_ROOT" ]; then
    echo "NG: $RUNTIME requires one explicit existing workspace directory" >&2
    exit 1
  fi
  WORKSPACE_ROOT="$(cd "$WORKSPACE_ROOT" && pwd -P)"
  case "$WORKSPACE_ROOT/" in
    "$PACKAGE_ROOT/"*) echo "NG: workspace must be outside the package" >&2; exit 1 ;;
  esac
  WORKSPACE_ROOT_POINTER="$WORKSPACE_ROOT"
  if command -v cygpath >/dev/null 2>&1; then
    WORKSPACE_ROOT_POINTER="$(cygpath -w "$WORKSPACE_ROOT")"
  fi
fi
escape_sed_replacement() {
  printf '%s' "$1" | sed 's/[\\&|]/\\&/g'
}
PACKAGE_ROOT_SED=$(escape_sed_replacement "$PACKAGE_ROOT_POINTER")
WORKSPACE_ROOT_SED=$(escape_sed_replacement "$WORKSPACE_ROOT_POINTER")
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
      "$d/SKILL.md" | awk -v runtime="$RUNTIME" '
        runtime == "codex" && /^## Codex.*読み替え/ { skip = 1; next }
        /^## / { skip = 0 }
        !skip {
          if (runtime == "codex") gsub(/Claude Code [Pp]ointer/, "Codex pointer")
          print
        }
      ' > "$tmp_pointer"
  chmod 644 "$tmp_pointer"
  mv -f "$tmp_pointer" "$DEST/$name/SKILL.md"
  echo "installed: $DEST/$name/SKILL.md"
done
python3 "$PACKAGE_ROOT/scripts/skill_pointer_check.py" \
  --installed-root "$DEST_POINTER" \
  --json
echo "OK: $RUNTIME 用 pointer を検査済み。次のセッションで discovery と実行を確認してください"
echo '初回設定は別途確認します。保存先・読んでよい素材・本人の文体参照について、次のセッションで「NPSの初回設定から案内して」と依頼してください。既存settingsは再初期化しません。手順: references/note-workflow-review-contract.md の初回設定の案内。'
