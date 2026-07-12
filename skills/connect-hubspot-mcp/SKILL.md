---
name: connect-hubspot-mcp
description: "Connect Claude Code to HubSpot's official remote MCP server for natural-language CRM reads and writes. Covers OAuth setup, scope selection, verification, and when to use MCP versus this repo's API scripts."
license: MIT
metadata:
  author: tomgranot
  version: "1.1"
  category: audit-planning
---

# Connect Claude Code to HubSpot via MCP

Set up HubSpot's official remote MCP server so Claude can read and write CRM records conversationally — look up a contact, inspect a company's deals, spot-check the results of a cleanup — without writing a script for every question.

## What the MCP Server Is (and Isn't)

HubSpot's remote MCP server (generally available since April 2026) is an OAuth-secured gateway at `mcp.hubspot.com` that exposes CRM operations as tools to MCP clients like Claude Code:

- **Read/write CRM objects**: contacts, companies, deals, tickets, line items, products, engagements
- **Read content**: campaigns, landing pages, website pages, blog posts, and content analytics
- **Create content**: landing pages (added June 2026)

It is the right tool for **interactive, judgment-heavy work**: spot-checks, triage, one-off lookups, small targeted edits. It is the wrong tool for **bulk operations**: batch-archiving thousands of contacts, paginated sweeps, or anything that needs a CSV audit trail and an abort threshold. That is what this repo's scripts are for. The two share the same portal — use both.

| Task shape | Use |
|-----------|-----|
| "Show me 5 contacts the cleanup touched" | MCP |
| "Why is this company in Tier 2?" | MCP |
| "Review this week's bounce-flagged contacts" | MCP |
| "Delete 4,000 no-email contacts with an audit trail" | Scripts (`/delete-no-email-contacts`) |
| "Create 10 segmentation lists" | Scripts (`/build-smart-lists`) |
| "Export every workflow to JSON" | Scripts (`/workflows-as-code`) |

## Prerequisites

- A HubSpot account and a user with permission to create user-level apps (or approval via your portal's MCP Auth Apps governance, if enabled)
- Claude Code (or another MCP client)
- This is **separate** from the private app token the scripts use — MCP connects via OAuth as *you*, with your HubSpot permissions

## Execution Pattern

### Stage 1: Plan

1. Decide the scopes to grant. Start read-only (CRM object read scopes); add write scopes only if you want Claude making edits through MCP.
2. Check with your admin whether the portal restricts app installs (App Install Governance) — MCP connections may need approval.

### Stage 2: Execute — Connect

**Option A: HubSpot Connector for Claude (no terminal).** In Claude's connector settings, add the HubSpot connector and complete the OAuth flow in the browser. HubSpot's guide: knowledge.hubspot.com > "Set up and use the HubSpot connector for Claude".

**Option B: MCP client configuration.** Add the remote server to Claude Code:

```bash
claude mcp add --transport http hubspot https://mcp.hubspot.com
```

Then authenticate when prompted — the OAuth flow creates a user-level app with the scopes you approve.

**Option C: HubSpot CLI.** With HubSpot CLI v8.2.0+, `hs mcp setup` walks through connecting an MCP client, and also offers HubSpot's *local developer* MCP server (aimed at app development rather than CRM administration).

### Stage 3: After — Verify

Ask Claude to perform a harmless read and confirm it round-trips:

> "Using the HubSpot MCP tools, fetch one contact and tell me its email and lifecycle stage."

If the call fails: check that the OAuth flow completed, the scopes include contact read, and your portal hasn't blocked the connection via app governance.

## Rollback

- Disconnect the MCP server from your client settings (`claude mcp remove hubspot` in Claude Code).
- Revoke the connection in HubSpot: Settings > Integrations > Connected Apps — removing the user-level app invalidates its tokens.

## Technical Gotchas

1. **MCP access is user-scoped.** Claude can do exactly what your HubSpot user can do — no more, no less. Bulk-risky operations are naturally bounded by the scopes you grant; grant write scopes deliberately.
2. **Two credentials, two purposes.** `HUBSPOT_ACCESS_TOKEN` (private app) powers the scripts; the MCP OAuth connection powers conversational access. Rotating one does not affect the other.
3. **Rate limits still apply.** MCP calls consume the same API capacity as any integration. Don't use MCP for high-volume sweeps — that's script territory.
4. **Headless environments.** MCP servers that require interactive OAuth may be unavailable in scheduled/CI runs. Scripts with a private app token work everywhere; treat MCP as the interactive layer.
