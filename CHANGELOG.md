# 変更履歴

## 0.3.11

日付: 2026-10-24

変更:
- 必要なGitHub CIを維持し、workflow・イベント別に古い検証のキャンセルを分離。共同執筆UIを関連差分で実行し、verifierと後続stepの同一CLI再実行を解消。
- Windowsのstandalone検証fixtureも公開identity正本の名義を使う。package検証の文書差分は既存resolverでPR全体を確認し、HEAD^へ固定しない。
- 公開Git author名を既存identity正本へ整合し、CIの検査対象headと現行repo-preflight参照を固定する

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `identity契約18 tests、文書同期、版検査。全体2197 testsは修正前の同一機能差分で成功し、配送前に再確認する。`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.3.10

日付: 2026-10-24

変更:
- CIのrepo-preflightの固定先を v0.10.0（5b7c774）へ揃える（REPO_PREFLIGHT_SHA・preflight-gate の uses と preflight-ref・base-guard の PREFLIGHT_REF・整合設定の $schema）

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `文書同期検査成功。GitHub ActionsはPRで確認する。`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.3.9

日付: 2026-10-24

変更:
- CIのrepo-preflightを名義検査の走査最適化版へ固定更新

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `private-readiness近接テスト14件成功、文書同期検査成功。GitHub ActionsはPRで確認する。`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.3.8

日付: 2026-10-24

変更:
- 画面コメントの修正前・本人指示・採用後・適用範囲を既存feedbackへ結び付け、次の初稿で実適用を確認する制作手順を追加。
- 利用側のマーケティング正本と候補生成器を使い、著者・ブランド・連載・共同体・過去タグ・今回の追加除外を既存tag_designへ接続する。固有辞書は複製しない。
- 共有repo-preflightを固定SHAで更新し、pushの比較元を不変のevent SHAへ束縛する。private callerのfetchはその命令だけに認証情報を渡し、Git設定へ残さない。

検証:
- 既存feedbackとtag_designの契約、参照先・公開境界を独立レビュー。最終版のCI結果はPRへ記録する。
- Note記事や公開条件は変更しない。

追加の変更:
- すべてのadoptionを根拠発言へ照合し、本人同意の架空記録を拒否する。READMEの停止確認例へ原稿と明示出力先を補う。
- CIのprivate identity設定を2つの明示Secretsへ接続し、固定SHAの上流scannerだけを実行するjobと候補wheel・ratchetを実行するjobを分離。
- 欠落・不正設定は既存validatorで停止し、秘密入力の一時保存・削除と公開ログのpass/fail限定を検査。
- 直下の管理下Git作業用出力`/.worktrees/`だけをGit対象外とし、原資料・検査コードの追跡は保持。
- provenance全体検査は実登録された直下の作業checkoutへの再帰だけを除外し、未登録資料と明示入力の検査は維持。

検証:
- missing input、SHA不一致、候補sitecustomize、private stdout/stderrを使う隔離回帰検査を追加。
- Secret登録とGitHub実行結果はコード検査と区別し、管理者が登録後に確認する。

## 0.3.7

日付: 2026-10-24

変更:
- 旧NPSに残っていた骨組み・原文・本人同意範囲の制作手順と公開前照合手順を統合する
- 第7話移行で保持した回帰：保存原文と現稿の一致、現稿変更後の古い対応、誤った表示抜粋、古い抜粋の混在、原文差替えの5件を共通NPSの検査器へ移した。利用側に検査本体を複製しない。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `対応5回帰とskill integrationの50件が成功。実装は新側に同等搭載済みで文書4件と既存の原文対応回帰を統合。旧履歴や個人名義は新Gitへ取り込まない`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.3.6

日付: 2026-10-23

変更:
- 骨組みの書く内容と根拠を保全し、表示用補助コードの変更も生成版へ束縛する。公開準備のROADMAP確認文言を復元する

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `骨組み互換46件と補助コード版変更1件、利用側44件と19subtests、保存経路4件。PowerShell検証器277項目成功。公開CIの非公開policy供給は未解決`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.3.5

日付: 2026-10-23

変更:
- 消えた Release ではなく、保全済み ai-ratchet-gate 0.1.1 wheel を vendor から hash 固定で入れる

検証:
- `保全wheelは10108 bytesでSHA-256一致。--no-index --require-hashes で導入し、ratchetは新規0。契約テスト2件が成功`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.3.4

日付: 2026-10-23

変更:
- 初回pushで親のないコミットは比較元を作らず、既存の整合性検査へ渡す
- READMEとPUBLIC_READYへ、公開パッケージ検証が要求する起動コマンドを戻す

検証:
- `README 292行。test_repository_guarantees_cover_all_caller_events が成功`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.3.3

日付: 2026-10-23

変更:
- READMEを300行以内にし、毎回の開発検査をdocsへ移し、ワークフロー図をPUBLIC_READYへリンクした

検証:
- `readme_release_gate pass、findings 0。README 292行`
- `python3.13 -m pytest の関連契約5件が成功`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.3.2

日付: 2026-10-23

変更:
- 既存入力guardへRange/widget保護と型付き段落入力を統合し、表示用classの変化による誤停止を修正
- 先頭・末尾へのnativeスクロールを回数・期限・本文とselection保持の照合付きで共通化
- 純粋な催促のみ独立レビュー付きで元の承認を継承し、内容・採否・権限変更は通常再確認
- timeout復旧で接続を再利用し、結果不明の再送と別記事の完了記録流用を防止

検証:
- `対象Python487ケース成功（workflow・会話対応・復旧・入力・PDCA）`
- `Node22入力guard135ケース成功。clipping祖先で隠れる末尾の到達誤判定も拒否`
- `変更Python Ruff、git diff --check成功`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.3.1

日付: 2026-10-23

変更:
- 共同執筆画面のVitestとViteを修正版へ更新し、脆弱な推移依存を解消
- 取得できないrepo-preflight固定コミットを、実在を確認した同一コミットへ統一
- スキル参照検査で現在checkoutと同一リポジトリの正規配置先を区別し、作業ツリーからのコミットを妨げる誤判定を修正
- 入力ガードのコメント保持テストに、欠けていたカード変換のfixture動作を補完

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `Node.js 22: npm ci, npm test, npm run build, npm audit --json`
- `既存Python契約テスト、固定参照の取得とワークフロー整合性の確認`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.3.0

