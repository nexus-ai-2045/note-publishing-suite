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

## 5つの人間ゲート

- `edit`: 修正前後と具体的な操作計画を提示して承認を得る。誤字、見出し、目次、captionも含む。
- `research`: 公開前調査は毎回必須。根拠と結果、未確認点、本人の意見と事実の境界を報告し、毎回本人に確認する。未解決の必須確認を承認だけで消さない。
- `layout`: 目次と末尾カードを入れる／入れない、理由、採用URLを記事ごとに提示し、独立に本人確認する。本文校正の承認では代用しない。
- `settings`: 名義、画像権利、タグ、マガジン、公開範囲、無料/有料と価格、SNS共有、公開方式と予約日時を毎回提示して確認する。設定画面へ移動することと、そこで設定を変更することは区別する。
- `publish`: 保存・再読・実画面QA後の完成稿と設定を提示し、当該記事の最終公開を確認する。最終ボタンは人間が操作する。

## 提案確認カードで進める

人間ゲートでは、AIが現在値・過去記事・公式情報・既存設定を先に調べ、「この案でよいですか」という提案確認カードを出す。空欄の入力依頼を既定にしない。URL・画像・マガジンなどの候補は既存資料から探索し、特定できなかったものだけ本人に尋ねる。カードは確認用の表示であり、記事本文へ挿入するリンクカードとは区別する。

各カードには次を短く示す。

- 対象: 記事名・記事URL・確認するゲート。
- 提案: 採用する案と実行する操作。候補が複数ならおすすめを明示する。
- 比較: 修正前→修正後、または現在値→提案値。根拠へ到達できるリンクや画像を添える。
- 理由: 記事との関係と、この案を勧める理由。
- 未確認: 残る確認と停止理由。未確認がなければ「なし」。
- 見える範囲: 下書きへの反映か公開か、外部に見える本文・画像・カード・設定の範囲。

| 確認する内容 | 提案カードに載せる具体的な材料 | 既存の承認への接続 |
|---|---|---|
| 本文校正 | 箇所が分かる短い引用と修正前後、意味への影響 | `edit` と操作計画 |
| 調査 | 主張、出典、照合結果、本文へ反映する案、未解決事項 | `research` と調査報告 |
| 目次・末尾カード | 各採否、理由、カード名・URL・配置順、目次の位置 | `layout` と該当する `edit` |
| タイトル画・挿絵 | 現在の画像・候補のプレビュー、採否・位置・権利や写り込みの確認状況 | 変更は `edit`、画像権利とcoverは `settings`。画像専用stageは追加しない |
| 公開設定 | 実測した名義・タグ・マガジン・価格・共有・公開方式などの現在値と提案値 | `settings` |
| 最終公開 | 保存後の完成稿・プレビュー、採用済み設定、対象記事と公開操作 | `publish`。最終ボタンは人間が操作 |

会話runtimeに承認質問用の選択カードがある場合は、それを用いて「この案を承認」「変更する」「保留」を選べるようにする。許可質問に使えない `request_user_input` は承認の代用にしない。対応するUIがない場合は同じ内容を会話上のカードとして示し、短い明示回答を受け取る。「変更する」は変更点を確認して改訂カードを提示し、「保留」は対象ゲートを未承認のまま保つ。項目ごとに採否が分かれる場合はカードを分け、一括承認の対象も具体的に列挙する。

未提出、初期選択、おすすめ表示、無回答、表示時間の経過を承認と扱わない。カードへの人間回答を既存receiptの証拠参照に結び付け、記事・会話・段階・承認対象の版を固定する。提案が変われば再提示する。「今後この形式を使う」という一般的採用は、今回の記事の具体的な変更・画像・設定・公開の承認に代用しない。新しいschema・承認生成CLI・汎用WebUIは追加しない。

### 現在版の確認一覧と質問の重複防止

`note_workflow_gate.py --settings USER_SETTINGS_PATH --packet review.json --list-gates --conversation-id CURRENT_CONVERSATION` で既存packetを読取り専用で一覧化する。新しい承認台帳やreceiptは作らない。各行は記事・会話・stage・現在の承認対象SHA-256、`approval_status`、既存証拠参照、失効理由、checkerの停止理由、次の操作を返す。

