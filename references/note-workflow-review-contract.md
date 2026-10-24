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
- `layout`: タイトル画・挿絵、目次・見出し、埋め込み・末尾カードの具体案と理由を記事ごとに提示し、壁打ちと本人の採否を独立に確認する。本文校正の承認では代用しない。画像権利とタイトル画の設定は `settings`、実際の変更は `edit` で扱う。
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
| タイトル画・挿絵 | 現在の画像・候補のプレビュー、採否・理由・位置・権利や写り込みの確認状況 | 採否は `layout`、変更は `edit`、画像権利と実画像は `settings`。画像専用stageは追加しない |
| 公開設定 | 実測した名義・タグ・マガジン・価格・共有・公開方式などの現在値と提案値 | `settings` |
| 最終公開 | 保存後の完成稿・プレビュー、採用済み設定、対象記事と公開操作 | `publish`。最終ボタンは人間が操作 |

会話runtimeに承認質問用の選択カードがある場合は、それを用いて「この案を承認」「変更する」「保留」を選べるようにする。許可質問に使えない `request_user_input` は承認の代用にしない。対応するUIがない場合は同じ内容を会話上のカードとして示し、短い明示回答を受け取る。「変更する」は変更点を確認して改訂カードを提示し、「保留」は対象ゲートを未承認のまま保つ。項目ごとに採否が分かれる場合はカードを分け、一括承認の対象も具体的に列挙する。

未提出、初期選択、おすすめ表示、無回答、表示時間の経過を承認と扱わない。カードへの人間回答を既存receiptの証拠参照に結び付け、記事・会話・段階・承認対象の版を固定する。提案が変われば再提示する。「今後この形式を使う」という一般的採用は、今回の記事の具体的な変更・画像・設定・公開の承認に代用しない。新しいschema・承認生成CLI・汎用WebUIは追加しない。

### 現在版の確認一覧と質問の重複防止

#### タグ・リンク・埋め込みの確認漏れを防ぐ

5段階の承認は維持し、一覧では `layout.review_items` にタイトル画、目次、末尾カード、挿絵、埋め込み、ハイパーリンクの採否を個別表示する。`settings.tag_review` は既存 `tag_design` の内容・発見・ブランドの根拠と実選択の観測を表示する。「設定確認」にまとめて、選定そのものを省略しない。欠落は未確認のまま表示し、候補が並んでいるだけで通過扱いにしない。

`layout.hyperlinks` も必須とし、`decision`、`reason`、`items` を記録する。採用時の各itemは `url`、読者に見える `text`、`purpose`、`placement` を持つ。不採用は明示的な `omit` と空の `items`。既存packetで欠けている場合は実際の本文リンクと本人の採否を読み戻して補い、承認を自動生成しない。候補URLの存在確認、本文との関係、正しい本人のサイトか、表示文と到達先の一致、保存後の保持を確認する。URLや表示文を変えれば構成の承認対象も変わる。

本文中の文字リンク、本文中の埋め込み、末尾カードは別の表示形式として検討する。記事・マガジン・ホームページ・GitHub・SNS・サービス等は、読者が次に何をできるかに応じて既存の公開先から選ぶ。存在しないサービスURLや未許可のコミュニティ案内を補わない。カードを省く案でも、候補と理由を提示した本人判断を記録する。末尾の順序・形式と表示読戻しは既存 `footer-selection` と `note_editor_prepublish_verify.py` を使う。

ハッシュタグは本文との適合、読者が探す語、note内の掲載文脈、既存ブランド、比較して外した候補を確認する。表示記事件数を検索ボリューム・流入効果に置き換えない。Google等の検索導線はタイトル・見出し・本文も併せて検討し、タグだけの効果を保証しない。提案、本人の採否、note上の実選択、公開後の実測を分けて既存feedbackと調査報告へ戻す。設定画面で選択できたことを、キャンセル後も保存されたことと混同しない。

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

## 初回設定の案内

導入担当は、初めての利用者または採用settingsが未確認の利用者へ次を案内する。既存settingsがある人は変更前に読戻し、再初期化しない。installerの前に外部workspaceを選ぶ。installerはスキルpointerを登録するだけで、個別設定やNoteログインを代行しない。

1. **保存先**: package外のworkspaceと、原文・下書き・feedbackの保存先を選ぶ。Git管理や外部配送は別判断。
2. **素材**: 読んでよいフォルダーと範囲を指定する。未指定の場所を探さない。
3. **本人の言葉**: 文体参照として使ってよい過去記事・口述・編集指示を選ぶ。過去記事がない場合は短い問答から本人の回答を保存し、AIの感想で埋めない。

画像を使う時は本人の画像・参照policy、履歴を強制する時は `history_learning_policy`、公開前調査を強制する時は `research_quality_policy` を本人と選ぶ。使わない任意policyは未採用と明記する。Noteのログインや画像アップロードは、editor段階で実際の利用可否を確認し、対応外の操作は手動へ戻す。

例としてpackageと並ぶ `my-note-workspace/` を選ぶ場合、`config/`、`content/drafts/`、`content/sources/`、`content/feedback/`、`content/assets/`、`data/`、`references/` を作る。`references/author-style.md` には本人が採用した表現・口調・避けたい表現を保存する。`config/nps-settings.json` の最小例は次の通り。個人名、home、driveを埋め込まず、設定ファイルからworkspace、workspaceから保存先・参照先を相対指定する。

```json
{
  "schema_version": "nps-workspace-settings/v1",
  "workspace_root": "..",
  "storage": {
    "drafts": "content/drafts",
    "sources": "content/sources",
    "feedback": "content/feedback",
    "assets": "content/assets",
    "ledgers": "data"
  },
  "style": {
    "default_profile": "references/author-style.md",
    "article_profiles": {"first-note": ["references/author-style.md"]}
  }
}
```

package rootから次を実行する。Windowsは `python -X utf8`、macOS等で必要なら `python3` を使う。JSONは復号してから本文・pathとして扱う。

```text
python scripts/note_feedback.py --settings ../my-note-workspace/config/nps-settings.json --article-id first-note --readback --history-only
```

snapshotの `archive_path` は採用workspace相対です。任意の台帳階層では `sync_note_public_snapshot.py --workspace-root WORKSPACE_ROOT` を渡し、台帳の階層からworkspaceを推測しません。旧 `data/published_notes.json` の省略時互換だけを保持します。