日付: 2026-10-22

変更:
- テーマの対話と複数記事を結ぶローカル共同執筆、原資料を保持する全文編集、候補の選択反映と履歴再開を追加

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `既存機能を含む全体検証と画面E2Eを実施。未解決事項は作業記録に保持`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.74

日付: 2026-10-22

変更:
- 利用側workspaceを明示する共通の骨組み・本人原文照合を移設

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python -m pytest tests/test_note_skeleton_review.py tests/test_package_consistency_check.py -q`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.73

日付: 2026-10-22

変更:
- 任意の既存記事更新許可と公開後点検の照合を追加

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python -m pytest tests/test_note_update_authorization.py tests/test_note_workflow_gate.py tests/test_note_work_packet_check.py tests/test_note_postpublish_review.py -q`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.72

日付: 2026-10-22

変更:
- 入力ガードの診断と照合上限、深いカードDOMの転送を修正

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `node --test tests/note_editor_guarded_input.test.mjs`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.71

日付: 2026-10-21

変更:
- 採用済みタグ参照資料の現版hashと検索意図をsettings/publishの必須検査に接続する。
- カード変換後に焦点が移っても、同じ文書と保護本文の保持を照合して終了する。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `Python関連441件成功、Node編集ガード53件成功`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.70

日付: 2026-10-20

変更:
- NPSの公開前確認を現在値へ更新し、固定SHAの共通preflight CIと履歴の例示文字列ratchetを導入
- READMEの概要・使い方・制約を明示し、詳しい制作・開発手順をdocsへ分離

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `全履歴のprivacyレビュー、repo-preflight公開ゲート、配布検査とローカル全体テストを実施。GitHub CIの未起動は成功扱いしない。`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.69

日付: 2026-10-20

変更:
- 採用済みの句点後改行を原稿・実HTML・保存後の必須ゲートへ接続

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `改行と入口の関連452テスト、独立レビュー、Note下書きの保存後読戻しを確認。全体CI同等検査は本PRで実行。`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

### 採用済みの句点後改行を必須検査へ接続

- 外部の著者設定から句点後改行を継承し、記事の指定漏れやfalseで規則が消えないようにする。
- 原稿の実本文をworkflow・authorship・prepublishで、Noteの実HTMLを改行・保存後cycle・公開前観測で検査する。
- HTMLソースの空白と実際のbrを分け、原稿との段落構造の一致も確認する。HTML欠落、記事ID欠落、同じ0件同士の比較による見逃しを回帰検査する。
- Markdownリンクの文末と入れ子リストのブロック境界を保持し、規則未採用settingsの互換性とUTF-8不正原稿のblocked判定を回帰検査する。
- 全体1911テスト成功・13件skipをローカルで確認。GitHub CIは課金制限により未起動。公開、リリース、他端末への反映は別工程。

## 0.2.68

日付: 2026-10-18

変更:
- 同名moduleが先に読み込まれていても、実ファイルを指定する共通loader（`scripts/nps_script_loader.py`）で同じ配布元の依存を取得し、公開module cacheと検索pathを変更しない。入口script間の兄弟module取得を同loaderへ統一し、同名の偽moduleが検索path先頭にあっても正本を使う回帰を追加。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `同配布元・異配布元・遅延import・初期化失敗・偽module混入の局所回帰。通常CIと実運用受入は別途確認する。`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.67

日付: 2026-10-18

変更:
- 語彙検査のリンク成立条件・同段落の複数行コード・Markdownブロック境界・空の例外配列を修正し、可視本文の見逃しと正常入力の誤停止を回帰検査する。
- 本人語彙の検査scriptを配布manifestへ宣言し、standalone環境でも既存の構成整合性検査を通す。
- 記事限定の履歴採用条件と本人語彙の必須検査を既存G2へ接続し、無根拠な例外を拒否する。
- 外部history policyの任意語彙規則を既存G2へ接続。記事別条件と全体条件を結合し、履歴が任意でも語彙検査を行う。
- 引用・資料名・保存原文の例外を既存sourceの許可参照・実hash・正確な現稿範囲へ束縛。無根拠な例外と本文更新後の古い例外を拒否する。
- 語彙規則・例外・可視本文・HTML表現・本文hash束縛の回帰検査を追加。意味や本人採否の認証は行わない。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.66

日付: 2026-10-16

変更:
- ハイパーリンク・埋め込み・末尾カード・タグ選定を既存確認一覧で分離し、リンク編集の構成承認と同一本文の履歴束縛を整合。標準pytest収集をCI対象へ固定し別worktree混入を防止。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python -m ruff check scripts tests`
- `python scripts/docs_sync_check.py --base-ref origin/main`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.65

- 公開前検査・package検証から個人識別子の固定値を除き、実ホームパスの拒否は維持する。拒否経路の回帰テストを追加。

日付: 2026-10-16

検証:
- `python -m pytest tests/test_provenance_leak_paths.py -q`

公開境界:
- Note 投稿、SNS 共有、外部告知、Release・タグ作成は未実行。

## 0.2.64

- 中断復旧journalへ実行時workspaceを束縛し、別の祖先を基点に再実行してもsnapshot/台帳を変更せず拒否する。

- 直接の全体手動検査では分岐feature・過去tagの共通履歴を検査し、通常イベント基点の祖先性要求と区別する。

- installerの全pointerも採用storageへ従わせ、任意階層の台帳ではworkspaceを明示してsnapshotの結線と中断復旧を行う。ローカル・CI共通verifierへ台帳CLIスモークを接続。固定版Ruffで構文・未定義名を通常CIの先頭から検査。

公開後レポートも採用した台帳ディレクトリを必須で受け取り、サンプル台帳への暗黙fallbackを除去。CIのサンプル集計は明示的にdataを指定。貢献ガイドの自動ゲートと外部workspace smokeも正本へ同期し、保存先と台帳内容・公開権限の区別を明確にしました。

画像・台帳も既存storageで外部保存先を選択でき、実台帳・公開snapshotをpackage内へ書く両CLIは、共通の出力境界で停止します。役割・出力・入力の固定packageパスも採用保存先へ統一しました。

PR・push・タグ・Release・手動実行の7正常と3拒否、および再利用jobとpackage-smokeの依存接続を既存package契約テストで毎回検査します。

日付: 2026-10-16

変更:
- MIT許諾と初回設定案内を採用。settingsの保存先を実制作へ接続し、両installerで実在する外部workspaceを必須化。既存test workflowの前提でrepo-preflightとratchetを毎回実行し、全対応イベントの基点を固定。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `関連テストと実CI、設定・workspace拒否、イベント全系列の6成功・3拒否、実workflow parserの未知値拒否を確認。初見の人間UATは未実施。`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。


## 0.2.63

日付: 2026-10-16

変更:
- 既知のhost設定NPS_PACKAGE_ROOTをpointer検査で解決し、非既定配置とHOME依存の不一致を防ぐ。未設定時は実checker所属package、空や相対値・未展開変数・式は拒否。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python -m pytest tests/test_skill_pointer_check.py -q`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.61

