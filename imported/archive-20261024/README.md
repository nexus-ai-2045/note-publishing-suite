# 控えから取り込んだ古い版（2026-10-24）

このフォルダには、履歴を作り直す前の非公開の控えにだけ残っていた中身を、消さずに残すために置いています。

- 置き方: `<控えの枝またはタグ>/<元のパス>`。中身は控えのままです（下の「伏せたもの」を除く）。
- ここにあるファイルは実行も読み込みもされません。テストの収集からも外しています。
- 今のコードへ採り入れるかは、ファイルごとに別のPRで決めます。
- 公開側の履歴に同じ中身があるもの、行がすべて公開側にあるもの、ほかの版で行がそろうものは入れていません。
- 意図して外されていたもの（個人の情報を含む、公開側で削除済みなど）は入れていません。

## 入れたファイル

| 元のパス | 控えの枝・タグ | 置き場所 | 備考 |
|---|---|---|---|
| `README.md` | `codex/nps-editor-workflow-efficiency-20261023` ほか1 | `codex/nps-editor-workflow-efficiency-20261023/README.md` |  |
| `README.rendered.html` | `codex/nps-editor-workflow-efficiency-20261023` ほか1 | `codex/nps-editor-workflow-efficiency-20261023/README.rendered.html` |  |
| `package.yaml` | `codex/nps-editor-workflow-efficiency-20261023` ほか1 | `codex/nps-editor-workflow-efficiency-20261023/package.yaml` |  |
| `README.md` | `codex/nps-note-ops-feedback-20261023` ほか1 | `codex/nps-note-ops-feedback-20261023/README.md` |  |
| `README.rendered.html` | `codex/nps-note-ops-feedback-20261023` ほか1 | `codex/nps-note-ops-feedback-20261023/README.rendered.html` |  |
| `package.yaml` | `codex/nps-note-ops-feedback-20261023` ほか1 | `codex/nps-note-ops-feedback-20261023/package.yaml` |  |
| `.github/workflows/preflight.yml` | `main` ほか7 | `main/.github/workflows/preflight.yml` |  |
| `.repo-preflight/ratchet-baseline.json` | `main` ほか11 | `main/.repo-preflight/ratchet-baseline.json` |  |
| `PREFLIGHT.md` | `main` ほか11 | `main/PREFLIGHT.md` |  |
| `PUBLIC_READY.md` | `main` ほか11 | `main/PUBLIC_READY.md` |  |
| `README.md` | `main` ほか1 | `main/README.md` |  |
| `README.rendered.html` | `main` ほか1 | `main/README.rendered.html` |  |
| `docs/note-preview/editor-dom-analysis.md` | `main` ほか69 | `main/docs/note-preview/editor-dom-analysis.md` |  |
| `package.yaml` | `main` ほか1 | `main/package.yaml` |  |
| `references/note-workflow-review-contract.md` | `main` ほか3 | `main/references/note-workflow-review-contract.md` |  |
| `scripts/note_editor_guarded_input.mjs` | `main` ほか6 | `main/scripts/note_editor_guarded_input.mjs` |  |
| `scripts/note_editor_timeout_recovery.py` | `main` ほか85 | `main/scripts/note_editor_timeout_recovery.py` |  |
| `scripts/note_workflow_gate.py` | `main` ほか3 | `main/scripts/note_workflow_gate.py` |  |
| `scripts/provenance_label_check.py` | `main` ほか3 | `main/scripts/provenance_label_check.py` |  |
| `tests/test_note_editor_timeout_recovery.py` | `main` ほか85 | `main/tests/test_note_editor_timeout_recovery.py` |  |
| `tests/test_note_virtual_preview.py` | `main` ほか48 | `main/tests/test_note_virtual_preview.py` |  |
| `writing-app/package-lock.json` | `main` ほか1 | `main/writing-app/package-lock.json` |  |
| `writing-app/package.json` | `main` ほか1 | `main/writing-app/package.json` |  |
| `.github/workflows/test.yml` | `pull/1` ほか1 | `pull/1/.github/workflows/test.yml` |  |
| `CHANGELOG.md` | `pull/1` ほか1 | `pull/1/CHANGELOG.md` |  |
| `PUBLIC_RELEASE_CHECKLIST.md` | `pull/1` ほか1 | `pull/1/PUBLIC_RELEASE_CHECKLIST.md` |  |
| `README.md` | `pull/1` ほか1 | `pull/1/README.md` |  |
| `README.rendered.html` | `pull/1` ほか1 | `pull/1/README.rendered.html` |  |
| `ROADMAP.md` | `pull/1` ほか13 | `pull/1/ROADMAP.md` |  |
| `adapters/claude-code/install.sh` | `pull/1` ほか4 | `pull/1/adapters/claude-code/install.sh` |  |
| `data/note_image_upload_automation_policy.json` | `pull/1` ほか4 | `pull/1/data/note_image_upload_automation_policy.json` |  |
| `package.yaml` | `pull/1` ほか1 | `pull/1/package.yaml` |  |
| `references/note-editor-capability-inventory.md` | `pull/1` ほか8 | `pull/1/references/note-editor-capability-inventory.md` |  |
| `scripts/note_image_upload_boundary_check.py` | `pull/1` ほか4 | `pull/1/scripts/note_image_upload_boundary_check.py` |  |
| `scripts/note_preview.py` | `pull/1` ほか15 | `pull/1/scripts/note_preview.py` |  |
| `scripts/post_publish.py` | `pull/1` ほか7 | `pull/1/scripts/post_publish.py` |  |
| `scripts/provenance_label_check.py` | `pull/1` ほか15 | `pull/1/scripts/provenance_label_check.py` |  |
| `skills/note-draft-production/SKILL.md` | `pull/1` ほか15 | `pull/1/skills/note-draft-production/SKILL.md` |  |
| `skills/note-editor-ops/SKILL.md` | `pull/1` ほか8 | `pull/1/skills/note-editor-ops/SKILL.md` |  |
| `skills/note-postpublish-ledger/SKILL.md` | `pull/1` ほか7 | `pull/1/skills/note-postpublish-ledger/SKILL.md` |  |
| `CHANGELOG.md` | `pull/10` | `pull/10/CHANGELOG.md` |  |
| `README.md` | `pull/10` | `pull/10/README.md` |  |
| `README.rendered.html` | `pull/10` | `pull/10/README.rendered.html` |  |
| `docs/superpowers/specs/2026-07-16-docs-sync-design.md` | `pull/10` ほか1 | `pull/10/docs/superpowers/specs/2026-07-16-docs-sync-design.md` |  |
| `package.yaml` | `pull/10` | `pull/10/package.yaml` |  |
| `README.md` | `pull/11` | `pull/11/README.md` |  |
| `README.rendered.html` | `pull/11` | `pull/11/README.rendered.html` |  |
| `package.yaml` | `pull/11` | `pull/11/package.yaml` |  |
| `README.md` | `pull/12` | `pull/12/README.md` |  |
| `README.rendered.html` | `pull/12` | `pull/12/README.rendered.html` |  |
| `package.yaml` | `pull/12` | `pull/12/package.yaml` |  |
| `README.md` | `pull/13` | `pull/13/README.md` |  |
| `README.rendered.html` | `pull/13` | `pull/13/README.rendered.html` |  |
| `package.yaml` | `pull/13` | `pull/13/package.yaml` |  |
| `README.md` | `pull/14` | `pull/14/README.md` |  |
| `README.rendered.html` | `pull/14` | `pull/14/README.rendered.html` |  |
| `package.yaml` | `pull/14` | `pull/14/package.yaml` |  |
| `README.md` | `pull/15` | `pull/15/README.md` |  |
| `README.rendered.html` | `pull/15` | `pull/15/README.rendered.html` |  |
| `package.yaml` | `pull/15` | `pull/15/package.yaml` |  |
| `README.md` | `pull/16` | `pull/16/README.md` |  |
| `README.rendered.html` | `pull/16` | `pull/16/README.rendered.html` |  |
| `package.yaml` | `pull/16` | `pull/16/package.yaml` |  |
| `README.md` | `pull/3` | `pull/3/README.md` |  |
| `README.rendered.html` | `pull/3` | `pull/3/README.rendered.html` |  |
| `package.yaml` | `pull/3` | `pull/3/package.yaml` |  |
| `scripts/review_draft.py` | `pull/3` ほか13 | `pull/3/scripts/review_draft.py` |  |
| `README.md` | `pull/30` | `pull/30/README.md` |  |
| `README.rendered.html` | `pull/30` | `pull/30/README.rendered.html` |  |
| `package.yaml` | `pull/30` | `pull/30/package.yaml` |  |
| `scripts/note_preview.py` | `pull/30` ほか6 | `pull/30/scripts/note_preview.py` |  |
| `tests/test_provenance_draft_review.py` | `pull/30` ほか6 | `pull/30/tests/test_provenance_draft_review.py` |  |
| `README.md` | `pull/31` | `pull/31/README.md` |  |
| `README.rendered.html` | `pull/31` | `pull/31/README.rendered.html` |  |
| `package.yaml` | `pull/31` | `pull/31/package.yaml` |  |
| `README.md` | `pull/32` | `pull/32/README.md` |  |
| `README.rendered.html` | `pull/32` | `pull/32/README.rendered.html` |  |
| `package.yaml` | `pull/32` | `pull/32/package.yaml` |  |
| `README.md` | `pull/33` | `pull/33/README.md` |  |
| `README.rendered.html` | `pull/33` | `pull/33/README.rendered.html` |  |
| `package.yaml` | `pull/33` | `pull/33/package.yaml` |  |
| `CHANGELOG.md` | `pull/34` | `pull/34/CHANGELOG.md` |  |
| `README.md` | `pull/34` | `pull/34/README.md` |  |
| `README.rendered.html` | `pull/34` | `pull/34/README.rendered.html` |  |
| `SKILL.md` | `pull/34` | `pull/34/SKILL.md` |  |
| `package.yaml` | `pull/34` ほか1 | `pull/34/package.yaml` |  |
| `README.md` | `pull/36` | `pull/36/README.md` |  |
| `README.rendered.html` | `pull/36` | `pull/36/README.rendered.html` |  |
| `package.yaml` | `pull/36` | `pull/36/package.yaml` |  |
| `README.md` | `pull/37` | `pull/37/README.md` |  |
| `README.rendered.html` | `pull/37` | `pull/37/README.rendered.html` |  |
| `package.yaml` | `pull/37` | `pull/37/package.yaml` |  |
| `README.md` | `pull/38` | `pull/38/README.md` |  |
| `README.rendered.html` | `pull/38` | `pull/38/README.rendered.html` |  |
| `package.yaml` | `pull/38` | `pull/38/package.yaml` |  |
| `scripts/note_workflow_gate.py` | `pull/38` ほか2 | `pull/38/scripts/note_workflow_gate.py` |  |
| `skills/note-publication-gate/SKILL.md` | `pull/38` | `pull/38/skills/note-publication-gate/SKILL.md` |  |
| `tests/test_note_workflow_gate.py` | `pull/38` | `pull/38/tests/test_note_workflow_gate.py` |  |
| `README.md` | `pull/39` ほか2 | `pull/39/README.md` |  |
| `README.rendered.html` | `pull/39` ほか2 | `pull/39/README.rendered.html` |  |
| `package.yaml` | `pull/39` ほか2 | `pull/39/package.yaml` |  |
| `references/note-workflow-review-contract.md` | `pull/39` ほか6 | `pull/39/references/note-workflow-review-contract.md` |  |
| `scripts/note_feedback.py` | `pull/39` ほか9 | `pull/39/scripts/note_feedback.py` |  |
| `scripts/sync_note_public_snapshot.py` | `pull/39` ほか4 | `pull/39/scripts/sync_note_public_snapshot.py` |  |
| `README.md` | `pull/4` | `pull/4/README.md` |  |
| `README.rendered.html` | `pull/4` | `pull/4/README.rendered.html` |  |
| `package.yaml` | `pull/4` | `pull/4/package.yaml` |  |
| `README.md` | `pull/40` ほか1 | `pull/40/README.md` |  |
| `README.rendered.html` | `pull/40` ほか1 | `pull/40/README.rendered.html` |  |
| `package.yaml` | `pull/40` | `pull/40/package.yaml` |  |
| `CHANGELOG.md` | `pull/41` | `pull/41/CHANGELOG.md` |  |
| `README.md` | `pull/41` | `pull/41/README.md` |  |
| `README.rendered.html` | `pull/41` | `pull/41/README.rendered.html` |  |
| `USER_TEST.md` | `pull/41` | `pull/41/USER_TEST.md` |  |
| `README.md` | `pull/42` | `pull/42/README.md` |  |
| `README.rendered.html` | `pull/42` | `pull/42/README.rendered.html` |  |
| `package.yaml` | `pull/42` | `pull/42/package.yaml` |  |
| `scripts/verify_published_update.py` | `pull/42` ほか27 | `pull/42/scripts/verify_published_update.py` |  |
| `skills/note-postpublish-ledger/SKILL.md` | `pull/42` ほか14 | `pull/42/skills/note-postpublish-ledger/SKILL.md` |  |
| `CHANGELOG.md` | `pull/43` ほか1 | `pull/43/CHANGELOG.md` |  |
| `README.md` | `pull/43` ほか1 | `pull/43/README.md` |  |
| `README.rendered.html` | `pull/43` ほか1 | `pull/43/README.rendered.html` |  |
| `SKILL.md` | `pull/43` ほか1 | `pull/43/SKILL.md` |  |
| `data/local_draft_qa_stop_before_publish_evidence.json` | `pull/43` ほか1 | `pull/43/data/local_draft_qa_stop_before_publish_evidence.json` |  |
| `issue-drafts.md` | `pull/43` ほか1 | `pull/43/issue-drafts.md` |  |
| `package.yaml` | `pull/43` ほか1 | `pull/43/package.yaml` |  |
| `references/note-workflow-review-contract.md` | `pull/43` ほか1 | `pull/43/references/note-workflow-review-contract.md` |  |
| `scripts/draft_topic_coverage_check.py` | `pull/43` ほか1 | `pull/43/scripts/draft_topic_coverage_check.py` |  |
| `scripts/note_authorship_gate.py` | `pull/43` ほか1 | `pull/43/scripts/note_authorship_gate.py` |  |
| `scripts/post_publish.py` | `pull/43` ほか1 | `pull/43/scripts/post_publish.py` |  |
| `skills/note-draft-production/SKILL.md` | `pull/43` ほか1 | `pull/43/skills/note-draft-production/SKILL.md` |  |
| `skills/note-editor-prepublish/SKILL.md` | `pull/43` ほか1 | `pull/43/skills/note-editor-prepublish/SKILL.md` |  |
| `skills/note-postpublish-ledger/SKILL.md` | `pull/43` ほか1 | `pull/43/skills/note-postpublish-ledger/SKILL.md` |  |
| `skills/note-prepublish-qa/SKILL.md` | `pull/43` ほか1 | `pull/43/skills/note-prepublish-qa/SKILL.md` |  |
| `skills/note-publication-gate/SKILL.md` | `pull/43` ほか1 | `pull/43/skills/note-publication-gate/SKILL.md` |  |
| `tests/test_note_editor_session_check.py` | `pull/43` ほか1 | `pull/43/tests/test_note_editor_session_check.py` |  |
| `CHANGELOG.md` | `pull/45` | `pull/45/CHANGELOG.md` |  |
| `README.md` | `pull/45` | `pull/45/README.md` |  |
| `README.rendered.html` | `pull/45` | `pull/45/README.rendered.html` |  |
| `SKILL.md` | `pull/45` | `pull/45/SKILL.md` |  |
| `issue-drafts.md` | `pull/45` | `pull/45/issue-drafts.md` |  |
| `package.yaml` | `pull/45` | `pull/45/package.yaml` |  |
| `scripts/run_local_draft_qa_proof.py` | `pull/45` | `pull/45/scripts/run_local_draft_qa_proof.py` |  |
| `references/post-publish-context-proof.md` | `pull/46` | `pull/46/references/post-publish-context-proof.md` |  |
| `scripts/sync_note_public_snapshot.py` | `pull/46` | `pull/46/scripts/sync_note_public_snapshot.py` |  |
| `scripts/note_workflow_gate.py` | `pull/48` | `pull/48/scripts/note_workflow_gate.py` |  |
| `scripts/review_draft.py` | `pull/48` | `pull/48/scripts/review_draft.py` |  |
| `tests/test_editorial_review_integration.py` | `pull/48` | `pull/48/tests/test_editorial_review_integration.py` |  |
| `README.md` | `pull/49` | `pull/49/README.md` |  |
| `README.rendered.html` | `pull/49` | `pull/49/README.rendered.html` |  |
| `adapters/claude-code/install.sh` | `pull/49` ほか17 | `pull/49/adapters/claude-code/install.sh` |  |
| `adapters/claude-code/note-draft-production/SKILL.md` | `pull/49` ほか19 | `pull/49/adapters/claude-code/note-draft-production/SKILL.md` |  |
| `adapters/claude-code/note-editor-prepublish/SKILL.md` | `pull/49` ほか19 | `pull/49/adapters/claude-code/note-editor-prepublish/SKILL.md` |  |
| `adapters/claude-code/note-idea-intake/SKILL.md` | `pull/49` ほか19 | `pull/49/adapters/claude-code/note-idea-intake/SKILL.md` |  |
| `adapters/claude-code/note-postpublish-ledger/SKILL.md` | `pull/49` ほか19 | `pull/49/adapters/claude-code/note-postpublish-ledger/SKILL.md` |  |
| `adapters/claude-code/note-prepublish-qa/SKILL.md` | `pull/49` ほか19 | `pull/49/adapters/claude-code/note-prepublish-qa/SKILL.md` |  |
| `adapters/claude-code/note-publication-gate/SKILL.md` | `pull/49` ほか19 | `pull/49/adapters/claude-code/note-publication-gate/SKILL.md` |  |
| `adapters/claude-code/note-publishing-suite/SKILL.md` | `pull/49` ほか19 | `pull/49/adapters/claude-code/note-publishing-suite/SKILL.md` |  |
| `package.yaml` | `pull/49` | `pull/49/package.yaml` |  |
| `references/note-draft-authority-and-layout-contract.md` | `pull/49` ほか12 | `pull/49/references/note-draft-authority-and-layout-contract.md` |  |
| `scripts/fetch_note_official_specs.py` | `pull/49` ほか23 | `pull/49/scripts/fetch_note_official_specs.py` |  |
| `scripts/note_article_version.py` | `pull/49` ほか23 | `pull/49/scripts/note_article_version.py` |  |
| `scripts/note_editor_apply.py` | `pull/49` ほか23 | `pull/49/scripts/note_editor_apply.py` |  |
| `scripts/note_editor_session_check.py` | `pull/49` ほか6 | `pull/49/scripts/note_editor_session_check.py` |  |
| `scripts/note_research_quality.py` | `pull/49` ほか3 | `pull/49/scripts/note_research_quality.py` |  |
| `scripts/note_workflow_gate.py` | `pull/49` ほか2 | `pull/49/scripts/note_workflow_gate.py` |  |
| `tests/test_editor_workflow_entry.py` | `pull/49` ほか11 | `pull/49/tests/test_editor_workflow_entry.py` |  |
| `tests/test_note_editor_prepublish_verify.py` | `pull/49` ほか2 | `pull/49/tests/test_note_editor_prepublish_verify.py` |  |
| `tests/test_note_editor_session_check.py` | `pull/49` ほか6 | `pull/49/tests/test_note_editor_session_check.py` |  |
| `tests/test_skill_pointer_check.py` | `pull/49` ほか16 | `pull/49/tests/test_skill_pointer_check.py` |  |
| `README.md` | `pull/5` | `pull/5/README.md` |  |
| `README.rendered.html` | `pull/5` | `pull/5/README.rendered.html` |  |
| `package.yaml` | `pull/5` | `pull/5/package.yaml` |  |
| `CHANGELOG.md` | `pull/50` | `pull/50/CHANGELOG.md` |  |
| `README.md` | `pull/50` | `pull/50/README.md` |  |
| `README.rendered.html` | `pull/50` | `pull/50/README.rendered.html` |  |
| `SKILL.md` | `pull/50` | `pull/50/SKILL.md` |  |
| `data/local_draft_qa_stop_before_publish_evidence.json` | `pull/50` | `pull/50/data/local_draft_qa_stop_before_publish_evidence.json` |  |
| `issue-drafts.md` | `pull/50` | `pull/50/issue-drafts.md` |  |
| `package.yaml` | `pull/50` | `pull/50/package.yaml` |  |
| `references/note-editor-pdca-orchestration.md` | `pull/50` | `pull/50/references/note-editor-pdca-orchestration.md` |  |
| `references/post-publish-context-proof.md` | `pull/50` | `pull/50/references/post-publish-context-proof.md` |  |
| `scripts/note_work_packet_check.py` | `pull/50` | `pull/50/scripts/note_work_packet_check.py` |  |
| `scripts/post_publish.py` | `pull/50` | `pull/50/scripts/post_publish.py` |  |
| `tests/test_post_publish_context_proof.py` | `pull/50` | `pull/50/tests/test_post_publish_context_proof.py` |  |
| `README.md` | `pull/53` | `pull/53/README.md` |  |
| `README.rendered.html` | `pull/53` | `pull/53/README.rendered.html` |  |
| `package.yaml` | `pull/53` | `pull/53/package.yaml` |  |
| `CHANGELOG.md` | `pull/55` | `pull/55/CHANGELOG.md` |  |
| `README.md` | `pull/56` | `pull/56/README.md` |  |
| `README.rendered.html` | `pull/56` | `pull/56/README.rendered.html` |  |
| `package.yaml` | `pull/56` | `pull/56/package.yaml` |  |
| `README.md` | `pull/57` | `pull/57/README.md` |  |
| `README.rendered.html` | `pull/57` | `pull/57/README.rendered.html` |  |
| `package.yaml` | `pull/57` | `pull/57/package.yaml` |  |
| `scripts/note_editor_guarded_input.mjs` | `pull/57` ほか1 | `pull/57/scripts/note_editor_guarded_input.mjs` |  |
| `skills/note-editor-ops/SKILL.md` | `pull/57` ほか1 | `pull/57/skills/note-editor-ops/SKILL.md` |  |
| `README.md` | `pull/58` | `pull/58/README.md` |  |
| `README.rendered.html` | `pull/58` | `pull/58/README.rendered.html` |  |
| `package.yaml` | `pull/58` | `pull/58/package.yaml` |  |
| `scripts/note_feedback.py` | `pull/58` | `pull/58/scripts/note_feedback.py` |  |
| `tests/test_note_feedback.py` | `pull/58` ほか21 | `pull/58/tests/test_note_feedback.py` |  |
| `README.md` | `pull/59` | `pull/59/README.md` |  |
| `README.rendered.html` | `pull/59` | `pull/59/README.rendered.html` |  |
| `package.yaml` | `pull/59` | `pull/59/package.yaml` |  |
| `references/note-workflow-review-contract.md` | `pull/59` ほか1 | `pull/59/references/note-workflow-review-contract.md` |  |
| `scripts/note_authorship_gate.py` | `pull/59` | `pull/59/scripts/note_authorship_gate.py` |  |
| `scripts/note_editor_guarded_input.mjs` | `pull/59` ほか23 | `pull/59/scripts/note_editor_guarded_input.mjs` |  |
| `scripts/note_editor_pdca_cycle_check.py` | `pull/59` ほか20 | `pull/59/scripts/note_editor_pdca_cycle_check.py` |  |
| `scripts/note_feedback.py` | `pull/59` | `pull/59/scripts/note_feedback.py` |  |
| `scripts/note_workflow_gate.py` | `pull/59` ほか1 | `pull/59/scripts/note_workflow_gate.py` |  |
| `tests/note_editor_guarded_input.test.mjs` | `pull/59` ほか23 | `pull/59/tests/note_editor_guarded_input.test.mjs` |  |
| `tests/test_image_reference_gate.py` | `pull/59` ほか1 | `pull/59/tests/test_image_reference_gate.py` |  |
| `README.md` | `pull/6` | `pull/6/README.md` |  |
| `README.rendered.html` | `pull/6` | `pull/6/README.rendered.html` |  |
| `adapters/claude-code/install.sh` | `pull/6` ほか11 | `pull/6/adapters/claude-code/install.sh` |  |
| `package.yaml` | `pull/6` | `pull/6/package.yaml` |  |
| `scripts/skill_pointer_check.py` | `pull/6` ほか11 | `pull/6/scripts/skill_pointer_check.py` |  |
| `tests/test_skill_pointer_check.py` | `pull/6` ほか11 | `pull/6/tests/test_skill_pointer_check.py` |  |
| `README.md` | `pull/60` | `pull/60/README.md` |  |
| `README.rendered.html` | `pull/60` | `pull/60/README.rendered.html` |  |
| `package.yaml` | `pull/60` | `pull/60/package.yaml` |  |
| `tests/test_history_learning_gate.py` | `pull/60` | `pull/60/tests/test_history_learning_gate.py` |  |
| `README.md` | `pull/61` | `pull/61/README.md` |  |
| `README.rendered.html` | `pull/61` | `pull/61/README.rendered.html` |  |
| `package.yaml` | `pull/61` | `pull/61/package.yaml` |  |
| `scripts/note_authorship_gate.py` | `pull/61` ほか1 | `pull/61/scripts/note_authorship_gate.py` |  |
| `scripts/note_feedback.py` | `pull/61` ほか3 | `pull/61/scripts/note_feedback.py` |  |
| `tests/test_history_learning_gate.py` | `pull/61` | `pull/61/tests/test_history_learning_gate.py` |  |
| `README.md` | `pull/62` | `pull/62/README.md` |  |
| `README.rendered.html` | `pull/62` | `pull/62/README.rendered.html` |  |
| `package.yaml` | `pull/62` | `pull/62/package.yaml` |  |
| `README.md` | `pull/63` | `pull/63/README.md` |  |
| `README.rendered.html` | `pull/63` | `pull/63/README.rendered.html` |  |
| `package.yaml` | `pull/63` | `pull/63/package.yaml` |  |
| `scripts/note_editor_prepublish_verify.py` | `pull/63` | `pull/63/scripts/note_editor_prepublish_verify.py` |  |
| `tests/test_editor_publication_boundary.py` | `pull/63` | `pull/63/tests/test_editor_publication_boundary.py` |  |
| `README.md` | `pull/64` | `pull/64/README.md` |  |
| `README.rendered.html` | `pull/64` | `pull/64/README.rendered.html` |  |
| `package.yaml` | `pull/64` | `pull/64/package.yaml` |  |
| `scripts/note_authorship_gate.py` | `pull/64` | `pull/64/scripts/note_authorship_gate.py` |  |
| `README.md` | `pull/65` | `pull/65/README.md` |  |
| `README.rendered.html` | `pull/65` | `pull/65/README.rendered.html` |  |
| `package.yaml` | `pull/65` | `pull/65/package.yaml` |  |
| `scripts/note_authorship_gate.py` | `pull/65` ほか1 | `pull/65/scripts/note_authorship_gate.py` |  |
| `scripts/note_workflow_gate.py` | `pull/65` | `pull/65/scripts/note_workflow_gate.py` |  |
| `tests/test_history_mutable_readback.py` | `pull/65` ほか14 | `pull/65/tests/test_history_mutable_readback.py` |  |
| `README.md` | `pull/66` | `pull/66/README.md` |  |
| `README.rendered.html` | `pull/66` | `pull/66/README.rendered.html` |  |
| `package.yaml` | `pull/66` | `pull/66/package.yaml` |  |
| `scripts/note_workflow_gate.py` | `pull/66` ほか1 | `pull/66/scripts/note_workflow_gate.py` |  |
| `tests/test_note_workflow_gate.py` | `pull/66` ほか1 | `pull/66/tests/test_note_workflow_gate.py` |  |
| `README.md` | `pull/67` | `pull/67/README.md` |  |
| `README.rendered.html` | `pull/67` | `pull/67/README.rendered.html` |  |
| `package.yaml` | `pull/67` | `pull/67/package.yaml` |  |
| `README.md` | `pull/68` | `pull/68/README.md` |  |
| `README.rendered.html` | `pull/68` | `pull/68/README.rendered.html` |  |
| `package.yaml` | `pull/68` | `pull/68/package.yaml` |  |
| `scripts/image_reference_gate.py` | `pull/68` | `pull/68/scripts/image_reference_gate.py` |  |
| `scripts/note_workflow_gate.py` | `pull/68` | `pull/68/scripts/note_workflow_gate.py` |  |
| `tests/test_note_workflow_gate.py` | `pull/68` | `pull/68/tests/test_note_workflow_gate.py` |  |
| `README.md` | `pull/69` | `pull/69/README.md` |  |
| `README.rendered.html` | `pull/69` | `pull/69/README.rendered.html` |  |
| `package.yaml` | `pull/69` | `pull/69/package.yaml` |  |
| `scripts/note_workflow_gate.py` | `pull/69` ほか5 | `pull/69/scripts/note_workflow_gate.py` |  |
| `README.md` | `pull/7` | `pull/7/README.md` |  |
| `README.rendered.html` | `pull/7` | `pull/7/README.rendered.html` |  |
| `package.yaml` | `pull/7` | `pull/7/package.yaml` |  |
| `CHANGELOG.md` | `pull/70` | `pull/70/CHANGELOG.md` |  |
| `SKILL.md` | `pull/70` | `pull/70/SKILL.md` |  |
| `package.yaml` | `pull/70` | `pull/70/package.yaml` |  |
| `references/note-workflow-review-contract.md` | `pull/70` | `pull/70/references/note-workflow-review-contract.md` |  |
| `README.md` | `pull/71` | `pull/71/README.md` |  |
| `README.rendered.html` | `pull/71` | `pull/71/README.rendered.html` |  |
| `references/post-publish-context-proof.md` | `pull/71` ほか1 | `pull/71/references/post-publish-context-proof.md` |  |
| `scripts/note_postpublish_review.py` | `pull/71` ほか1 | `pull/71/scripts/note_postpublish_review.py` |  |
| `scripts/post_publish.py` | `pull/71` ほか3 | `pull/71/scripts/post_publish.py` |  |
| `.github/workflows/repository-guarantees.yml` | `pull/72` | `pull/72/.github/workflows/repository-guarantees.yml` |  |
| `CHANGELOG.md` | `pull/72` | `pull/72/CHANGELOG.md` |  |
| `PREFLIGHT.md` | `pull/72` | `pull/72/PREFLIGHT.md` |  |
| `SKILL.md` | `pull/72` | `pull/72/SKILL.md` |  |
| `package.yaml` | `pull/72` | `pull/72/package.yaml` |  |
| `skills/note-draft-production/SKILL.md` | `pull/72` | `pull/72/skills/note-draft-production/SKILL.md` |  |
| `README.md` | `pull/73` | `pull/73/README.md` |  |
| `README.rendered.html` | `pull/73` | `pull/73/README.rendered.html` |  |
| `scripts/note_postpublish_review.py` | `pull/73` ほか6 | `pull/73/scripts/note_postpublish_review.py` |  |
| `scripts/skill_pointer_check.py` | `pull/73` ほか1 | `pull/73/scripts/skill_pointer_check.py` |  |
| `CHANGELOG.md` | `pull/74` | `pull/74/CHANGELOG.md` |  |
| `README.md` | `pull/74` | `pull/74/README.md` |  |
| `README.rendered.html` | `pull/74` | `pull/74/README.rendered.html` |  |
| `package.yaml` | `pull/74` | `pull/74/package.yaml` |  |
| `scripts/post_publish.py` | `pull/74` ほか4 | `pull/74/scripts/post_publish.py` |  |
| `scripts/test_skill_integration.py` | `pull/74` | `pull/74/scripts/test_skill_integration.py` |  |
| `README.md` | `pull/75` | `pull/75/README.md` |  |
| `README.rendered.html` | `pull/75` | `pull/75/README.rendered.html` |  |
| `package.yaml` | `pull/75` | `pull/75/package.yaml` |  |
| `README.md` | `pull/76` | `pull/76/README.md` |  |
| `README.rendered.html` | `pull/76` | `pull/76/README.rendered.html` |  |
| `package.yaml` | `pull/76` | `pull/76/package.yaml` |  |
| `PUBLIC_READY.md` | `pull/77` ほか4 | `pull/77/PUBLIC_READY.md` |  |
| `README.md` | `pull/77` | `pull/77/README.md` |  |
| `README.rendered.html` | `pull/77` | `pull/77/README.rendered.html` |  |
| `package.yaml` | `pull/77` | `pull/77/package.yaml` |  |
| `scripts/pre_publish_check.py` | `pull/77` ほか2 | `pull/77/scripts/pre_publish_check.py` |  |
| `README.md` | `pull/78` | `pull/78/README.md` |  |
| `README.rendered.html` | `pull/78` | `pull/78/README.rendered.html` |  |
| `package.yaml` | `pull/78` | `pull/78/package.yaml` |  |
| `README.md` | `pull/79` | `pull/79/README.md` |  |
| `README.rendered.html` | `pull/79` | `pull/79/README.rendered.html` |  |
| `package.yaml` | `pull/79` | `pull/79/package.yaml` |  |
| `scripts/note_authorship_gate.py` | `pull/79` | `pull/79/scripts/note_authorship_gate.py` |  |
| `scripts/note_workflow_gate.py` | `pull/79` | `pull/79/scripts/note_workflow_gate.py` |  |
| `tests/test_author_vocabulary.py` | `pull/79` | `pull/79/tests/test_author_vocabulary.py` |  |
| `README.md` | `pull/8` | `pull/8/README.md` |  |
| `README.rendered.html` | `pull/8` | `pull/8/README.rendered.html` |  |
| `SKILL.md` | `pull/8` | `pull/8/SKILL.md` |  |
| `package.yaml` | `pull/8` | `pull/8/package.yaml` |  |
| `README.md` | `pull/80` | `pull/80/README.md` |  |
| `README.rendered.html` | `pull/80` | `pull/80/README.rendered.html` |  |
| `package.yaml` | `pull/80` | `pull/80/package.yaml` |  |
| `README.md` | `pull/81` | `pull/81/README.md` |  |
| `README.rendered.html` | `pull/81` | `pull/81/README.rendered.html` |  |
| `package.yaml` | `pull/81` | `pull/81/package.yaml` |  |
| `README.md` | `pull/82` | `pull/82/README.md` |  |
| `README.rendered.html` | `pull/82` | `pull/82/README.rendered.html` |  |
| `package.yaml` | `pull/82` | `pull/82/package.yaml` |  |
| `README.rendered.html` | `pull/83` | `pull/83/README.rendered.html` |  |
| `package.yaml` | `pull/83` ほか1 | `pull/83/package.yaml` |  |
| `scripts/note_editor_guarded_input.mjs` | `pull/83` ほか1 | `pull/83/scripts/note_editor_guarded_input.mjs` |  |
| `README.md` | `pull/84` | `pull/84/README.md` |  |
| `README.md` | `pull/85` | `pull/85/README.md` |  |
| `README.rendered.html` | `pull/85` | `pull/85/README.rendered.html` |  |
| `package.yaml` | `pull/85` | `pull/85/package.yaml` |  |
| `README.md` | `pull/86` | `pull/86/README.md` |  |
| `README.rendered.html` | `pull/86` | `pull/86/README.rendered.html` |  |
| `package.yaml` | `pull/86` | `pull/86/package.yaml` |  |
| `README.md` | `pull/87` | `pull/87/README.md` |  |
| `README.rendered.html` | `pull/87` | `pull/87/README.rendered.html` |  |
| `package.yaml` | `pull/87` | `pull/87/package.yaml` |  |
| `README.md` | `pull/9` | `pull/9/README.md` |  |
| `README.rendered.html` | `pull/9` | `pull/9/README.rendered.html` |  |
| `package.yaml` | `pull/9` | `pull/9/package.yaml` |  |
| `AGENTS.md` | `tags/v0.2.20` ほか74 | `tags/v0.2.20/AGENTS.md` |  |
| `LICENSE` | `tags/v0.2.20` ほか84 | `tags/v0.2.20/LICENSE` |  |
| `PROJECT_SSOT.md` | `tags/v0.2.20` ほか15 | `tags/v0.2.20/PROJECT_SSOT.md` |  |
| `README.md` | `tags/v0.2.20` ほか1 | `tags/v0.2.20/README.md` |  |
| `README.rendered.html` | `tags/v0.2.20` ほか1 | `tags/v0.2.20/README.rendered.html` |  |
| `ROADMAP.md` | `tags/v0.2.20` ほか15 | `tags/v0.2.20/ROADMAP.md` |  |
| `SECURITY.md` | `tags/v0.2.20` ほか71 | `tags/v0.2.20/SECURITY.md` |  |
| `adapters/claude-code/note-draft-production/SKILL.md` | `tags/v0.2.20` ほか65 | `tags/v0.2.20/adapters/claude-code/note-draft-production/SKILL.md` |  |
| `adapters/claude-code/note-editor-prepublish/SKILL.md` | `tags/v0.2.20` ほか65 | `tags/v0.2.20/adapters/claude-code/note-editor-prepublish/SKILL.md` |  |
| `adapters/claude-code/note-idea-intake/SKILL.md` | `tags/v0.2.20` ほか65 | `tags/v0.2.20/adapters/claude-code/note-idea-intake/SKILL.md` |  |
| `adapters/claude-code/note-postpublish-ledger/SKILL.md` | `tags/v0.2.20` ほか65 | `tags/v0.2.20/adapters/claude-code/note-postpublish-ledger/SKILL.md` |  |
| `adapters/claude-code/note-prepublish-qa/SKILL.md` | `tags/v0.2.20` ほか65 | `tags/v0.2.20/adapters/claude-code/note-prepublish-qa/SKILL.md` |  |
| `adapters/claude-code/note-publication-gate/SKILL.md` | `tags/v0.2.20` ほか65 | `tags/v0.2.20/adapters/claude-code/note-publication-gate/SKILL.md` |  |
| `adapters/claude-code/note-publishing-suite/SKILL.md` | `tags/v0.2.20` ほか65 | `tags/v0.2.20/adapters/claude-code/note-publishing-suite/SKILL.md` |  |
| `adapters/codex/install.ps1` | `tags/v0.2.20` ほか66 | `tags/v0.2.20/adapters/codex/install.ps1` |  |
| `data/local_draft_qa_stop_before_publish_evidence.json` | `tags/v0.2.20` ほか31 | `tags/v0.2.20/data/local_draft_qa_stop_before_publish_evidence.json` |  |
| `data/note_editor_prepublish_observation.fixture.json` | `tags/v0.2.20` ほか43 | `tags/v0.2.20/data/note_editor_prepublish_observation.fixture.json` |  |
| `data/note_image_upload_automation_policy.json` | `tags/v0.2.20` ほか31 | `tags/v0.2.20/data/note_image_upload_automation_policy.json` |  |
| `package.yaml` | `tags/v0.2.20` ほか1 | `tags/v0.2.20/package.yaml` |  |
| `references/note-editor-live-constraint-boundaries.md` | `tags/v0.2.20` ほか50 | `tags/v0.2.20/references/note-editor-live-constraint-boundaries.md` |  |
| `references/topic-consolidation-ledger.md` | `tags/v0.2.20` ほか1 | `tags/v0.2.20/references/topic-consolidation-ledger.md` |  |
| `scripts/engagement_tracker.py` | `tags/v0.2.20` ほか85 | `tags/v0.2.20/scripts/engagement_tracker.py` |  |
| `scripts/note_authorship_gate.py` | `tags/v0.2.20` ほか38 | `tags/v0.2.20/scripts/note_authorship_gate.py` |  |
| `scripts/note_editor_prepublish_verify.py` | `tags/v0.2.20` ほか43 | `tags/v0.2.20/scripts/note_editor_prepublish_verify.py` |  |
| `scripts/note_fact_check.py` | `tags/v0.2.20` ほか65 | `tags/v0.2.20/scripts/note_fact_check.py` |  |
| `scripts/note_preview.py` | `tags/v0.2.20` ほか32 | `tags/v0.2.20/scripts/note_preview.py` |  |
| `scripts/render_readme.py` | `tags/v0.2.20` ほか38 | `tags/v0.2.20/scripts/render_readme.py` |  |
| `scripts/review_draft.py` | `tags/v0.2.20` ほか49 | `tags/v0.2.20/scripts/review_draft.py` |  |
| `scripts/run_local_draft_qa_proof.py` | `tags/v0.2.20` ほか65 | `tags/v0.2.20/scripts/run_local_draft_qa_proof.py` |  |
| `scripts/skill_pointer_check.py` | `tags/v0.2.20` ほか66 | `tags/v0.2.20/scripts/skill_pointer_check.py` |  |
| `scripts/sync_note_public_snapshot.py` | `tags/v0.2.20` ほか40 | `tags/v0.2.20/scripts/sync_note_public_snapshot.py` |  |
| `scripts/test_skill_integration.py` | `tags/v0.2.20` ほか47 | `tags/v0.2.20/scripts/test_skill_integration.py` |  |
| `scripts/topic_status_check.py` | `tags/v0.2.20` ほか1 | `tags/v0.2.20/scripts/topic_status_check.py` |  |
| `scripts/verify_public_package.sh` | `tags/v0.2.20` ほか47 | `tags/v0.2.20/scripts/verify_public_package.sh` |  |
| `skills/note-editor-ops/SKILL.md` | `tags/v0.2.20` ほか19 | `tags/v0.2.20/skills/note-editor-ops/SKILL.md` |  |
| `skills/note-idea-intake/SKILL.md` | `tags/v0.2.20` ほか83 | `tags/v0.2.20/skills/note-idea-intake/SKILL.md` |  |
| `tests/test_content_pdca_check.py` | `tags/v0.2.20` ほか66 | `tags/v0.2.20/tests/test_content_pdca_check.py` |  |
| `tests/test_note_authorship_gate.py` | `tags/v0.2.20` ほか38 | `tags/v0.2.20/tests/test_note_authorship_gate.py` |  |
| `tests/test_note_editor_prepublish_verify.py` | `tags/v0.2.20` ほか45 | `tags/v0.2.20/tests/test_note_editor_prepublish_verify.py` |  |
| `tests/test_provenance_draft_review.py` | `tags/v0.2.20` ほか32 | `tags/v0.2.20/tests/test_provenance_draft_review.py` |  |
| `tests/test_topic_status_check.py` | `tags/v0.2.20` ほか1 | `tags/v0.2.20/tests/test_topic_status_check.py` |  |
| `tests/test_windows_skill_installer.py` | `tags/v0.2.20` ほか66 | `tags/v0.2.20/tests/test_windows_skill_installer.py` |  |
| `README.md` | `tags/v0.2.21` ほか1 | `tags/v0.2.21/README.md` |  |
| `README.rendered.html` | `tags/v0.2.21` ほか1 | `tags/v0.2.21/README.rendered.html` |  |
| `package.yaml` | `tags/v0.2.21` ほか1 | `tags/v0.2.21/package.yaml` |  |
| `README.md` | `tags/v0.2.22` ほか1 | `tags/v0.2.22/README.md` |  |
| `README.rendered.html` | `tags/v0.2.22` ほか1 | `tags/v0.2.22/README.rendered.html` |  |
| `assets/demo/README.md` | `tags/v0.2.22` ほか1 | `tags/v0.2.22/assets/demo/README.md` |  |
| `package.yaml` | `tags/v0.2.22` ほか1 | `tags/v0.2.22/package.yaml` |  |
| `README.md` | `tags/v0.2.23` ほか2 | `tags/v0.2.23/README.md` |  |
| `README.rendered.html` | `tags/v0.2.23` ほか2 | `tags/v0.2.23/README.rendered.html` |  |
| `package.yaml` | `tags/v0.2.23` ほか2 | `tags/v0.2.23/package.yaml` |  |
| `README.md` | `tags/v0.2.24` ほか1 | `tags/v0.2.24/README.md` |  |
| `README.rendered.html` | `tags/v0.2.24` ほか1 | `tags/v0.2.24/README.rendered.html` |  |
| `package.yaml` | `tags/v0.2.24` ほか1 | `tags/v0.2.24/package.yaml` |  |
| `.repo-preflight-consistency.json` | `tags/v0.2.25` ほか15 | `tags/v0.2.25/.repo-preflight-consistency.json` |  |
| `README.md` | `tags/v0.2.25` ほか3 | `tags/v0.2.25/README.md` |  |
| `README.rendered.html` | `tags/v0.2.25` ほか3 | `tags/v0.2.25/README.rendered.html` |  |
| `package.yaml` | `tags/v0.2.25` ほか3 | `tags/v0.2.25/package.yaml` |  |
| `README.md` | `tags/v0.2.27` ほか1 | `tags/v0.2.27/README.md` |  |
| `README.rendered.html` | `tags/v0.2.27` ほか1 | `tags/v0.2.27/README.rendered.html` |  |
| `assets/note-preview/template.html` | `tags/v0.2.27` ほか15 | `tags/v0.2.27/assets/note-preview/template.html` |  |
| `docs/design/2026-09-11-three-departments.md` | `tags/v0.2.27` ほか1 | `tags/v0.2.27/docs/design/2026-09-11-three-departments.md` |  |
| `package.yaml` | `tags/v0.2.27` ほか1 | `tags/v0.2.27/package.yaml` |  |
| `scripts/clipboard_bridge.py` | `tags/v0.2.27` ほか1 | `tags/v0.2.27/scripts/clipboard_bridge.py` |  |
| `scripts/note_virtual_preview.py` | `tags/v0.2.27` ほか15 | `tags/v0.2.27/scripts/note_virtual_preview.py` |  |
| `tests/test_clipboard_bridge.py` | `tags/v0.2.27` ほか1 | `tags/v0.2.27/tests/test_clipboard_bridge.py` |  |
| `scripts/note_editor_pdca_cycle_check.py` | `tags/v0.2.29` ほか27 | `tags/v0.2.29/scripts/note_editor_pdca_cycle_check.py` |  |
| `.github/workflows/repository-guarantees.yml` | `tags/v0.2.30` ほか40 | `tags/v0.2.30/.github/workflows/repository-guarantees.yml` |  |
| `CONTRIBUTING.md` | `tags/v0.2.30` ほか41 | `tags/v0.2.30/CONTRIBUTING.md` |  |
| `PREFLIGHT.md` | `tags/v0.2.30` ほか40 | `tags/v0.2.30/PREFLIGHT.md` |  |
| `README.md` | `tags/v0.2.30` ほか1 | `tags/v0.2.30/README.md` |  |
| `README.rendered.html` | `tags/v0.2.30` ほか1 | `tags/v0.2.30/README.rendered.html` |  |
| `package.yaml` | `tags/v0.2.30` ほか1 | `tags/v0.2.30/package.yaml` |  |
| `README.md` | `tags/v0.2.31` ほか1 | `tags/v0.2.31/README.md` |  |
| `README.rendered.html` | `tags/v0.2.31` ほか1 | `tags/v0.2.31/README.rendered.html` |  |
| `package.yaml` | `tags/v0.2.31` ほか1 | `tags/v0.2.31/package.yaml` |  |
| `references/note-draft-authority-and-layout-contract.md` | `tags/v0.2.31` ほか19 | `tags/v0.2.31/references/note-draft-authority-and-layout-contract.md` |  |
| `scripts/note_footer_selection.py` | `tags/v0.2.31` ほか19 | `tags/v0.2.31/scripts/note_footer_selection.py` |  |

## 伏せたもの

- なし
