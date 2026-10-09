"""Download the latest e-boekhouden OpenAPI spec and report operation changes.

Usage: uv run scripts/update_spec.py
"""

import json
from pathlib import Path
from typing import Any

import httpx2

SPEC_URL = "https://api.e-boekhouden.nl/openapi/v1.json"
SPEC_PATH = Path(__file__).parent.parent / "src" / "eboekhouden_mcp" / "openapi" / "v1.json"
METHODS = {"get", "post", "put", "patch", "delete"}


def operations(spec: dict[str, Any]) -> set[str]:
    return {
        f"{method.upper():6} {path}  ({op.get('operationId', '-')})"
        for path, item in spec.get("paths", {}).items()
        for method, op in item.items()
        if method in METHODS
    }


def main() -> None:
    response = httpx2.get(SPEC_URL, follow_redirects=True, timeout=30)
    response.raise_for_status()
    new: dict[str, Any] = response.json()
    old: dict[str, Any] = json.loads(SPEC_PATH.read_text("utf-8")) if SPEC_PATH.exists() else {}

    added, removed = operations(new) - operations(old), operations(old) - operations(new)
    for line in sorted(added):
        print(f"+ {line}")
    for line in sorted(removed):
        print(f"- {line}")
    if not (added or removed):
        print("No operations added or removed.")

    SPEC_PATH.parent.mkdir(parents=True, exist_ok=True)
    SPEC_PATH.write_text(json.dumps(new, indent=2, ensure_ascii=False) + "\n", "utf-8")
    print(f"Wrote {SPEC_PATH} - review the full diff with `git diff`.")


if __name__ == "__main__":
    main()
