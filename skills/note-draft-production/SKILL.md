---
name: note-draft-production
description: "Use inside note-publishing-suite when the user asks to create or revise an article/draft from approved local materials, conversation, or notes, including Japanese requests such as 記事を書いて, 文章にまとめて, 会話を記事に, メモを記事に, or 下書きを直して."
---

# note-draft-production

初回または採用settingsが未確認なら、親スキルの「初回利用・設定が未採用の場合」と [初回設定の案内](../../references/note-workflow-review-contract.md#初回設定の案内)を先に適用する。既存設定を再初期化せず、未確認の設定で制作・保存へ進まない。

## 役割

選ばれた候補を採用済み `storage.drafts` のローカル下書きへ進める。既存稿は本人の編集正本を保持する。

## 入力

- 記事候補、読者、読後に得るもの、公開目的。
- 読んでよいローカル素材 path。
- 既存 draft path。未作成なら Unknown。
- article lane。`production_candidate`、`exploratory_draft`、
  `editor_fixture`、`continuation_article` のいずれか。
- source mode。例: `source_pack_locked`、`skeleton_first`、
  `conversation_reflection`、`fixture_only`。
- TOP 画像の有無。未作成なら Unknown。
- 権利、引用、秘密情報、内部メモに関する未確認事項。

## 手順

0. **本文案を書く前に、現在の参照内容を読む。** `../../references/note-workflow-review-contract.md` の設定契約に従い、利用者が採用した外部settingsから共通口調・対象記事の参照を解決する。本人原文・現稿・採用済みの直し・最新feedbackを先に読む。既存記事では次の読取り専用入口で、参照本文、採否履歴、実差分を取得する。

   ```powershell
   python scripts/note_feedback.py --readback --settings USER_SETTINGS_PATH --article-id ARTICLE_ID --source SOURCE_SNAPSHOT --draft CURRENT_DRAFT
   ```

   hashを取得しただけで内容を使ったことにしない。履歴がまだない新規記事は未作成と明記し、本人原文の保全から始める。存在しない採否を作らず、本人の発言にない体験・感想・判断で空きを埋めない。参照や保存済み履歴が壊れている場合は停止する。
   返却時には参照した版と、今回適用・保全・保留した具体的な直しを原文との比較で示す。何も該当しない場合も理由を記す。人物の体感や疑問などを毎節の必須項目にせず、本人原文・現在の指示を優先する。
0.1. 外部styleで `history_learning_policy.required: true` を採用している場合は、既存authorship証拠の履歴候補を `note_feedback.py --readback --history-only --history-evidence` で制作前に回収する。許可資料と原文引用を読み、最新Discord／本人原文を主資料にしたまま文体制約へ使う。新稿保存後は既存feedback.entriesに実適用／保全／非該当理由を残し、本文hashとafter実在をQA／workflowで検査する。候補・適用・本人採用を分ける。契約は `../../references/note-workflow-review-contract.md`「過去修正の回収と現稿への適用」。
   画面で指定された訂正も、対象の短い引用、修正前、本人の指示、採用後、適用範囲を外部の既存feedbackへ結び付ける。指示から推測した理由は本人発言と分ける。次稿では該当する訂正を既存の制作メモで対応付け、最初の本文案へ反映したかを提示前に確かめる。今回だけの具体例・衣装・文字数を全記事の必須則にせず、意味の採否をhash検査の成功で代用しない。
0.2. **壁打ち・口述を主資料にする場合は、発言抜粋を全文の代用にしない。** `../../references/note-workflow-review-contract.md`「壁打ち全体と本文の忠実性」に従い、既存 `provenance_label_check.capture_conversation` で対象会話の記録全体を固定し、記事profileの `conversation_fidelity_policy.required=true` とsource/hashを結ぶ。本文前に全本人発言の反映・省略理由・更新関係を整理し、本文後に全段落の根拠を対応付ける。執筆者とは独立した担当の意味照合を回収し、本人未発言の判断を本文へ混ぜない。新しい本人説明が来たら原資料と対応・レビューを更新する。会話記録を取得できない場合は、本人へ不足範囲を示し、選択抜粋で全体照合済みとは扱わない。
1. `../../references/note-article-provenance-design.md` を読み、
   `article_lane`、`source_mode`、source database、source pack、plot、
   skeleton、wall-bang、stance brief を固定する。
1.1. `../../references/note-draft-authority-and-layout-contract.md` を読み、材料不足時は問答 intake を先に行う。許可済み資料から `voice_profile` を作る場合も、本人の発言にない感想や体験を作文しない。
2. 今回の読者と記事の目的を、本人の依頼・素材から整理する。読後に得るもの、解決、公開後の指標は、今回必要で根拠がある場合だけ扱う。未解決の疑問を考える記事に解決策・効果・読後行動を枠埋めで足さない。
3. plot / skeleton を作る。壁打ちの記事化では、発言の一覧を執筆用の骨組みとして返さない。各項目で何を書くかを短く整理し、使う具体例と未解決の疑問があれば示す。本人の考え、本人が同意した返答、調べて説明する事実、答えが出ていない疑問を区別する。原文は根拠として別に確認できるようにする。読者の痛み・反論・結論・CTAなどを枠埋めで足さず、必要な項目だけを使う。
   共通の確認画面には `skeleton_mode: writing-plan` と各節の `writing_plan.items` を使い、各itemの根拠を同節の原文paragraph IDへ結ぶ。詳細は `../../references/note-provenance-review.md`。引用だけの旧表示は資料一覧であり、執筆計画の確認済みとは扱わない。
   AIの返答に本人が同意した内容も使える。対象の返答、同意した本人発言、同意の範囲を記録し、「そうだね」や会話の継続を返答全体への同意へ拡張しない。質問や調査依頼を本人の確定的な考えへ変えない。機械検査の成功は、意味の一致や本人による骨組みの採用ではない。
   骨組みを確認している段階で本文を書き直さない。本人が骨組みに修正を求めた場合は、その内容を更新してから本文へ進む。既存の採用や明確な編集指示は再質問せず使う。
4. 本文では事実、推定、意見を分ける。根拠が必要な主張は確認対象として残す。
5. 長い転載、歌詞全文、未承認引用、個人情報、秘密情報、内部メモを本文に入れない。
6. TOP 画像案を 7 件出す。各案に `concept`、`prompt`、`style`、`avoid`、`fit_reason` を付ける。
7. タグ案は広い発見タグ、主題タグ、文脈タグ、所有シリーズタグを混ぜる。
   外部settingsの `tag_reference_policy.required` がtrueなら、readbackに含まれる採用済みマーケティング資料を読み、既存 `tag_design` に3観点の資料参照、全資料の `reference_readback`、読者の `search_intents` 2〜3件を保存する。本文との対応と未測定事項をreasonへ記録し、単に候補タグを並べて選定済みとしない。参照の版はsettings / publishの既存validatorで再照合する。
   候補生成時から、主題語に加え、外部の戦略資料にある著者・ブランド・連載・共同体の候補と過去記事の採用タグを照合する。利用側に候補生成器がある場合はその正本を使い、NPSへ同じ固有ルールを作らない。固定指定、記事ごとの候補、本人の追加・除外を区別し、比較して外した候補の理由も既存 `tag_design` へ残す。件数の大小は採用元の基準と日時付き実測がある場合だけ示し、未取得・古い値を0や検索需要へ置き換えない。
8. 新規稿の既定保存先は、採用settingsの読戻しJSON `storage.drafts` に `<date>-<slug>.md` を連結して決める。本人が明示した既存稿の編集正本はそのpathを保持し、別の保存先へ勝手に移動・複製しない。`content/drafts/` やpointerの既定値へ戻さない。原資料とfeedbackも同じ読戻しの `storage.sources` / `storage.feedback` を使い、設定hashを後続QAへ引き継ぐ。設定未採用・読戻し失敗・保存先不明なら保存を止める。package内サンプルの検査は明示されたeditor_fixtureに限る。
9. frontmatter に `article_lane`、`source_mode`、`based_on`、
   `allowed_use`、`not_allowed`、`editor_test_allowed`、
   `publication_gate: human_review_required`、`external_action: none` を置く。
10. 各本文ブロックの直前へローカル管理用の `<!-- provenance ... -->` を置き、
    `kind`、`source`、`review` を記録する。AI が補った未確認の主張は
    `kind: hold` とし、本人発言として補完しない。
11. `provenance_label_check.py`、`note_preview.py --review-provenance` の順に実行し、
    ローカル Markdown とレビュー HTML を人間レビューへ渡す。
12. 会話での修正は内部 ID を要求せず、見出しまたは本文の短い引用で対象を特定する。
    修正後は検査とレビュー HTML を再生成する。
    本文へ進む際は、各段落で何を伝えるかを採用した骨組みと照合する。本人の判断・体験・疑問に戻れない結論、気の利いた感想、一般論のつなぎ、作業説明を本人の語りへ加えない。出典のある外部事実も、本人がそう考えていることの根拠にはしない。疑問のまま残した項目を勝手に解決しない。読みやすさの編集は、論点の順番・重複・段落の長さから始め、足りない感想をAIが補わない。
13. `hold` を解消し検査が通った後だけ `--public-output` を使う。公開、投稿、
    共有は引き続き別の明示承認まで行わない。
14. `production_candidate` では、問答packetまたは編集前正本を一意に指す
   `shortening_source` と、許容削減率 `shortening_budget` をfrontmatterへ記録する。
   CLI と frontmatter で異なる比較元または許容値を指定しない。
   既定では意味段落、具体例、本人発言、出典、図、キャプションを維持し、省略候補を勝手に削除しない。
15. 改行と図を含む場合は `note_linebreak_gate.py` と `note_figure_structure_gate.py` の対象を明記する。
16. production QA では
   `python scripts/note_authorship_gate.py <draft> --settings USER_SETTINGS_PATH --article-id CURRENT_ARTICLE_ID --json` を実行する。機械的な履歴適用だけを独立確認する場合は同じコマンドへ `--history-only` を付ける。必須段階では設定省略・not_requiredを通過扱いにしない。
   会話忠実性policy必須の場合は同じCLIへ `--conversation-id CURRENT_CONVERSATION` を渡し、`conversation_fidelity.status=mechanical_ok` と `semantic_review=independent_review_recorded` を確認する。旧語句検出・短縮比較の数値を、全文からの意味保持の代用にしない。policyが任意の従来経路では `shortening.checked=true` と `overall=ok` を確認する。

## 境界

必須の原文・履歴・短縮・会話照合が未検証または失敗なら、完了扱いにしない。

公開文面として扱える水準まで整えるが、公開承認ではない。公開、予約投稿、SNS 共有、外部告知は行わない。

`editor_fixture` lane は公開候補にしない。Note editor 操作テストは fixture 文で行い、
`production_candidate` の本文をテスト目的で改変しない。

## 出力

- `<storage.drafts>/<date>-<slug>.md`: 本文。
- 必要なら `<storage.drafts>/<date>-<slug>-production-pack.md`: skeleton、壁打ち、画像案、タグ案。
- `<storage.assets>/<slug>/`: 採用した外部画像保存先。未採用なら画像保存前に確認し、既存の画像正本は動かさない。previewは対象原稿の保存先へ置く。

## 停止条件

- 根拠が必要な主張を確認できない。
- 権利リスクのある引用や画像が公開前提になっている。
- ユーザーが求めている記事種別が未確定。
- `production_candidate` の `shortening_source` または `shortening_budget` がない、
  比較元が複数に分岐する、あるいは短縮検査が `shortening.checked=true` にならない。

## Closeout Evidence

- 作成/更新した draft path。
- article lane / source mode。
- 使った source database / source pack / plot / skeleton / wall-bang / stance brief。
- 残した未確認事項。
- 次の QA コマンド。
- 問答 intake の確認事項、`voice_profile` の根拠、`shortening_budget`、図・キャプション・改行の維持結果。

## ハッシュタグ選定

- 候補は 5-10 個。記事の主題タグ + 文脈タグ + 固有タグを混ぜる。
- 過去記事のタグ実績を台帳 (採用した外部台帳の published_notes.json の tags) で確認し、続き物は揃える。
- 公式ソースで確認済み: ハッシュタグは公開設定で追加する方法と、本文中に半角 `#` + 単語を書く方法がある。本文中に書く方法でも公開設定へ反映される。
- local policy: 主題タグ、文脈タグ、固有タグを混ぜる。これは公式推奨としては扱わない。
- local observation: ハッシュタグは本文中で使うと候補に出やすくなる場合がある。断定せず、必要なら実測確認へ回す。
- 断定的な流入予測をしない。タグ案は人間レビューに回す。

## AI 利用の境界 (本 skill 内)

- AI が作ってよいもの: skeleton、構成案、要約、タグ候補、画像案。
- AI が作ってはいけないもの: 本人の一言・体験・判断の代作、原文と一致しない引用 (作文禁止)。
- 引用はすべて source と突き合わせ、言い換えは間接話法にする。

## 口述モード

`source_mode: source_pack_locked_with_user_speech_priority` の draft で、
本人が話した内容をそのまま本文化する場合の運用。

- 本文は本人が話した言葉だけを使う。AI が代わりに構成や言い回しを作らない
  (作文禁止)。AI が整えてよいのは語尾・誤変換・句読点など、意味を変えない
  範囲だけ。
- 本文中の数字・固有名詞・日付・URL は `scripts/note_fact_check.py local
  <draft.md>` で抜き出し、事実確認は本体モデルではなく Sonnet/Haiku 相当の
  cheaper worker に委譲する (Runtime Guarantee の worker 分担を継承)。
- 確認できた項目は本文に一次情報へのリンクを付ける。確認できない項目は
  本文に残さず、`<draft.md>` と対になる `<draft.md>` 相当の notes file
  (例: `<storage.drafts>/<date>-<slug>.notes.md`) の未確認一覧へ移す。
  本文には空欄 (`【 】` など) を残してよい。
- 構成・言い回し・方針の判断は本人がする。AI は案を並べて止まり、
  正解が一つに決まる事実修正だけを直して報告する。
- 各段の変更は `<draft.md>` に追記した後、`provenance_label_check.py`
  で `user-said` / `external-fact` / `assistant-organized` / `hold` の
  境界を確認し、`note_preview.py` でプレビューを再生成してから本人へ返す。

## 末尾リンク選定

本文中のハイパーリンク、本文埋め込み、末尾カードを区別して候補を出す。本人の既存記事・サービス・ホームページ・GitHub・SNSを許可された資料から確認し、表示文・目的・配置・採否を既存 `layout.hyperlinks` と `footer-selection` へ結び付ける。URLが特定できないサービスは内部の確認待ちへ残し、読者向け本文に推測URLや作業メモを入れない。

Planに読者・シリーズ・読後行動を固定し、採用リンクの登録参照、理由、カード又は文字リンク、
順序、必須/任意を記録する。既存制作パック内の `footer-selection` ブロックを使う。
固定5枚などの記事固有案を汎用規則にしない。
形式は `../../references/note-draft-authority-and-layout-contract.md` の末尾リンク選定契約に従う。
意味の適合性と既存登録の確認を人間がレビューするまで未承認を維持する。


## 読書表示の生成

Noteの見た目で確認する依頼は `scripts/note_virtual_preview.py <draft> -o <preview.html>` を使う。既存の抽出Note CSSとtemplateが正本。`note_preview.py` の簡易表示はOSのダーク設定に追従し、Note再現の入口ではない。由来の色分け確認には `note_preview.py --review-provenance`、編集診断には `note_virtual_preview.py --diagnostics` を使い、用途を混同しない。実Noteの表示と完全同一とは報告しない。

## 経路選択と編集承認

`../../references/note-workflow-review-contract.md` を読む。本人原稿、素材記事化、共同執筆の経路を選び、変更前snapshotをworkspaceへ保存して編集稿と分ける。note本文が出発点なら写真・caption・見出し・リンクの構造も保全する。AIの追加案と本人発話を対応表で分ける。草稿候補を作ることと現稿へ採用・反映することを区別し、誤字も変更前後を本人に提示する。承認の照合には `note_workflow_gate.py --settings USER_SETTINGS_PATH --packet USER_REVIEW_PACKET --conversation-id CURRENT_CONVERSATION --stage edit` を用いる。

## キャラクター画像の参照ゲート

利用者の外部settingsが `image_reference_policy` を宣言している場合、画像生成前に `python scripts/image_reference_gate.py --settings USER_SETTINGS_PATH --article-id CURRENT_ARTICLE_ID --stage pre_generation` を通す。既存reference manifestの実体hash、必要な役割、今回toolへ渡す全 `referenced_image_paths`、完全promptを既存生成receiptへ束縛する。blockedなら生成しない。生成後は実際の添付pathと出力hashを記録し、同じ出力への参照別の観察を `visual_qa` へ追加して `python scripts/image_reference_gate.py --settings USER_SETTINGS_PATH --article-id CURRENT_ARTICLE_ID --stage qa` を通す。参照画像の取得状態を本人採用へ昇格させない。schemaと限界は `../../references/note-workflow-review-contract.md` の画像参照契約を読む。


骨組みから本文へ進む場合は ../../references/note-provenance-review.md を使う。修正の意味確認を求められた場合は原文・理解・提案を一件ずつ確認し、pendingと本人採用を区別する。