storageには任意の `assets` / `ledgers` ディレクトリも宣言でき、同じworkspace基準・package外境界で解決します。未採用なら実画像や台帳の保存前に選び、package内へfallbackしません。

出力の `storage.drafts` / `storage.sources` / `storage.feedback` は既存readerが解決した実行ホスト上の保存先です。実記事ではこの値を使い、固定の `content/drafts` へ戻しません。保存時もsettings hashを通常QAへ結び付けます。workspaceを変更した場合は、同じinstallerへ新しいworkspaceを渡してpointerを再登録します。

これは読取り専用で、settingsのschema、保存先のpackage外境界、参照の実体・非空・hashを既存readerで検査する。最小例の `status: not_required` は履歴強制policyが未採用という意味で、本文・画像・公開の全ゲート合格ではない。履歴必須なら既存authorship証拠も渡して回収する。missing fileや不正な参照は失敗のまま修正箇所を案内する。一般利用者の設定を特定著者のpolicyへ差し替えない。

初回の検査後も、記事制作では設定の現在版と参照本文を読み、後続の通常QA・workflowを通す。ここで設定を検査したことを、次の記事の本人採用やNote公開の許可へ流用しない。

## 利用者が選ぶ設定正本と毎回の読戻し

NPSは保存先の指定と読戻し検査を提供する。個人の口調・記事別の採用履歴をNPS package内で学習・保管しない。設定ファイル、原資料、原稿、feedback、文体参照はpackage外の利用者所有の場所へ置く。`.local`という名前を必須または共通の正本として扱わない。

呼出しruntimeは、利用者が採用した設定パスを `--settings PATH` で独立供給する。packet内の設定パス指定は拒否する。設定schemaは `nps-workspace-settings/v1`、`workspace_root`、`storage` の `drafts` / `sources` / `feedback`（任意で `assets` / `ledgers`）、`style.default_profile`、`style.article_profiles`（記事IDから参照パス配列、または `references` 配列を持つobject）を持つ。workspace_rootの相対指定は設定ファイルの親を基準に解決し、各保存先と参照先は解決後のworkspace_rootを基準に解決する。絶対パスも利用できる。設定の保存先を決めることと、Git管理・GitHubへの配送・Obsidianからの参照を有効化することは別の採用事項である。

各段階のchecker呼出しで設定と選択した文体参照のbytesを読み直す。packetの `ssot_readback: {settings_sha256, reference_hashes}` は独立取得した値と完全一致を必要とする。参照hashのキーは解決後の絶対パス。設定・参照hashは全段階の承認対象にも含め、参照が変わった後に古い承認を再利用できない。欠落・空参照・設定不正・指定外の原資料や草稿は停止する。

これはファイル取得と版一致の保証であり、AIが文体の意味を理解して本文へ適切に反映した証明ではない。runtimeは起稿・修正前に参照内容を読んで用い、本人原文・採用済み差分との比較を人間レビューへ提示する。現在の本人判断と原文・採用した直しを優先し、共通口調はAIの既定参照にする。一つの記事の直しを自動で全記事の口調へ昇格させない。画像枚数・間隔・カード・フッターの採否も記事ごとに確認する。

既存記事の制作開始時は `note_feedback.py --readback --settings PATH --article-id ID --source SOURCE --draft CURRENT_DRAFT` を使い、解決した文体参照の本文、現在の記事別採否履歴、実差分を読取り専用で受け取る。既存のsettingsとfeedback検査を再利用し、参照の欠落・版の不一致は停止する。標準出力はコンソールの文字コードに依存しないJSONで返す。json.loadsやConvertFrom-Json等で復号して参照本文を読み、Unicode escapeの表記を原文へ混ぜない。この出力は人間の採用や意味理解の証明ではない。runtimeは本文案を書く前に内容を読み、今回適用・保全・保留した具体的な直しを返却物に示す。本人の体験・感情・判断などを必須スロットとして埋める契約は追加しない。新規記事で未作成の履歴を捏造せず、本人原文と文体参照の保全・読取りから開始する。

設定ファイルの所在は利用者workspaceの配置規約で決める。NPSは `.local/nps` を新規作成する既定を持たない。Git管理する設定正本と、Git外に置く個人運用記録を分ける。公開後台帳の保存先は、既存の外部台帳先か任意の `storage.ledgers` で一度採用し、既存CLIの `--ledger-dir` または両台帳pathへ同じ値を明示する。設定へ台帳の内容・配信処理・公開権限を格納せず、保存先の採用を公開承認へ昇格しない。利用者固有の絶対パスをpackageの共通設定へ埋め込まない。


## 構成要素の個別採否と実画面照合

既存の `packet.layout` に次を必須とする。画像専用の段階や別台帳を増やさない。

- `toc`、`footer_cards`、`illustrations`、`embeds`: それぞれ `decision: "include"`（採用）または `"omit"`（非採用）と、空でない `reason` を持つ。
- `footer_cards.urls`: 採用なら重複のない `http(s)` のURLを1件以上、非採用なら `[]` を指定する。
- `illustrations.items`: 採用なら1件以上、非採用なら `[]` を指定する。各項目に空でない `purpose`（目的）、`placement`（位置）、`source_ref`（画像・候補の参照）を持つ。
- `embeds.items`: 採用なら1件以上、非採用なら `[]` を指定する。各項目に空でない `purpose`、`placement`、`url` を持つ。URLはホストがある `http` または `https` とし、認証情報、空白・制御文字、不正なポートを含めない。
- `review.proposal_ref`、`review.discussion_ref`、`review.decision_ref`: 具体案、壁打ち、本人の採否へ到達できる空でない証拠参照を持つ。`pending`、`unknown`、`todo`、`tbd`、`none`、`null`、`n/a`、未確認・未定・保留・確認待ち・未決定・未承認・検討中の仮値は認めない。

タイトル画も具体案と理由を提示して壁打ちし、採用／非採用を本人に確認する。タイトル画の設定と権利は既存の `settings` で扱い、本文の挿絵と混同しない。未言及・無回答・候補なしは未確認であり、非採用へ変換しない。

`layout` 承認は原文の保存版、現稿、構成案と証拠参照、名義、外部設定と参照版に固定する。設定・公開ゲートは独立した `layout` 承認を必須とする。目次、カードURL、挿絵、埋め込みの追加を含む編集操作にも同じ承認が必要で、操作計画の採否と採用内容を照合する。本文の誤字だけの編集は構成決定前にも進められる。