日付: 2026-10-16

変更:
- 公開plain textと制作Markdownの機械検査責務を分離し、秘密情報・内部メモの停止を維持する。
- pointerのHOME可搬表記を限定解決し、任意環境変数・shell式・欠落参照を拒否する。

検証:
- `python3 -m pytest tests/test_note_postpublish_review.py tests/test_skill_pointer_check.py tests/test_pre_publish_editorial_review.py tests/test_local_postpublish_observation.py -q`
- `python3 scripts/skill_pointer_check.py --installed-root WORKSPACE/.agents/skills --json`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.60

日付: 2026-10-16

変更:
- 公開後入口へ機械lint・trusted runtimeの全文点検照合・既存feedback追記読戻しを接続し、未実行や古い本文を点検完了にしない。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python -m pytest tests/test_note_postpublish_review.py tests/test_local_postpublish_observation.py tests/test_post_publish_context_proof.py -q`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.59

日付: 2026-10-16

変更:
- 画像なしを含むタイトル画の採否・理由を構成承認へ束縛し、既存v1画像ポリシーにも3候補の既定検査と移行手順を適用。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python -m pytest tests/test_note_workflow_gate.py tests/test_editor_workflow_entry.py tests/test_image_reference_gate.py -q`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.58

日付: 2026-10-16

変更:
- 目次・挿絵・埋め込みの提案と対話を必須化し、タグの本文・発見性・ブランド根拠と画像3候補の確認を既存ゲートへ統合。
- 安全規則と既読制作・公開後文書を日本語化し、公開パッケージの作業記録から個人絶対パスを除去。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python -m pytest scripts/test_skill_integration.py tests -q`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.57

日付: 2026-10-14

変更:
- Allow portable evidence-relative history source paths while preserving canonical reference checks.

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `136 history/mutable and 252 workflow/PDCA tests passed locally; relocation and forbidden-source cases included.`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.56

日付: 2026-10-14

変更:
- 履歴入力検査を利用するworkflow gateの単独file loader互換を復旧。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `通常コマンドに加え、fresh subprocessからのstandalone module読取りを回帰検査。`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.55

日付: 2026-10-14

変更:
- 操作計画は既知の非公開操作だけを許可し、再投稿・交差投稿・未知操作を停止する。
- 履歴検査の入力pathは初回読取り前に実体へ束縛し、同内容の別実体へのsymlink差替えを検出する。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python3 -m pytest scripts/test_skill_integration.py tests -q`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.54

日付: 2026-10-14

変更:
- 公開前の観測は既知の未公開状態だけを受理し、不明な公開状態を停止する。
- 画像ゲート回帰テストのimport対象を同梱scriptsへ固定し、親workspaceと同名moduleの取り違えを防ぐ。

- 履歴の記録・差分・保存snapshotを役割付きの実pathで返し、同じhashの本文によるsnapshotの代用を防ぐ。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.53

日付: 2026-10-13

変更:
- 公開前の本人操作境界、記事同一性、保存読戻し、公開操作の検査をproductionとcontinuationで維持する。
- 履歴ゲートが検証したfeedback参照の実体pathとhashを返し、外側の検査完了時まで同じ入力版へ結び付ける。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python3 -m pytest scripts/test_skill_integration.py tests -q`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.52

日付: 2026-10-13

変更:
- 制作本文と継続記事のQAで記事IDと文体参照を共通検査し、任意履歴policyでもID欠落を停止する。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python3 -m pytest tests/test_history_learning_gate.py tests/test_content_pdca_check.py -q (90 passed)`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.51

日付: 2026-10-13

変更:
- 履歴必須policyの明示article profileとrequired_sourcesをG1/G2で共通照合し、未知ID・候補欠落・引用差替えを停止する。
- 既存履歴適用のsettings付き共通APIと隔離CLIをQA・workflow・authorshipへ接続し、本文と告知のsnapshot取り違えを拒否する。意味・文体・本人採用の自動保証はしない。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.50

日付: 2026-10-13

変更:
- 履歴適用の著者性検査で、本文hashと履歴出典を同じsidecar読取りsnapshotへ束縛する。検証後の差替えを拒否し、制作前の履歴候補回収は維持する。
- 有効なsnapshot、本文hashの欠落・不一致、capture前後の差替えを回帰検査する。原稿本文・本人原文・公開承認の境界は変更しない。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.49

日付: 2026-10-11

画像参照の検査と記事profileへの接続。パッケージ内の版更新であり、GitHub release/tagは未作成。

