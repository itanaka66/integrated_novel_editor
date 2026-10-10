---
title: ComfyUI Guide
layout: default
---

[← Manual home](index.md) | [日本語](comfyui.ja.md)

# ComfyUI Guide (cover image generation)

The editor generates book covers by calling a **ComfyUI** server over HTTP. ComfyUI is not bundled: you run it yourself (usually on the machine with the GPU) and point the editor at it.

## 1. Set up ComfyUI

1. Install ComfyUI and start it so its API is reachable, e.g. `python main.py --listen 0.0.0.0 --port 8188` (`--listen` is required if the editor runs in Docker or on another machine).
2. Put at least one checkpoint (`.safetensors` / `.ckpt`) in the `models/checkpoints` folder **of the ComfyUI you started**, then restart ComfyUI or press Refresh. SDXL-family models (e.g. NoobAI-XL for anime) suit the default 832×1216 portrait size.
3. Check `http://<host>:8188/object_info/CheckpointLoaderSimple` in a browser: the `ckpt_name` list must contain your model.

## 2. Tell the editor where ComfyUI is

| Setting | Meaning | Default |
|---|---|---|
| `COMFYUI_URL` | ComfyUI base URL | `http://localhost:8188` (Docker Compose: `http://host.docker.internal:8188`) |
| `COMFYUI_CHECKPOINT` | Checkpoint to use; blank = the first one ComfyUI lists | blank |

- Docker Compose: ComfyUI on the same PC is reached via `host.docker.internal`; for another PC use its IP, e.g. `COMFYUI_URL=http://192.168.1.20:8188` in `.env`.
- Docker-free Windows installer: `localhost` works as-is.
- The checkpoint name may be written with or without extension and in any case (`NoobAI-XL` matches `NoobAI-XL.safetensors`).

## 3. Generate a cover

Open a project → cover panel → choose the look (アニメ風 / 劇画風 / 実写風 / その他) → "作品内容からプロンプトを作成" → edit the prompt if you like → select **ComfyUI** → "表紙を生成". Images are saved under `COVERS_DIR/<project id>/` (Docker: the `covers` volume) together with a `.json` of the prompt and settings used. The prompt, look and engine are remembered per project.

## 4. Tuning without restarting: `cover_config.json`

Models and parameters are not hard-coded. They live in `cover_config.json` (`COVER_CONFIG_PATH`, Docker: `/covers/cover_config.json`; created with defaults on first use). The file is re-read when it changes, so edits apply to the next generation; a broken file is ignored and the last good one stays in effect.

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

- Base values under `comfyui` apply to every look; a key under `styles.<look>.comfyui` overrides it for that look only (`negative_extra` is appended to the negative prompt instead). This is how you use a different checkpoint per look.
- `prompt_style` steers the generated prompt; `prompt_suffix` is appended to the prompt sent to ComfyUI.
- Order of precedence for the checkpoint: look override → `comfyui.checkpoint` → `COMFYUI_CHECKPOINT` → first installed.

## 5. Troubleshooting

| Message | Cause / fix |
|---|---|
| Connection refused / timeout | ComfyUI is not running, wrong `COMFYUI_URL`, or started without `--listen` while the editor is in Docker. Docker on Linux needs `extra_hosts: host.docker.internal:host-gateway` (already in the compose files). |
| `ckpt_name: '…' not in []` / "no checkpoints" | The ComfyUI that answered has an empty `models/checkpoints` — often a different ComfyUI instance (e.g. desktop app vs. portable) holds your models. Put the file in the one the URL points to, then Refresh/restart. |
| `COMFYUI_CHECKPOINT="…" は…一覧にありません` | Name not in the installed list; the message lists the available names. |
| Out of memory / very slow | Lower `width`/`height`/`steps` in `cover_config.json`. |

Generation waits up to 10 minutes per image.
