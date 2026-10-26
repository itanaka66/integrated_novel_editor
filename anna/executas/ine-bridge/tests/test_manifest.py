"""Keep the on-disk Anna tool manifest aligned with the Executa describe response."""
import json
import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_DIR))

import ine_plugin  # noqa: E402


def test_manifest_json_is_valid_and_matches_describe_tool_names():
    manifest_path = Path(__file__).parents[1] / "manifest.json"
    bundled = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert bundled["version"] == ine_plugin.MANIFEST["version"]
    assert bundled["description"] == ine_plugin.MANIFEST["description"]
    assert [tool["name"] for tool in bundled["tools"]] == [
        tool["name"] for tool in ine_plugin.MANIFEST["tools"]
    ]
    assert [tool["name"] for tool in bundled["tools"]] == list(
        ine_plugin.TOOL_DISPATCH.keys()
    )


def test_manifest_declares_credentials_and_uv_runtime():
    manifest_path = Path(__file__).parents[1] / "manifest.json"
    bundled = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert bundled["runtime"]["type"] == "uv"
    credential_names = {item["name"] for item in bundled["credentials"]}
    assert {"INE_BASE_URL", "INE_USERNAME", "INE_PASSWORD"} <= credential_names