- `image_reference_gate.py` を画像検査の正本として追加。参照manifest・実画像hash・必要な役割・生成添付path・prompt・生成output・同じoutputへの観察を照合する。
- 生成前、原稿QA、workflow edit/settings/publish、画像反映と保存前の既存入口へ接続。操作stageでは実対象のoutput指定を必須とし、画像証拠hashを承認subjectへ含める。
- 既存 `style.article_profiles` の参照配列を維持し、`references` と記事別画像policy/receiptを持つobjectも扱う。記事ID省略を拒否し、他記事へ画像receiptを流用しない。
- 過去修正の回収と現稿への適用を既存feedback／authorship／品質／workflowへ接続。外部styleの明示ポリシーで有効にし、履歴候補と本文after・現在hashを別々に照合する。本文／設定編集の画像stage誤分類、scoped画像receiptの別記事流用、検証後の未検証bytesへのhash束縛も回帰で防ぐ。
- タグ設計を既存settings/publishゲートへ接続。本文hash・役割・選定理由・前話比較・設定タグの一致を確認し、公開時は既存タグpreflightの実選択を必須とする。候補タグを選択済みへ昇格させず、5〜10はlocal policyとして明記する。
- URL埋込みguardはnativeのTab.ax.get/pasteにも対応。document.hasFocus未提供は無条件に許可せず、同じTabのAX本文行・focused ID・本文全文と、2回のfresh DOM／AX照合を通した場合だけ入力する。false focus・対象違い・truncate・選択driftは入力前に停止する。
- 固有の人物名、参照path、PNGは利用者の外部workspaceに保持する。ローカルJSONの整合を、モデルの注意・実際の視認・本人採用・承認の真正性とは扱わない。
- 欠損／改変参照、添付なし、別人物、output替え、異なるQA hash、操作対象省略、単独／集約stageの承認整合、記事profile境界を回帰検査する。

## 0.2.48

日付: 2026-10-11

制作前の文体・採否履歴の読取り。パッケージ内の版更新であり、GitHub release/tagは未作成。

- 既存 `note_feedback.py` に読取り専用の `--readback` を追加し、外部settingsから現在の文体参照本文・記事別採否履歴・実差分を取得する。既存の保存先・版照合を再利用する。
- 標準出力JSONをコンソール文字コードに依存せず返し、復号後の日本語・emoji・原文hashを保持する。cp1252環境の読取り・停止・保存互換を回帰検査する。
- 制作スキルの先頭で、本文案を書く前の内容読取りを必須にする。参照hashの一致を意味理解・本人採用・公開許可へ読み替えず、適用・保全・保留した直しを返す。
- 本人の体験・感情・判断を必須項目として作文させるテンプレートは追加しない。個人の語彙・学習は利用者側の既存正本に保持する。

## ローカル統合候補（2026-10-06・未配送）

上流0.2.40を基準に、既存の検索QA、POSIX pointer、原稿保全、目次・編集session・論点対応・packet検査を統合。上流と同一の配布版とは扱わない。原文と公開判断の境界は維持する。

このファイルは `note-publishing-suite` パッケージの版管理正本。
GitHub リリースやタグは別の公開操作として扱い、ここにはパッケージ内の
変更内容と検証範囲だけを記録する。

## 0.2.47

日付: 2026-10-10

変更:
- URL単一入力ガードを救済し、fresh DOM・空段落・前後の全block照合とpending/blocked停止を既存の操作説明へ接続する。現在版のworkflow承認とsurface指定を維持する。
- 任意のNode.js 22経路として宣言し、CIで34ケースの隔離検査を実行する。実ブラウザ互換性、保存、公開はローカル検査から保証しない。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `sh scripts/verify_public_package.sh`
- `python scripts/docs_sync_check.py --base-ref origin/main`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.46

日付: 2026-10-09

変更:
- 未吸収の検索QA、POSIX pointer、原稿保全、目次・編集session・論点・workpacket検査を既存入口へ統合し、著者構造レビューを共通原稿QAへ接続する。
- 不正入力の拒否、workspace保存先とdry-run、編集途中失敗後の停止を回帰検査する。既存の品質報告と本人承認・公開手前停止を維持する。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `sh scripts/verify_public_package.sh`
- `python scripts/docs_sync_check.py --base-ref origin/main`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.45

日付: 2026-10-09

変更:
- 既存research段階に任意の品質ポリシーを接続し、SEO・AIO・Note・タグ・PDCA・関連作者と旬の根拠、鮮度、保存ハッシュ、採否と5段階の計画を検査する。旧Markdown報告はポリシー未設定時に維持する。
- 承認済み制作計画の明示的なフッター省略を空links・空nodesと照合する。未承認省略と矛盾は停止し、採用時の必須リンク検査は維持する。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `sh scripts/verify_public_package.sh`
- `python scripts/docs_sync_check.py --base-ref origin/main`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.44

日付: 2026-10-07

変更:
- main の 0.2.43（#53）に追従し、受け入れテスト手順書を含む本 PR のパッケージ版を 0.2.44 に上げた。
- 初めて使う人がローカルだけで主要な流れと公開直前の停止位置を確かめる受け入れテスト手順書 `USER_TEST.md`（4ケース）を追加し、README と package.yaml から参照できるようにした。受け入れテストの合格は Note 公開の承認ではないことを明記した。
- 公開パッケージ検証スクリプトで、ローカル下書きQAの証跡を一時ファイルへ出力して終了後に削除し、検証後もリポジトリ内の追跡ファイルが変わらないことをテストで確かめるようにした。
- CHANGELOG の版の並びを新しい順に直し、その順序を確かめるテストを追加した。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `sh scripts/verify_public_package.sh`
- `python scripts/docs_sync_check.py --base-ref origin/main`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.43

日付: 2026-10-06

変更:
- 公開済み記事の扉絵・本文更新を、元下書きなしで公開APIの現在値から照合する読み取り専用ルートを追加。画像変換クエリを除いた素材IDを比較し、仮のdraft来歴は生成しない。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python scripts/check_version_bump.py`（基準: `origin/main`）
- `python scripts/docs_sync_check.py --base-ref origin/main`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.42

日付: 2026-10-06

変更:
- 初めて使う人がローカルだけで主要な流れと公開直前の停止位置を確かめる受け入れテスト手順書 `USER_TEST.md`（4ケース）を追加し、README と package.yaml から参照できるようにした。受け入れテストの合格は Note 公開の承認ではないことを明記した。
- 公開パッケージ検証スクリプトで、ローカル下書きQAの証跡を一時ファイルへ出力して終了後に削除し、検証後もリポジトリ内の追跡ファイルが変わらないことをテストで確かめるようにした。
- CHANGELOG の版の並びを新しい順に直し、その順序を確かめるテストを追加した。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `sh scripts/verify_public_package.sh`
- `python scripts/docs_sync_check.py --base-ref origin/main`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.41

日付: 2026-10-06

変更:
- macOSのクリップボード同意ファイル検査で、ACL属性が存在しないことを同じファイル記述子で確かめてから許可するようにした。ACL非対応や判定失敗は従来どおり拒否する。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python scripts/check_version_bump.py`（基準: `origin/main`）
- `python scripts/docs_sync_check.py --base-ref origin/main`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.40

