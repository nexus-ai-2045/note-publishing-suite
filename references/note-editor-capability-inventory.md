---
title: note editor capability inventory
type: reference
status: active
created: 2026-06-12
source_scope: note official source registry and local observation
last_official_guidance_intake: 2026-06-16
last_local_capability_review: 2026-07-16
---

# note editor capability inventory

## 目的

note editor 操作で、公式が用意している機能、ローカルで実測した挙動、
まだ足りない棚卸しを分ける。

skill 本文へ「公式がそう言っている」と書く前に、この file へ一次情報と
観測差分を集める。

## 公式ソース

`confirmed_on` は、この package の `note-official-guidance-intake` lane で
公式ソースを確認した日付。公式扱いできるのは、この表に URL と
確認日がある内容だけ。表にない便利な運用論は `local policy`、
実画面で見ただけの挙動は `local observation`、未検証の挙動は
`needs measurement` と書く。

| 領域 | source | confirmed_on | 公式扱いできること |
|---|---|---|---|
| 推奨環境 | https://www.help-note.com/hc/ja/articles/360008947573 | 2026-06-16 | ブラウザは各最新版。Windows 10 以上は Google Chrome / Microsoft Edge / Mozilla Firefox、macOS 14 以上は Safari / Google Chrome。推奨環境でも OS と browser の組み合わせで一部表示不具合や機能不可があり得る。 |
| 埋め込み | https://www.help-note.com/hc/ja/articles/360019596133 | 2026-06-16 | 外部サービス URL を貼ると埋め込みまたはカード化される。URL 貼り付け後に Enter / Return が必要な場合があり、表示まで時間がかかる場合がある。埋め込み先サービス側が許可していない場合はできない。 |
| 目次 | https://www.help-note.com/hc/ja/articles/360017021253 | 2026-06-16 | 目次は記事の見出しから作られ、見出しとリンクされる。目次機能には見出し設定が必要。PC では挿入位置の plus menu から目次を選ぶ。プレビュー画面では目次表示できないが、予約投稿を設定した記事はプレビューでも表示される。 |
| ハッシュタグ | https://www.help-note.com/hc/ja/articles/360011358913 | 2026-06-16 | PC のタグ設定は、公開設定で入力する方法と、本文中に半角 `#` + 単語を書く方法がある。本文中に書く方法でも公開設定へ反映される。iOS ではおすすめタグから選ぶ導線がある。非公開マガジンに追加しているとハッシュタグが表示されない場合がある。 |
| 公開タイミング | https://note.com/info/n/n7b62e94e08c8 | 2026-06-16 | note 公式の創作カレンダーは、季節性・トレンド性のあるテーマやキーワードを公開タイミング検討の参考として示す。これはテーマ/公開日の参考であり、公式の「最適な時刻」保証ではない。 |
| 予約投稿とメンテナンス | https://note.com/info/n/n10cb85ca3ca8 | 2026-06-16 | メンテナンス停止予定期間に予約された記事やメンバーシップ掲示板投稿は、メンテナンス完了後に順次投稿される場合がある。メンテナンス完了後の公開を避けたい場合は、メンテナンス開始までに予約投稿を解除する。 |
| 新エディタ概要 | https://note.com/info/n/nedf8b9646b68 | historical | 公開設定画面の全画面表示、編集中の埋め込みURL表示、複数デバイス/複数タブ同時編集時の競合提示、キーボードショートカットが紹介されている。再利用前に現行ヘルプで再確認する。 |
| 新エディタ追加機能 | https://note.com/info/n/n611d3e257e54 | historical | 小見出し、箇条書き/番号付きリスト、右寄せ、取り消し線、出典元、区切り線、画像 alt、画像キャプションなどが紹介されている。再利用前に現行ヘルプで再確認する。 |
| 新エディタ改善 | https://note.com/info/n/n1574dece52e4 | historical | 画像キャプション改行、編集中の埋め込みURL表示、10MB以上画像の圧縮アップロード、GIF、外部サービス埋め込み、埋め込みURLの後修正が紹介されている。再利用前に現行ヘルプで再確認する。 |
| 自動保存/プレビュー/目次 | https://note.com/info/n/ncd8a8d534a3f | historical | 自動保存表示、閉じるボタン、三点リーダ内プレビュー、長い目次のスクロール、埋め込み削除後のURL確認、予約投稿時 timezone 表示が紹介されている。再利用前に現行ヘルプで再確認する。 |

