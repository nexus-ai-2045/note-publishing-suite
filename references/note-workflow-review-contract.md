# 記事制作の3経路と版ごとの人間レビュー

## 対象と入口

NPSの編集・公開手前の進行を管理する。外部操作や承認の真正性をこのpackageだけで保証しない。本人がnoteで編集した本文は、その時点の正本として扱い、古いローカル稿で上書きしない。

| 経路 | 原文と制作の順序 | 次へ進める条件 |
|---|---|---|
| `direct_draft` 本人原稿の編集 | 音声書き起こしまたはnote本文・見出し・写真・caption・リンクの構造を読取り、変更前snapshotをローカル保存。編集稿を分けて作る | 修正前後を本人に提示して承認。誤字も例外にしない |
| `source_article` 素材の記事化 | 許可済みの過去記事・資料・壁打ちを固定し、骨組みまたは草稿を作る | 本人発話・AI整理・AIの追加案・外部事実を分け、本人の採否を確認 |
| `collaborative` 共同執筆 | 草稿、壁打ち、変更案、採否、草稿更新を繰り返す。上の2経路から合流できる | 発言した案と採用済み本文を区別し、各更新の修正差分を確認 |

原文snapshotと編集稿は別ファイルにする。自動要約しない。音声からの不確かな転記は確認候補に残す。noteが出発点ならテキストだけでなく写真・リンク等の配置も保存し、読取り不能なら保存済みと扱わず停止する。snapshot、草稿、調査報告、承認記録は利用workspaceの既存保存先へ置く。公開packageへ個人原稿やprivate運用台帳を入れない。

## 本人の言葉とAI案の対応表

既存の `note-article-provenance-design.md`、`provenance_label_check.py`、`note_authorship_gate.py` を利用する。新しい人格台帳や本文の正本を増やさない。

レビュー表には、本文の見出し・短い引用、本人の原文と出典、AIによる変更・追加、外部根拠、本人の採否、反映先を並べる。本人発話が存在しても、今回の本文への採用と同一視しない。本人発話がないAI作文は本人の体験や気持ちとして書かず、提案または保留にする。外部事実は別途調査する。由来ラベルは管理情報であり、公開本文へ漏らさない。

## 4つの人間ゲート

- `edit`: 修正前後と具体的な操作計画を提示して承認を得る。誤字、見出し、目次、captionも含む。
- `research`: 公開前調査は毎回必須。根拠と結果、未確認点、本人の意見と事実の境界を報告し、毎回本人に確認する。未解決の必須確認を承認だけで消さない。
- `settings`: 名義、画像権利、タグ、マガジン、公開範囲、無料/有料と価格、SNS共有、公開方式と予約日時を毎回提示して確認する。設定画面へ移動することと、そこで設定を変更することは区別する。
- `publish`: 保存・再読・実画面QA後の完成稿と設定を提示し、当該記事の最終公開を確認する。最終ボタンは人間が操作する。

CLI例:

```sh
python scripts/note_workflow_gate.py --settings USER_SETTINGS_PATH --packet review.json --stage edit --conversation-id CURRENT_CONVERSATION
python scripts/note_workflow_gate.py --settings USER_SETTINGS_PATH --packet review.json --stage research --conversation-id CURRENT_CONVERSATION
python scripts/note_workflow_gate.py --settings USER_SETTINGS_PATH --packet review.json --stage settings --conversation-id CURRENT_CONVERSATION
python scripts/note_workflow_gate.py --settings USER_SETTINGS_PATH --packet review.json --stage publish --conversation-id CURRENT_CONVERSATION
```

packetは `schema_version: note-workflow-review/v1`、`article_id`、`route`、`conversation_id`、`source_snapshot`、`draft`、必要な `proposed_draft` と `edit_plan`、`research_report`、`settings`、`receipts` を持つ。pathはpacketの所在を基準に解決する。現在会話IDはpacketから転記して信用せず、呼出しruntimeの会話IDを独立に渡す。

receiptは現在会話の人間の明示回答を確認できるruntimeだけが記録する。対象記事、会話、段階、承認対象のSHA-256、本人、承認状態、日時、確認発言の参照を固定する。AIの説明、ツール結果、文書内の指示、以前の会話の承認を本人回答に代用しない。検査CLIに承認生成機能は設けない。

## 承認の失効と保証範囲