日付: 2026-10-06

変更:
- 内部ブラウザのローカル証跡による公開snapshot／台帳更新を追加。dry-runを既定にし、記事IDの冪等更新と未知field保持、二台帳の中断復旧を実装。
- 現在版の承認一覧、目次・末尾カードの独立採否、外部の記事別feedback読戻しを追加。
- タグ候補と選択済みタグを区別し、同時変更を検出する純粋事前照合と回帰検証を追加。
- 利用者固有の編集CLI・個人設定・台帳・実記事の証跡は配布へ含めない。
- 原稿・証跡・snapshotと台帳・journalのalias衝突を拒否し、SHA-256形式検査を保持。

検証:
- 全体実行では既存clipboardのDarwin ACL検査17件が失敗。今回の配送差分に含まない環境依存の未解決事項として扱う。
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python3 -m pytest scripts/test_skill_integration.py tests --ignore=tests/test_clipboard_bridge.py -q`
- `sh scripts/verify_public_package.sh --json`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.39

日付: 2026-10-05

変更:
- 記事制作の3経路と版ごとの人間承認・外部設定読戻しcheckerを追加
- 著者性APIからの呼出しにも原資料と短縮予算の検査を適用

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.38

日付: 2026-10-02

変更:
- レビュー表示が `--!>` で閉じた由来コメントを認識し（検査器と同じ）、先頭の BOM があっても frontmatter を外すようにした。未知の種類は色なしの塊にする。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python scripts/docs_sync_check.py --base-ref origin/main`
- `sh scripts/verify_public_package.sh`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.37

日付: 2026-10-02

変更:
- 通常本文の空行を段落境界、段落内の原稿改行をbrへ変換。期待・観測soft-break配列の欠落、型不正、段落別不一致を改行gateで拒否し、外部記事カードのDOM検査契約を同期。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`: 364件合格、10件skip、18件失敗。ACL17件は変更前にも再現。standalone fixtureの生成物drift1件は単独再検査で合格。
- `python3 -m pytest tests/test_note_linebreak_gate.py tests/test_note_virtual_preview.py tests/test_note_editor_prepublish_verify.py tests/test_docs_sync_check.py -q: 92件合格。`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.36

日付: 2026-10-02

変更:
- 内部ブラウザ指定を最初の接続確認から保持し、内部Playwrightと外部MCPを区別。内部限定時のChrome切替質問を候補から除外。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python3 scripts/note_editor_pdca_failure_check.py --json`
- `独立担当による操作手順差分レビュー。ブラウザ実行による再発防止は未実測。`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.35

日付: 2026-10-02

変更:
- Note読書用プレビューのMarkdown画像を既存の安全な画像処理で描画。相対パスとHTTPS画像、代替テキストの保護、リンク誤変換を検証。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `画像と装飾の回帰テストおよび文書同期テスト: 34件合格。全体テスト: 349件合格、10件skip、macOSクリップボード権限検査17件失敗は変更前にも再現。`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.34

日付: 2026-10-02

変更:
- Note読書用プレビューの背景を白にし、light表示を明示。公開ページCSSの再照合値と近似の限界を記録。
- 制作スキルで、読書表示・由来レビュー・編集診断の入口を区別。

検証:
- `python3 -m pytest tests/test_note_virtual_preview.py -q`: 12件PASS。
- 作成担当セルフレビューと主担当の独立差分レビュー: 指摘なし。
- GitHub CIの初回で版更新不足とdocs-sync不足を検出し、既存の版管理契約に従い修正。

公開境界:
- Note投稿、SNS共有、GitHubリリース・タグ作成、公開範囲変更は未実行。

## 0.2.33

日付: 2026-10-02

変更:
- 読書用プレビューから設定と内部コメントと診断枠を除外し、編集診断を --diagnostics に分離。由来レビューとQA手順を統一。本人確認と保留の停止条件は維持。
- 既存の設定解析を再利用し、コメント終端・空設定・リンクの二重エスケープを修正。原稿非変更を含む回帰テストを追加。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python -m pytest tests/test_note_virtual_preview.py tests/test_provenance_draft_review.py tests/test_docs_sync_check.py -q`
- `独立レビュー完了。全体テストのmacOSクリップボード権限検査17失敗は変更前にも再現。`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.32

日付: 2026-10-02

変更:
- `note_preview.py` が下書き冒頭の frontmatter（先頭の `---` 行から次の `---` 行まで）を本文から外すように修正。設定の行が段落・箇条書きとして出ていた。本文中の区切り線は従来どおり。
- `--review-provenance` の表示を、由来ごとの色の塊（本人=緑、AIのつなぎ=黄、資料の事実=青、保留=赤）に変更。見出しは塊の外に出し、種類ごとの件数と本文の字数（空白・リンク先・見出し・保留を除く）を上に出す。1文1行の改行は `<br>` で残し、リンクは別タブで開く。ダークモードに対応。
- リンク先 URL の `&` などが二重に escape されて開けなかった問題を修正。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python scripts/docs_sync_check.py --base-ref origin/main`
- `sh scripts/verify_public_package.sh`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.31

日付: 2026-09-29

変更:
- 記事ごとの末尾選定計画とDOM順snapshotの照合を実入口へ接続。空計画・未レビュー・不一致・手動境界を停止し、live観測や公開承認とは分ける。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.30

日付: 2026-09-24

変更:
- 開発保証スイート（repo-preflight + ai-ratchet-gate）を 関連プロジェクト と同じ吸収パターンで追加。workflow_dispatch のみ。inspection ロジックは持ち込まない。
- PREFLIGHT.md・.repo-preflight-consistency.json・.ai-ratchet-gate/baseline.txt・requirements-tools.txt・repository-guarantees.yml を追加。

