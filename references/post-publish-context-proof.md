---
title: Note公開後の文脈と本文点検の証拠
type: reference
status: active
created: 2026-07-16
updated: 2026-10-06
tags: [note, post-publish, ledger, snapshot, provenance]
---

# Note公開後の文脈と本文点検の証拠

## 目的

Note editorで公開直前に本文が変わっても、ローカルdraftを公開版の正本と誤認せず、公開ページ・snapshot・hash・台帳状態を接続する。

## 境界

- 実行コードの正本: `note-publishing-suite/scripts/`
- workspace固有データ: 利用側が指定するdraft、snapshot、ledger directory
- 公開本文の正本: 確認時点の公開URL
- 再現証跡: 取得snapshotとSHA-256
- 状態遷移: `note_drafts.json`の既存行を`published_from_note_editor_record`へ更新
- 公開済み一次台帳: `published_notes.json`

packageをworkspaceへコピーしてscriptsを二重化しない。利用側は`post_publish.py --ledger-dir <dir>`でprivate台帳を注入する。

## 公開後本文点検と既存feedback

公開観測の `body` は題名と分離したplain textであり、Markdown見出しを含む制作原稿とは別の入力形式として扱う。機械結果に `input_format: published_plain` を記録し、秘密情報・HTMLコメント・作業マーカー・再確認マーカーを検査する。明示的な「内部メモ」はerrorとして止める。制作中のH1・見出し数・導入の定型句・段落長・原稿長を公開後の誤字点検に流用しない。`pre_publish_check.collect_issues` の原稿向け既定の構成要件は維持する。

公開事実の台帳更新と、公開本文の誤字脱字点検を分離する。`post_publish.py` は既存の公開観測があれば `collect_published_issues` による公開plain text向け機械lintを自動実行し、`postpublish_review` と `postpublication_complete` を返す。公開観測なしは `waiting_for_publication`、AI未実行は `postpublish_review_pending` であり完了ではない。exit0や原稿との完全一致をAI点検の代用にしない。予約公開は公開本文の観測後に同じ入口を再実行する。

現在のtrusted agent runtimeが公開本文を読み、実toolの点検回答を回収する。新しいLLM/APIは追加しない。既存 `note-public-observation/v1` の `editorial_review` は次の内容を持つ。

```json
{
  "note_id": "n123",
  "url": "https://note.com/example/n/n123",
  "body_sha256": "実際の公開bodyをUTF-8にしたSHA-256",
  "scope": "full_public_body",
  "coverage_start": 0,
  "coverage_end": 100,
  "checks": ["typos", "omissions", "readability", "voice_preservation"],
  "source_thread_id": "実際の呼出元thread ID",
  "worker_id": "実toolで回収したworker ID",
  "reviewed_at": "2026-10-16T00:00:00+09:00",
  "summary": "実際に行った点検と結果",
  "findings": [{"before": "公開本文からの実引用", "after": "修正候補", "reason": "修正の理由"}],
  "evidence_ref": "実回答を保存したJSONの相対path",
  "evidence_sha256": "実回答ファイルのSHA-256"
}
```

`coverage_end` は本文のPython文字数に置き換える。`worker_id` の代わりに実 `turn_id` でもよい。実回答JSONは上記の `evidence_ref` / `evidence_sha256` を除いた全項目と一致させる。0件でもfindings配列・全範囲・実回答・実行IDを省略しない。これは構造例であり、実行済みの証拠ではない。実回答とIDは現在のtool結果から取得し、任意のactorを自称したJSONを作るだけでは完了にしない。

共通正本 `note_postpublish_review.check_postpublish_review(observed, base_dir=..., runtime_verifier=..., feedback_context=..., write_feedback=...)` を既存の利用側入口から呼ぶ。`runtime_verifier(review, raw_result_bytes)` は実tool結果を回収したownerが供給し、現在の実thread/worker/turn、点検した全文hashと範囲、実回答の内容を照合してTrueを返す。常にTrueを返すcallbackやJSON内のactor申告は真正性の照合ではない。callbackなしのCLIは `runtime_confirmation_required` のままでfeedbackを書かない。暗号学的署名や全runtimeの自動発火をこのPython検査が保証するわけではない。

既存 `post_publish.main(argv, runtime_verifier=...)` も同じ共通検査を呼ぶ。feedback接続は `--settings` / `--review-source` / `--conversation-id`（必要なら `--review-prior`）で既存保存先と原文を渡す。`--write-ledger` の明示時だけfeedback保存も実行する。共通関数を直接使う場合の `feedback_context` は `{dirs, source, draft, prior, conversation_id}`。dirsは既存 `read_workspace_settings` の解決結果、各原稿pathは `Path`、conversationは実点検のsource_thread_idと一致させる。

