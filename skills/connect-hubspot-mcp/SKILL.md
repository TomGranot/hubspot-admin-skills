---
name: connect-hubspot-mcp
description: "Connect Claude to HubSpot's official remote MCP server for conversational CRM lookups, spot-checks, and small confirmed edits. Covers the MCP connector setup with OAuth and PKCE, what the server's tools can and cannot do, and when to use MCP versus the Agent CLI versus this repo's scripts."
license: MIT
metadata:
  author: tomgranot
  version: "2.0"
  category: audit-planning
---

# Connect Claude to HubSpot via MCP

Set up HubSpot's official remote MCP server so Claude can read and write CRM records conversationally: look up a contact, inspect a company's deals, spot-check the results of a cleanup, without writing a script for every question.

## Three Ways to Reach a Portal

This toolkit can talk to HubSpot three ways. They overlap less than they appear to.

| | Remote MCP server (this skill) | Agent CLI (`/connect-hubspot-agent-cli`) | REST scripts (every scripted skill) |
|---|---|---|---|
| Status | Generally available | Beta | v3/v4 paths, see `/audit-api-usage` |
| Auth | OAuth as you, via an MCP connector | OAuth as you, or a service key | Service key in `.env` |
| Best for | Lookups, spot-checks, judgment calls, small edits | Bulk and admin work driven from the terminal | Repeatable runs with a CSV audit trail and an abort threshold |
| Bulk reads | 200 records per page | Paginated, JSONL out | Paginated |
| Bulk writes | A few records at a time, each confirmed | JSONL in, dry run first | Batches of 100 |
| Delete or archive | **Not available** | Yes, guarded | Yes, guarded |
| Workflows | **Not available** | List, get, create, update, delete | Create, export, restore |
| Properties | Create only | Create, update, archive | Create |
| Runs headless (CI, scheduled) | No | With a service key | Yes |

Rule of thumb: **MCP to look, scripts to change at scale.** Reach for the Agent CLI when a job is bulk or administrative and no scripted skill covers it.

| Task shape | Use |
|-----------|-----|
| "Show me 5 contacts the cleanup touched" | MCP |
| "Why is this company in Tier 2?" | MCP |
| "Which open deals has nobody touched this quarter? Show me a few." | MCP |
| "Delete 4,000 no-email contacts with an audit trail" | Scripts (`/delete-no-email-contacts`) |
| "Create 10 segmentation lists" | Scripts (`/build-smart-lists`) |
| "Export every workflow to JSON" | Scripts (`/workflows-as-code`) |
| "Archive these 60 unused properties" | Agent CLI |

## What the Server Exposes

HubSpot's remote MCP server lives at `https://mcp.hubspot.com` and speaks streamable HTTP. It currently offers 32 tools. The ones that matter for CRM administration:

| Tool | What it does | Limit |
|------|--------------|-------|
| `get_user_details` | Your user, account, and per-object read/write access | Run this first to verify the connection |
| `discover_hubspot_schema` | Object types and whether each is readable or writable | |
| `search_crm_objects` | Search and filter records | 5 filter groups of 6 filters; 200 results per page |
| `get_crm_objects` | Fetch records by ID | 100 IDs per call |
| `query_crm_data` | SQL-style aggregate queries | No joins, subqueries, aliases, or association traversal |
| `search_properties`, `get_properties` | Property definitions and enum values | 5 keywords per search |
| `search_owners` | Owners by name, email, or ID | 100 results |
| `manage_crm_objects` | Create or update records and activities | Shows a change summary and waits for confirmation |
| `manage_custom_properties` | Create custom properties | Create only |
| `manage_custom_pipelines` | Create and manage pipelines | Can edit the default pipeline |
| `manage_segment` | Create segments; add or remove records in static segments | Requires confirmation |
| `get_marketing_email_analytics` | Send statistics, health diagnostics, per-contact engagement | |
| `tool_guidance` | Usage instructions for the other tools | Call before `query_crm_data` |

The rest cover campaigns, conversations, buyer intent, landing and website pages, blog posts, and AEO.

Readable objects include contacts, companies, deals, tickets, leads, custom objects, segments, activities, and owners. Revenue objects (invoices, orders, line items, products, quotes, subscriptions) are read-only and in beta.

**What it cannot do**, and what to use instead:

| Cannot | Use instead |
|--------|-------------|
| Delete or archive anything | The scripted skill for that cleanup, or the Agent CLI |
| Read or change workflows | `/workflows-as-code`, `/cleanup-workflows`, or the Agent CLI |
| Update or archive a property | `/cleanup-properties` or the Agent CLI |
| Page through a large result set efficiently | A script. Use `query_crm_data` when a count or aggregate is all you need |
| Read activities or conversations when Sensitive Data is enabled | The REST API, which is unaffected |

