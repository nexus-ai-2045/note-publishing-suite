---
name: note-publication-gate
description: "note-publishing-suiteで、Noteの公開または予約投稿の確定直前に、記事ごとの必須確認と人間の明示承認を検査する。"
---

# `note-publication-gate`

初回または採用settingsが未確認なら、親スキルの「初回利用・設定が未採用の場合」と [初回設定の案内](../../references/note-workflow-review-contract.md#初回設定の案内)を先に適用する。既存設定を再初期化せず、未確認の設定で制作・保存へ進まない。

## 役割

公開、投稿、予約確定ボタンを押す直前で停止し、現在会話の明示承認を確認する。

## 入力

- `note` アカウント。
- 対象記事の ローカル原稿のパス と `Note`の編集画面または下書きの`URL`。
- 公開方式。即時公開、予約投稿、下書き保存のみのいずれか。
- 予約投稿の場合は日時と タイムゾーン。
- `QA`、画像権利、タグ、マガジン、公開範囲、価格、`SNS` 共有設定の確認状態。
- タイトル画・挿絵、目次・見出し、埋め込み・末尾カードについての具体案、壁打ち、本人の採否、反映結果と表示の読戻し。
- 現在会話での明示承認文。

## 手順

1. 必須確認をすべて埋める。
2. 対象記事、対象操作、公開方式が現在会話で明示されているか確認する。
3. 承認が不足する場合は停止メッセージを出して停止する。
4. 承認が足りている場合だけ、ユーザーが指定した操作へ進める。

## 必須確認

- `note` アカウント、対象記事、タイトル、本文、タイトル画、画像権利。
- タグ、マガジン、公開範囲、無料/有料、価格。
- `SNS` 共有設定、外部告知設定。
- 下書き保存、プレビュー、事実確認、秘密情報除外、内部メモ除外。
- 即時公開か予約投稿か。予約なら日時と タイムゾーン。
- 公開日やテーマの助言を公式扱いする場合は、創作カレンダーなどの 出典の`URL` を確認する。固定の「おすすめ公開時刻」は公式未確認として扱う。
- 予約投稿日時が `note` 公式メンテナンス告知の停止予定期間に重なる場合は、メンテナンス後に順次投稿される可能性を確認し、ユーザーへ明示する。
- 現在の会話で対象記事と操作を特定した明示承認があるか。

## 利用側が公開前草稿を必須にした場合

必要な草稿は記事別policyで選ぶ。全記事に同じ数を要求しない。
`footer_readback_policy`を採用した記事は、保存後のreader画面の実観測と
既存`footer-selection`を`footer_readback`へ渡す。
予約確定後もcanonical記事画面で読み戻し、一般公開後は`public`面で再照合する。
生URLや予約中の本人向け表示だけで、公開後確認を完了にしない。

予約済み記事のpreviewが旧本文を表示する場合、明示した`allow_saved_editor`を使える。
保存前と保存後の再読込みでHTML hashが一致し、同じ保存済みDOMからカードの表示を取得した
`editor_saved`観測だけを公開前に受け付ける。一般公開後は引き続き`public`面で確認する。

外部settingsの`publication_drafts_policy.required: true`を採用している場合は、
既存packetの`publication_drafts_manifest`へ草稿と確認証拠の実体を結び、
`note_workflow_gate.py --stage publish`で必須スロット・現在の記事版・草稿/確認証拠のhash一致を確認する。
欠落・未確認・旧版なら、即時公開と予約確定のどちらも停止する。
媒体の種類や本文のルールは利用側が所有し、packageへ固有名や私的草稿を移さない。
未設定の利用者へ必須化せず、制作途中の段階にも先取りしない。
契約は`../../references/note-workflow-review-contract.md`の「公開前草稿の任意契約」を参照する。
草稿QAのassistant確認は許容するが、公開の本人承認や外部告知の送信許可とは別であり、実送信は行わない。

## 構成要素の確認抜けを防ぐ

`--list-gates` の `layout.review_items` と `settings.tag_review` を読み、ハイパーリンク、埋め込み、末尾カード、タグ選定を個別に棚卸しする。ハイパーリンクは `layout.hyperlinks` に表示文・URL・目的・配置を記録する。すでに挿入済みでも到達先・文脈・保存後の保持を確認し、確認済みと未確認を分ける。タグ候補数や文字リンクの存在だけで選定・埋め込みの確認を済ませない。サービス紹介は本人の実在する公開先から候補を選び、末尾カードの形式・順序は既存 `footer-selection` と実表示を照合する。

既存の5段階（`edit` / `research` / `layout` / `settings` / `publish`）を維持する。構成の提案と採否は `layout`、実際の本文・配置変更は `edit`、画像権利とタイトル画の設定は `settings` で扱う。画像専用の段階を増やさない。

公開前に、記事ごとに次の3群すべてを壁打ちで確認する。

- タイトル画・挿絵: 候補のプレビュー、用途、位置、キャプション、採用する／しない案と理由。
- 目次・見出し: 見出し構造と目次の表示・位置、採用する／しない案と理由。
- 埋め込み・末尾カード: 候補の`URL`、種類、記事との関係、配置順、採用する／しない案と理由。

各群について、具体案と理由を提示し、本人との壁打ち、本人の採用／不採用／保留の回答、承認範囲内の反映、保存後の表示読戻しを順に確認する。変更は既存の `edit` 承認を経る。採用しない場合も本人の明示判断と理由を残し、読戻しでは意図せず残っていないことを確認する。未言及・無回答・候補なしは未確認であり、不要と推定しない。保留も完了へ変換しない。

`layout` の現在版と本人回答の証拠参照を照合し、保存後のプレビューまたは実画面で、画像の有無と位置、目次・見出し、埋め込み・末尾カードの表示を読戻す。表示を確認できなければ未確認として止める。`JSON`や機械検査の成功は記録の整合性を示すだけで、実際の壁打ち、本人承認の真正性、表示の受入れを証明しない。

## 停止条件

- 対象記事、対象操作、公開方式のどれかが不明。
- `QA`、画像権利、秘密情報除外、内部メモ除外が未確認。
- 上記3群の具体提案・壁打ち・本人採否・反映結果・表示読戻しのいずれかが未確認、または現在版に対応しない。
- 現在会話で対象記事と操作を特定した明示承認がない。

## 判定

承認あり:
- 対象記事、対象操作、公開方式が現在会話で明示されている。
- `QA`、画像権利、秘密情報除外、内部メモ除外が確認済み。
- 構成要素3群の壁打ち・本人採否・反映結果・表示読戻しが現在版で確認済み。
- その場合だけ、ユーザーが指定した操作へ進める。

承認なし:
- 停止メッセージを出して停止する。
- 「公開して」「投稿して」だけでは不十分。対象記事と操作を特定してもらう。

## 停止メッセージ

```text
ここで停止します。
- Note 画面: 公開/投稿/予約確定ボタンを押す手前
- 確認済み: 実際に確認できた項目だけを記載
- 未確認: タイトル画・挿絵 / 目次・見出し / 埋め込み・末尾カードなど、未確認の項目と停止理由を記載
- 未実行: 公開 / 予約投稿 / SNS共有 / 外部告知

対象記事と操作を明示して、最終承認をもらうまで押しません。
```

## 終了時の証拠

- 確認済み項目。
- 未確認項目。
- 実行していない公開操作。
- 最終承認の有無。
- 構成要素3群の具体案、壁打ちの参照、本人の採否、反映と保存後の表示読戻しの証拠。

## 版に結び付く最終確認

`../../references/note-workflow-review-contract.md` が3経路と承認失効の正本。最終手前では `note_workflow_gate.py --settings USER_SETTINGS_PATH --packet USER_REVIEW_PACKET --conversation-id CURRENT_CONVERSATION --stage publish` を実行し、現稿・原文・調査・公開設定と、現在会話の本人承認記録（`receipt`）が一致することを確認する。毎回の調査確認・設定確認は省略しない。既存の公開前`QA`も必須。通過しても `manual_publish_required: true` / `automation_allowed: false` とし、公開・更新・予約確定の最終ボタンは人間へ渡す。

## 現在版の承認を区別する

`note_workflow_gate.py --list-gates` で対象・版・根拠・失効理由・次の操作を確認する。タイトル画・挿絵、目次・見出し、埋め込み・末尾カードの構成案と採否は `layout` に独立記録し、本文校正の承認で代用しない。外部フィードバックと文体参照を毎回読戻す。現在版で承認済みの対象を再質問せず、変更・失効した対象のみ具体案の確認カードにする。最終ボタンの人間境界を維持する。

## 任意の既存記事更新許可

既定の最終操作は人間に残す。利用者が既存記事の更新に限った継続許可を採用している場合だけ、外部settingsのpublication_policy.existing_article_updateを使う。個人・ブランドの実値はpackageへ置かない。

policyはschema=nps-existing-update-policy/v1、enabled=true、account、workspace内のapproval_refとそのapproval_sha256を持つ。本人の許可原文は利用側で保持する。publish packetにupdate_observationを付け、note_update_authorization.pyのauthorize_updateで判定する。operation=update_existing、published_before=true、account・note_id・public_url・action=更新する、new_publication/schedule_change/external_share=falseを確認する。approved_content_sha256/editor_content_sha256/saved_content_sha256の一致、baseline_settings_sha256/current_settings_sha256の一致を実観測から渡す。checksはrequested_change_only/body_and_links_verified/layout_verified/saved_and_reloaded/public_identity_verified/prepublish_qa_passedがすべてtrue、edit_request_refは現在の本人依頼を参照する。edit_plan.target_urlとsettings.accountも同じ対象へ束縛する。

note_workflow_gate.py --stage publishは、この許可が有効な場合に最終publish receiptの再確認だけを省略する。他の調査・構成・設定・文体・タグ等の失敗は保持する。status=approvedかつupdate_authorization.automation_allowed=trueかつautomation_allowed=trueのときだけ「更新する」を実行できる。それ以外は従来の人間境界を維持する。新規公開・予約変更・課金や公開範囲の変更・外部共有を許可しない。本人が下書きまでと指定した場合、update_observationを供給しない。

公開前QAは従来どおり最終ボタン未操作の観測として実行する。このQAが出す人間境界の既定値を単独で書換えず、後続publishゲートの限定的な許可と区別する。更新後は公開URLで本文・導線・公開設定を読戻す。JSONとpolicy hashは本人許可や実観測の真正性を証明せず、trusted runtimeが引用・依頼・実画面・対象版を照合する。
