# Initial Note workflow ruleset

このファイルは、Note Publishing Suite が Note 記事支援を始める前に
最初に確認し、完了まで戻ってくる 13 工程の SSOT。

目的は Note を自動公開することではない。人間がローカル素材、記事意図、
公開方式、レビュー状態を選び、suite が必要な下書き、検査、エディタ引き継ぎ、
公開直前停止、台帳更新案をレビュー可能にすること。

## スコープ

この ruleset は Note Publishing Suite 専用。Discord bridge、X 投稿、
外部告知、GitHub repository visibility 変更、公開範囲変更は含めない。

public package に保存してよいのは、空台帳、fixture、safe metadata、
検査結果 schema、レビュー可能な local artifact、停止線、検証コマンド。
実運用中の非公開下書き URL、Cookie、token、ブラウザプロファイル、
個人ローカルパス、実アカウント固有 denylist は public package に混ぜない。

## 主工程

1. **素材入口指定**

   ユーザーが読んでよいローカル素材フォルダ、下書き候補、または
   source database を指定する。未指定なら停止する。
   Note 全体、非公開 URL、ブラウザ履歴、未承認フォルダは読まない。

2. **既存 SSOT / 台帳確認**

   `data/note_drafts.json`、`data/published_notes.json`、
   `references/note-article-provenance-design.md`、既存 source pack を確認する。
   既存記事、続編、重複候補、stale draft、公開済み note との関係を分ける。

3. **記事スコープと公開方式の仮決め**

   記事の目的、読者、article lane、source mode、公開方式を仮決めする。
   即時公開、予約投稿、下書き保存のみ、未定のどれかを明示する。
   公開方式が未定でも下書きまでは進めてよいが、公開 gate では停止する。

4. **根拠パック構成**

   source database、source pack、series plot、article plot、skeleton、
   wall bang、stance brief を分ける。
   事実として使えるものと、仮説、構成、表現候補を混ぜない。

5. **骨子確認 gate**

   skeleton と主張、根拠、読者への約束、避ける表現を短く確認する。
   根拠不足、権利リスク、秘密情報、公開名義の未確認があれば下書きへ進まない。

6. **下書きプローブ**

   公開候補ではない provisional draft を作る。
   これは文章化の試作であり、未確認表現、数字、本人発言、体験談、
   出典不足を発見するために使う。

7. **下書きリスクレビュー**

   provisional draft を、根拠適合、未確認表現、内部メモ、秘密情報、
   URL、トーン、権利、公開名義、読者への誤解リスクで確認する。
   状態は `revise`、`needs_source`、`qa_ready`、`stop` など短く返す。

8. **Markdown レビュー artifact / local preview**

   下書き、確認対象、QA 結果、ファクトチェック候補、未解決事項、
   次の選択肢を Markdown または local evidence artifact に残す。
   `note_preview.py` で preview を生成できる場合は、公開せず確認する。

9. **最終下書き候補**

   review 後に final draft candidate を作る。
   AI 生成でも人間編集でもよいが、人間が編集した本文を source of truth とする。
   ここでもまだ Note に公開済みではない。

10. **Note editor 引き継ぎ**

   in-app Browser で接続できる場合だけ、タイトル、本文、画像、リンク、
   タグ、マガジン、公開範囲、無料/有料などを確認する。
   画像 upload、埋め込み、目次、カーソル位置は実測できない場合、手動境界に戻す。

11. **公開直前 human gate**

   `note-publication-gate` で、対象記事、操作、公開方式、公開名義、
   画像権利、タグ、マガジン、公開範囲、SNS 共有設定を確認する。
   現在の会話で対象記事と操作を特定した明示承認がない限り、
   公開、投稿、予約確定、SNS 共有、外部告知は実行しない。

12. **公開後確認 / 台帳更新案**

   公開または予約が明示承認済みで完了した後だけ使う。
   Note URL、公開状態、表示日時、本文差分、下書き状態を確認し、
   `post_publish.py --dry-run` で台帳更新案を作る。
   未確認なら `data/published_notes.json` へ書かない。

13. **終了・handoff**

   作業を止める時、記事を次工程へ渡す時、公開後改善へ進む時は、
   current state、read scope、draft path、QA 状態、editor 状態、
   publication gate、ledger 状態、stopline、next action を残す。
   handoff は local Markdown / metadata artifact であり、公開物ではない。

## 任意割り込み

- **壁打ち割り込み**

  人間がいつでも主張、違和感、読者角度、比喩、タイトルを相談できる。
  suite は採用した変更、捨てた案、残った unknown を review artifact に戻す。

- **追加出典取得割り込み**

  根拠が足りない場合、ユーザーが指定した素材範囲へ戻る。
  外部ファクトチェックや未承認フォルダ読取は自動実行しない。

- **公式ガイダンス割り込み**

  note 公式仕様として扱う前に `note-official-guidance-intake` へ戻る。
  公式ソース URL と confirmed_on がない便利運用は local policy として分ける。

- **エディタ制約デバッグ割り込み**

  埋め込み、目次、Shift+Enter、画像 caption / alt、保存表示が不安定なら
  `note-editor-constraint-debug` と `note-editor-ops` で 1 cycle 1 action の
  実測に戻す。

## Stopline

- Note 公開、投稿、予約確定、SNS 共有、外部告知は明示承認までしない。
- repository visibility 変更、GitHub public 化、外部 tracker 登録はしない。
- Cookie、token、非公開 URL、ブラウザプロファイルを読まない、保存しない。
- 実運用中の非公開下書き、個人ローカルパス、秘密情報を public package に入れない。
- 実記事候補と editor fixture を混ぜない。
- Discord bridge、X 投稿、Note 記事制作以外の作業をこの ruleset に混ぜない。