## 公式未確認 / local policy

- note 公式ソースとして、汎用的な「何時に公開すると最も読まれる」
  という固定時刻の推奨は、この intake では確認していない。
  公開時刻の助言は local policy として扱い、公式扱いしない。
- タグ案の「広い発見タグ、主題タグ、文脈タグ、所有シリーズタグを混ぜる」
  という分類は local policy。公式扱いできるのは、公開設定または
  本文内 `#` で設定できること、本文内タグが公開設定へ反映されること、
  iOS のおすすめタグ導線まで。
- `figure[data-src]` などの DOM 成功判定は local observation / local checker。
  公式ヘルプの主張ではない。

## local observation

詳細な再現手順は `references/note-editor-live-constraint-boundaries.md` を正本にする。

| 領域 | 実測日 | 観測したこと | 境界 |
|---|---|---|---|
| Shift+Enter | 2026-06-16 | in-app Browser の本文 root で Shift+Enter は同一 `p` 内の `<br>` になった。 | paragraph split ではなく `<br>` を成功条件にする。 |
| URL embed | 2026-06-16 | `https://note.com/info/n/n4abb4e998dfc` は Enter 後に `figure[data-src]` と `iframe.note-embed` へ変換された。raw URL と `a[href]` は残らなかった。 | embed 後の `Control+Z` 1回では DOM が残ったため、Undo 復旧は保証しない。 |
| 目次 | 2026-06-16 | 挿入メニューの `大見出し` は `H2`、`小見出し` は `H3`。`目次` は `table-of-contents contenteditable="false"` と `toc` 属性を生成した。 | 目次挿入後の `Control+Z` 1回では DOM が残ったため、誤位置は手動境界に戻す。 |
| automation Enter | 2026-06-16 | Playwright / dom_cua の通常 Enter は、通常テキストでは同一 paragraph 内の `<br>` として観測された。 | automation surface で一般段落分割を保証しない。 |

## 操作軸

### 1. 公式機能軸

- 埋め込みは Markdown link や HTML figure を直接貼るのではなく、
  URL を本文段落に貼る。公式ヘルプ上で公式扱いできるのは、
  外部サービス URL の貼り付けで埋め込みまたはカード化されることと、
  URL 貼り付け後に Enter / Return が必要な場合があることまで。
  `figure[data-src]` や `iframe.note-embed` は 2026-06-16 の
  local live measurement に基づく local checker であり、公式主張ではない。
- 目次は見出し設定が前提。目次のプレビュー表示は通常不可で、
  予約投稿設定済み記事だけプレビュー表示の例外が公式ヘルプにある。
- 公開タイミングは、公式創作カレンダーをテーマ/公開日の参考にする。
  固定の「おすすめ公開時刻」は公式未確認として扱う。
- 推奨環境として扱えるのは、公式ヘルプにある OS/browser の組み合わせと、
  推奨環境でも一部表示不具合や機能不可があり得るという注意まで。

### 1a. local live measurement 軸

- Enter / Shift+Enter / Undo / DOM 成功判定は、公式機能軸ではなく
  2026-06-16 の local live measurement として扱う。
- Shift+Enter は、in-app Browser の本文 root で同一 `p` 内の `<br>` として
  観測された。これは公式一般仕様ではなく、この surface の成功条件。
- Playwright / dom_cua の通常 Enter は、通常テキストでは同一 paragraph 内の
  `<br>` として観測された。automation surface で一般段落分割を保証しない。
- URL embed と目次挿入後の `Control+Z` 1回では DOM が残ったため、
  Undo 復旧は保証せず、誤位置は手動境界へ戻す。
