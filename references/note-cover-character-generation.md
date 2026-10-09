---
title: note cover character generation rules
type: reference
status: active
created: 2026-08-08
publication_gate: human_review_required
---

# Note 扉絵 — キャラ生成ルール

## 目的

ねく入り扉絵を「既存シーンの焼き直し」や「たまたま近い絵」で作らない。  
キャラ正本と記事コンセプトからシチュを膨らませる。

## 必須手順（生成前）

1. `Documents/nexus_ai/content/assets/character-references/manifest.yaml` を読む。
2. `tracked_references` の画像を最低1枚、できれば2枚 `image_edit` の参照にする。
3. 記事テーマの核（例: 成功顔 ≠ 稼働）を1文で固定する。
4. 筆談・抽象コンセプト絵がある場合はモチーフ参照にしてよい（キャラ正本の代替にはしない）。
5. Windows では path 一覧だけで採択しない。`explorer` + `Start-Process` で人間目視する。

## 禁止

- マガジン候補や別記事の生成絵をキャラ正本として使う。
- ファイル名 concept（例: unlit-status-lamp）だけで採択する。
- コデたんを黒ぬいぐるみ化・半透明星座なしで固定する。
- ねくをちび化してホスト感を落とす（正本と違う絵柄になったら差し戻し）。
- タイトル日本語を画像に焼き込む（note 側表示を優先）。

## ねく固定 traits（manifest 要約）

- black to dark-gray short bob / cyan glowing tips
- cyan glowing cat-ear cyber headphones
- nose bandage
- dark oversized hoodie with cyan pixel/glitch-cat motif
- black thigh-high socks / sneakers

## コデたん固定 traits

- small translucent hooded companion
- black face area
- cyan angle-bracket eyes
- constellation / star pattern

## image_edit 制約

- 入力参照画像は最大3枚（超過すると 400）。
- 推奨セット: ラボOPEN正本 + 忠実度の高い today-cover + （任意）コンセプト線画1枚。

## 採択

- 最低3案を出し、違いと推奨を質問形式で示す。
- 人間採択後だけ Note TOP upload へ進む。
- upload 経路は `note-image-upload-automation-boundary.md`（Chrome DevTools MCP は TEMP stage）。

## Closeout

- 読んだ manifest path
- 使った reference 画像 path
- 生成候補一覧と人間採択
- Note 反映有無 / 公開未実行