保存後はプレビューまたは実画面で採用した要素の表示と位置、非採用要素が意図せず残っていないことを読戻す。JSONの整合性だけで実際の壁打ち、本人承認の真正性、表示の受入れを証明しない。構成の制作・表示確認と末尾リンクの詳細は [原稿の正本と構成の契約](note-draft-authority-and-layout-contract.md) を参照する。

## 記事別フィードバックの毎回の照合

`storage.feedback/<article_id>/feedback.json` と `note-vs-local-diff.md` を設定から独立に解決し、原資料・以前の原稿・現稿の保存snapshotと実差分を検査する。packetに任意の履歴pathを指定する経路は設けない。`feedback_readback` は現在のrecord/diff/snapshot hashと一致必須。すべてのstageの承認対象に含み、採否履歴変更時も旧承認は失効する。新しい本人追記がある場合、前の履歴をhistoryへ保持して原資料・現稿・差分・採否を更新し、新版に対して承認を取り直す。

採用履歴が過去の会話に由来すること自体は正常。履歴の由来会話を記録しつつ、今回の各stage承認は今回のconversation_idとの一致を必要とする。読戻し検査は保存・版一致の証明であり、適切な著者性の反映は本人レビューで確かめる。

実画面の採否照合は呼出し側runtimeが担当する。この候補の `note_editor_prepublish_verify.py` は供給snapshotの既存検査とタグ事前照合を提供する。汎用Browserの操作経路へ承認照合を強制したとは扱わない。

## 利用者設定で必須化する調査品質

外部workspace settingsの `research_quality_policy` で有効にする。未指定の利用者は従来のMarkdown調査報告を継続できる。指定する場合は次の形を使い、無効にする時も `required: false` を明示する。日数は利用者が採用する1〜365の整数で、下の7日・30日は設定例である。

```json
{
  "research_quality_policy": {
    "schema_version": "nps-research-quality-policy/v1",
    "required": true,
    "max_age_days": {"dynamic": 7, "official": 30, "creator": 30}
  }
}
```

設定の読戻し結果にもpolicyが含まれる。`ssot_readback` は `read_workspace_settings` の現在の返却値と一致させる。packetからpolicyを上書きしない。

有効時は、既存 `research_report` を `note-research-quality/v1` のJSONにする。新しい承認段階は増やさない。researchとpublishで毎回保存資料を読み直し、観測日時と現在時刻の差をPython標準のdatetimeで検査する。観測にはtimezoneが必要で、未来・期限超過・欠落・不正なJSON・重複キーは停止する。記事本文、外部設定、調査報告、資料、feedbackの変更は現在版の承認照合に反映される。時間経過による鮮度切れは承認済みでも停止する。

構造の例は `data/note_research_quality.example.json`。これは架空のテスト資料で、現在の調査結果ではない。実運用では記事ID、主題、実際に確認した出典・保存資料・観測日時・採否案を置き換え、本人が確認する。例のfeedback参照先も自動作成されない。

| 項目 | 必須内容 |
|---|---|
| report | `schema_version`、`article_id`、`topic`、`sources`、`areas`、`pdca_loops` |
| source | 一意な `id`、`kind`（`official` / `dynamic` / `creator`）、再訪できる `url`、`observed_at`、`evidence_path`、`evidence_sha256`、本文を照合した `readback` |
| 再利用 | `reuse` はnull、または今回と同じ `topic`、`unchanged: true`、`reason`。再利用でも鮮度検査を省略しない |
| 領域 | `seo` / `aio` / `note` / `tags` / `pdca` / `creator_trends` の6件。各 `status` は `pass` または `not_applicable`、`reason`、`decision`、`source_ids`、`unresolved: []` |
| 適用外 | 理由と採否案を明示し、資料IDは空配列にできる。未取得の必須資料を適用外へ読み替えない |
| 保存資料 | `evidence_path` はreport所在からの相対パス、または絶対パス。実ファイルの非空とSHA-256を照合する |

領域ごとの読み合わせでは、次を確認する。機械検査は保存資料と構造の整合性だけを検査し、内容の正しさ、実際の閲覧、検索順位、AIによる引用、収益を保証しない。出典の分類と本文の意味は人間レビューの対象である。

- SEO: 主題の分かる題名・要点・見出し、独自の考え、出典、過度な断定。
- AIO: 用語、主張、事実と意見の区別、根拠。専用ファイルやschemaの追加は必須にしない。
- Note: 扉絵、目次、読みやすさ、タグ、マガジン、企画条件、下書き保存状態。選択しただけの公開フォームを保存済みと扱わない。期限のある募集は期限・参加条件を毎回確認する。
- タグ: 候補と選択済み、キーワードとハッシュタグページ、表示記事数と検索需要を区別する。規模の分類は今回のテーマ内の相対比較にする。動的な表示の観測は `dynamic` を使う。
- PDCA: 変更、測定対象、時期、担当、未取得、制約。未取得を数値0で埋めない。
- 書き手・トレンド: 利用者側の既存リストから関連する記事の構成・題名・導入・タグ・締め方を読む。書き手の記事は `creator`、動的なトレンドは `dynamic` とし、今回のテーマへの採否案を返す。リストをNPSへ複製しない。

### 5段階の振り返りと既存feedback

`pdca_loops` は次の5件を一度ずつ持つ。各件に `scope`、`owner`、`change`、`measure`、`when`、`status`、`missing_data`（配列）、`constraints`（配列）、`feedback_entry_ref` を記録する。

| scope | 段階と記録先 |
|---|---|
| `article_local` | 今回の記事の修正。記事別feedbackで採否を残す |
| `immediate_publication` | 公開直後の表示・設定・保存状態。実際の公開後に観測する |
| `article_outcomes` | 記事単位の成果。測定可能な数値と未取得を区別する |
| `topic_portfolio` | 同テーマの複数記事。既存の利用者側集計へ戻す担当を置く |
| `strategy` | 運用戦略。利用者側の知見・施策の正本へ採否を戻す担当を置く |

`feedback_entry_ref` は既存 `storage.feedback/<article_id>/feedback.json` の `entries[].evidence_ref` と一致させる。既存の `note_feedback.py` で計画案と採否を記録し、そのreadbackをpacketへ反映する。計画は `status: planned` とし、将来の結果は要求しない。実測を記録する時だけ `status: observed`、`result`、確認済みの `source_id` が必要になる。計画の記録やローカル検査を、人間の採用・Note公開・将来の成果と同一視しない。定期通知や別の完了台帳は作らない。