検証:
- `python -m pip install --require-hashes -r requirements-tools.txt && python -m ai_ratchet_gate --repo .`
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python scripts/docs_sync_check.py --base-ref origin/main`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.29

日付: 2026-09-21

変更:
- Noteエディタ作業の記事ごとPDCA cycle受領JSONを scripts/note_editor_pdca_cycle_check.py で検査する経路を追加した。
- 1 action・前後DOM証跡・非公開・routeあたり最大2回試行の契約を package.yaml / note-editor-ops / PDCA orchestration に配線した。
- cycle受領検査で top-level state と終端 cycle の整合、および証跡の非空文字列/非負整数型を fail-closed にした。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python -m pytest -q tests/test_note_editor_pdca_cycle_check.py`
- `python scripts/docs_sync_check.py --base-ref origin/main`
- `VERSION_BUMP_BASE_REF=origin/main python scripts/check_version_bump.py`
- `python scripts/note_editor_pdca_failure_check.py --json`

公開境界:
- 人間承認後に公開PR #27を更新。マージ・リリース・タグ作成は未実行。
- Note 投稿、予約投稿、SNS 共有、外部告知、リポジトリ公開範囲変更は未実行。
- PR #27 のタイトル・本文はリポジトリ契約どおり日本語へ書き換える必要がある（エージェント権限では編集不可）。推奨タイトル: 「Noteエディタ作業向けの検証済みPDCA cycle受領検査を追加」。

日付: 2026-09-13

変更:
- OSクリップボードの全入口に利用者・端末・期限・操作範囲の事前同意ゲートを追加。共同利用者へ承認を継承せず、未確認なら副作用前に停止する。
- 画像upload境界の文書・policy・checkerを条件付き経路に統一。
- 同意記録の保存先・ファイルの所有者と権限を検査し、別OS利用者による記録の差し替えを防ぐ。

検証:
- `python -m pytest -q`（Windows、保存権限修正後: 296 passed / 16 skipped）
- `python3 -m pytest tests/test_clipboard_bridge.py -q`（Linux: 123 passed / Mac専用2 skipped）
- `python scripts/note_image_upload_boundary_check.py --json`
- `python scripts/docs_sync_check.py --base-ref origin/main`
- `python scripts/package_consistency_check.py --json`
- `python scripts/check_version_bump.py`（Windowsでは `PYTHONUTF8=1`）
- Macの実クリップボード操作は未検証。別途利用者が実機確認する。

公開境界:
- 人間承認後に公開PR #26を作成。マージ・リリース・タグ作成は未実行。
- Note 投稿、予約投稿、SNS共有、外部告知、同意の代理発行は未実行。

## 0.2.27

日付: 2026-09-13

変更:
- 3部門設計ドキュメント、クリップボード橋渡し、仮想noteプレビュー移植、口述モードを追加
- package.yaml に clipboard_bridge / note_virtual_preview を宣言

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python scripts/docs_sync_check.py --base-ref origin/main --review-file /tmp/nps-doc-review.txt`
- `python scripts/package_consistency_check.py --json`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.26

日付: 2026-08-28

変更:
- サンプル下書き1本を着想→QA→公開直前停止まで通し、run_local_draft_qa_proof.py の証跡を再生成した（external_actions_performed: []）
- axis-2 の fixture パッケージ証跡を更新。実記事 live / エディタ引き継ぎは人間作業のまま

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python scripts/run_local_draft_qa_proof.py --json`
- `python -m pytest scripts/test_skill_integration.py tests/test_content_pdca_check.py tests/test_topic_status_check.py -q`
- `python scripts/topic_status_check.py --json`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.25

日付: 2026-08-25

変更:
- repo-preflight 整合性ゲートを shadow モードで採用

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `consistency_gate.py --repo . --json => status=pass`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.24

日付: 2026-08-06

変更:
- PR で package-smoke が確実に付くよう CI を強化し、NPS 運用スモーク手順を CONTRIBUTING に固定した。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python -m pytest scripts/test_skill_integration.py -q; python scripts/docs_sync_check.py --base-ref origin/main`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.23

日付: 2026-08-06

変更:
- README を動画なし運用を正面にし、デモ動画は任意枠に下げた。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python scripts/render_readme.py; python -m pytest scripts/test_skill_integration.py -q`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.22

日付: 2026-08-06

変更:
- NPSとして使う導線をREADMEに整理し、使い方動画の置き場 assets/demo を追加した。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python scripts/render_readme.py; python -m pytest scripts/test_skill_integration.py tests/test_topic_status_check.py -q; pwsh -NoProfile -File scripts/verify_public_package.ps1`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.21

日付: 2026-08-06

変更:
- PUBLIC_READY を v0.2.20 Release 反映済みの状態へ更新し、外部追加スキャナ候補（旧 CHINJU 記載）を採用しない方針に整理した。
- 話題統合台帳の停止線と worktree 方針を現状に合わせ、status 語彙検査を現行軸に追随した。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python -m pytest tests/test_topic_status_check.py -q`
- `python scripts/topic_status_check.py --json`
- `python scripts/check_version_bump.py`
- `pwsh -NoProfile -File scripts/verify_public_package.ps1`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- 追加の GitHub リリース作成、tag 作成、リポジトリ公開範囲変更は未実行。

## 0.2.20

日付: 2026-08-06

