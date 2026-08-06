---
title: note-publishing-suite topic consolidation ledger
type: reference
status: active
publication_gate: human_review_required
external_action: none
updated: 2026-08-06
---

# topic consolidation ledger

ローカル会話・worktree・Draft PR に散らばった話題を、公開 package 内の 1 枚に畳む。
記事本文・画像選定・動画・公開後反応は製品機能と混ぜず、各記事運用タスクが所有する。

検査: `python scripts/topic_status_check.py --json`

## 正本ルーティング

| 正本 | 所有範囲 | 状態 |
|---|---|---|
| 本 ledger + ROADMAP + issue-drafts | 機能棚卸し、SSOT、Roadmap、重複排除、将来設計 | active |
| PR #17 `codex/windows-runtime-and-note-gates-20260806` | 0.2.20 ゲート / Windows 配布 | Draft / CI green / human review 待ち |
| main | 公開 package の既定 branch | active |

## 6軸ステータス

| id | 軸 | status | owner | evidence |
|---|---|---|---|---|
| axis-1 | 公式ガイダンス・機能棚卸し | open | package | `skills/note-official-guidance-intake` / `references/note-editor-capability-inventory.md` の未確認節 |
| axis-2 | 実記事1本のローカル一気通貫証跡 | open | package | `scripts/run_local_draft_qa_proof.py` は fixture 可。実記事 live 証跡は human + 記事作業 |
| axis-3 | Note editor live 引き継ぎ確認 | open | package + human | editor skills / PDCA ledger / image upload boundary。実 UI と公開は human 承認後 |
| axis-4 | 壁打ちから複数コンテンツへの制作展開 | open | package | provenance / authorship / interview。wall_bang を事実出典にする fail 検査は未実装 |
| axis-5 | 型付き agent 運用・eval・observability | deferred | package | worker deny 契約と focused checker のみ。eval harness は後回し |
| axis-6 | 0.2.20 release | done | human | PR #17 merge + tag `v0.2.20` + GitHub Release 済み。追加 tag/Release は別承認 |

## 吸収済み（active TODO から除外）

| item | 行き先 | status |
|---|---|---|
| issue-drafts 課題1 パッケージ契約 | skill / package / tests | absorbed |
| issue-drafts 課題2 tracker-free runtime | package.yaml / SKILL.md | absorbed |
| issue-drafts 課題3 Spark/Sonnet optional | package.yaml / SKILL.md | absorbed |
| 埋め込み・目次・改行制約 | live constraint refs + linebreak/figure/toc gates | absorbed |
| capability-candidates worktree の authorship/interview/cover/toolbar | PR #17 へ選別採用 | absorbed |
| PDCA failure ledger JSON + docs 配線 | `data/note_editor_pdca_failure_patterns.json` + checker | absorbed |

## fixture TODO の扱い

- `content/drafts/*fixture*` や QA evidence 内の `TODO` / `todo_marker` / future-date は **製品残務ではない**。
- 製品 TODO は本 ledger の open 行と `issue-drafts.md` の active 課題だけを数える。

## worktree / branch 保全方針

| class | 扱い |
|---|---|
| 主 clone `.repos/.../note-publishing-suite` (main) | KEEP。正本 |
| PR #17 / capability / pr9 / pr10 / pr16 / ssot / public-sync / nested 0.2.0 | **削除済み**（2026-08-06）。patch/bundle は private reports に退避 |
| Projects リポの `nps-project-*` | WRONG_REPO。本 package の branch 整理対象外 |

force push は明示承認なしに実行しない。

## 停止線

- Note 公開 / 予約 / SNS / 外部告知（未承認）
- 追加の tag / GitHub Release
- repository visibility 変更
