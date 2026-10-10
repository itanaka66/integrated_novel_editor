---
title: ComfyUI ガイド
layout: default
---

[← マニュアルトップ](index.md) | [English](comfyui.md)

# ComfyUI ガイド（表紙画像生成）

表紙画像は、HTTP 経由で **ComfyUI** サーバーを呼び出して生成します。ComfyUI は同梱されていません。GPU のあるマシンなどで各自起動し、エディタから接続先を指定します。

## 1. ComfyUI を用意する

1. ComfyUI をインストールし、API に届く状態で起動します。例：`python main.py --listen 0.0.0.0 --port 8188`（エディタが Docker 内や別PCにある場合は `--listen` が必須です）。
2. **起動した ComfyUI の** `models/checkpoints` に、チェックポイント（`.safetensors` / `.ckpt`）を1つ以上置き、ComfyUI を再起動するか Refresh を押します。標準の 832×1216 縦長サイズには SDXL 系（アニメなら NoobAI-XL など）が向いています。
3. ブラウザで `http://<ホスト>:8188/object_info/CheckpointLoaderSimple` を開き、`ckpt_name` の一覧にモデルがあることを確認します。

## 2. エディタに接続先を伝える

| 設定 | 意味 | 既定値 |
|---|---|---|
| `COMFYUI_URL` | ComfyUI の URL | `http://localhost:8188`（Docker Compose では `http://host.docker.internal:8188`） |
| `COMFYUI_CHECKPOINT` | 使用するチェックポイント。空なら ComfyUI が返す先頭のもの | 空 |

- Docker Compose：同じPCの ComfyUI は `host.docker.internal` 経由で届きます。別PCなら `.env` に `COMFYUI_URL=http://192.168.1.20:8188` のようにIPを指定します。
- Docker なしの Windows インストーラ：`localhost` のままで動作します。
- チェックポイント名は拡張子の有無・大文字小文字を問いません（`NoobAI-XL` は `NoobAI-XL.safetensors` に一致します）。

接続先は **設定 →「表紙画像」** の「ComfyUI 接続先URL」でも指定でき、「接続テスト」で到達可否と利用可能なチェックポイントを確認できます。ここで保存したURL（`cover_config.json` の `comfyui.url`）は `COMFYUI_URL` より優先されます。空欄なら環境変数が使われます。

## 3. 表紙を生成する

作品を開く → 表紙パネル → イメージ（アニメ風 / 劇画風 / 実写風 / その他）を選ぶ →「作品内容からプロンプトを作成」→ 必要ならプロンプトを編集 → **ComfyUI** を選択 →「表紙を生成」。画像は `COVERS_DIR/<作品ID>/`（Docker では `covers` ボリューム）に、使用したプロンプト・設定の `.json` と一緒に保存されます。プロンプト・イメージ・エンジンは作品ごとに記憶されます。

## 4. 再起動なしで調整する：`cover_config.json`

モデルやパラメータはハードコードされておらず、`cover_config.json`（`COVER_CONFIG_PATH`。Docker では `/covers/cover_config.json`。初回利用時に既定値で作成）にあります。変更されるたびに読み直されるので、次の生成から反映されます。壊れたファイルは無視され、直前の正常な内容が使われ続けます。

```json
{
  "comfyui": {
    "checkpoint": "", "width": 832, "height": 1216,
    "steps": 28, "cfg": 6.5, "sampler_name": "euler", "scheduler": "normal",
    "negative": "text, watermark, low quality, ..."
  },
  "styles": {
    "anime": {
      "label": "アニメ風",
      "prompt_suffix": "anime style, masterpiece, best quality",
      "comfyui": { "checkpoint": "NoobAI-XL", "negative_extra": "photorealistic" }
    }
  }
}
```

- `comfyui` 直下の値は全イメージ共通です。`styles.<イメージ>.comfyui` に書いたキーはそのイメージだけ上書きします（`negative_extra` はネガティブプロンプトに追記）。イメージごとにチェックポイントを変えるにはこれを使います。
- `prompt_style` は自動作成されるプロンプトの方向づけ、`prompt_suffix` は ComfyUI に送るプロンプトの末尾に付く文言です。
- チェックポイントの優先順位：イメージ別の上書き → `comfyui.checkpoint` → `COMFYUI_CHECKPOINT` → ComfyUI の先頭。

## 5. トラブルシューティング

| 症状 | 原因・対処 |
|---|---|
| 接続拒否 / タイムアウト | ComfyUI 未起動、`COMFYUI_URL` の誤り、またはエディタが Docker なのに `--listen` なしで起動。Linux の Docker では `extra_hosts: host.docker.internal:host-gateway` が必要です（compose には設定済み）。 |
| `ckpt_name: '…' not in []` /「チェックポイントが1つもありません」 | 応答した ComfyUI の `models/checkpoints` が空です。モデルを置いた別の ComfyUI（デスクトップ版とポータブル版など）に接続している場合があります。URL の指す ComfyUI に配置し、Refresh／再起動してください。 |
| `COMFYUI_CHECKPOINT="…" は…一覧にありません` | 名前が一覧にありません。メッセージに利用可能な名前が表示されます。 |
| メモリ不足・非常に遅い | `cover_config.json` の `width`/`height`/`steps` を下げてください。 |

1枚あたり最大10分待ちます。