- キーボードショートカット、複数タブ競合、自動保存/手動保存の表示は
  historical source または未整理領域が混ざるため、現行公式扱いする前に
  公式ソースの再確認か live measurement を行う。

### 2. 画面サイズ / responsive 軸

- note editor の toolbar、左下 plus、AI、見出し selector、公開/保存系 button は
  viewport 幅、scroll 位置、選択状態で見える場所が変わる。
- 配置が変わるだけでなく、DOM 構造、role、aria-label、menu 内への移動、
  親子関係、対象要素の出現タイミングも変わる可能性がある。
- 固定座標ではなく、DOM、ラベル、role、状態、本文 root から操作対象を探す。
- 固定 selector / XPath / nth-child だけで操作対象を決めない。
- 操作対象は、role、label、visible text、aria 属性、disabled 状態、
  editor root との距離、クリック後に出る menu の内容を組み合わせて確認する。
- viewport を変えたら、同じ selector が使える前提を捨て、候補要素の
  再列挙からやり直す。
- 画面が狭い場合は、button が overflow menu や toolbar 内に畳まれる前提で扱う。
- スクリーンショット確認は、viewport size と scroll position を closeout に残す。

### 3. カーソル / selection 軸

- URL 埋め込みは、カーソルが独立した空段落にあることを先に確認する。
- 選択中の文字列がある状態で paste / Enter すると、置換や装飾変更になり得る。
- paragraph 内にカーソルがある場合、URL が本文中リンクとして残る可能性がある。
- 意図しない段落へ入力したら、追加編集で直そうとせず Undo で戻す。
- Undo 後は本文末尾、対象URL、重複URL、壊れた文字列の有無を確認する。

### 4. Browser surface 軸

| surface | 読み取り/DOM確認 | 本文・タイトル入力 | local file upload | 使う条件と境界 |
|---|---|---|---|---|
| in-app Browser | attach / inspect できる場合は可能 | 対象 editor と入力位置を再確認できる範囲で可能 | `File uploads are not supported` の場合は不可。再試行しない | Codex の第一候補。Playwright DOM と CUA 実操作面が同期しない場合は固定座標を使わない。 |
| Chrome extension | 接続済みの対象tabを確認できる場合は可能 | ユーザーがこの surface を明示選択した場合だけ候補 | profile と可視UIの能力に依存し、自動成功を保証しない | ログイン状態、拡張機能、普段の profile が必要な場合。in-app Browser から無断で切り替えない。Cookie/profile を worker に渡さない。 |
| manual browser / human supervised | ユーザーが見えている画面を確認 | 人間操作として可能 | 可視ファイル選択または手動 upload | 画像 upload、カーソル位置が不安定な操作、profile依存操作の既定 fallback。Codex は対象pathと確認項目を渡す。 |
| note official recommended browsers | note側の対応環境 | 人間操作としての候補 | 人間操作としての候補 | Mac は Safari / Chrome、Windows は Chrome / Edge / Firefox。推奨環境でも機能成功を保証しない。 |

### 4a. 操作対象ロック / surface 切替確認契約

Note editor に write 操作を行う前に、`note id / draft URL / article lane / tab / Browser surface / account / read-only or write` を現在の操作対象としてロックする。

- 同一 editor 内の DOM 再確認や scroll は対象切替ではない。
- 別 note、別 draft、公開済み記事、別tab、別Browser surface、別accountへの変更は対象切替。
- 対象切替が必要なら、切替先、理由、実行予定操作、未実行の公開系操作、戻り先を1画面で示し、ユーザーの事前確認を得る。
- 同一対象へのwriteが現在の会話で承認済みなら、read-onlyからwriteへ進むためだけの重複確認は不要。未承認ならwrite前にユーザー確認を得る。
- ユーザーが in-app Browser や Chrome を明示選択している場合、その選択はtask中の制約として保持する。接続や認証に失敗しても無断で別surfaceへ移らない。
- `File uploads are not supported` は能力不足の確定結果。Chrome、Computer Use、note API、Cookie、別tabへ自動fallbackせず、画像pathを返して manual browser / human supervised へ引き継ぐ。

