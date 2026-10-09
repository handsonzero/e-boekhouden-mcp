import httpx2
from fastmcp import Client

from eboekhouden_mcp.config import Settings
from eboekhouden_mcp.server import build_server, tool_name
from tests.conftest import FakeApi


def test_tool_name() -> None:
    assert tool_name("GetOutstandingInvoices") == "get_outstanding_invoices"
    assert tool_name("CreateInvoice") == "create_invoice"


async def test_read_only_by_default(settings: Settings, transport: httpx2.MockTransport) -> None:
    async with Client(build_server(settings, transport)) as client:
        tools = await client.list_tools()
    assert len(tools) > 20
    assert all(t.name.startswith("get_") for t in tools)
    assert all(t.annotations and t.annotations.read_only_hint for t in tools)


async def test_writes_opt_in(settings: Settings, transport: httpx2.MockTransport) -> None:
    settings.allow_writes = True
    async with Client(build_server(settings, transport)) as client:
        tools = {t.name: t for t in await client.list_tools()}
    assert {"create_invoice", "create_mutation", "delete_product"} <= tools.keys()
    delete = tools["delete_product"].annotations
    assert delete is not None
    assert delete.destructive_hint
    assert not delete.read_only_hint


async def test_call_get_invoices(
    settings: Settings, transport: httpx2.MockTransport, api: FakeApi
) -> None:
    invoice = {"Id": 1000, "InvoiceNumber": "F00001", "TotalAmount": 131.89}

    def invoices(_: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"Items": [invoice], "Count": 1})

    api.routes[("GET", "/v1/invoice")] = invoices
    async with Client(build_server(settings, transport)) as client:
        result = await client.call_tool(
            "get_invoices", {"limit": 5, "offset": 10, "date__gte": "2025-01-01"}
        )
    assert result.structured_content == {"Items": [invoice], "Count": 1}
    (request,) = api.api_requests
    assert request.headers["Authorization"] == "session-1"
    assert dict(request.url.params) == {"limit": "5", "offset": "10", "date[gte]": "2025-01-01"}


async def test_call_get_mutation_with_integer_type(
    settings: Settings, transport: httpx2.MockTransport, api: FakeApi
) -> None:
    mutation: dict[str, object] = {
        "id": 6,
        "type": 7,
        "date": "2026-09-14",
        "ledgerId": 1700,
        "rows": [],
    }
    api.routes[("GET", "/v1/mutation/6")] = lambda _: httpx2.Response(200, json=mutation)
    async with Client(build_server(settings, transport)) as client:
        result = await client.call_tool("get_mutation", {"id": 6})
    assert result.structured_content == {"result": mutation}