### タイトル画を入れない判断も構成へ記録する

`layout.cover` はタイトル画の `decision: "include" | "omit"` と空でない `reason` を必須とする。`settings.cover_image` が `null` でも省略しない。採否と理由は他の構成項目と同じ `layout` 承認対象hashに含める。`settings` / `publish` では、画像pathがある場合は `include`、ない場合は `omit` と一致させる。構成検討中の `layout` 段階では画像生成前の採用案も確認できる。

## 画像参照契約

検査の正本は `scripts/image_reference_gate.py`。利用者ごとのcharacter名、path、PNG、訂正内容は外部workspaceに保持し、このpackageへコピーしない。外部settingsが `image_reference_policy` と `image_reference_receipt` を宣言する（両pathは `workspace_root` 相対、絶対pathも可）。policyのない利用者は既存経路を維持する。宣言済みpolicyを外した検査を同じ記事の完了証拠へ流用しない。

policyは `schema: image-reference-policy/v1`、`required_character_id`、`reference_manifest`（policy親相対）、空でない `required_roles` を持つ。manifestは既存 `files: [{path, sha256, state}]` を使う（pathはmanifest親相対）。`state` は取得状態であり採用証拠ではない。

生成receiptは `schema: image-reference-receipt/v1`、`character_id`、`policy_sha256`、`reference_manifest_sha256`、`references: [{path, sha256, role}]`、`referenced_image_paths`、完全な `prompt` とUTF-8の `prompt_sha256` を持つ。receiptのpathはreceipt親相対。`pre_generation` では添付予定の実体と必要役割を検査し、生成直後に実呼出の添付pathへ照合する。

`image-reference-policy/v1` の候補数は既定3とする。既存のpolicyで `draft_candidate_count` が未指定でも検査を省略しない。明示する場合も整数3だけを受け入れる。移行時はpolicyを複製せず既存receiptへ、生成前なら `planned_candidate_count: 3`、生成後なら `draft_candidates` 3件（それぞれ `path` / 実ファイルの `sha256` / 異なる具体的な `composition`）を追記し、選択outputを候補の一つへ結び付ける。過去の単一画像receiptを自動補完したり、候補を生成済みと推測したりしない。

3枚の生成前に本人が途中採用する場合は、実際の本人判断がある時だけ `early_selection` に `article_id`、選択画像の `output_sha256`、`actor: "user"`、`status: "approved"`、`reason`、`evidence_ref`、timezone付き `observed_at` を記録する。記事と実画像hashを一致させる。今回の例外を以後の一般的な1枚運用へ転用しない。

生成後の `qa/image_edit/pre_save/publish` は `output: {path, sha256}` と `visual_qa: {output_sha256, status: pass, reviewer, observations: [{criterion, observation, reference_path}]}` を必須とする。観察は必要役割すべての参照を比較し、checkboxだけでは通らない。実upload候補はCLI `--output` で同一path/hashへ束縛する。policy有効の `image_edit/pre_save` では実操作対象の `--output` を必須とし、省略はblocked。通常QAはreceipt内outputの検査だけでもよい。

生成前CLI、原稿QA、既存workflow gate、editor保存前PDCAは同じvalidatorを呼ぶ。workflow承認subjectへ画像証拠hashを追加する。editor操作や保存ボタンはこのpackageが自動実行しないため、実操作前には上のCLIを実行する。検査結果はfile整合と記録の束縛だけを保証し、実際のモデルの注意・視認・本人採用・承認の真正性・Note uploadの一致を単独では証明しない。

画像設定を記事ごとに適用する場合は、既存 `style.article_profiles[article_id]` を `{references: [...], image_reference_policy: ..., image_reference_receipt: ...}` のobjectへ拡張する。既存の参照配列形は互換を保つ。同じ記事キーで文体と画像を解決し、新しいprofile台帳は作らない。CLI／editor PDCAには `--article-id CURRENT_ARTICLE_ID` を渡す。生成前は `python scripts/image_reference_gate.py --settings USER_SETTINGS_PATH --article-id CURRENT_ARTICLE_ID --stage pre_generation`、原稿QAは `python scripts/pre_publish_check.py <draft.md> --settings USER_SETTINGS_PATH --article-id CURRENT_ARTICLE_ID`、保存前の既存PDCA検査は `python scripts/note_editor_pdca_cycle_check.py <receipt.json> --settings USER_SETTINGS_PATH --article-id CURRENT_ARTICLE_ID --output ACTUAL_IMAGE_PATH` とする。画像profileが存在するsettingsでarticle_idを省略するとblocked。対象記事に画像設定がない場合はglobal画像defaultを使い、defaultもなければ従来互換。別記事の画像receiptを流用しない。


## タグ設計と実選択の設定・公開ゲート

既存の `settings` / `publish` は、既存の確認記録の `tag_design` を必須とする。`edit` / `layout` / `research` には適用しない。設計のtag順序と `settings.tags` は、先頭の `#`・外側空白・大文字小文字を正規化して一致させる。設計を変更するとsettings / publishの承認対象hashも変わる。

```json
{
  "tag_design": {
    "schema": "note-tag-design/v1",
    "article_id": "fixture-article",
    "body_sha256": "現在本文のSHA-256",
    "policy": {"id": "nps-local-tags/v1", "min_tags": 5, "max_tags": 10},
    "strategy": {
      "content": {"reason": "本文で実際に扱う研究と技術に合わせる", "evidence_ref": "draft.md#main"},
      "discovery": {"reason": "検索意図と関連記事の文脈を照合して入口を選ぶ", "evidence_ref": "research.md#tag-comparison"},
      "branding": {"reason": "採用済み連載名を固定の入口として維持する", "evidence_ref": "production-pack.md#series"}
    },
    "tags": [
      {"tag": "AI", "role": "topic", "reason": "本文の主題", "evidence_ref": "draft.md#main"},
      {"tag": "研究", "role": "topic", "reason": "研究の話題", "evidence_ref": "draft.md#research"},
      {"tag": "ニュース", "role": "context", "reason": "今回の文脈", "evidence_ref": "draft.md#intro"},
      {"tag": "技術", "role": "context", "reason": "利用する技術", "evidence_ref": "draft.md#tools"},
      {"tag": "観測連載", "role": "series", "reason": "連載・固有の入口", "evidence_ref": "production-pack.md#series"}
    ],
    "previous_article": {
      "article_id": "previous-article", "reference": "previous.md#tags",
      "tags": ["AI"], "comparison": "前話の主題を維持し今回の文脈を追加する"
    }
  }
}
```