## Prerequisites

- A HubSpot user who can create an MCP connector, or an admin who will create one for you
- Claude Code, or the Claude app on a Pro, Max, Team, or Enterprise plan
- Nothing else. This is separate from the service key the scripts use: MCP connects as *you*, with your HubSpot permissions

## Execution Pattern

### Stage 1: Plan

1. Decide who is connecting. Access is user-scoped, so connect with a user whose permissions match what you want Claude to be able to do. A read-only user gives a read-only connection.
2. Check with a Super Admin whether the portal restricts who can connect apps. MCP connections may need approval.

### Stage 2: Execute

**Option A: the HubSpot connector in the Claude app (no terminal).** In Claude's connector settings, add the HubSpot connector and complete the OAuth flow in the browser. HubSpot's guide: knowledge.hubspot.com, "Set up and use the HubSpot connector for Claude". It runs on the same remote server, and HubSpot caps its bulk create and update at 10 records at a time.

**Option B: Claude Code.** The server does not support dynamic client registration, so a bare `claude mcp add` cannot authenticate. Register a connector first:

1. In HubSpot, go to **Development > MCP Connectors** and click **Create MCP connector**.
2. Give it a name and a redirect URL. Claude Code listens on localhost during OAuth, so pick a fixed port and register `http://localhost:8765/callback`. The redirect URL must match exactly; if authentication fails with a redirect mismatch, copy the URL from the error into the connector.
3. Open the connector and copy its client ID and client secret.
4. Add the server, using the same port:

   ```bash
   claude mcp add --transport http --client-id YOUR_CLIENT_ID --client-secret --callback-port 8765 hubspot https://mcp.hubspot.com
   ```

   Claude Code prompts for the secret. Do not paste it into the command line or commit it.
5. In Claude Code, run `/mcp`, choose `hubspot`, and authenticate. Pick the account, review the permissions, and authorize.

You do not choose scopes. They are derived from the tools the server offers and the permissions you grant. When HubSpot adds tools that need new scopes, reconnect to grant them.

HubSpot has not published Claude Code setup steps for the remote server; the steps above follow from the server's OAuth metadata and Claude Code's `claude mcp add` options. If they stop working, the connector in the Claude app (Option A) is the supported path.

### Stage 3: After

Ask Claude for a harmless read and confirm it round-trips:

> "Using the HubSpot MCP tools, call get_user_details, then fetch one contact and tell me its lifecycle stage."

`get_user_details` also reports which objects the connection can write to. If that list is longer than you intended, reconnect as a user with narrower permissions.

If the call fails, check that the OAuth flow completed, that the redirect URL and port match the connector, and that the portal has not blocked the connection.

## Rollback

- Remove the server from Claude Code: `claude mcp remove hubspot`.
- Revoke the connection in HubSpot under Settings > Integrations > Connected Apps, and delete the MCP connector under Development > MCP Connectors. Deleting the connector invalidates its tokens.

## Technical Gotchas

1. **MCP access is user-scoped.** Claude can do exactly what your HubSpot user can do. There is no separate permission layer to fall back on.
2. **No deletes is a feature, not a gap to work around.** The server cannot archive records, so a conversational session cannot wipe a segment by accident. Destructive work goes through skills that export a CSV first and stop at a threshold.
3. **Two credentials, two purposes.** The service key in `HUBSPOT_ACCESS_TOKEN` powers the scripts; the MCP connection powers conversational access. Rotating one does not affect the other, and a service key cannot authenticate to the MCP server.
4. **Counts and lists are different tools.** For "how many", use `query_crm_data`. For "show me", use `search_crm_objects`. Paging 200 at a time to count a large segment is slow and burns context.
5. **Sensitive Data blocks activities.** With Sensitive Data enabled on the account, calls, emails, meetings, notes, tasks, and conversations are unavailable through MCP.
6. **Not for headless runs.** Interactive OAuth is unavailable in scheduled or CI runs. Scripts with a service key run anywhere; treat MCP as the interactive layer.
7. **`@hubspot/mcp-server` on npm is a different thing.** That local package targets app developers and has not been released since mid-2025. Do not build CRM administration on it.
8. **HubSpot ships its own Claude Code plugins.** `HubSpot/hubspot-mcp-plugins` bundles this same server for sales-rep and partner workflows. They complement this toolkit; they do not cover hygiene or administration.