標準packet:

```text
note_editor_target_lock:
- note_id_or_draft_url:
- article_lane:
- browser_surface:
- account_confirmed:
- operation_mode: read_only | write_draft | save_draft | publish_gate
- switch_requested: yes | no
- switch_reason:
- user_confirmation: confirmed | missing | not_required_same_target | not_required_current_conversation_approval
- return_to:
```

### 4b. 失敗分類と復旧契約

| failure class | 同じrouteの再試行 | 対応 |
|---|---:|---|
| `unsupported_capability` | 0回 | 即停止。未実行状態、local file path、手動手順を返す。 |
| `wrong_or_ambiguous_target` | 0回 | writeせず対象候補を示し、ユーザー確認へ戻す。 |
| `authentication_required` | 0回 | 選択中surfaceでのsign-inを依頼する。別surfaceへは切り替えない。 |
| `attach_or_connection_failure` | 1回 | 同一surface・同一targetへの再接続だけ試し、失敗なら保留。 |
| `selector_or_viewport_drift` | 1回 | DOM候補を再列挙して同一targetで1 actionだけ再試行する。 |
| `unexpected_write_or_recovery_uncertain` | 0回 | 追加編集を止め、Undoまたは最後の検証済み状態を確認する。復旧不明なら人間監督へ渡す。 |

fallback順は `same target re-inspect -> manual/human supervised -> user-approved surface switch -> hold`。surface切替は常に新しい対象ロックとユーザー確認を必要とする。

### 5. AI surface 軸

| surface | 使う条件 | 禁止/境界 |
|---|---|---|
| Codex main | 採否、設計、Type1、公開 gate、最終報告。 | 公開/予約/共有/外部送信の最終操作は明示承認までしない。 |
| Spark / lightweight worker | URL候補抽出、diff/log圧縮、risk second-pass、公式source一覧化。 | credential、Cookie、非公開URL、公開権限を渡さない。 |
| Browser automation | read-only DOM inspect、本文一致確認、埋め込みDOM確認。 | 固定座標で公開/保存/共有系を押さない。 |
| Human supervised | 画像 upload、カーソル位置が不安定な操作、ブラウザprofile依存操作。 | 実施した操作と未実施操作を closeout に分ける。 |

## 足りていない棚卸し

- 現行 note editor の最新ヘルプセンター記事を、編集機能別にまだ全取得していない。
- TOP画像、本文画像、alt、caption、みんなのフォトギャラリー、Canva 連携の操作差分を未整理。
- 目次の表示/非表示、長い目次、公開後表示の実測確認手順が薄い。
  見出し階層と editor 内 DOM は `note-editor-live-constraint-boundaries.md` に実測済み。
- タグ、マガジン、共同マガジン、公開範囲、無料/有料、予約投稿 timezone の実画面確認手順が薄い。
- 「公開時刻の最適化」は公式の固定時刻推奨が未確認なので、実績台帳や
  local observation による PDCA としてのみ扱う。
- 保存表示、自動保存、手動保存、下書き競合、複数タブ競合の回復手順が薄い。
- 画面幅ごとの button / toolbar 配置を、viewport 別にまだ snapshot 化していない。
- 画面幅ごとの DOM 構造差分、selector 差分、overflow menu への移動条件を
  まだ snapshot 化していない。
- Chrome extension の file upload、認証回復、DOM/CUA同期は未実測。ユーザー確認後の個別測定が必要で、fallback成功は保証しない。

## closeout で必ず残す条件

- Browser surface: in-app Browser / Chrome extension / manual browser。
- AI surface: Codex main / worker / human supervised。
- viewport size、scroll position、本文 root の確認可否。
- 操作対象の候補数、採用した識別子、使わなかった候補、DOM path が
  viewport 依存だったか。
- cursor / selection の状態。空段落、本文中、選択あり、URL行上など。
- 実行した note 操作と、明示承認がないため未実行にした操作。
- target lock、対象切替の有無、ユーザー確認状態、失敗分類、再試行回数、採用したfallback。