タグの戦略は `tag_design.strategy` に `content`（内容）、`discovery`（発見される入口）、`branding`（著者・連載の固有性）の3観点を持たせ、各観点に空でない `reason` と `evidence_ref` を残す。一般向けパッケージへ固定のブランドタグを埋め込まない。意味の妥当性と本人の採否は人間レビューで確認する。

### 利用者のマーケティング正本をタグ選定へ必須接続する

外部workspace settingsに `tag_reference_policy` を採用すると、既存のsettings / publishと、外部settings付きの通常editor検査が同じタグvalidatorを使う。記事別profileへ毎回参照を足すだけの運用にはしない。

```json
{
  "tag_reference_policy": {
    "schema": "nps-tag-reference-policy/v1",
    "required": true,
    "strategy_sources": {
      "content": ["strategy/tag-playbook.md"],
      "discovery": ["strategy/search-guidance.md"],
      "branding": ["strategy/brand-terms.md"]
    }
  }
}
```

パスはworkspace root相対または絶対パス。readback時に全記事の参照へ加え、実ファイルの非空・現在SHA-256を検査する。固有のrepo名、ブランド、利用者のprivate pathをNPSへ埋め込まない。未採用の利用者は従来の経路を維持する。

有効時は `tag_design.reference_readback` に、解決済み絶対パスからSHA-256への辞書を保存し、policy内の全資料の現在値と一致させる。各strategyの `evidence_ref` は当該観点で採用された資料の絶対パスを指す。節や行の説明はreasonへ置く。`tag_design.search_intents` に今回の読者が検索しそうな語句を重複なく2〜3件記録する。資料欠落・読戻し欠落・古いhash・採用外参照・検索語不足は通さない。資料が変われば既存の設定・参照hashと承認対象も変わる。

この検査は参照と版の整合性を扱う。実際に読んだこと、内容を理解したこと、検索需要、順位や流入効果、人間承認の真正性は自動認定しない。検索量を未測定のまま需要の大小を断定せず、意味の適合は記事と読者に照らしてレビューする。直接のGUI操作を全経路で遮断するhookではない。

候補生成は利用側の採用済みマーケティング正本を起点とする。主題語だけで完了せず、著者の固定指定、記事ごとのブランド・連載・共同体候補、過去記事の採用タグ、今回の本人追加・除外を比較する。既存の候補生成器があれば利用し、その固有辞書・閾値・ブランド戦略は利用側に保持する。NPSに第二の辞書や推薦エンジンを作らず、結果の根拠と採否を既存 `tag_design` へ接続する。表示件数の大・中・小を示す場合は採用元の分類基準、観測日時、対象名義と有効期限を確認し、欠測・古い観測は不明とする。件数から検索需要や効果を保証しない。

これは架空の構造例で、本文hash・選定理由・参照・前話比較は実際の記録に置き換える。各tagに `reason` / `evidence_ref` が必要で、`topic`（主題）、`context`（文脈）、`series`（連載または記事・著者の固有タグ）の3役割を含める。意味の妥当性や著者採用を自動分類・認定しない。5〜10は既存制作手順のlocal policyであり、Noteのプラットフォーム上限や公式推奨ではない。policyの省略・任意のmin/maxへの差替えは拒否する。

`body_sha256` は `pre_publish_check.split_frontmatter(draft_text)[1].encode('utf-8')` のSHA-256とする。front matterだけを除いた本文で、返された先頭改行や末尾をtrimせずそのままhashする。front matterなしのHTMLを対象にした場合はその全文になる。原稿ファイル全体のhashと混同しない。

前話がない記事は `previous_article: {"status": "none", "reason": "初回記事の理由", "reference": "production-pack.md#first"}` で明示する。`continuation_article` はこの省略経路を使えず、前話のID・参照・タグ・比較が必要。原稿front matterの続き記事指定をpacket側で初回扱いへ上書きしない。

設定段階は未選択の提案を確認できる。タグ操作前は既存 `tag_preflight` のbaseline/currentを読み戻し、候補欄と選択済み欄を区別する。`publish` では同じ既存preflightを必須とし、対象記事・名義・選択領域確認・baseline/current一致を検査した上で、**current.selected_tags** が `settings.tags` / 設計と一致する必要がある。suggested_tagsやplanned_additionsを実選択へ昇格させない。操作後には、その時点で人間が確認したbaselineとcurrentを新しく取得する。

供給snapshotのeditor検査も、`stage: "settings" | "publish"` と `tag_design` / `draft_text` を渡して同じvalidatorを使う。publishは `note_id` / `account` / `tag_preflight` の実選択を照合する。旧fixtureなどstageを宣言しない一般観測は従来の重複検査を維持するが、workflow publish必須検査の代わりにはならない。footer-onlyの検査成功もタグ・公開ゲートの成功ではない。JSONは記録の整合性だけを検査し、実DOM操作・選定の正しさ・本人承認の真正性を保証しない。


## 過去修正の回収と現稿への適用を分ける

利用者が既存外部settingsの `style.history_learning_policy` に `{"schema":"nps-history-learning-policy/v1","required":true}` を宣言した記事へ適用する。未指定または明示falseの一般利用者は従来互換を保つ。許可資料は既存 `style.default_profile` / `article_profiles.references` から解決し、履歴の並行コピー・新しい採否台帳・自動分類器を増やさない。

必須policyの記事IDは空でない `article_profiles` を明示する。未知IDをdefault参照だけへfallbackさせない。任意の `required_sources` 配列は、必須候補の `id` / `path` / `quote` / `evidence_ref`（JSON引用では任意の `json_pointer`）を宣言する。pathは他の設定参照と同じworkspace相対または絶対で指定でき、解決先がstyle許可参照にない場合は停止する。同じIDの別引用、根拠refの差替え、必須候補欠落はG1/G2の同じ読取りで拒否する。実hashはsidecarと許可資料の実体を照合する。個人の採用則・私的資料をpackageへ複製しない。

