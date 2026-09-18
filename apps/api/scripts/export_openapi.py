"""Writes the API's OpenAPI schema to a file — run this after changing any
endpoint so docs/openapi.json stays in sync.

    cd apps/api && python scripts/export_openapi.py [output_path]

Defaults to ../../docs/openapi.json. Only imports app.main:app and calls its
.openapi() method — no database connection needed (the schema is built from
route/schema definitions, not from anything in the DB).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402


def main() -> None:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent.parent.parent / "docs" / "openapi.json"
    schema = app.openapi()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out_path} ({len(schema.get('paths', {}))} paths)")


if __name__ == "__main__":
    main()