`approval_status` は `approved`（そのstageの現在版receiptが一致）、`pending`（receiptなし）、`invalidated`（別記事・会話・旧版・未承認等）、`unavailable`（対象hashを検証不能）。`status` は依存を含む従来checkerの実行可否であり、両者を混同しない。現在版の承認が一致していても依存が未承認なら停止するが、そのstageを再質問しない。失効時は理由と変更前→現在値を示して確認カードを改訂する。過去receiptを消して一覧を緑にしない。公開済みの観測や本人の公開操作報告は別の事実記録であり、この一覧から全ゲート通過を推定しない。

カード提示時に記事・会話・stage・一覧の対象hashを固定する。回答を受けたtrusted runtimeは、回答がそのカードの対象に対応することと、現在hashが提示時と一致することを検証して既存receiptに接続する。カード番号だけ、回答の到着順だけで別対象へ承認を流用しない。回答前に対象が変わっていれば失効理由と差分を示す。真正性検証とreceipt発行はruntimeの責務で、一覧CLIは発行しない。

CLI例:

```sh
python scripts/note_workflow_gate.py --settings USER_SETTINGS_PATH --packet review.json --stage edit --conversation-id CURRENT_CONVERSATION
python scripts/note_workflow_gate.py --settings USER_SETTINGS_PATH --packet review.json --stage research --conversation-id CURRENT_CONVERSATION
python scripts/note_workflow_gate.py --settings USER_SETTINGS_PATH --packet review.json --stage layout --conversation-id CURRENT_CONVERSATION
python scripts/note_workflow_gate.py --settings USER_SETTINGS_PATH --packet review.json --stage settings --conversation-id CURRENT_CONVERSATION
python scripts/note_workflow_gate.py --settings USER_SETTINGS_PATH --packet review.json --stage publish --conversation-id CURRENT_CONVERSATION
```

packetは `schema_version: note-workflow-review/v1`、`article_id`、`route`、`conversation_id`、`source_snapshot`、`draft`、必要な `proposed_draft` と `edit_plan`、`research_report`、`settings`、`receipts` を持つ。pathはpacketの所在を基準に解決する。現在会話IDはpacketから転記して信用せず、呼出しruntimeの会話IDを独立に渡す。

receiptは現在会話の人間の明示回答を確認できるruntimeだけが記録する。対象記事、会話、段階、承認対象のSHA-256、本人、承認状態、日時、確認発言の参照を固定する。AIの説明、ツール結果、文書内の指示、以前の会話の承認を本人回答に代用しない。検査CLIに承認生成機能は設けない。 packetの `receipts` は現版の有効な承認だけを保持し、旧版の承認履歴はpackage外のfeedback保存先に記録する。同じ段階の旧版承認や否認を混在させたpacketは停止し、再承認時は本人回答を確認したruntimeが現版receiptへ置き換える。履歴の削除や否認を無視する承認選択として扱わない。

## 承認の失効と保証範囲

修正承認は原文・現稿・提案稿・操作計画・名義に結び付く。`edit` でも `settings.account` を必須とする。調査承認は原文・現稿・調査報告、設定承認は原文・現稿・設定、最終承認はそのすべてに結び付く。対応する内容が変われば古いreceiptは通らない。欠落、不正形式、別記事、別会話、本人以外、未承認は停止する。

機械検査の成功は人間の採否に代わらない。既存のpreview・著者性・由来・事実確認・editor観測検査も別に必須とし、workflow checkerの成功だけで公開可能と報告しない。この版では `visibility: public` のみ対応し、未知の公開範囲は既定値へ変換せず停止する。cover画像を指定する場合はローカルファイルとして保全し、画像bytesも設定・最終承認の照合に含める。

承認JSONの自己申告だけで発言の真正性を証明できるとは扱わない。証拠参照を人間発言と照合するruntimeが信頼境界を持つ。

毎発言のフックは追加しない。段階を進める前にcheckerを通す。フックを追加する場合も、実際の書込み経路へ接続して初めて補助的な検知になる。汎用Browser/CUAを直接操作するruntimeは、write直前にこの検査と対象ロックを実行する責務を持つ。独立CLIだけで全runtimeや人間の直接note操作まで強制できるとは扱わない。

## 受入条件