記事限定の採用則は既存 `style.article_profiles[article_id]` のobject形へ、`references` と並べて `history_learning_policy` を置く。同じ `nps-history-learning-policy/v1` を使い、有効なpolicyは全体policyと選択記事policyの `required` をOR、`required_sources` を結合して求める。記事側のfalseで全体必須を弱めない。同じIDは同じ引用でも重複として停止し、曖昧な上書きをしない。記事別sourceは選択記事の `references` に含め、default参照だけでは許可しない。配列形の既存profileは互換を保ち、他の記事へ記事限定の採用則を伝播しない。記事限定の必須policyが設定されている場合、ID省略で任意policyへfallbackしない。

保存した本人訂正を自動で全て必須則へ昇格させない。今回だけの採用か、今後も保持する則かは本人の判断を既存の根拠へ残す。必須化した則はsidecarのsourceとfeedbackの `history_source_id`・`application_status`・今版hashへ接続して初めてG2の適用検査へ入る。`origin: author` や `decision: adopted` の保存だけで次稿の強制検査が増えたとは扱わない。

画面コメントや口述による具体的な直しは、対象引用・修正前・本人指示・採用後・適用範囲を利用側の既存feedbackと原資料で辿れるようにする。AIが整理した理由や操作は本人の言葉・本人の直接入力と区別する。新しい学習台帳を増やさず、初稿を書く前に該当する訂正を読み、既存の制作メモと履歴適用行へ対応付ける。提示前に実際の本文で確かめ、保存・読戻しだけで再発防止が運用されたとは報告しない。記事固有の採用を著者一般の癖や性格へ拡張しない。

外部アダプターは `note_authorship_gate.check_history_learning_from_settings(draft, settings, article_id, evidence=None)`、または隔離processの `python scripts/note_authorship_gate.py DRAFT --history-only --settings SETTINGS --article-id ID --evidence SIDECAR --json` を使う。CLIは `mechanical_ok` だけをexit 0とし、無設定・not_requiredは必須段階の通過にならない。本文用と告知用は明示した別対象IDで既存feedbackを使い、別対象のsnapshotを本文適用へ読み替えない。

G2が確認するのは引用・hash・対象本文・afterの実在と申告の対応であり、文体の意味や適用理由の正しさではない。全件not_applicableの申告も意味の正当性を自動保証しない。本人の採否は既存の判断正本とtrusted runtimeが保持する。

### 制作前の履歴回収

既存 `<draft>.authorship.json` の `history_learning.sources` に、許可された過去稿・本人修正・feedback履歴から抽出した**候補**を置く。

```json
{
  "schema_version": "note-authorship-evidence/v1",
  "draft_sha256": "新稿保存後に現在ファイルのSHA-256を記録する",
  "claims": [],
  "history_learning": {"sources": [
    {"id":"author-voice-1", "path":"../references/author-voice-profile.md",
     "sha256":"参照ファイルのSHA-256", "quote":"保存原文の短い引用",
     "evidence_ref":"過去の本人指摘の位置"}
  ]}
}
```

架空の構造例。実際の原文・hash・参照へ置き換え、公開packageに利用者の素材や絶対pathを含めない。JSON履歴の改行などを含む引用は、任意の補完でなく `json_pointer: "/entries/0/after"` の明示位置から読む。引用を既存資料の実文字列と照合する。AIが抽出した文体制約を本人採用のラベルへ昇格させない。

新稿がまだない段階は、以下の既存readbackの履歴専用入口を使う。`--source` / `--draft` / 書込み引数は併用しない。

```sh
python scripts/note_feedback.py --readback --history-only --settings USER_SETTINGS_PATH --article-id ARTICLE_ID --history-evidence EXISTING_AUTHORSHIP_EVIDENCE
```

許可path・ファイルhash・原文引用・根拠refを実読取りし、`candidate_sources_verified` を返す。この段階は新稿のhash、意味理解、本人採用、公開許可を発行しない。旧latest feedbackだけを読んだことやhashだけの取得を、過去修正の回収済みへ置換しない。資料の範囲は既存参照に明示し、全過去履歴の網羅性を宣言しない。

### 現稿へ適用したことの検査

既存 `feedback.entries` の `origin` / `decision` / `before` / `after` / `reason` / `evidence_ref` を保持し、履歴の適用行へ次を付ける。

```json
{
  "origin":"ai", "decision":"pending",
  "before":"直す前の文", "after":"現在本文にある修正後の文",
  "reason":"本人の原文へ戻す", "evidence_ref":"source候補と同じ根拠ref",
  "history_source_id":"author-voice-1", "application_status":"applied",
  "target_sha256":"適用対象ファイル全体のSHA-256",
  "target_excerpt_id":"note_authorship_gate.excerpt_id(after)"
}
```

`applied` はafterの実本文中での存在とexcerpt ID、`preserved` はbefore=afterと実本文中の存在を照合する。`not_applicable` はbefore/afterを空にし、非該当理由・現在のtarget hashを残す（excerpt IDは不要）。source候補の全IDをいずれかの状態へ対応させる。これは保存物と現版の機械的一致であり、適用の意味・本人採用・全authorship検査の合格ではない。未発言の作文は既存の原文照合と本人レビューへ残す。

QA／workflowは既存feedbackのsnapshot・差分検査を先に通し、`evaluate_history_learning` でstyle許可資料・適用行・authorship側の `draft_sha256`・現在本文を結び付ける。直接APIへ渡すfeedback recordも `read_feedback_record` で検証する。本文・資料・適用理由が変われば旧承認を失効させる。front matterにだけafterがある場合は本文への適用と数えない。

workflowのeditは `proposed_draft`、それ以外は現在 `draft` を対象にする。`proposed_draft` がJSON局所planなら、既存 `edit_plan.history_application_target` にレビューする全文pathを明示する。指定drafts保存先へ限定し、その全文hashも承認対象へ含める。JSONplan中のafter文字列を現本文への適用証拠にしない。任意planから全文を自動復元したとは言わず、planと全文の意味の対応はレビューする。

`pre_publish_check` はポリシー有効時にproduction／continuationを含む現稿へ同じ適用検査を行う。workflowは既存packetの `history_evidence`、または対象本文の既存authorship sidecarを読む。調査品質を併用する場合は `article_local` の結果を実適用の `observed` とfeedback refへ結び付ける。公開直後・成果・戦略など将来の測定はplannedのままにし、予測を実測へ変えない。

Discordの最新公開・本人原文が今回の制作の主資料である。過去稿は文体と失敗予防の制約として使い、古い外部事実やAI案で最新原稿を置換しない。新しいgateの作業用checkout検査と、installed primaryへの採用・実運用は別の状態として記録する。

