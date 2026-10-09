"""MCP server exposing the e-boekhouden REST API, generated from its OpenAPI spec."""

import re
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from typing import Any, cast

import httpx2
from fastmcp import FastMCP
from fastmcp.server.providers.openapi import (
    MCPType,
    OpenAPIResource,
    OpenAPIResourceTemplate,
    OpenAPITool,
)
from fastmcp.utilities.openapi import HTTPRoute
from mcp.types import ToolAnnotations
from pydantic import ValidationError

from eboekhouden_mcp.auth import SESSION_PATH, SessionAuth
from eboekhouden_mcp.config import Settings
from eboekhouden_mcp.spec import load_spec, rewrite_filters

INSTRUCTIONS = """\
Access to a Dutch e-boekhouden.nl bookkeeping administration.

- List tools are paginated: `limit` (default 100, max 2000) and `offset`. Responses
  contain `Items` and the total `Count`; page further when Count exceeds the items.
- Dates are ISO 8601 `YYYY-MM-DD`. Amounts are in EUR.
- Filter variants: `<field>__gte` / `<field>__lte` for date and number ranges, and
  `<field>__like` for wildcard text search (`%` = any characters, `?` = one character).
- Mutations are journal entries; outstanding invoices are under get_outstanding_invoices.
- VAT codes: HOOG_VERK_21 / LAAG_VERK_9 (sales 21%/9%), HOOG_INK_21 / LAAG_INK_9
  (purchases 21%/9%), VERL_* reverse charge, BI_EU_* / BU_EU_* within/outside the EU.
"""


def tool_name(operation_id: str) -> str:
    """`GetOutstandingInvoices` -> `get_outstanding_invoices`."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", operation_id).lower()


def build_server(settings: Settings, transport: httpx2.AsyncBaseTransport | None = None) -> FastMCP:
    """Build the MCP server. `transport` lets tests swap in a mock HTTP transport."""
    spec = load_spec()
    auth = SessionAuth(settings.api_token, settings.source)
    client = httpx2.AsyncClient(
        base_url=settings.base_url,
        auth=auth,
        timeout=settings.timeout,
        transport=transport,
        event_hooks={"request": [rewrite_filters]},
    )

    def route_map_fn(route: HTTPRoute, _mcp_type: MCPType) -> MCPType:
        if route.method != "GET" and not settings.allow_writes:
            return MCPType.EXCLUDE
        return MCPType.TOOL

    def mcp_component_fn(
        route: HTTPRoute, component: OpenAPITool | OpenAPIResource | OpenAPIResourceTemplate
    ) -> None:
        if not isinstance(component, OpenAPITool):
            return
        component.annotations = ToolAnnotations(
            read_only_hint=route.method == "GET",
            destructive_hint=route.method == "DELETE",
            idempotent_hint=route.method in {"GET", "PATCH", "DELETE"},
            open_world_hint=True,
        )

    @asynccontextmanager
    async def lifespan(_: FastMCP) -> AsyncGenerator[None]:
        async with client:
            yield
            if auth.token:  # Revoke the session token on shutdown.
                with suppress(httpx2.HTTPError):
                    await client.delete(SESSION_PATH)

    # Path items hold operations (dicts) next to shared `parameters` (list) and `summary` (str).
    paths = cast(dict[str, dict[str, dict[str, Any] | list[Any] | str]], spec["paths"])
    operation_ids = [
        str(op["operationId"])
        for item in paths.values()
        for op in item.values()
        if isinstance(op, dict) and "operationId" in op
    ]
    return FastMCP.from_openapi(
        openapi_spec=spec,
        client=client,
        name="e-boekhouden",
        instructions=INSTRUCTIONS,
        lifespan=lifespan,
        route_map_fn=route_map_fn,
        mcp_component_fn=mcp_component_fn,
        mcp_names={op_id: tool_name(op_id) for op_id in operation_ids},
    )


def main() -> None:
    try:
        settings = Settings()  # pyright: ignore[reportCallIssue]
    except ValidationError as e:
        sys.exit(f"eboekhouden-mcp: invalid configuration, set EB_API_TOKEN.\n{e}")
    build_server(settings).run()