修正承認は原文・現稿・提案稿・操作計画・名義に結び付く。`edit` でも `settings.account` を必須とする。調査承認は原文・現稿・調査報告、設定承認は原文・現稿・設定、最終承認はそのすべてに結び付く。対応する内容が変われば古いreceiptは通らない。欠落、不正形式、別記事、別会話、本人以外、未承認は停止する。

機械検査の成功は人間の採否に代わらない。既存のpreview・著者性・由来・事実確認・editor観測検査も別に必須とし、workflow checkerの成功だけで公開可能と報告しない。この版では `visibility: public` のみ対応し、未知の公開範囲は既定値へ変換せず停止する。cover画像を指定する場合はローカルファイルとして保全し、画像bytesも設定・最終承認の照合に含める。

承認JSONの自己申告だけで発言の真正性を証明できるとは扱わない。証拠参照を人間発言と照合するruntimeが信頼境界を持つ。

毎発言のフックは追加しない。段階を進める前にcheckerを通す。フックを追加する場合も、実際の書込み経路へ接続して初めて補助的な検知になる。汎用Browser/CUAを直接操作するruntimeは、write直前にこの検査と対象ロックを実行する責務を持つ。独立CLIだけで全runtimeや人間の直接note操作まで強制できるとは扱わない。

## 受入条件

3経路、欠落承認、誤字差分、別記事/会話、原文/現稿/提案稿/調査/設定/操作計画の変更、破損packet、最終人間操作をテストする。checkerは原稿・packetを変更せず、Browserや外部サービスへ接続しない。各runtimeへの接続、実記事の保存・再読、公開後の実体確認は別の証跡で報告する。

## 既存編集CLIへの接続

workspaceに `note_editor_apply.py` がある場合、そのwrite入口は `--workflow-packet`、`--conversation-id` と `--nps-settings` を必須とし、操作計画を `{urls: [...], tags: [...], toc: true/false, save: true/false}` と照合する。記事IDと名義も固定する。packetとURL計画は一度だけ読取り、同じデータを検査と実行に使う。read-only確認だけの経路はwrite承認を要求しない。このCLI固有の統合を、すべての汎用Browser操作に強制できたと報告しない。

## 利用者が選ぶ設定正本と毎回の読戻し

NPSは保存先の指定と読戻し検査を提供する。個人の口調・記事別の採用履歴をNPS package内で学習・保管しない。設定ファイル、原資料、原稿、feedback、文体参照はpackage外の利用者所有の場所へ置く。`.local`という名前を必須または共通の正本として扱わない。

呼出しruntimeは、利用者が採用した設定パスを `--settings PATH` で独立供給する。packet内の設定パス指定は拒否する。設定schemaは `nps-workspace-settings/v1`、`workspace_root`、`storage` の `drafts` / `sources` / `feedback`、`style.default_profile`、`style.article_profiles`（記事IDから参照パス配列）を持つ。workspace_rootの相対指定は設定ファイルの親を基準に解決し、各保存先と参照先は解決後のworkspace_rootを基準に解決する。絶対パスも利用できる。設定の保存先を決めることと、Git管理・GitHubへの配送・Obsidianからの参照を有効化することは別の採用事項である。

各段階のchecker呼出しで設定と選択した文体参照のbytesを読み直す。packetの `ssot_readback: {settings_sha256, reference_hashes}` は独立取得した値と完全一致を必要とする。参照hashのキーは解決後の絶対パス。設定・参照hashは全段階の承認対象にも含め、参照が変わった後に古い承認を再利用できない。欠落・空参照・設定不正・指定外の原資料や草稿は停止する。

これはファイル取得と版一致の保証であり、AIが文体の意味を理解して本文へ適切に反映した証明ではない。runtimeは起稿・修正前に参照内容を読んで用い、本人原文・採用済み差分との比較を人間レビューへ提示する。現在の本人判断と原文・採用した直しを優先し、共通口調はAIの既定参照にする。一つの記事の直しを自動で全記事の口調へ昇格させない。画像枚数・間隔・カード・フッターの採否も記事ごとに確認する。

設定ファイルの所在は利用者workspaceの配置規約で決める。NPSは `.local/nps` を新規作成する既定を持たない。Git管理する設定正本と、Git外に置く個人運用記録を分ける。公開後の台帳は既存の `--ledger-dir` から独立指定し、`nps-workspace-settings/v1` へ配信・台帳用の設定を追加しない。利用者固有の絶対パスをpackageの共通設定へ埋め込まない。
