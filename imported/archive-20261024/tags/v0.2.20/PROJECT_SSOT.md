---
title: Note Publishing Suite プロジェクト正本
type: project
status: active
created: 2026-07-25
updated: 2026-08-05
tags: [note, publishing, ssot, project]
schema_version: project-ssot/v1
recorded_at: 2026-08-05
recorded_by: claude-code
publication_gate: human_review_required
external_action: none
---

# Note Publishing Suite プロジェクト正本

## 正本宣言

`nexus-ai-2045/note-publishing-suite` の default branch `main` の履歴を
Note Publishing Suite のプロダクト正本とする。
ローカル checkout、private workspace、runtime skill、過去のコピーは正本そのものではなく、
この repository を参照または更新するための作業面・来歴である。

正本内の責務は次の通り。

| 対象 | 正本 |
|---|---|
| 目的・停止線・ルーティング | `SKILL.md` |
| 機械可読の構成契約・検証コマンド・子スキル一覧 | `package.yaml` |
| 文書同期の必須条件 | `package.yaml` の `docs_sync_contract` |
| 優先順位・受入条件 | `ROADMAP.md` |
| プロジェクト境界・現在地 | `PROJECT_SSOT.md` |
| 公開準備の証拠 | `PUBLIC_READY.md` |
| リリース履歴 | `CHANGELOG.md` |
| 非公開議論の来歴と吸収状況 | private workspace 側の索引（公開 package 外） |

文書間で矛盾した場合は、外部操作を行わない安全側へ倒し、
`PROJECT_SSOT.md` で責務を確認してから該当する正本ファイルを修正する。

## 北極星

ローカル素材から Note 記事の着想、下書き、品質確認、エディタ引き継ぎ、
公開後確認までを再現可能に支援する。ただし公開、予約投稿、告知、外部共有、
repository visibility 変更は、現在会話の人間レビューと明示承認なしに実行しない。

## 現在地

- 記録日: 2026-08-05（Asia/Tokyo）
- repository: `nexus-ai-2045/note-publishing-suite`
- visibility: public（fork 0 / star 0）
- default branch: `main`（実測確定）
- `main` head: `6de2d573a40b20b1f709589fa293f463c5e33bf6`
- open pull request: #13 相当の README 系は取り込み済み。残る open は別 branch 由来
- CI: `test` / `Push on main` / CodeQL いずれも成功
- open issue: 0 件（追跡は `issue-drafts.md` 側で継続）
- 本 SSOT 候補: local branch `codex/note-publishing-suite-ssot-20260805`（`main` 起点）
- 外部操作: 未実行
- 公開操作: 未実行

## 当面の成果

1. 散在する議論を private workspace 側の索引から追跡可能にする。
2. 議論から得た現行契約だけを `SKILL.md`、`package.yaml`、`ROADMAP.md` へ吸収する。
3. 旧コピーや記事固有記録は履歴として保持し、現行仕様へ自動昇格させない。
4. 1本のローカル下書きで、公開直前停止までの一気通貫証跡を再現する。

## 変更の入口

- 新しい要求や議論は、まず private workspace 側の「未吸収」索引に追加する。
- 採用する仕様は責務に応じて `SKILL.md`、`package.yaml`、`ROADMAP.md` に反映する。
- 実装・テスト・運用証跡を分ける。
- push、PR、release、Note公開、予約投稿、外部共有は別々の明示承認を必要とする。

## 公開 package に置かないもの

`main` は公開 repository の正本であり、「置いたが見せない」は成立しない。
次のものは公開 package へ含めず、private workspace 側に置く。

- 内部の設計文書、実装計画、レビューパケット（`docs/` 配下の内部設計を含む）
- private workspace の内部 path、記事コードネーム、運用台帳
- 個人を特定しうるメールアドレス、認証情報、非公開 URL

公開 package に残すのは、実装済みの契約と、その利用者が必要とする説明に限る。

## private workspace との境界

private workspace は横断ポインタ、議論原本、記事素材、運用証跡を保持する。
その内部 path や記事コードネームを公開 package へ記載しない。
プロダクト仕様を private workspace 側のコピーだけで変更しない。