共通検査は既存feedbackを検証して読み、AI候補だけを `origin: ai` / `decision: pending` で追加する。同じ由来・採否・引用・修正案は実回答fileや理由が変わっても重複追加せず、元候補の証拠と今回観測の実点検証拠を分けて保持し、既存 `record_feedback` へ渡してsnapshotと履歴を保全する。保存後は同じreaderでentries/hashを再取得する。現在source/draftと保存済み候補が同じなら、書込なしの再確認でも既存feedbackの実体とhashを再検証してsaved_verifiedを返せる。未保存候補や初回未保存をこの経路で完了にしない。保存失敗・本文hash/記事違い・範囲不足・実行照合不能は完了にしない。新規候補、現在本文に引用が残る既存pending提案、または機械lintのerrorがあれば `review_required` として本人へ提示し、本文や本人採否は自動変更しない。公開後に本文が変われば古い点検を流用せず再取得する。計測queueのenabledや定期取得を点検のために変更しない。

## 最小フロー

### 初回公開（元draftあり）

```bash
python scripts/note_diff_check.py \
  <public-note-url> <local-draft> <required-phrase...> \
  --snapshot-out <workspace-snapshot.txt> --json

python scripts/post_publish.py \
  --url <public-note-url> \
  --draft <local-draft> \
  --note-id <note-id> \
  --verification-status published_verified \
  --published-snapshot <workspace-snapshot.txt> \
  --published-body-sha256 <sha256> \
  --ledger-dir <workspace-data-dir> \
  --write-ledger
```

公開版がlocal draftと異なる場合だけ`--local-draft-differs-from-published`を追加する。見出し画像を公開ページで確認した場合だけ`--cover-image-verified`を追加する。

### 公開済み記事の更新（元draftなしでも可）

公開URLを渡してNoteの公開APIを毎回読み直し、URLのnote IDと所有者、`published`状態、題名、アイキャッチ画像の素材ID（HTTPSホストとパス）を照合する。Noteが付ける画像変換クエリは比較から除くが、異なるホスト・パスやuserinfo付きURLは拒否する。公開APIが返した生URLは結果に残す。必要なら新しい本文句の存在と古い本文句の不在も確認する。編集画面や完了トースト、過去のsnapshotだけでは成功としない。

```bash
python scripts/verify_published_update.py \
  --url <public-note-url> \
  --expected-title <published-title> \
  --expected-eyecatch-url <expected-image-url> \
  --contains <new-body-phrase> \
  --absent <old-body-phrase> \
  --ledger <private-published_notes.json>
```

出力が`overall=ok`のときだけ公開APIの現在値と期待値が一致する。`body_sha256`と`verified_at`を確認し、記事固有の照合結果を利用側のprivate workspaceへ保存する。この検査器はファイルを書き出さない。本文snapshotが必要なら既存の`scripts/sync_note_public_snapshot.py`を別途使い、出力先を確認する。`--contains`/`--absent`は任意だが、本文を変更した場合はその差分を指定する。アイキャッチは期待するNote公開画像URLを指定し、画像変換クエリを除いた素材IDを比較する。視覚的な同一性や画像バイトの一致まで保証するものではない。URLを取得できない、期待値がない、画像が違う場合は保留する。

`--ledger`は既存のprivate公開済み台帳を**読み取るだけ**の任意引数で、指定時は同じnote IDの行が1件だけあり、URL・題名・画像素材ID・公開本文SHA-256が現在値と一致しなければ停止する。本文ハッシュは`published_body_sha256`または`public_body_sha256`を読み、両方あれば両方とも現在値に一致することを要求する。機械判定用の`verification_status`があれば`published_verified`を必須とし、ない場合にだけ従来NPS形式の`plain_status: published_verified`を使う。`status`があれば`published`でなければ停止する。人が読む`plain_status`の文章は書き換えない。台帳の作成・更新は利用側の既存writer/RSS経路で行い、書込後にこのコマンドで再照合する。元draftがない場合、`post_publish.py --draft`へ仮のpathを渡してdraft台帳を作らない。元draftの来歴は不明のまま保持する。

## 完了条件

- 公開URL・表示日時・title・image・tagsを実測済み。
- 必須phraseが公開本文に存在する。
- snapshot pathとSHA-256を記録済み。
- published ledgerはURLごとに1行。
- draft ledgerはnote idまたはdraft filenameごとに1行で、公開状態へ遷移済み。
- 再実行しても台帳行数が増えない。
- SNS共有や外部告知は別承認のまま。

公開済み記事の更新では、公開APIの現在値の照合と、台帳を管理している場合は`--ledger`の一致を完了条件とする。元draftの存在やdraft台帳遷移は要求しない。
