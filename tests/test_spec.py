import re
from typing import Any

import httpx2

from eboekhouden_mcp.spec import load_raw_spec, load_spec, rewrite_filters

METHODS = {"get", "post", "patch", "put", "delete"}


def operations(spec: dict[str, Any]) -> list[dict[str, Any]]:
    paths: dict[str, dict[str, Any]] = spec["paths"]
    return [op for item in paths.values() for m, op in item.items() if m in METHODS]


def test_internal_paths_removed() -> None:
    paths = load_spec()["paths"]
    assert not any(p.startswith(("/swagger", "/v1/session")) for p in paths)
    assert "/v1/invoice" in paths


def test_every_operation_has_an_operation_id() -> None:
    assert all(op.get("operationId") for op in operations(load_spec()))


def test_descriptions_have_no_html() -> None:
    spec = load_spec()
    for key in ("paths", "components"):
        assert "<table>" not in str(spec[key])
        assert "<br>" not in str(spec[key])


def test_vendored_file_is_untouched() -> None:
    assert "<table>" in str(load_raw_spec()["paths"])


def test_filter_parameters_get_operator_variants() -> None:
    params = {p["name"]: p for p in load_spec()["paths"]["/v1/invoice"]["get"]["parameters"]}
    assert {"date", "date__gte", "date__lte", "invoiceNumber__like"} <= params.keys()
    assert "relationId__gte" not in params  # plain int32, not a filter


async def test_rewrite_filters() -> None:
    request = httpx2.Request(
        "GET", "https://x/v1/invoice", params={"date__gte": "2025-01-01", "limit": 5}
    )
    await rewrite_filters(request)
    assert request.url.params["date[gte]"] == "2025-01-01"
    assert request.url.params["limit"] == "5"
    assert "date__gte" not in request.url.params


def test_dangling_schema_refs_removed() -> None:
    spec = load_spec()
    known = spec["components"]["schemas"].keys()
    assert '"#/components/schemas/MutationsResponseDto"' in str(load_raw_spec()).replace("'", '"')
    refs = re.findall(r"#/components/schemas/(\w+)", str(spec))
    assert refs
    assert set(refs) <= known


def test_numeric_enums_accept_integers() -> None:
    mutation_type = load_spec()["components"]["schemas"]["MutationType"]
    assert mutation_type["type"] == ["string", "integer"]
    assert "4" in mutation_type["enum"]
    assert 4 in mutation_type["enum"]
    assert load_raw_spec()["components"]["schemas"]["MutationType"]["type"] == "string"
