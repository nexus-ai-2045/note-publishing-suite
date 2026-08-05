#!/bin/sh
set -u

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
CHECKED=0
ERRORS=""
JSON=0

if [ "${1:-}" = "--json" ] || [ "${1:-}" = "-Json" ]; then
  JSON=1
fi

add_checked() {
  CHECKED=$((CHECKED + 1))
}

add_error() {
  ERRORS="${ERRORS}
$1"
}

require_file() {
  if [ -f "$ROOT/$1" ]; then
    add_checked
  else
    add_error "missing required file: $1"
  fi
}

contains() {
  if grep -F "$2" "$ROOT/$1" >/dev/null 2>&1; then
    add_checked
  else
    add_error "$1 missing: $2"
  fi
}

run_json_ok() {
  label=$1
  shift
  output=$(cd "$ROOT" && "$@" 2>&1)
  status=$?
  if [ "$status" -ne 0 ]; then
    add_error "$label failed: exit=$status output=$output"
    return
  fi
  add_checked
}

for item in \
  SKILL.md \
  package.yaml \
  README.md \
  CHANGELOG.md \
  PUBLIC_READY.md \
  PUBLIC_RELEASE_CHECKLIST.md \
  scripts/review_draft.py \
  scripts/docs_sync_check.py \
  scripts/verify_public_package.sh \
  scripts/verify_public_package.ps1 \
  tests/test_review_draft_cli.py \
  data/note_editor_prepublish_observation.fixture.json \
  content/drafts/sample-note-prepublish-fixture.md
do
  require_file "$item"
done

contains package.yaml "scripts/review_draft.py"
contains package.yaml "scripts/docs_sync_check.py"
contains package.yaml "scripts/verify_public_package.sh"
contains package.yaml "data/note_editor_prepublish_observation.fixture.json"
contains package.yaml "sh scripts/verify_public_package.sh"
contains README.md "review-draft"
contains README.md "build-context-card"
contains README.md "sh scripts/verify_public_package.sh"
contains README.md "scripts/note_editor_prepublish_verify.py data/note_editor_prepublish_observation.fixture.json --json"
contains PUBLIC_READY.md "sh scripts/verify_public_package.sh"
contains PUBLIC_RELEASE_CHECKLIST.md "sh scripts/verify_public_package.sh"

run_json_ok "docs sync check" python3 scripts/docs_sync_check.py --base-ref HEAD^

run_json_ok "provenance leak check" python3 scripts/provenance_leak_check.py --scope all --json
run_json_ok "provenance label check" python3 scripts/provenance_label_check.py content/drafts/caramel-provenance-label-fixture.md --json
run_json_ok "GitHub identity guard" python3 scripts/github_identity_guard.py --json
run_json_ok "Japanese closeout language check" python3 scripts/japanese_closeout_language_check.py --json
run_json_ok "Note image upload boundary check" python3 scripts/note_image_upload_boundary_check.py --json
run_json_ok "Note editor prepublish observation fixture" python3 scripts/note_editor_prepublish_verify.py data/note_editor_prepublish_observation.fixture.json --json
run_json_ok "local draft QA proof" python3 scripts/run_local_draft_qa_proof.py --json
run_json_ok "review context card fixture" python3 scripts/review_draft.py build-context-card content/drafts/sample-note-prepublish-fixture.md --json

review_output=$(cd "$ROOT" && python3 scripts/review_draft.py review-draft content/drafts/sample-note-prepublish-fixture.md --json 2>&1)
review_status=$?
if [ "$review_status" -eq 2 ] && printf '%s' "$review_output" | grep -F '"verdict": "blocked"' >/dev/null && printf '%s' "$review_output" | grep -F '"reason_codes"' >/dev/null && printf '%s' "$review_output" | grep -F '"confirmation_questions"' >/dev/null; then
  add_checked
else
  add_error "review-draft fixture contract failed: exit=$review_status output=$review_output"
fi

if [ -n "$ERRORS" ]; then
  if [ "$JSON" -eq 1 ]; then
    python3 - "$CHECKED" "$ERRORS" <<'PY'
import json
import sys

checked = int(sys.argv[1])
errors = [line for line in sys.argv[2].splitlines() if line]
print(json.dumps({
    "ok": False,
    "command": "sh scripts/verify_public_package.sh",
    "checked_count": checked,
    "verification_lanes": ["embedded_copy", "standalone_clone"],
    "errors": errors,
    "external_actions_performed": [],
    "publication_actions_performed": [],
}, ensure_ascii=False, indent=2))
PY
  else
    echo "NG public package verification failed"
    printf '%s\n' "$ERRORS" | sed '/^$/d; s/^/- /'
  fi
  exit 1
fi

if [ "$JSON" -eq 1 ]; then
  python3 - "$CHECKED" <<'PY'
import json
import sys

print(json.dumps({
    "ok": True,
    "command": "sh scripts/verify_public_package.sh",
    "checked_count": int(sys.argv[1]),
    "verification_lanes": ["embedded_copy", "standalone_clone"],
    "errors": [],
    "external_actions_performed": [],
    "publication_actions_performed": [],
}, ensure_ascii=False, indent=2))
PY
else
  echo "OK public package verification passed"
  echo "checked_count=$CHECKED"
  echo "external_actions_performed=0"
  echo "publication_actions_performed=0"
fi
