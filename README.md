# eboekhouden-mcp

An [MCP](https://modelcontextprotocol.io) server for the [e-boekhouden.nl](https://www.e-boekhouden.nl) API. Its tools are generated from e-boekhouden's OpenAPI spec.

**Unofficial; not affiliated with e-boekhouden.nl.**

Read-only by default: only `get_*` tools are available unless you set `EB_ALLOW_WRITES=true`.

## Setup

1. In e-boekhouden, create an API token: **Beheer → Inrichting → Koppelingen → API → e-Boekhouden API**.
2. Install [uv](https://docs.astral.sh/uv/) and clone this repository.
3. Store the token in a `.env` file in this directory (it is git-ignored):

   ```sh
   cp .env.example .env
   chmod 600 .env
   # then set EB_API_TOKEN in that file
   ```

4. Add the server to your MCP client, for example Claude Code:

   ```sh
   claude mcp add e-boekhouden -- uv run --directory /path/to/e-boekhouden-mcp eboekhouden-mcp
   ```

   Or in a JSON client config:

   ```json
   {
     "mcpServers": {
       "e-boekhouden": {
         "command": "uv",
         "args": ["run", "--directory", "/path/to/e-boekhouden-mcp", "eboekhouden-mcp"]
       }
     }
   }
   ```

## Configuration

Set these in the `.env` file in this directory or as environment variables (which take precedence). A `.env` in any other working directory is not read.

| Variable          | Default                       | Description                                          |
|-------------------|-------------------------------|------------------------------------------------------|
| `EB_API_TOKEN`    | *(required)*                  | e-boekhouden API token                               |
| `EB_ALLOW_WRITES` | `false`                       | Also expose create/update/delete tools               |
| `EB_SOURCE`       | `MCP`                         | Integration name sent to e-boekhouden (max 10 chars) |
| `EB_BASE_URL`     | `https://api.e-boekhouden.nl` | API URL (must be `https://` on `e-boekhouden.nl`)    |
| `EB_TIMEOUT`      | `30`                          | HTTP timeout in seconds                              |

## Tools

Always available:

| Tool                         | Description                                         |
|------------------------------|-----------------------------------------------------|
| `get_administrations`        | List administrations managed by the accountant      |
| `get_linked_administrations` | List administrations linked to this one             |
| `get_cost_centers`           | List cost centers                                   |
| `get_cost_center`            | Get a cost center                                   |
| `get_email_templates`        | List email templates                                |
| `get_invoices`               | Search invoices                                     |
| `get_invoice`                | Get an invoice                                      |
| `get_invoice_templates`      | List invoice templates                              |
| `get_outstanding_invoices`   | List outstanding invoices                           |
| `get_ledgers`                | List ledgers                                        |
| `get_ledger`                 | Get a ledger                                        |
| `get_balance`                | Get the balance of one ledger                       |
| `get_balances`               | Get the balances of all ledgers                     |
| `get_members`                | List members (clubs and associations only)          |
| `get_member`                 | Get a member (clubs and associations only)          |
| `get_mutations`              | List mutations (journal entries)                    |
| `get_mutation`               | Get a mutation                                      |
| `get_products`               | List products                                       |
| `get_product`                | Get a product                                       |
| `get_product_group`          | List product groups                                 |
| `get_relations`              | List relations (customers and suppliers)            |
| `get_relation`               | Get a relation                                      |
| `get_units`                  | List units                                          |

With `EB_ALLOW_WRITES=true`:

| Tool                 | Description                                   |
|----------------------|-----------------------------------------------|
| `create_cost_center` | Create a cost center                          |
| `update_cost_center` | Update a cost center                          |
| `delete_cost_center` | Delete a cost center                          |
| `create_invoice`     | Create an invoice                             |
| `create_ledger`      | Create a ledger                               |
| `update_ledger`      | Update a ledger                               |
| `create_member`      | Create a member (clubs and associations only) |
| `update_member`      | Update a member (clubs and associations only) |
| `create_mutation`    | Create a mutation                             |
| `create_product`     | Create a product                              |
| `update_product`     | Update a product                              |
| `delete_product`     | Delete a product                              |
| `create_relation`    | Create a relation                             |
| `update_relation`    | Update a relation                             |

## Development

```sh
uv sync
uv run pytest
uv run ruff check && uv run ruff format --check && uv run pyright
```

To update the bundled API spec, run `uv run scripts/update_spec.py` and review the diff.

## License

MIT
