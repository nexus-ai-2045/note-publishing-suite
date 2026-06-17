---
title: Note Publishing Suite README
type: スキルパッケージREADME
status: active
created: 2026-06-08
publication_gate: human_review_required
---

# Note Publishing Suite

このパッケージは、Note 記事投稿をリポジトリ内で一気通貫に扱うための
スキル群。

パッケージ版: `0.2.2`

使命は、記事アイデア、下書き、投稿前検査、Note エディタ反映、
公開直前停止、公開後台帳までを、Codex が安全に迷わず進めること。

## 最初に開くリンク

- [ROADMAP.md](ROADMAP.md): 今やること、次にやること、後でやること。
- [README.rendered.html](README.rendered.html): この README の整形 HTML 表示。
- [PUBLIC_READY.md](PUBLIC_READY.md): 公開リポジトリとして見せてよいかの確認。
- [PUBLIC_RELEASE_CHECKLIST.md](PUBLIC_RELEASE_CHECKLIST.md): 公開前の最終チェック。

## 30秒でわかること

Note Publishing Suite は、Note 記事を「書く」「確認する」「エディタに反映する」
「公開直前で止める」ためのリポジトリ内パッケージ。

読者は 3 種類を想定する。

| 読者 | まず見るもの | わかること |
| --- | --- | --- |
| 初めて使う人 | `ワークフロー`、`最短確認` | 着想からゲートまでの流れ |
| 運用する人 | `保証ラチェット`、`実行境界` | 何を自動化し、どこで止まるか |
| 公開前に見る人 | `PUBLIC_READY.md`、`PUBLIC_RELEASE_CHECKLIST.md` | 公開リポジトリと記事公開の安全確認 |

このパッケージは記事本文を勝手に公開しない。
Note 公開、予約投稿、SNS 共有、リポジトリ公開範囲変更は、
現在の会話で対象と操作を特定した人間レビューと明示承認が必要。

## 最短確認