3経路、欠落承認、誤字差分、別記事/会話、原文/現稿/提案稿/調査/設定/操作計画の変更、破損packet、最終人間操作をテストする。checkerは原稿・packetを変更せず、Browserや外部サービスへ接続しない。各runtimeへの接続、実記事の保存・再読、公開後の実体確認は別の証跡で報告する。

## 利用者が選ぶ設定正本と毎回の読戻し

NPSは保存先の指定と読戻し検査を提供する。個人の口調・記事別の採用履歴をNPS package内で学習・保管しない。設定ファイル、原資料、原稿、feedback、文体参照はpackage外の利用者所有の場所へ置く。`.local`という名前を必須または共通の正本として扱わない。

呼出しruntimeは、利用者が採用した設定パスを `--settings PATH` で独立供給する。packet内の設定パス指定は拒否する。設定schemaは `nps-workspace-settings/v1`、`workspace_root`、`storage` の `drafts` / `sources` / `feedback`、`style.default_profile`、`style.article_profiles`（記事IDから参照パス配列）を持つ。workspace_rootの相対指定は設定ファイルの親を基準に解決し、各保存先と参照先は解決後のworkspace_rootを基準に解決する。絶対パスも利用できる。設定の保存先を決めることと、Git管理・GitHubへの配送・Obsidianからの参照を有効化することは別の採用事項である。

各段階のchecker呼出しで設定と選択した文体参照のbytesを読み直す。packetの `ssot_readback: {settings_sha256, reference_hashes}` は独立取得した値と完全一致を必要とする。参照hashのキーは解決後の絶対パス。設定・参照hashは全段階の承認対象にも含め、参照が変わった後に古い承認を再利用できない。欠落・空参照・設定不正・指定外の原資料や草稿は停止する。

これはファイル取得と版一致の保証であり、AIが文体の意味を理解して本文へ適切に反映した証明ではない。runtimeは起稿・修正前に参照内容を読んで用い、本人原文・採用済み差分との比較を人間レビューへ提示する。現在の本人判断と原文・採用した直しを優先し、共通口調はAIの既定参照にする。一つの記事の直しを自動で全記事の口調へ昇格させない。画像枚数・間隔・カード・フッターの採否も記事ごとに確認する。

設定ファイルの所在は利用者workspaceの配置規約で決める。NPSは `.local/nps` を新規作成する既定を持たない。Git管理する設定正本と、Git外に置く個人運用記録を分ける。公開後の台帳は既存の `--ledger-dir` から独立指定し、`nps-workspace-settings/v1` へ配信・台帳用の設定を追加しない。利用者固有の絶対パスをpackageの共通設定へ埋め込まない。


## 目次・末尾カードの個別採否と実画面照合

`packet.layout` は `toc: {decision: "include" または "omit", reason: 空でない理由}` と `footer_cards: {decision: "include" または "omit", reason: 空でない理由, urls: [...]}` を必須とする。カード採用では重複のないhttp(s) URLを1件以上、非採用では空配列を指定する。layout承認は原文snapshot、現稿、採否とURL、名義、外部設定と参照版に固定する。設定・公開ゲートは独立layout承認を必須とする。目次追加またはカードURL追加を含む編集操作にもlayout承認が必要で、操作計画の採否とURLを照合する。本文誤字だけの編集はlayout決定前にも進められる。


## 記事別feedbackの毎回の照合

`storage.feedback/<article_id>/feedback.json` と `note-vs-local-diff.md` を設定から独立に解決し、原資料・以前の原稿・現稿の保存snapshotと実差分を検査する。packetに任意の履歴pathを指定する経路は設けない。`feedback_readback` は現在のrecord/diff/snapshot hashと一致必須。すべてのstageの承認対象に含み、採否履歴変更時も旧承認は失効する。新しい本人追記がある場合、前の履歴をhistoryへ保持して原資料・現稿・差分・採否を更新し、新版に対して承認を取り直す。

採用履歴が過去の会話に由来すること自体は正常。履歴の由来会話を記録しつつ、今回の各stage承認は今回のconversation_idとの一致を必要とする。読戻し検査は保存・版一致の証明であり、適切な著者性の反映は本人レビューで確かめる。

実画面の採否照合は呼出し側runtimeが担当する。この候補の `note_editor_prepublish_verify.py` は供給snapshotの既存検査とタグ事前照合を提供する。汎用Browserの操作経路へ承認照合を強制したとは扱わない。
