---
title: note editor PDCA orchestration
type: reference
status: active
created: 2026-06-12
source_scope: local operation pattern
---

# note editor PDCA orchestration

## 目的

note editor 操作を一括実行せず、薄い PDCA cycle で回す。
画面幅、DOM 変化、カーソル位置、ブラウザ面、AI面が変わるため、
各操作を小さい work packet に分けて evidence を取ってから次へ進む。

## 最小サイクル

### 1. Goal

- 今回の 1 cycle で何を確認/変更するかを 1 文で決める。
- 完了条件、非目標、公開/保存/共有 gate を明示する。

例:

```text
Goal: 公式URL1件を footer の空段落でリンクカード化する。
Done: 対象URLの figure[data-src] が footer 直下に1件ある。
Non-goal: 公開、共有、SNS告知、別URLの変換。
Gate: 一時保存 / 公開に進む / 共有は押さない。
```

### 2. Plan

- 操作前に Browser surface、AI surface、viewport、scroll、cursor/selection を確認する。
- 操作対象候補を DOM から再列挙する。固定 selector / nth-child / 座標を前提にしない。
- 失敗時の Undo / stopline を先に決める。

### 3. Do

- 1 cycle では 1 action だけ行う。
- 例: URL 1件を空段落へ貼る、Enter 1回、DOM 1回確認、Undo 1回。
- worker / Spark に渡す場合は、read-only summary、候補抽出、diff/log圧縮に限る。

### 4. Check

- DOM、表示、本文末尾、重複URL、壊れた文字列を確認する。
- `figure[data-src]`、`href`、visible text、対象 paragraph を分けて見る。
- 画面条件を記録する: viewport size、scroll position、cursor/selection、候補数、採用識別子。

### 5. Act

- 成功なら次 cycle へ進む。
- 通常リンク残り、誤段落入力、DOM不明、候補が複数で曖昧なら Undo または手動境界へ戻す。
- 同じ失敗が2回続いたら、その操作 route は使わない。
- 新しく分かった失敗や手順は checker、contract test、または skill 文言へ落とす。

## work packet 分割例

| packet | Goal | Done | Stopline |
|---|---|---|---|
| attach | editor を read-only で確認 | URL / note id / body root を確認 | attach/inspect 不可 |
| viewport map | 現在画面で候補要素を列挙 | 候補数と採用識別子を記録 | 候補が曖昧 |
| cursor prep | 空段落へ cursor を置く | selection なし / 空段落 | 本文中や選択あり |
| embed one URL | URL 1件を貼って Enter | `figure[data-src]` 1件 | hrefだけ / 誤段落 |
| footer sweep | footer のリンク状態を検査 | raw URL / 重複 / 旧ラベルなし | 不一致あり |
| save state | 保存状態を表示確認 | 自動保存/手動保存表示の evidence | 保存系 button を押す必要 |
| publish gate | 公開前停止条件を確認 | 未実行 action を列挙 | 明示承認なし |
| postpublish ledger | 公開URLと台帳を確認 | published/draft ledger evidence | 公開URL/status 未確認 |

## orchestration ルール

- Main agent は goal、採否、公開 gate、secret/auth、最終報告を保持する。
- Spark / worker は、候補抽出、公式source表化、diff/log圧縮、risk second-pass に限定する。
- worker へ Cookie、非公開URL、公開権限、保存/共有/公開操作を渡さない。
- UI 操作の write packet は原則 main agent が担当する。
- 複数 packet を並列化できるのは、DOM操作と競合しない read-only 作業だけ。

## closeout template

```text
今回のPDCA:
- Goal:
- Plan:
- Do:
- Check:
- Act:

画面条件:
- Browser surface:
- AI surface:
- viewport / scroll:
- cursor / selection:
- DOM候補:

Gate:
- 実行した操作:
- 未実行の公開/保存/共有/SNS:
- 次の cycle:
```
