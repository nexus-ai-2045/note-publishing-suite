---
title: Note Publishing Suite 課題下書き
type: 持ち運び可能な課題下書き
status: active
created: 2026-06-08
publication_gate: human_review_required
external_action: none
tracker_required: false
---

# 課題下書き: Note Publishing Suite

このファイルは外部追跡ツール非依存の作業分解メモ。

Linear、GitHub Issues、Notion、Obsidian、todo.md のどれにも転記できるが、
どれも必須ではない。Codex または Claude Code だけでこのパッケージを使える。

情報の基準源:
- `SKILL.md`
- `package.yaml`
- `issue-drafts.md`
- `skills/*/SKILL.md`
- `scripts/test_skill_integration.py`
- `data/note_drafts.json` は下書き台帳。
- `data/published_notes.json` は公開済み一次台帳。

現在の検証根拠:
- `python -m pytest scripts/test_skill_integration.py tests/test_content_pdca_check.py`
- `python scripts/pre_publish_check.py <draft.md>`
- 公開、予約投稿、SNS共有、外部告知は、このパッケージでは実行しない。

## 課題 1: パッケージ契約を検証する

概要:
親スキル、管理情報、README、6子スキルが Note 投稿支援パッケージの契約を満たすことを確認する。

受入条件:
- 親 `SKILL.md` に `idea`、`draft`、`qa`、`editor`、`gate`、`ledger` のルーティングがある。
- `package.yaml` に Codex / Claude Code 単体運用の前提がある。
- 6子スキルが `入力`、`手順`、`停止条件`、完了確認証跡を持つ。
- `publication_gate: human_review_required` と `external_action: none` が標準状態として明記されている。
- パッケージ検証テストが通る。

## 課題 2: 追跡ツールなしの実行互換性を保つ

概要:
Linear などの外部追跡ツールや別実行環境が無くても、Codex または Claude Code 単体で実行できる契約を保つ。

受入条件:
- `tracker_required: false` が管理情報と課題下書きにある。
- Linear、GitHub、Slack、Drive などの連携口は任意と明記されている。
- 外部追跡ツールが無い場合でも、親スキルと子スキルだけでワークフローを進められる。
- 追跡ツールへの転記は現在会話でユーザーが明示依頼した場合だけ行う。

## 課題 3: Spark/Sonnet ワーカー加速を任意に保つ

概要:
Spark/Sonnet ワーカーは速度改善の任意手段として残し、必須条件にはしない。

受入条件:
- 親 `SKILL.md` に実行保証がある。
- `package.yaml` に `optional_acceleration: true` と `required: false` がある。
- Codex の任意ワーカーが `spark`、Claude Code の任意ワーカーが `sonnet` として記録されている。
- ワーカーが無い場合は `parent_runtime_sequential` で同じ分担粒度を順に処理する。
- ワーカーには認証情報、Cookie、非公開URL、公開/予約/送信権限、リポジトリ公開範囲変更権限を渡さない。
- ワーカー出力は親実行環境が出典、差分、テスト、公開ゲートを確認してから採用する。

## 課題 4: 1つのローカル Note 下書きを QA 領域に通す

概要:
任意のローカル下書きを `qa` 段階に通し、Note 投稿前検査の流れが運用可能であることを確認する。

受入条件:
- 下書き frontmatter に `article_lane`、`source_mode`、`based_on`、
  `allowed_use`、`not_allowed`、`editor_test_allowed` があり、
  出典パック / 骨子 / 姿勢メモの役割が分かる。
- `scripts/note_preview.py` でプレビューを生成または生成手順を確認できる。
- `scripts/pre_publish_check.py <draft.md>` が実行できる。
- `scripts/note_fact_check.py local <draft.md>` の要確認候補を記録できる。
- `scripts/note_diff_check.py` は比較対象がない場合、未実行理由を記録する。
- 警告が残る場合は `note-draft-production` へ戻る。

## 課題 5: 公開せずに Note エディタ引き継ぎを確認する

概要:
Note エディタ反映段階を公開なしで通し、下書き保存までの境界と停止点を確認する。

受入条件:
- 反映対象記事、タイトル、本文、タグ、TOP画像状態、マガジン状態を確認する。
- Note エディタへの反映が可能な場合でも、公開/予約確定ボタンの手前で停止する。
- 画像アップロードは完全自動化前提にせず、未確認または手動確認として記録する。
- エディタ反映後の差分確認が可能なら実施し、不可なら理由を記録する。
- 外部公開、SNS共有、告知は実行しない。

## 課題 6: 公開後台帳手順を定義する

概要:
公開後にだけ使う台帳更新手順を、SNS共有と分離したまま運用可能にする。

受入条件:
- `scripts/post_publish.py --dry-run` の接続または help/import 確認ができる。
- `data/published_notes.json` に記録する項目が明記されている。
- `data/note_drafts.json` からの扱いが明記されている。
- `--x-text` と `--x-schedule` はパッケージ内で使用禁止とする。
- 公開URL、公開状態、表示日時が未確認なら台帳更新しない。

## 課題: note 公式ノウハウの取り込み

- note 公式 (ヘルプセンター / 公式マガジン / クリエイター向け記事) の執筆・タグ・目次・公開時間のノウハウを一次情報として収集し、references/ に落とす。
- 収集前に skill 本文へ「公式が言っていること」として書かない (作文禁止)。
- 担当: 未割当 / 状態: 未処理

## 課題: 埋め込み・目次・段落内改行のエディタ制約ドキュメント

- HTML 貼り付けで再現できない note エディタ機能 (リンクカード埋め込み / 目次 / Shift+Enter の段落内改行) を実測ベースで文書化し、editor-prepublish skill の手動境界リストに反映する。
- 実測済み: Shift+Enter は同一 `p` 内の `<br>` / URL 埋め込みは URL 単独行の Enter 後に `figure[data-src]` + `iframe.note-embed` / 目次は `table-of-contents` + `toc` 属性 / 大見出しは `H2` / 小見出しは `H3`。
- 復旧境界: 埋め込み変換後と目次挿入後の `Control+Z` 1回では DOM が残ったため、誤位置は手動削除/復旧確認へ戻す。
- URL 行が通常リンクのまま残る、または埋め込みカード位置を実測確認できない場合は、本文崩れを避けて手動境界として報告する。
- 担当: 未割当 / 状態: 未処理
