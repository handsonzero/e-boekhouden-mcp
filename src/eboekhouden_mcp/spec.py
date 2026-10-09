"""Load the vendored e-boekhouden OpenAPI spec and prepare it for tool generation.

The vendored file is never modified; all changes are made to an in-memory copy:

- Internal routes (session handling, swagger UI) are removed.
- References to schemas missing from the spec are made permissive (see `_drop_dangling_refs`).
- HTML error-code tables are stripped from descriptions to keep tool schemas lean.
- Numeric string enums (`MutationType`: "1".."7") also accept the integers the API returns.
- Filter parameters get extra operator variants. The API puts the operator in the
  parameter name (`date[gte]=2025-01-01`), which is not a valid tool argument name,
  so we expose `date__gte` instead and rewrite it on the wire (see `rewrite_filters`).
"""

import json
import re
from importlib.resources import files
from typing import Any, cast

import httpx2

EXCLUDED_PATHS = re.compile(r"^/(swagger|v1/session)")

# Operators exposed per filter format, with a description template.
_NUMBER_OPERATORS = {
    "gte": "{name} greater than or equal to this value.",
    "lte": "{name} less than or equal to this value.",
}
FILTER_OPERATORS: dict[str, dict[str, str]] = {
    "filter-string": {
        "like": "Matches {name} using wildcards: % (any characters), ? (one character).",
    },
    "filter-date": {
        "gte": "On or after this date (YYYY-MM-DD).",
        "lte": "On or before this date (YYYY-MM-DD).",
    },
    "filter-int32": _NUMBER_OPERATORS,
    "filter-int64": _NUMBER_OPERATORS,
}
OPERATOR_SEPARATOR = "__"
_OPERATOR_PARAM = re.compile(rf"^(?P<name>.+){OPERATOR_SEPARATOR}(?P<op>like|gte|lte)$")

_SCHEMA_REF = "#/components/schemas/"
_ERROR_TABLE = re.compile(r"<div><h3>Error codes</h3>.*?</div>", re.DOTALL)
_TAG = re.compile(r"<[^>]+>")

type Json = dict[str, Json] | list[Json] | str | int | float | bool | None


def load_raw_spec() -> dict[str, Any]:
    return json.loads(files(__package__).joinpath("openapi/v1.json").read_text("utf-8"))


def load_spec() -> dict[str, Any]:
    spec = load_raw_spec()
    spec["paths"] = {
        path: item for path, item in spec["paths"].items() if not EXCLUDED_PATHS.match(path)
    }
    for item in spec["paths"].values():
        for operation in item.values():
            if isinstance(operation, dict) and "parameters" in operation:
                parameters = cast(list[dict[str, Any]], operation["parameters"])
                operation["parameters"] = _expand_filters(parameters)
    known = set(spec.get("components", {}).get("schemas", {}))
    spec = cast(dict[str, Any], _drop_dangling_refs(spec, known))
    _accept_numeric_enums(spec.get("components", {}).get("schemas", {}))
    _clean_descriptions(spec["paths"])
    _clean_descriptions(spec.get("components", {}))
    return spec


def _drop_dangling_refs(node: Json, known: set[str]) -> Json:
    """Replace `$ref`s to undefined component schemas by an empty (accept-anything) schema.

    The upstream spec references item schemas such as `MutationsResponseDto` from its
    `ListDto*` wrappers without defining them. MCP clients reject tools whose output
    schema contains such unresolvable references.
    """
    if isinstance(node, dict):
        ref = node.get("$ref")
        if (
            isinstance(ref, str)
            and ref.startswith(_SCHEMA_REF)
            and ref[len(_SCHEMA_REF) :] not in known
        ):
            return {}
        return {key: _drop_dangling_refs(value, known) for key, value in node.items()}
    if isinstance(node, list):
        return [_drop_dangling_refs(item, known) for item in node]
    return node


def _accept_numeric_enums(schemas: dict[str, Any]) -> None:
    """Let enums like `MutationType` ("1".."7") also match the integers the API returns.

    The spec declares them as strings, but responses contain `"type": 1`, which fails
    output-schema validation for tools such as `get_mutation`.
    """
    for schema in schemas.values():
        values = schema.get("enum")
        if schema.get("type") == "string" and values and all(str(v).isdigit() for v in values):
            schema["type"] = ["string", "integer"]
            schema["enum"] = [*values, *(int(v) for v in values)]


def _expand_filters(parameters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for param in parameters:
        expanded.append(param)
        operators = FILTER_OPERATORS.get(param.get("schema", {}).get("format", ""), {})
        if param.get("in") != "query":
            continue
        for op, description in operators.items():
            expanded.append(
                {
                    "name": f"{param['name']}{OPERATOR_SEPARATOR}{op}",
                    "in": "query",
                    "description": description.format(name=param["name"]),
                    "schema": param["schema"],
                }
            )
    return expanded


def _clean_descriptions(node: Json) -> None:
    if isinstance(node, dict):
        description = node.get("description")
        if isinstance(description, str) and "<" in description:
            cleaned = _TAG.sub(" ", _ERROR_TABLE.sub("", description))
            cleaned = " ".join(cleaned.split())
            if cleaned:
                node["description"] = cleaned
            else:
                del node["description"]
        for value in node.values():
            _clean_descriptions(value)
    elif isinstance(node, list):
        for item in node:
            _clean_descriptions(item)


async def rewrite_filters(request: httpx2.Request) -> None:
    """httpx2 request hook: turn `date__gte=...` into the API's `date[gte]=...`."""
    params = request.url.params
    if not any(_OPERATOR_PARAM.match(key) for key in params):
        return
    rewritten: list[tuple[str, str]] = []
    for key, value in params.multi_items():
        match = _OPERATOR_PARAM.match(key)
        rewritten.append((f"{match['name']}[{match['op']}]" if match else key, value))
    request.url = request.url.copy_with(params=rewritten)
