---
name: note-editor-prepublish
description: "Repo-local Note editor handoff skill for reflection, formatting, save, and pre-publication verification."
---

# note-editor-prepublish

## 役割

Note editor への反映、目次、リンク、画像、埋め込み、タグ確認、下書き保存を扱う。

## Source

この package 内の `skills/note-editor-prepublish/SKILL.md` を正本にする。
低レベル操作や実測復旧が必要な場合だけ、`../note-editor-ops/SKILL.md` を追加で読む。

## 入力

- local draft path。
- Note editor または draft URL。未作成なら Unknown。
- draft frontmatter の `article_lane`、`source_mode`、`editor_test_allowed`。
- TOP 画像 path。未設定なら Unknown。
- タグ、マガジン、公開範囲、無料/有料、価格。
- QA 結果。preview / pre_publish / fact_check の状態。

## 手順

1. 親 suite の Hard Gates を再確認する。
2. この repo-local skill の境界と Closeout Evidence を確認する。
3. `../../references/note-article-provenance-design.md` を読み、
   実記事候補と editor fixture が混ざっていないか確認する。
4. 低レベル操作が必要なら `../note-editor-ops/SKILL.md` を読む。note editor attach、埋め込み、URL単独行、Enter変換、DOM確認、figure/data-src、Undo復旧、Playwright/CUAズレ、公開後台帳のいずれかが出たら必ず読む。
5. in-app Browser で editor を開く、または attach する。
6. タイトル、本文、見出し、リンク、画像、タグ、マガジン、公開範囲を反映/確認する。
7. 下書き保存までで止める。
8. 公開/投稿/予約確定ボタンは押さない。
9. 画像 upload が関わる時は、先に `../../references/note-image-upload-automation-boundary.md` を読み、`python ../../scripts/note_image_upload_boundary_check.py --json` 相当の保証を確認する。
10. 公開設定画面へ進む場合も、`投稿する`、`更新する`、予約確定、共有系の最終ボタンは押さない。画面状態を読み取り、公開手前QAを満たすかだけ確認する。

## 公開手前QA

公開設定画面または editor から閉じる前に、次を明示的に確認する。

- TOP画像: 設定済み、またはユーザー監督の手動uploadに残した理由がある。
- 目次: `table-of-contents` が1件あり、H2/H3見出しを参照している。
- フッター導線: 公式、リリース、Discord、マガジンURLがカード化済み、または生URLのまま残す判断と理由がある。
- マガジン: 対象マガジンが `追加済`。
- タグ: 重複タグがなく、触れなかったタグの理由がある。
- 記事タイプ: 無料/有料/価格が意図通り。
- 公開ボタン: `投稿する` / `更新する` / 予約確定 / 共有は未操作。

実測結果をJSONで残せる場合は、`python ../../scripts/note_editor_prepublish_verify.py <observation.json>` を通す。
このcheckerはnote画面を操作しない。agentがDOMから読んだ観測JSONを検査するだけの公開手前ゲートである。

## 埋め込み

- note 公式ヘルプでは、外部サービス URL の貼り付けで埋め込みまたはカード化され、URL 貼り付け後に Enter / Return が必要な場合がある。
- この suite の local policy として、Markdown リンクや HTML 貼り付けではなく、URL を独立段落に入力して変換を確認する。
- URL 行が通常リンクのまま残る、またはカード位置が意図した段落直下に入らない場合は、本文崩れを避けて手動境界として報告する。
- 既存の本文URL行をその場で自動カード化しない。位置制御が実測で不安定な場合があるため、空段落に新規挿入できる時だけ行い、既存URLを置換する操作は人間確認へ渡す。
- 誤位置にカードやURLが入った場合は、追加編集を続けず、ローカル正本から本文再反映または人間確認で復旧する。
- `figure[data-src]` などの DOM 判定は local checker であり、公式ヘルプの記述として扱わない。

## 境界

- in-app Browser を優先する。
- attach/inspect できない場合は停止する。Chrome、Computer Use、live article へ無断で切り替えない。
- write前に note id、draft URL、tab、Browser surface、account、operation mode を対象ロックとして確認する。別note、別tab、別surface、別accountへ切り替える場合は、切替理由と予定操作を示してユーザーの事前確認を得る。同一対象へのwriteが現在の会話で承認済みなら、read-onlyからwriteへ進むためだけの重複確認は不要とし、未承認ならwrite前に確認する。
- 能力非対応は再試行せず手動境界へ渡す。接続失敗またはDOM状態ズレだけ、同一対象で1回まで再確認・再試行する。別surfaceへの移行は自動fallbackにしない。
- note editor のボタン、ツールバー、サイドパネル配置は画面幅や選択状態で動的に変わる。公開、予約、共有、保存系は固定座標で操作せず、DOM、ラベル、状態で識別し、明示承認がなければ押さない。
- Playwright の DOM 座標と CUA の実操作面が同期しない場合、固定座標操作を継続しない。意図しない段落に入力したら即 Undo で復旧し、DOM/ラベル/選択状態で再確認できる方法へ切り替える。復旧できない場合は手動境界として止める。
- 公開、予約投稿、投稿、SNS 共有、外部告知は行わない。
- `production_candidate` の本文を editor 操作テスト目的で改変しない。
  editor 操作検証が必要な場合は `editor_fixture` lane の無害なテスト文を使う。
- 画像アップロードは内部ブラウザだけで完全自動化できる前提にしない。必要なら手動または supervised 操作に分ける。
- Codex in-app Browser が file upload をサポートしない場合、画像候補選定までで止め、実uploadはユーザー監督の手動操作へ渡す。
- 画像 upload 境界は `../../references/note-image-upload-automation-boundary.md` と `../../scripts/note_image_upload_boundary_check.py` で確認する。画面に見えている Windows ファイル選択ダイアログだけを扱う場合も、現在会話での明示確認があるまで実行しない。
- リンクカード埋め込み、目次位置、カーソル操作は実測確認できない場合、手動境界として報告する。
- 目次は公式ヘルプ上、見出し設定が前提。プレビュー表示は通常できず、予約投稿設定済み記事だけ例外があるため、下書き段階で表示保証しない。
- in-app Browser API から `note.com` / `editor.note.com` の直URL open/goto がブロックされる場合、迂回しない。ユーザーがサイドパネルで対象URLを開いた後に attach だけ行う。
- Cookie、token、非公開 URL、個人情報をログに残さない。

## 停止条件

- in-app Browser で Note editor を attach / inspect できない。
- 画像アップロードが内部ブラウザで完了しない。
- Codex in-app Browser が `File uploads are not supported` を返した。
- 既存URL行のカード化で誤位置挿入、重複、生URL残骸が発生した。
- タグチップのクリックが削除ではなく重複追加になった。
- QA 結果、タグ、マガジン、公開範囲、価格のどれかが Unknown。
- 公開/投稿/予約確定ボタンを押す必要が出た。

## Closeout Evidence

- URL、title field、H2 数、anchor 数、TOC 有無、画像有無、保存通知、metadata leakage 有無を報告する。
- article lane、source mode、editor fixture を使ったかを報告する。
- 埋め込みカードの有無、対象 URL、配置できた位置、手動境界に残した理由を報告する。
- 実測で増やした保証、復旧した失敗、再発防止、追加/実行した checker や contract test を報告する。
- 下書き保存まで完了したか。
- 手動境界に残した操作。
- 対象ロック、対象切替の有無、ユーザー確認、失敗分類、再試行回数、fallback。
