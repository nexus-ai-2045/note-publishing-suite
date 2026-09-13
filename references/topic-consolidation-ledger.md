---
title: note-publishing-suite topic consolidation ledger
type: reference
status: active
publication_gate: human_review_required
external_action: none
updated: 2026-08-28
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
| axis-2 | 実記事1本のローカル一気通貫証跡 | open | package | fixture 着想→QA→公開直前停止を 2026-08-28 再証跡（`data/local_draft_qa_stop_before_publish_evidence.json`、`external_actions_performed: []`）。実記事 live は human + 記事作業 |
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

### 2026-09-13 POSIX Codex pointer 配布

- 目的: 別OS由来の到達不能な正本パスを手修正で維持せず、既存インストーラーから再生成する。
- 所有者: package は生成・検査、利用側は workspace の所有者確認・配布先・次セッションの発見と実行を担当する。
- 正本: `adapters/claude-code/install.sh` と共通テンプレート。`NOTE_SKILL_RUNTIME=codex` を追加し、既存 `scripts/skill_pointer_check.py` で生成前後を検査する。Windows の `adapters/codex/install.ps1` は別OS実装として維持する。
- 検証: `tests/test_skill_pointer_check.py` に旧参照の置換成功、未知runtimeの書込み前拒否、CODEX_HOME適用を追加。既存の欠落・不一致・symlink拒否も維持する。
- 完了条件: パッケージ検証に加え、利用側の正しいworkspaceへの配布、次セッションの発見、実行結果を別々に確認する。
- 状態: 実装・隔離環境の配布テスト済み。利用側workspaceが未確定のため実配布・有効化・次セッション実行は未確認。CI・公開・統合完了とは扱わない。
- 実測: macOSで全体pytestは172 passed / 10 skipped（Windows固有）。docs_sync_check、pointer checker、差分の空白検査は成功。Codexのworkspace省略・不存在を配布前に拒否するテストも追加。配布担当は再配布と次セッション検証を限定受理済み。入力workspaceの確定と実配布は未完了。
- 公開済み記事は `skills/note-postpublish-ledger` の公開snapshotと差分記録を使う。旧草稿を公開本文とみなす独自台帳は追加しない。

- Note 公開 / 予約 / SNS / 外部告知（未承認）
- 追加の tag / GitHub Release
- repository visibility 変更