変更:
- 問答・著者性・短縮防止・改行・図版・Browser復旧ゲートとWindows Codex配布経路を追加した。
- 問答packet APIの質問数を1〜5件へ制限し、dirty worktreeにだけ残っていた回帰テストを正規候補へ回収した。
- Browser復旧はread-only計画専用にし、自己申告JSONによるprocess終了機能を公開packageから除外した。
- Linuxの通常テストとWindows installer smokeをCIで分離し、既存のpointer検査と公開package verifierを再利用した。
- 初回PR CIで検出したpointer path終端の部分一致と、Windows cloneの生成HTML改行driftを回帰テスト付きで修正した。
- PDCA failure ledger (`data/note_editor_pdca_failure_patterns.json`) と docs 配線を回収し、default path の運用保証テストを追加した。
- 話題統合台帳 (`references/topic-consolidation-ledger.md`) と `scripts/topic_status_check.py` で、ローカル話題の chat 化と fixture TODO 混同を止めた。
- issue-drafts の吸収済み課題 (1〜3 / 埋め込み制約) を ledger と揃えた。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `pwsh -NoProfile -File scripts/verify_public_package.ps1`
- `python scripts/docs_sync_check.py --base-ref origin/main`
- `python scripts/package_consistency_check.py --json`
- `python scripts/note_editor_pdca_failure_check.py --json`
- `python scripts/topic_status_check.py --json`
- `python -m pytest tests/test_note_interview_packet.py tests/test_note_browser_transport_recovery.py tests/test_windows_skill_installer.py tests/test_note_editor_pdca_failure_check.py tests/test_topic_status_check.py -q`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.19

日付: 2026-08-05

変更:
- プロジェクト正本境界をPROJECT_SSOT.mdへ集約し、内部設計文書を公開packageから分離した。根拠ラベル対応の下書きレビュー経路を取り込んだ。
- 版はpatchに留める。`0.3.0`はrelease判断と同時に別レビューで扱う。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `pwsh -NoProfile -File scripts/verify_public_package.ps1`
- `python scripts/docs_sync_check.py --base-ref origin/main`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.18

日付: 2026-08-05

変更:
- README冒頭に公開停止線を示すワークフロー図を追加。
- ローカルREADMEレンダラーへ安全な画像表示を追加。

検証:
- `python3 -m pytest scripts/test_skill_integration.py tests -q`
- `python3 scripts/docs_sync_check.py --base-ref origin/main`
- `sh scripts/verify_public_package.sh`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.17

日付: 2026-08-05

変更:
- `package.yaml`にドキュメント同期契約を追加した。
- 生成物差分、関連文書レビュー漏れ、必須文書欠損をread-onlyで検出するcheckerとPR workflowを追加した。
- CI失敗時に検査JSONと生成物patchをartifactとして取得できるようにした。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python scripts/docs_sync_check.py --base-ref origin/main`
- `sh scripts/verify_public_package.sh`

公開境界:
- CI権限は`contents: read`。commit、push、PR編集は行わない。
- Note投稿、予約投稿、SNS共有、外部告知、GitHub release、tag、repository visibility変更は未実行。

## 0.2.16

日付: 2026-08-05

変更:
- READMEの視覚的な階層と折りたたみ表示を改善

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `README renderer contract tests`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.15

日付: 2026-08-05

変更:
- 内部のドキュメント同期設計を公開パッケージからProjects側の設計正本へ移し、パッケージには実装済みの契約だけを置く境界へ修正した。
- 0.2.14のREADME改善と0.2.13のGitHub公開名義修正は維持した。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `sh scripts/verify_public_package.sh`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.14

日付: 2026-08-05

変更:
- README の初回導線を短く再構成

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `README contract tests`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.13

日付: 2026-08-04

変更:
- GitHubの非公開メール保護と両立するよう、公開commitの正規名義をnexus-ai-2045のnoreplyアドレスへ更新した。

検証:
- `python -m pytest scripts/test_skill_integration.py -q`（34件）
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify_public_package.ps1`（265項目）
- `public-readiness readiness_scan.py`（人間レビュー前の停止条件を確認）

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.11

日付: 2026-07-16

変更:
- Note editorのBrowser能力表を読み取り、入力、file upload、手動操作に分けて整理した。
- 別note、tab、Browser surface、accountの切替、または現在の会話で未承認のread-onlyからwriteへの変更前にユーザー確認を必須化した。
- 能力非対応は再試行0回、同一対象の接続・DOM状態ズレは1回までとし、fallback順を固定した。

検証:
- 人間レビュー前にpackage contract testとpublic package verificationを実行する。

公開境界:
- Note投稿、予約投稿、SNS共有、外部告知は未実行。
- package変更はcommit、pushし、Draft PRとして人間レビューへ提出した。GitHubリリース、tag作成は未実行。

## 0.2.10

日付: 2026-07-16

変更:
- `post_publish.py --ledger-dir`でworkspace固有のprivate台帳を注入可能にした。
- draft ledgerを追記ではなく一意な公開状態遷移として更新するようにした。
- 公開本文snapshot、SHA-256、公開版との差分、見出し画像確認をledgerへ記録可能にした。
- `note_diff_check.py --snapshot-out`で公開本文snapshotとSHA-256を同時に生成可能にした。

検証:
- 人間レビュー前に実行し、結果をレビューpacketへ記録する。

公開境界:
- Note投稿、予約投稿、SNS共有、外部告知は未実行。
- commit、push、PR、GitHubリリース、tag作成は人間レビュー後まで未実行。

## 0.2.9

日付: 2026-07-14

変更:
- READMEの初見導線とHTMLレンダリングを改善

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `pytest 72 passed / public package 31 checks passed`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.8

日付: 2026-07-13

変更:
- `note-publishing-suite` の独立 repo worktree を復旧し、Claude Code pointer の
  package root を独立正本へ再インストールした。
- 2026-07-13 の Note editor 実測として、`text/html` paste、hidden WebView、
  DOM selection の tick、連続画像 separator、CDN 取りこぼしを正本へ反映した。
- `cmux_dom_file_paste` を明示確認必須の画像経路として追加し、OS clipboard、
  Cookie、note API を使わない browser-scoped route に限定した。
- `scripts/skill_pointer_check.py`、回帰テスト、CI、pre-commit hook template を追加し、
  正本 pointer の消失を fail-closed で検知するようにした。

検証:
- `python3 -m pytest scripts/test_skill_integration.py tests -q`
- `python3 scripts/skill_pointer_check.py --installed-root "$HOME/.claude/skills" --json`
- `python3 scripts/note_image_upload_boundary_check.py --json`

公開境界:
- Note 投稿、下書き保存、予約投稿、SNS 共有、外部告知は未実行。
- git push、GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.7

日付: 2026-06-22