### 画像gateの版・記事・操作対象

記事profileに画像policyを宣言した場合、生成receiptの `article_id` は選択した記事IDと一致必須。global policyの一般利用者と区別する。実cover pathがない本文／設定の編集は記録済みoutputへのQAを使い、画像の操作stageへ誤分類しない。実画像の反映とpre_saveは引き続き実対象のoutput指定を必須とする。

policy・manifest・receipt・参照画像・outputのhashは、検証で読んだ同じbytesから計算する。返却前に入力bytesの変更を再確認し、改変・差替えをblockedにする。実際の操作までの原子的なロックや、視認・承認の真正性を保証したとは言わない。


### 公開前観測の未公開状態

公開前のoperation計画は空配列、または既知の正式名の配列だけを認める。読取り・設定確認の既存名は`read_only`、`read-only`、`open_settings`、`settings-open`、`open_publish_settings`、`open_publication_settings`、`read_publication_settings`、`inspect_publish_settings`、`公開設定を開く`、`公開設定を確認`。下書きの編集・保存は既存capability inventoryの`write_draft`・`save_draft`を使う。前後空白と大文字小文字以外を自動翻訳・分類しない。`post`・`repost`・`crosspost`・`schedule`等の公開操作に限らず、未知の操作名・型不正も停止する。名前が許可されても実操作の権限、保存後読戻し、本人の公開許可を与えたことにはならない。

`production_candidate`・`continuation_article`の公開前観測では、`publication_state`または`status`に、確認した`draft`を明示する。現在の安全状態の列挙は`draft`だけで、前後空白・大文字小文字を除いた同値を認める。他の文字列・型不正・両項目の欠落を、未公開状態と推測しない。両項目を供給する場合は双方を独立に検査し、一方の`draft`で他方の公開済み・予約済み・未知状態を隠さない。

`draft_saved=true`は保存確認であり、未公開の証拠ではない。実画面またはAPIの読戻しで公開状態を確認できなければ、公開前の`ok`へ昇格させない。公開済み記事の読取りやfooter-onlyの供給snapshot検査は別用途として保持し、公開前検査の代用にしない。`ready_for_publish=false`と、供給snapshotのみの検査範囲を維持する。


### 移植できる履歴参照

共有するsettingsのpathは既存どおりworkspace_root基準、history evidenceのsources[].pathは証拠JSONのあるフォルダー基準の相対pathで保存する。区切りは `/` とし、ユーザーhomeやdrive文字を埋め込まない。実行時だけnativeの絶対pathへ解決し、必須契約の参照先・許可参照・実hash・初回のpath/bytesを同じ検査で照合する。quote/id/evidence_refの一致は維持する。実測receiptの解決済みpathはその実行ホストに属し、別ホストでは再生成する。過去の絶対path入力も同じ許可参照検査を経る。

## インストール済みpointerの可搬表記

`skill_pointer_check.py` は絶対pathに加え、先頭の `$HOME/`・`${HOME}/`・`~/` を現在のhomeへ限定解決する。shellのeval、コマンド置換、任意の環境変数展開は行わない。未対応の表記、欠落先、別packageへの参照、symlinkの既存停止条件を維持する。可搬表記の途中から `/Projects/...` 等を切り出して絶対pathと誤認しない。

### 採用済みの本人語彙を提示前に検査する

既存history policyの任意 `vocabulary_rules` に `id`・`avoid`・`preferred`・`excluded_compounds`（文字列配列）を指定できる。語句は利用者の外部settingsに置く。全体と選択記事の規則を結合し、重複ID、不正な型、空語句、avoidそのものや無関係な除外語を拒否する。`required: false` でも語彙検査を省略しない。既存G2共通入口は `vocabulary_check` の実本文hashと検査結果を返す。

本文・見出し・リンクの表示文字を検査し、frontmatter、閉じたコード範囲、リンク宛先は対象外。HTMLの可視文字・実体参照も照合し、タグで語を分断して回避しない。一般の本文にavoidがあればAI本人語りか判定せず、`context_review_required` として提示を止める。自動置換はしない。引用記号、blockquote、参考見出しだけで本人原文や資料名を認定しない。

例外は既存sidecarの `history_learning.vocabulary_exceptions` を使い、`kind`（`quotation` / `source_title` / `preserved_original`）、`source_id`、`target_sha256`、`target_excerpt`、`target_excerpt_sha256`、`line`、`start` を指定する。lineは元Markdownの1始まり行番号、startはその行を可視文字化した後の0始まり位置。excerptとhashはその可視文字の完全一致範囲を指定する。sourceは同じsidecarの既存sourceで、G1の許可参照・実hash・保存quoteを同じ入力captureで検査する。保存quoteの可視文字とexcerptが一致する指定範囲だけを除外し、同じ段落の追加AI proseや別の出現へ適用しない。本文版・source版・位置・引用が変わった例外は拒否する。

例外指定は意味や本人採否の認証ではない。根拠のある引用範囲の束縛に限る。曖昧なMarkdown、複数行にまたがる例外、未対応の書式では停止して文脈確認する。全自然言語の同義語や全Markdown rendererの意味を判定する保証はない。`not_applicable` のhistory申告で語彙検査を無効化できない。


## 任意の既存記事更新許可と公開後点検

利用者の外部settings `publication_policy.existing_article_update` は明示採用・hash一致する許可記録を必要とする。`note_update_authorization.py`とworkflow publish検査は既存公開記事の更新だけを対象にし、実draftと設定のhash、対象ID、保存後一致の検査を照合する。新規公開・予約変更・SNS共有は対象外。既定は人間による公開確認を維持する。JSONは承認や実行の真正性を証明せず、trusted runtimeが現在の依頼と実状態を照合する。

公開後点検では利用側の内部 `article_id` と公開note IDを分ける。closed/accepted packetがpostpublicationを必須にした場合は、対象全件の点検完了と既存計測への登録receiptを照合し、不正・不足したJSONは停止する。新しい定期処理を作る機能ではない。


任意policyでも現在会話の本人依頼を必須にする。既存receipt列に `stage: update_request`、本人actor/approved、現在conversation_id、publishと同じsubject_sha256、operation=update_existing、対象note_idを持たせ、evidence_refをupdate_observation.edit_request_refと一致させる。現在の依頼を過去の許可だけで代替せず、追加の最終質問だけを省略する。

