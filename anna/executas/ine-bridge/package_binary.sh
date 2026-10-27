#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

TOOL_ID="$(python -c 'import json; print(json.load(open(".anna/executa.json"))["tool_id"])')"
VERSION="$(python -c 'import json; print(json.load(open("executa.json"))["version"])')"
DISPLAY_NAME="$(python -c 'import json; print(json.load(open("executa.json"))["name"])')"
DESCRIPTION="$(python -c 'import json; print(json.load(open("executa.json"))["description"])')"

BUILD_ENV="$DIR/.build-venv"
OUT="$DIR/dist-anna"
STAGE="$OUT/staging-linux-x86_64"

rm -rf "$BUILD_ENV" "$OUT"
python -m venv "$BUILD_ENV"
"$BUILD_ENV/bin/python" -m pip install --upgrade pip
"$BUILD_ENV/bin/python" -m pip install . pyinstaller

ENTRY="$BUILD_ENV/bin/tool-dev-ine-bridge"
test -f "$ENTRY"

"$BUILD_ENV/bin/pyinstaller" \
  --onefile \
  --clean \
  --noupx \
  --name "$TOOL_ID" \
  --distpath "$OUT/build" \
  "$ENTRY"

mkdir -p "$STAGE/bin"
cp "$OUT/build/$TOOL_ID" "$STAGE/bin/$TOOL_ID"
chmod 755 "$STAGE/bin/$TOOL_ID"

export TOOL_ID VERSION DISPLAY_NAME DESCRIPTION STAGE

python - <<'PY'
import json
import os
from pathlib import Path

stage = Path(os.environ["STAGE"])
tool_id = os.environ["TOOL_ID"]

manifest = {
    "name": tool_id,
    "display_name": os.environ["DISPLAY_NAME"],
    "version": os.environ["VERSION"],
    "description": os.environ["DESCRIPTION"],
    "runtime": {
        "binary": {
            "entrypoint": {"default": f"bin/{tool_id}"},
            "permissions": {f"bin/{tool_id}": "0o755"}
        }
    }
}

(stage / "manifest.json").write_text(
    json.dumps(manifest, indent=2) + "\n",
    encoding="utf-8"
)
PY

ARCHIVE="$OUT/$TOOL_ID-linux-x86_64.tar.gz"
tar -czf "$ARCHIVE" -C "$STAGE" .
sha256sum "$ARCHIVE" > "$ARCHIVE.sha256"

echo "Built archive: $ARCHIVE"
tar -tzf "$ARCHIVE"