変更:
- package version の自動採番スクリプトを追加し、README / rendered HTML / CHANGELOG の版管理メタデータを一括更新できるようにした。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python scripts/check_version_bump.py`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.6

日付: 2026-06-22

変更:
- root `AGENTS.md` を追加し、公開、広域共有、repository visibility 変更の
  人間レビュー必須ゲートを repository 入口に明記した。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- GitHub Actions `package-smoke`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.5

日付: 2026-06-22

変更:
- Windows / PowerShell 環境で `sh` が無い場合でも、
  standalone clone verifier lane が `scripts/verify_public_package.ps1 -Json`
  に fallback して動くようにした。
- standalone clone fixture の統合テストも、`sh` がある環境では
  `verify_public_package.sh`、無い環境では PowerShell verifier を使うようにした。

検証:
- `python -m pytest scripts/test_skill_integration.py tests/test_content_pdca_check.py tests/test_note_image_upload_boundary.py tests/test_note_editor_prepublish_verify.py tests/test_review_draft_cli.py -q`
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify_public_package.ps1`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.4

日付: 2026-06-20

変更:
- `scripts/review_draft.py` を追加し、`build-context-card` と
  `review-draft` の CLI flow を実装した。
- `review-draft` は `review-intent` ではなく、`build_context_card` /
  `review_draft` 経路で verdict、reason_codes、confirmation_questions、
  context_card を返す契約にした。
- `content/drafts/sample-note-prepublish-fixture.md` を使う fixture-backed
  local review を追加し、editor fixture は公開候補として進めず blocked にする。
- Mac / Linux 向けの `scripts/verify_public_package.sh` を primary verifier にし、
  PowerShell verifier は Windows / PowerShell equivalent として残した。
- `data/note_editor_prepublish_observation.fixture.json` を追加し、
  `<observation.json>` placeholder なしで公開前観測 checker を実行できるようにした。

検証:
- `sh scripts/verify_public_package.sh`
- `python3 -m pytest scripts/test_skill_integration.py tests -q`
- `python3 scripts/note_editor_prepublish_verify.py data/note_editor_prepublish_observation.fixture.json --json`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.3

日付: 2026-06-18

変更:
- package version と README / CHANGELOG の整合性を公開検証の必須条件にした。
- verifier の実行要件を PowerShell、Python、git として明記し、
  Python なしで動くように読める誤保証を禁止語として検査するようにした。
- standalone clone fixture から verifier 自身を再実行し、単独 repo 形態でも
  公開操作なしで検証できることを確認するようにした。
- `scripts/provenance_label_check.py` を追加し、
  `source_pack_locked_with_user_speech_priority` の draft で `user-said`、
  `external-fact`、`assistant-organized`、`hold` の境界を検査できるようにした。
- Caramel 完全解説風の draft fixture を追加し、本人発言優先構成の
  provenance label 回帰ケースにした。

検証:
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify_public_package.ps1`
- `python -m pytest scripts/test_skill_integration.py tests/test_content_pdca_check.py tests/test_note_image_upload_boundary.py tests/test_note_editor_prepublish_verify.py`
- `python scripts/provenance_label_check.py content/drafts/caramel-provenance-label-fixture.md --json`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.1

日付: 2026-06-17

変更:
- GitHub identity guard のユーザー固有 denylist を
  `data/github_identity_guard_policy.local.json` に分離し、公開パッケージには
  合成例の `data/github_identity_guard_policy.example.json` だけを含めるようにした。
- identity leak の回帰テストを、一時 local policy と一時 fixture ファイルで
  検出する形に戻した。
- Note エディタ公開手前の観測 JSON を検査する
  `scripts/note_editor_prepublish_verify.py` を追加。
- TOP 画像、目次、フッター埋め込み、マガジン、タグ重複、記事タイプ、
  最終投稿ボタン未操作を公開手前 QA として明示。
- in-app Browser の URL 制約、画像アップロード不可、リンクカード誤配置、
  タグ重複の停止線を editor / ops スキルへ反映。
- `scripts/verify_public_package.ps1` に embedded copy と standalone clone fixture の
  GitHub identity guard 検証レーンを追加し、さらに standalone clone fixture 側から
  verifier 自身を再実行して、公開操作なしで両形態を確認できるようにした。
- PR でパッケージ実体が変わった場合に、`package.yaml` の semver が
  base branch より上がっていることを確認する
  `scripts/check_version_bump.py` を追加。
- 採番検査を `0.2.0` 固定値ではなく、`package.yaml`、README、
  CHANGELOG の整合性と base branch からの増分確認に変更。

検証:
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify_public_package.ps1`
- `python -m pytest scripts/test_skill_integration.py tests/test_content_pdca_check.py tests/test_note_image_upload_boundary.py tests/test_note_editor_prepublish_verify.py`
- `python scripts/github_identity_guard.py --json`
- `python scripts/github_identity_guard.py --policy data/github_identity_guard_policy.local.json --json`
- `python scripts/note_editor_prepublish_verify.py <observation.json> --json`
- `python scripts/check_version_bump.py`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.0

日付: 2026-06-16

変更:
- 公開ゲート、Note エディタ境界、保証ラチェット、根拠設計の運用文書を強化。
- `scripts/provenance_leak_check.py` を追加し、ローカルパス、実行時メモリ、
  非公開リポジトリ名、出典外の運用文字列を PR 前に検出できるようにした。
- ユーザー固有の denylist を
  `data/provenance_leak_policy.local.json` に分離し、公開パッケージへ直書きしない
  ルールを追加。
- 実記事下書きを契約テストの必須検査材料から外し、
  `content/drafts/sample-note-prepublish-fixture.md` を QA 確認の正規検査材料にした。
- `data/post_publish_check_results.jsonl` の確認結果を版管理対象として更新。

検証:
- `python -m pytest scripts/test_skill_integration.py tests/test_content_pdca_check.py tests/test_note_image_upload_boundary.py`
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify_public_package.ps1`
- `python scripts/provenance_leak_check.py --scope all --json`
- `python scripts/note_image_upload_boundary_check.py --json`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リポジトリ公開範囲の変更、GitHub リリース作成、タグ作成は未実行。

## 0.1.2

前版:
- Note 投稿一気通貫の親スキル、子スキル、README、ROADMAP、公開準備
  検証を持つ公開パッケージ基準線。