## 壁打ち全体と本文の忠実性

### 執筆内容を整理する骨組み

全文の発言索引は資料であり、その生成を骨組みの完成とはしない。壁打ちの記事化では、`references/note-provenance-review.md` の `skeleton_mode: writing-plan` を使い、各節の執筆内容を本人の考え・同意した返答・説明する事実・未解決の疑問に分け、根拠原文へ結び付ける。研究を依頼したことと、研究から導く結論に同意したことは区別する。本文の構成や読みやすさを整える許可から、本人未発言の感想・体験・結論を補完する許可を推定しない。

本人の同意は、対象の返答と本人発言、範囲を明示する。同意の後に訂正された説明は更新し、返答全体への同意へ拡張しない。生成器とcheckerは計画の欠落や参照・表示のずれを検査し、独立レビューは意味の対応と未発言の結論を確認する。本人による骨組みの採用と、機械・独立レビューの合格を分ける。

「引用を並べただけ」「長すぎる」「AI作文」という修正を受けた場合、本文へ説明を足して整える前に、どの節の執筆内容・根拠・同意範囲が不足していたかへ戻す。字数や見出し数を一般的な正解として固定せず、今回必要な論点に絞って再提示する。


会話・口述を元にする記事では、workspace設定（または選択記事のprofile）の
`conversation_fidelity_policy` を使える。`schema` は
`note-conversation-fidelity-policy/v1`、`required` はboolean。
必須時は `source`（sources配下の全文原資料JSON）とその `sha256` を明示する。
globalの必須指定は記事profileのfalseでは解除しない。

既存 `provenance_label_check.py` の `capture_conversation` は指定会話のローカル
Codex記録からuser/assistant本文を取得する。tool出力は本文素材にしない。
元記録のprefix・会話ID・範囲を固定し、検査時に同じ原資料を再構成する。
AIが選んだ発言抜粋やAI初稿を「本人原文全体」の代用にしない。
本人発言が追記されたら旧原資料の検査を止め、最新説明まで再取得する。
assistant/toolの追記だけでは失効しない。

原資料の全user段落へ、本文反映先、省略理由、後の説明で更新した場合の参照を
付ける。質問・編集指示・本人の立場は同一視せず、複数内容の一部落ちも読む。
本文も見出し・表・出典行を含む全段落を `<draft>.fidelity.json` に対応付ける。
本人発言の引用は原資料で実在を検査し、assistant発言を本人の根拠にしない。
未採用の判断は `hold` として本文反映前に止める。

独立担当は、全原発言と全本文段落について欠落、条件・理由・強さの変化、
未発言の判断追加、正当な省略を照合する。原文の実在と、記事目的への採用は別に確認する。
後続発言による限定、論点の重みの変更、本文から見出しへの格上げも照合する。
報告はsource/draftと対応表の版へ
束縛し、執筆者の自己申告を独立レビューの代用にしない。
対応表の分類・省略理由・更新関係を変えたらレビューもやり直す。

`note_workflow_gate` はedit時のproposal、それ以外はcurrent draftを検査し、
結果hashを承認対象へ含める。`pre_publish_check` も同じ検査を使う。
外部設定で必須なら `source_mode` や `article_lane` の変更で外れない。
旧authorshipの語句検出・短縮検査だけで、この確認を済ませたと扱わない。

`mechanical_ok` は全件対応・引用・版と報告の実在確認。
`semantic_review: independent_review_recorded` は独立照合結果が記録された状態であり、
意味の完全一致、担当の真正性、人間の採用を機械だけで保証するものではない。
実担当の結果回収は呼出元が確認する。公開・外部送信の既存承認境界は維持する。


### 純進行の追記に対する任意の独立差分レビュー

既定は新しいuser発言があれば原資料を再取得し、全文レビューを更新する。
`conversation_fidelity_policy.allow_reviewed_progress_tail: true` を明示採用した場合だけ、
素材・本文・対応表・全文意味レビューを不変に保ち、`<draft>.fidelity-tail.json` へ
後続user発言の独立レビューを記録できる。キーワードから進行指示を自動認定しない。

sidecarは `schema_version: note-conversation-fidelity-tail/v1`、記事・会話の
`article_id` / `conversation_id` と次の値を持つ。

- `base_source_sha256`、`base_prefix_sha256`、`base_mapping_sha256`（既存 `fidelity_mapping_digest`）、
  `base_review_sha256`、`draft_sha256`：不変素材と既存全文レビューの版。
- `latest_source`（sidecar基準の相対pathまたは絶対path）、`latest_source_sha256`：
  同じ `capture_conversation` による最新原資料。その実ログpath・prefix・全user列を照合する。
- `reviewer_id`：空でなく執筆者と異なる独立担当。`reviewed_at`：timezone付きISO日時（未来を拒否）。
  `review_scope: all_new_user_units_and_article_constraints`：新規原文全体と記事制約を照合した宣言。
- `units`：追加された全user段落を順番どおり一度ずつ列挙する。各行は `unit_id`、
  完全な `quote`、UTF-8引用の `quote_sha256`、`classification: progress_only`、
  非空の `reason`、`unaffected: [body, adoption, conditions, strength, placement, settings, authority]`。

原文は最新captureに保持し、未反映の追記を素材から消さない。本文、採否、条件、強さ、
配置、設定、権限の付与・撤回に影響する追記、混合指示、判定不明はこの経路では通さない。
その場合は最新全文原資料・対応表・レビューへ戻る。旧素材のuser列が最新列のprefixでない場合、
最新user追記の漏れ、別ログ、本文の変更、原文改変、版の違うレビューも拒否する。
assistant/toolだけの後続追記は従来どおり許容する。

検査結果の `approval_hashes` は不変のdraft/source/mapping/reviewだけを保持する。
`hashes` は同じ値に `tail_review` / `latest_source` / `latest_prefix` の観測hashを追加する。
workflowの承認subjectは前者に束縛し、後者は返却receiptの `conversation_fidelity` に残す。
したがって純進行の差分レビューだけで本文等の承認を取り直さず、素材の変更では失効する。
feedbackのsource_snapshotは既存の不変素材のままでよい。

この検査は版・原文の実在・独立レビュー宣言の整合性を確認する。LLMの意味判定、
担当IDの真正性、日時の真正性、人間承認の真正性や公開権限を保証しない。
呼出元は独立担当の実結果を回収し、内容に影響する指示をprogress_onlyへ誤分類しない。
