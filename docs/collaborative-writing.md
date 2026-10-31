# 対話を続けながら骨組みと全文を育てる

NPSの既存の共同執筆を、テーマ単位の対話と複数の記事に結びます。記事を作る前から話し始め、骨組みや全文ができた後も問い直せます。チャットから使う保存処理とローカル編集画面は同じです。公開・Noteへの書込みはこの画面から実行しません。

## 最初の確認

Python 3.10以降（既存CLI設定を読むAI接続は3.11以降）と、利用者が採用したpackage外のworkspace設定を使います。新しい保存先を自動作成・移動する初期化処理ではありません。既存の`storage.sources`、`storage.drafts`、`storage.feedback`と文体参照を読み戻します。履歴policyが明示profileを必須にしている場合は、採用済みの`--profile-id`を指定してください。

```sh
python scripts/note_writing_server.py --help
python scripts/note_writing_server.py --settings /path/to/workspace/settings.json --preflight
python scripts/note_writing_server.py --settings /path/to/workspace/settings.json --dry-run
```

`--preflight`と`--dry-run`は設定の読取りのみです。サーバー起動、保存先の作成、AI通信を行いません。保存先の境界や必須参照に問題がある場合は理由を返します。設定ファイルを動作中に変更した場合は、内容を確認してサーバーを再起動します。

## ローカル編集画面

初回に画面をbuildしてから起動します。Node.jsとnpmは画面のbuild用です。

```sh
cd writing-app
npm ci
npm test
npm run build
cd ..
python scripts/note_writing_server.py --settings /path/to/workspace/settings.json
```

起動時のJSONにループバックのURLを表示します。通常ブラウザまたは内部ブラウザで開きます。`--port`でportを指定できます。終了は起動したターミナルのCtrl+Cです。LANやインターネットへ公開しないでください。

1. テーマを作り、対話から始めます。AIに返す前に本人の発言を保存します。
2. 必要になったら記事を作ります。一つのテーマから複数記事へ分けられます。既存稿は元の場所で開き、既存の骨組みも指定できます。
3. 素材欄に、読んでよいworkspace内のファイルpathを指定します。元資料は変更せず、取り込んだ版を保存します。
4. 「骨組みを提案」「本文案を提案」で、対話・選んだ素材・文体参照から候補を作ります。候補を作るだけでは現稿を置換しません。
5. 本文を記事の見た目のまま直接編集します。選択範囲へコメントを付け、対話を続けられます。
6. 提案一覧で原文・AIの意図・変更案を全文比較し、選んだ案だけを採用・見送り・保留にします。
7. 保存・取消し・再読込み後も、テーマ、記事、採否、本文の続きを使えます。

対応する書式は見出し、段落、太字、斜体、リンク、箇条書き、引用、段落内改行です。未対応の表・図・埋め込み等は元の内容を保持する読取り専用ブロックにします。原資料への逆書込みや、由来ラベルからの本人採用の推定は行いません。

## AIとの接続

初版は、正式な`codex exec`を使う任意の接続です。CLIのインストール、認証、利用枠、生成成功を分けて扱います。既存ログインを使い、ログイン切替・契約変更・認証情報の保存は行いません。利用枠が分からない場合は不明と表示します。`--model`を省略すると既存CLI設定を使います。

生成要求には、選んだテーマの対話、素材、対象記事、コメント、採否、採用済み文体参照を渡します。他記事の本文やworkspace全体を自動送信しません。大きすぎる入力は無断で要約せず止めます。Codexは一時フォルダーからread-onlyで呼び、schema付きの候補を受け取ります。[公式の非対話実行仕様](https://learn.chatgpt.com/docs/non-interactive-mode)に従います。

生成中も本人の文章を保持します。応答までに対話や本文が変わった場合は、その候補を自動反映せず再比較へ戻します。時間切れ・接続失敗で現稿を消しません。

## 保存・採否と復旧

本文の正本は`storage.drafts`のMarkdownです。テーマの対話と指定素材は`storage.sources`に内容のhashを伴って保存します。テーマの関連・コメント・未採用案は`storage.feedback/_themes`、記事別採否は既存feedback形式を使います。編集画面のキャッシュを本文の別正本にしません。

採否の初期範囲はこの変更だけです。記事全体や今後の文体への採用を、局所の修正から自動昇格しません。「今後にも使う」で明示採用した例だけを同じ文体の生成に参照し、後から取り消せます。画像の追加編集、独立したインストーラー、サービスを横断するチャット自動収集は初版の対象外です。

保存は版の照合と単一writerの排他を通し、書込み後の読戻しが一致してから成功とします。本文を置き換える際は、旧ファイルを同じdirectory内の `.nps-preserved-<ID>/` に移して保持し、新しい本文を空いたpathへ排他的に設置します。外部editorが直前に保存した内容や、開いたままの旧ファイルへ遅れて書いた内容も保全先に残ります。保全先は自動削除しません。通常の保存でも増えるため、必要な版を確認してから利用者が整理します。

本文pathは移動と設置の間に一時的に存在しなくなるため、非協調editorとの厳密なCASや本文pathの原子的な置換は保証しません。外部editorの変更を検知できた場合は競合として停止し、確認後に入った変更も旧ファイルを消さず保持します。hardlinkやopen中のファイル移動ができない環境では保存を失敗として返します。失敗時は既存の原稿・採否の復元を試み、復元自体が失敗した場合も保全先とtransactionを保持します。

プロセスの強制終了等でtransactionが残った場合は復旧操作で直近の正常版へ戻します。初回テーマ作成の中断も復旧対象で、未解決transactionがある同じIDへの作成再試行は拒否します。画面には未保存の退避、最新状態の取得、外部ファイルの再読込みがあります。再読込みは本文ファイルを書き直しません。競合時は編集中の本文と最新稿を並べて確認し、明示的に比較後の本文を保存できます。中断した保存の巻戻しでは編集中の本文を保持します。

## チャット・CLIから同じ保存処理を使う

```sh
python scripts/note_collaborative_session.py --settings /path/to/workspace/settings.json preflight
python scripts/note_collaborative_session.py --settings /path/to/workspace/settings.json create '考えているテーマ' --dry-run
python scripts/note_collaborative_session.py --settings /path/to/workspace/settings.json list
python scripts/note_collaborative_session.py --settings /path/to/workspace/settings.json show THEME_ID
```

変更操作は`action --help`のJSON入力と`--expected-revision`を使います。チャット側のAIが制作を担当し、同じ`SessionStore`の保存・提案・採否を呼びます。既存の公開前QAとNote editor工程は引き続き別のゲートです。この画面の保存成功やAI案の採用は、公開承認でも意味の完全一致の証明でもありません。