クリーン環境や公開前レビューでは、まずパッケージ契約を確認する。
この検証は公開操作なしで、`nexus_ai/public` 配下の embedded copy と、
一時 git repository として作る standalone clone fixture の両方を確認する。

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify_public_package.ps1
```

Python が使える環境では、公開前検査器と重点テストを回す。

```powershell
python scripts/provenance_leak_check.py --scope changed
python -m pytest scripts/test_skill_integration.py tests/test_content_pdca_check.py tests/test_note_image_upload_boundary.py tests/test_note_editor_prepublish_verify.py
```

README の整形表示を更新する時は、次を実行する。

```powershell
python scripts/render_readme.py
```

## まず何を見るか

このパッケージは、単なるスクリプト集ではなく、Note 公開運用の小さな
プロダクトとして扱う。読む順番は「全体像、起動条件、機械可読契約、
詳細参照、検査器」の順。

最初に見る順番:

- `README.md`: 全体像、保証範囲、ロードマップ。
- `CHANGELOG.md`: 版番号ごとの変更内容と検証範囲。
- `SKILL.md`: Codex がこのパッケージをどう起動し、どう止まるか。
- `package.yaml`: 機械可読の入口、ゲート、ワークフロー。
- `references/`: Note エディタの制約、PDCA、画像アップロード境界。
- `scripts/` と `tests/`: ローカルで確認できる保証。

## 中核モデル

記事制作で混ざりやすい材料を、次の単位に分ける。

| 単位 | 役割 | 事実として扱うか |
| --- | --- | --- |
| `source_database` | 最初に読んでよい材料 DB | はい。最優先の根拠 |
| `source_pack` | 記事単位に切り出した根拠 | はい。記事内事実の根拠 |
| `series_plot` | 連載全体の設計 | いいえ。構成 |
| `article_plot` | 1 本の記事の展開 | いいえ。構成 |
| `skeleton` | 見出しと流れの骨格 | いいえ。構成 |
| `wall_bang` | 壁打ち、問い、切り口、言い回し候補 | いいえ。仮説と表現 |
| `editor_fixture` | Note エディタ操作検証用の記事 | いいえ。本番記事と混ぜない |

原則は、事実は `source_database` から出し、記事単位では
`source_pack` に固定すること。構成案、骨子、壁打ちは
文章の設計や検討材料であり、事実根拠にはしない。

## ロードマップの見取り図

前提は、機能一覧ではなく「解く問題、成果、検証ゲート」で進めること。
Product Design は読者体験と運用体験を整え、Creative Production は
記事・画像・告知素材をレビュー可能な制作フローに分ける。

| 領域 | 目的 | このパッケージで見る場所 |
| --- | --- | --- |
| Product / UX | 読者、執筆者、運用者が迷わない流れにする | `ワークフロー`、Q&A、`references/note-editor-pdca-orchestration.md` |
| Note 投稿運用 | 着想から台帳までの実行単位を分ける | `skills/`、`scripts/`、`data/` |
| セキュリティ / 公開準備 | 公開前にシークレット、内部メモ、権利、承認を止める | `skills/note-publication-gate/SKILL.md`、`PUBLIC_READY.md`、`SECURITY.md` |
| AI エージェント / OpenAI 運用 | ワーカーを使っても親実行環境が採否とゲートを握る | `オーケストレーション`、`package.yaml` |
| 制作 / 配布 | TOP 画像案、タグ案、告知素材を公開前レビューに載せる | `skills/note-draft-production/SKILL.md`、外部操作境界 |
| 測定 / 学習ループ | 公開後の状態と反応を台帳に戻す | `skills/note-postpublish-ledger/SKILL.md`、`scripts/engagement_tracker.py` |
| 外部依存ゲート | Note 実画面、画像アップロード、Mac/Windows 差分を未保証のまま明示する | `references/note-image-upload-automation-boundary.md` |

## Now / Next / Later

### Now

- README / HTML プレビューで、全体像と停止線をすぐ読めるようにする。
- `note_image_upload_boundary_check.py --json` で画像アップロード境界を確認する。
- `note_editor_prepublish_verify.py <observation.json> --json` で公開設定画面の
  観測結果を確認する。
- `pre_publish_check.py` とローカルプレビューで、下書きの公開前 QA を回す。
- 公開、投稿、予約、SNS 共有、リポジトリ公開範囲変更は人間レビューまで止める。

### Next

- Note 実画面で、画像 caption / alt、長い目次、公開後目次表示を
  `note-editor-constraint-debug` に沿って実測する。埋め込み、目次 DOM、
  Shift+Enter は `references/note-editor-live-constraint-boundaries.md` に実測済み。
- Creative Production の観点で、TOP 画像案、タグ案、告知素材案を
  article flow から分離し、review 可能な候補として残す。
- Product Design の観点で、初回利用者が「どの skill を読むか」を
  README と issue packet から迷わず辿れるようにする。

### Later

- Mac 実機など、Windows だけで完結しない検証を
  external gate として別 lane に置く。
- 投稿後 ledger と反応測定を、記事改善の学習 loop へ戻す。
- 公開候補 package と独立 repo / worktree の扱いを、
  親 repo の `public/` 運用ルールと同期する。

## 採用前レビュー

この手の package はローカル環境、Codex の設定、Python、Browser 状態、
Note の UI 状態によって動かないことがある。

採用前に必ずレビューする。
レビューは Codex に依頼し、少なくとも README、`SKILL.md`、`package.yaml`、
`scripts/`、`tests/`、公開ゲート、外部送信境界を確認する。

レビューなしで公開、予約投稿、SNS共有、外部告知に使わない。

対象リポジトリ:

```text
repo root
```

## 表示について

Codex のファイルエディタは Markdown をレンダーではなく、
ソース表示とシンタックスハイライトで開くことがある。

整形表示で読みたい時は、同じディレクトリの
`README.rendered.html` を開く。
表示が古い時は `python scripts/render_readme.py` で再生成する。
Python が無いクリーン環境でパッケージと公開境界だけを確認する時は、
`pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify_public_package.ps1`
を使う。

この README 自体も素の表示で読めるように、
長い行を避けて書く。

## 構成

- `SKILL.md`: 親スキル。
  全体ゲート、入出力、子スキルルーティング、課題下書きを持つ。
- `README.rendered.html`: 整形表示用の HTML プレビュー。
- `CHANGELOG.md`: パッケージ版ごとの更新履歴。
- `scripts/render_readme.py`: README 表示確認用 HTML の再生成。
- `scripts/note_image_upload_boundary_check.py`: note 画像アップロード境界の
  残務ゼロ確認。
- `scripts/provenance_leak_check.py`: PR 前に実行時メモリ、
  非公開リポジトリ名、ローカルパス、出典外の運用文字列が混ざっていないか
  確認する検査器。
- `scripts/verify_public_package.ps1`: Python が無いクリーン環境用の
  パッケージ契約 / 公開準備検証。embedded copy と standalone clone fixture の
  GitHub identity guard lane も公開操作なしで確認する。
- `package.yaml`: パッケージ管理情報。
- `ROADMAP.md`: 公開前ゲートと運用拡張のロードマップ契約。
- `issue-drafts.md`: 追跡ツール非依存の課題下書き。
- `issue-packet.json`: 追跡ツール非依存の機械可読課題パケット。
- `references/note-editor-capability-inventory.md`: note エディタ公式機能、
  実測差分、画面幅、カーソル、ブラウザ面、AI面の棚卸し。
- `references/note-editor-pdca-orchestration.md`: note エディタ操作を
  目的 / 計画 / 実行 / 確認 / 反映の薄い周期で回す運用。
- `references/note-article-provenance-design.md`: 記事が何を元に
  作られたかを出典パック、骨子、姿勢メモ、検査材料に分けて
  固定する設計。
- `references/note-editor-live-constraint-boundaries.md`: 埋め込み、目次、
  Shift+Enter の実画面測定、復旧可否、手動境界、契約テスト境界。
- `references/note-image-upload-automation-boundary.md`: note 画像アップロードの
  手動境界、ユーザー確認待ち境界、禁止境界。
- `skills/note-idea-intake/SKILL.md`: 記事候補と素材探索。
- `skills/note-draft-production/SKILL.md`: 骨子、本文、画像案、タグ案。
- `skills/note-prepublish-qa/SKILL.md`: ローカルプレビュー、投稿前検査。
- `skills/note-editor-prepublish/SKILL.md`: Note エディタ反映ラッパー。
- `skills/note-editor-ops/SKILL.md`: エディタの接続、埋め込み、
  DOM 確認、取り消し復旧、検査器ラチェット。
- `skills/note-official-guidance-intake/SKILL.md`: note 公式ソースを
  一次情報として取り込み、未確認を公式扱いしないためのスキル。
- `skills/note-editor-constraint-debug/SKILL.md`: 埋め込み、目次、
  Shift+Enter、画像キャプション / 代替テキスト、保存表示などの実測デバッグスキル。
- `skills/note-publication-gate/SKILL.md`: 公開/予約直前停止。
- `skills/note-postpublish-ledger/SKILL.md`: 公開後確認と台帳更新。

## 実行境界

公開、予約投稿、投稿、SNS 共有、外部告知は、
現在の会話で対象記事と操作を特定した明示承認があるまで実行しない。

## オーケストレーション

Codex だけ、または Claude Code だけで動くことを前提にする。
Linear などの外部追跡ツールは必須ではない。

- Spark / Sonnet ワーカーは任意の速度改善として使ってよい。
- ワーカーが無い場合は、親実行環境が同じ分担粒度で順に処理する。
- 親実行環境は問い、採否、Type1 境界、公開ゲート、最終報告を持つ。
- ワーカーには認証情報、Cookie、非公開 URL、公開/送信権限を渡さない。
- ワーカー出力は親実行環境が出典、差分、テスト、ゲートを確認して採用する。

## 保証ラチェット

Note エディタで見つかった失敗や手動境界は、その場限りにしない。

- 失敗した操作は、原因、復旧方法、次回の禁止事項を短く残す。
- 再発防止できるものは、検査器、契約テスト、子スキルの境界文言へ落とす。
- 検査器に落としたら、実記事下書きへの実行結果まで確認する。
- note 公式ノウハウは `note-official-guidance-intake` で一次情報化してから
  `references/note-editor-capability-inventory.md` へ反映する。
- 埋め込み、目次、Shift+Enter などの実画面制約は
  `note-editor-constraint-debug` で再現手順と手動境界へ落とす。
- UI 状態に依存して自動保証できないものは、手動境界として公開ゲートに残す。
- 完了報告では、増やした保証、実行したテスト、まだ保証しないものを分けて報告する。
- 日本語運用中に PR / GitHub / CLI の状態語を英語のまま報告した場合は、
  文章ミスではなく出力ゲートの構造バグとして扱う。
  `ready for review` は下書き解除済み、`open PR` は未マージPR、
  `MERGED` はマージ済み、`mergeable` はマージ可能、`success` は成功、
  `failed` は失敗として報告する。
  コマンド、ファイルパス、URL、SHA、パッケージ識別子は原文のままでよい。

## ワークフロー

- idea: ローカル素材から記事候補を出す。
- draft: `references/note-article-provenance-design.md` に沿って
  `article_lane`、`source_mode`、出典データベース、出典パック、構成案、
  骨子、壁打ち、姿勢メモを固定してから、本文、TOP 画像案、
  タグ案を作る。
- qa: プレビュー、投稿前検査、ファクトチェック、必要な差分確認。
- editor: Note エディタに反映し、下書き保存まで確認する。
  実記事候補 (`production_candidate`) とエディタ操作検証
  (`editor_fixture`) は混ぜない。
  低レベル操作が必要なら `note-editor-ops` を自動で読む。
  公式機能や画面条件が関わる場合は
  `references/note-editor-capability-inventory.md` を先に読む。
  公式ソースの追加確認が必要なら `note-official-guidance-intake` を読む。
  埋め込み、目次、Shift+Enter、画像キャプション / 代替テキスト、保存表示の実測は
  `note-editor-constraint-debug` で行う。
  UI操作は `references/note-editor-pdca-orchestration.md` に沿って、
  1周期1操作で証跡を取る。
  画像アップロード境界は `references/note-image-upload-automation-boundary.md` と
  `scripts/note_image_upload_boundary_check.py` で確認する。
- gate: 公開/投稿/予約確定ボタンの手前で停止する。
- ledger: 公開後 URL / 状態を確認し、台帳更新案を作る。

## パッケージ全体で保証されるもの

このパッケージが保証するのは、ローカル素材から Note 下書きを作り、
公開前検査、Note エディタ反映準備、公開直前停止、公開後台帳更新案までを
安全に進めるための最小一式。

### 1. ネタ帳 / 素材指定

- 固定の `ネタ帳.md` は持たない。
- Note 操作前の素材入力は、ユーザーが指定する `読んでよい素材フォルダ`。
- `note-idea-intake` は選択フォルダ外を読まない。
- 読んでよい素材フォルダが未指定なら停止する。
- 記事下書きへ進める前に `article_lane` と `source_mode` を決める。
- ファクト抽出は最初の出典データベースを優先し、記事単位では
  出典パックに切り出す。
- 構成案 / 骨子は展開と構成の設計図であり、事実根拠として扱わない。
- 壁打ちは問い、切り口、仮説、言い回し候補であり、事実断定の根拠にしない。
- PR 前には `scripts/provenance_leak_check.py --scope changed` を実行する。
  ユーザー固有 denylist は gitignored の
  `data/provenance_leak_policy.local.json` に置き、公開パッケージへ直書きしない。
- GitHub account、email、private owner などの identity denylist は
  gitignored の `data/github_identity_guard_policy.local.json` に置く。
  公開パッケージには
  `data/github_identity_guard_policy.example.json` だけを含め、実ユーザー固有値を
  直書きしない。
- 実記事候補をエディタ操作テストの検査材料にしない。
- 既存下書き / 公開済み台帳を見る必要がある場合だけ、
  `data/note_drafts.json` と `data/published_notes.json` を読む。

### 2. パッケージ構成

- 親スキル、管理情報、README、課題下書き、課題パケットがある。
- 6つの段階別子スキルがある。
  `idea / draft / qa / editor / gate / ledger` をそれぞれ担当する。
- エディタ段階には、機能別低レベル操作の `note-editor-ops` がある。
- 公式ノウハウ取り込みには `note-official-guidance-intake` がある。
- エディタ制約デバッグには `note-editor-constraint-debug` がある。
- エディタ操作には、公式機能、画面幅、カーソル位置、ブラウザ面、
  AI操作面の棚卸し参照がある。
- エディタ操作には、目的 / 計画 / 実行 / 確認 / 反映を薄く回す
  PDCA オーケストレーション参照がある。
- `scripts/` にローカル QA / 台帳用スクリプトがある。
- `tests/` にパッケージ契約とローカル確認のテストがある。
- `data/` に空の初期台帳がある。
- `content/drafts/`、`content/assets/`、`published/` がある。

### 3. ローカルスクリプト

- `scripts/note_preview.py`
  - Markdown 下書きからローカル HTML プレビューを生成する。
  - 外部送信しない。
- `scripts/pre_publish_check.py`
  - シークレットらしい値、HTML コメント、TODO/FIXME、未確認語、
    非公開 URL の気配、短すぎる下書きを検出する。
  - `--fix` は HTML コメント除去だけを行う。
- `scripts/note_fact_check.py`
  - 未確認表現、数字/日付/件数、URL、内部メモ候補を抽出する。
  - 本人の発言、本人の言葉、体験ベースの主張、出典/根拠マーカーも
    公開前の確認候補として抽出する。
  - 外部ファクトチェックはしない。
- `scripts/note_diff_check.py`
  - Note/public URL がある場合だけ phrase の存在確認を行う。
  - URL が `Unknown` / `none` / `-` の場合は未実行として終了する。
- `scripts/fetch_note_body.js`
  - Note 公開記事の本文を Playwright で取得する。
  - `note_diff_check.py` で curl/fetch だけでは本文が取れない場合の手動補助として使う。
- `scripts/run_local_draft_qa_proof.py`
  - 1つのローカル下書きに対して preview、投稿前検査、
    local fact check、diff check を順に実行する。
  - 結果を `data/local_draft_qa_stop_before_publish_evidence.json` に記録し、
    人間レビュー必須、公開操作 0、外部操作 0 の停止線を残す。
- `scripts/check_version_bump.py`
  - PR でパッケージ実体が変わった場合、`package.yaml` の semver が
    base branch より上がっていることを CI で確認する。
  - `package.yaml`、README、CHANGELOG だけの版管理メタデータ更新は
    実体変更とは分けて扱う。
- `scripts/post_publish.py`
  - 既定はドライラン。
  - `--write-ledger` を付けた時だけ ledger を更新する。
  - SNS 投稿 option は持たない。
- `scripts/engagement_tracker.py`
  - ローカル台帳件数だけを報告する。
  - 外部アクセスしない。

### 4. Note エディタ操作

保証される範囲:

- in-app Browser で Note エディタを接続 / 確認できる場合だけ進める。
- タイトル、本文、見出し、リンク、画像、タグ、マガジン、公開範囲を
  反映または確認する手順を持つ。
- リンクカード埋め込みは、URL を単独行で入力し、その行末で Enter を
  押して変換する手順を持つ。
- 埋め込みの成功は、表示だけではなく `figure[data-src]` などの
  DOM で確認する手順を持つ。
- `href` だけが残る状態は通常リンク残りとして扱い、必要なら
  取り消しで復旧する。
- ボタン配置は動的に変わるため、公開/予約/共有/保存系は
  固定座標で押さず、DOM、ラベル、状態で識別する。
- Playwright と実操作面が同期しない場合は、固定座標操作を続けず、
  手動境界または別ルートへ切り替える。
- 下書き保存までで止める。
- 公開/投稿/予約確定ボタンは押さない。
- Cookie、トークン、非公開 URL、個人情報をログに残さない。
- Chrome、Computer Use、live article へ無断で切り替えない。

条件付き / 非保証:

- 画像アップロードは内部ブラウザだけで完全自動化できるとは保証しない。
- 画像アップロードの運用境界は
  `scripts/verify_public_package.ps1` でパッケージ契約と一緒に確認する。
  Python が使える開発環境では
  `python scripts/note_image_upload_boundary_check.py --json` で詳細確認してよい。
- Windows / Mac 環境差は
  `references/note-image-upload-automation-boundary.md` の対応表に従う。
  Windows 10 以上、macOS 14 以上の公式推奨ブラウザでも成功保証ではなく、
  停止線と禁止経路を保証する。
- 画面に見えている Windows ファイル選択ダイアログだけを扱う場合も、
  現在会話での明示確認があるまで実行しない。
- 接続 / 確認できない場合は停止する。
- 埋め込みカード位置、目次位置、カーソル操作、画像アップロードは
  実測確認できない場合、手動境界として報告する。

### 5. 公開ゲート

- 対象記事、対象操作、公開方式のどれかが `Unknown` なら停止する。
- QA、画像権利、秘密情報除外、内部メモ除外が未確認なら停止する。
- 現在会話で対象記事と操作を特定した明示承認がないなら停止する。
- 「公開して」「投稿して」だけでは不十分。
  対象記事と操作の特定が必要。

### 6. 外部 action 境界

- X 投稿は scope 外。
- いいねは scope 外。
- Discord / Slack 告知は scope 外。
- 自動告知、SNS 同時投稿、公開範囲変更は明示承認なしに実行しない。
- リポジトリ公開範囲変更は扱わない。
- credential、Cookie、非公開 URL、公開/予約/送信権限は worker に渡さない。

## 保証しないもの

- GitHub の Download ZIP や clone だけで Codex に自動インストールされること。
- Note へのログイン。
- Note エディタ接続 / 確認が常に成功すること。
- 画像アップロードの完全自動化。
- 公開、予約投稿、SNS共有、外部告知。
- 外部 URL の内容が常に取得できること。
- 記事内容の事実が正しいこと。
  `note_fact_check.py` は確認候補の抽出まで。
- 本人の発言や体験が本当に本人由来であること。
  `note_fact_check.py` は本人発言/体験ベースの確認候補を抽出するが、
  原文、会話ログ、体験メモ、ユーザー確認との突き合わせは人間レビューで行う。
- SEO、おすすめ掲載、PV、反応数。
- ユーザーが指定していない素材フォルダや private URL の読取。

## 必要十分の境界

この package が必要十分として保証する範囲:

- ローカル素材を指定して記事候補を作る。
- ローカル下書きを作る。
- ローカル preview と公開前検査を回す。
- Note エディタへ進む前の安全ゲートを持つ。
- Note エディタでは下書き保存までを扱い、公開直前で止まる。
- 画像アップロード境界は `references/note-image-upload-automation-boundary.md` と
  `scripts/note_image_upload_boundary_check.py` により、手動 upload、
  確認待ちの可視 Windows ダイアログ、Chrome/API/Cookie 禁止を分離する。
- 公開後にだけ ledger 更新案を作る。

この範囲を超える公開操作、外部送信、画像アップロード完全自動化、
成果保証は package の保証外。

## Q&A

### Q. 一言で言うと何？

Note記事をローカル素材から下書き・検査・下書き保存まで進め、
公開直前で必ず止める手順書。

### Q. ZIP は別で用意する？

別の独自 ZIP は不要。
GitHub の標準機能で、repository や branch は Download ZIP できる。
通常は repository を clone するか、GitHub の Download ZIP を使う。

### Q. ネタ帳はどこ？

固定の `ネタ帳.md` はない。
ユーザーが指定した `読んでよい素材フォルダ` をネタ帳として扱う。

### Q. 勝手な作文をしない？

指定素材フォルダだけを読む設計。
根拠がローカルに見つからない候補は停止条件。
下書きでは事実、推定、意見を分け、根拠が必要な主張は確認対象として残す。
本人の発言や体験として書く場合は、原文、会話ログ、体験メモ、
または現在会話での確認に戻れる形にする。

ただし文章化そのものは行うため、完全な作文ゼロではない。
公開前 QA と人間レビューで止める。

### Q. 公開まで自動で進む？

進まない。
公開、投稿、予約投稿、SNS共有、外部告知は、
現在の会話で対象記事と操作を特定した明示承認があるまで実行しない。

### Q. Note エディタで何ができる？

in-app Browser で接続 / 確認できる場合に限り、
タイトル、本文、見出し、リンク、画像、タグ、マガジン、公開範囲を
反映または確認する手順を持つ。
リンクカード埋め込みは URL 単独行の行末で Enter を押して変換する。
下書き保存までで止まる。

### Q. 画像アップロードは完全自動？

保証しない。
内部ブラウザで完了しない場合は停止し、手動または supervised 操作として扱う。

### Q. 外部 tracker や connector は必要？

不要。
`tracker_required: false`、`external_connectors_required: false` の前提。

### Q. script は外部送信する？

基本しない。
`note_preview.py`、`pre_publish_check.py`、`note_fact_check.py`、
`engagement_tracker.py` はローカル処理。
`note_diff_check.py` だけ、Note/public URL が指定された場合に取得確認を行う。

### Q. 何を保証しない？

Note ログイン、常時 attach 成功、画像 upload 完全自動化、
公開成果、PV、SEO、おすすめ掲載、事実の正しさは保証しない。

## 検証

`verify:local` 相当の基準は、公開操作なしで package の構成、安全境界、
README 表示、公開前停止線を確認できること。
加えて、`scripts/github_identity_guard.py` が embedded copy では
text scan only、standalone clone fixture では remote、HEAD author、
repository-local git config まで検査することを確認する。

クリーン環境では Python を前提にせず、まずこのコマンドを使う。

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify_public_package.ps1
```

Python と pytest が使える開発環境では、追加で以下を実行してよい。

```bash
python3 -m pytest scripts/test_skill_integration.py tests/test_content_pdca_check.py tests/test_note_image_upload_boundary.py tests/test_note_editor_prepublish_verify.py
python3 scripts/github_identity_guard.py --json
python3 scripts/github_identity_guard.py --policy data/github_identity_guard_policy.local.json --json
python3 scripts/japanese_closeout_language_check.py --json
python3 scripts/note_image_upload_boundary_check.py --json
python3 scripts/note_editor_prepublish_verify.py <observation.json> --json
python3 scripts/run_local_draft_qa_proof.py --json
python3 scripts/check_version_bump.py
```

任意の実記事 draft を見る場合だけ、追加で次を実行する。

```bash
python3 scripts/pre_publish_check.py <draft.md>
```
