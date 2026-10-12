---
name: connect-hubspot-agent-cli
description: "Install and connect HubSpot's Agent CLI so Claude Code can run bulk and administrative HubSpot operations directly from the terminal: JSONL bulk writes, deletes, property and pipeline management, and workflow CRUD, with dry runs. Covers user versus service key mode, safe-use rules, and how the CLI fits beside MCP and this repo's scripts."
license: MIT
metadata:
  author: tomgranot
  version: "1.0"
  category: audit-planning
---

# Connect Claude Code to HubSpot via the Agent CLI

HubSpot's Agent CLI is a command-line tool built for AI agents. Where the MCP server is for looking things up in conversation, the CLI is for doing administrative work: it reads and writes in bulk, deletes, manages properties and pipelines, and creates workflows. It is the most direct connection between Claude Code and a portal.

## Why This Matters

Before the CLI, any HubSpot job that was too big for MCP needed a purpose-written script. That is still the right answer for work you repeat and need to audit. For the long tail of one-off administrative jobs (archive these 60 properties, re-label this association, upsert this file) a script is overhead, and the CLI fills the gap.

**It is beta.** HubSpot states that commands, flags, and behavior may change without notice. Treat it as a power tool for supervised sessions, not as a dependency for anything scheduled.

## Where It Fits

| | Agent CLI (this skill) | Remote MCP (`/connect-hubspot-mcp`) | REST scripts (scripted skills) |
|---|---|---|---|
| Status | Beta | Generally available | v3/v4 paths |
| Delete and archive | Yes, guarded | No | Yes, guarded |
| Workflows | List, get, create, update, delete | No | Create, export, restore |
| Bulk input | JSONL on stdin | A few records at a time | Batches of 100 |
| Audit trail | Local `history` log of destructive operations | None | CSV export before every mutation |
| Abort threshold | None built in | Not applicable | Hard-coded per skill |
| Use it for | One-off bulk and admin jobs, supervised | Lookups and spot-checks | Anything repeatable or destructive at scale |

When a scripted skill exists for the job, prefer the skill. It was written with a threshold, an export, and a rollback note for that specific operation. Use the CLI when no skill covers the job, and apply the safe-use rules below yourself.

## Prerequisites

- Claude Code, with permission to run shell commands
- A HubSpot user whose permissions cover the work. The CLI is available on all HubSpot plans
- Approval from a Super Admin if the portal restricts who can connect apps
- On Claude Team or Enterprise, an admin may need to allowlist `api.hubapi.com`

## Execution Pattern

### Stage 1: Plan

Decide which mode you need before installing:

| Mode | How | Acts as | Use when |
|------|-----|---------|----------|
| User | `hubspot auth login` | You, with your HubSpot permissions | Almost always |
| Admin | `HUBSPOT_ACCESS_TOKEN` set to a service key | The service key's scopes | Schema changes, association batch operations, and other calls that need account-level access |

Start in user mode. It cannot exceed what you could do by hand in the UI.

### Stage 2: Execute

1. **Install.** Read the script before running it, as with any `curl | sh`:

   ```bash
   curl -fsSL https://api.hubapi.com/hub/cli/backend/hub-cli/latest/install.sh | sh
   ```

   On Windows PowerShell: `irm https://api.hubapi.com/hub/cli/backend/hub-cli/latest/install.ps1 | iex`

   The binary is `hubspot`. It is separate from `hs`, HubSpot's developer CLI for building apps and CMS projects.

2. **Verify and sign in.**

   ```bash
   hubspot --version
   ```

   ```bash
   hubspot auth login
   ```

   The login opens a browser. Review the requested permissions and connect.

3. **Confirm which portal you are in.**

   ```bash
   hubspot whoami
   ```

   Read the account name and ID back to the user and wait for them to confirm it is the intended portal. This matters most for anyone with access to more than one account.

4. **Optionally install HubSpot's own skills** for the CLI. They teach an agent the command surface and are complementary to this toolkit:

   ```bash
   npx skills add hubspot/agent-cli-skills
   ```

**Admin mode**, only when a command needs it: put a service key in the environment for that session and remove it afterward.

```bash
export HUBSPOT_ACCESS_TOKEN=pat-na1-xxxxxxxx
```

```bash
unset HUBSPOT_ACCESS_TOKEN
```

This is the same variable this repo's scripts read from `.env`. If it is exported in your shell, the CLI silently runs in admin mode. Check `hubspot whoami` before any write.

### Stage 3: After

Run a read and confirm the output matches the portal:

```bash
hubspot owners list --format table
```

The owner names should be people the user recognizes. If they are not, you are in the wrong account: stop and sign in again.

Before the first real write, run that command with `--dry-run` and read the preview together with the user, so the guard rails are familiar before they are needed.

## Command Surface

| Group | Subcommands |
|-------|-------------|
| `objects` | `types`, `list`, `get`, `search`, `create`, `update`, `upsert`, `merge`, `delete` |
| `properties` | `list`, `get`, `create`, `update`, `delete`, `batch-read`, `batch-create`, `batch-archive` |
| `pipelines` | `list`, `get`, `create`, `update`, `delete`, plus `stages` variants |
| `associations` | `list`, `create`, `delete`, batch variants, labels, limits |
| `workflows` | `list`, `get`, `create`, `update`, `delete` |
| `segments` (alias `lists`) | Segment and list management |
| `schemas` | `list`, `get`, `create`, `update`, `delete` |
| `owners` | `list` |
| `views`, `reports`, `imports`, `query`, `sequences`, `marketing`, `conversations`, `analytics`, `buyer-intent` | See `hubspot help` |
| `history` | Local log of destructive operations |

Run `hubspot help <group>` for exact flags; they are the part most likely to change during the beta.

Mutation commands read JSONL from stdin, one record per line, and commands emit JSONL by default (`--format json` and `--format table` are also available):

```bash
cat updates.jsonl | hubspot objects update --type contacts --dry-run
```

## Safe-Use Rules

The CLI gives an agent real destructive power with fewer guard rails than this repo's scripts. Apply these every time.

1. **Dry run first, always.** Every write supports `--dry-run`. Run it, show the user the preview, and wait for confirmation before the real call. Some destructive commands refuse to run without the digest a dry run produces.
2. **Export before you mutate.** The CLI does not write a before-state CSV. Save the affected records to `data/audit-logs/` first (that directory is gitignored, because the export may contain personal data):

   ```bash
   hubspot objects search --type contacts --format jsonl > data/audit-logs/contacts-before.jsonl
   ```
3. **Set your own threshold.** Count before you change. If the count is larger than the user expected, stop and ask rather than proceeding.
4. **Confirm the portal in the same session as the write.** `hubspot whoami`, every time, not from memory.
5. **Never delete in admin mode by default.** A service key bypasses the per-user permission check that would otherwise stop a mistake.
6. **Prefer the scripted skill when one exists.** `/delete-no-email-contacts`, `/reassign-deactivated-owners`, `/cleanup-workflows`, and the rest carry safeguards tuned to their operation.
7. **Treat generated JSONL as untrusted until reviewed.** A bulk file Claude produced is a proposal. Show a sample and the row count before piping it into a write.

## Rollback

- Sign out: `hubspot auth logout`. Revoke the connection in HubSpot under Settings > Integrations > Connected Apps.
- `hubspot history` lists the destructive operations run from this machine, which tells you what to undo.
- Deleted CRM records are restorable from HubSpot's recycling bin for 90 days. Property values overwritten by an update are not restorable unless you exported them first. Deleted workflows are not restorable through any API.

## Technical Gotchas

1. **Beta means the commands in this skill may be stale.** If a flag here is rejected, trust `hubspot help` over this document, and open an issue or PR on this repo.
2. **`hubspot` is not `hs`.** `hs` is the developer CLI. Its `hs mcp setup` command installs a *developer* MCP server for building apps, which does not administer CRM data.
3. **Shared environment variable.** The CLI's admin mode and this repo's scripts both read `HUBSPOT_ACCESS_TOKEN`. Keeping the token in `.env` rather than exporting it in your shell profile keeps the CLI in user mode unless you choose otherwise.
4. **Rate and size limits are undocumented.** HubSpot has not published the CLI's limits. Break very large jobs into files you can verify one at a time, and expect the general API limits to apply (see `/audit-api-usage`).
5. **Revenue records are read-only** unless a Super Admin has opted the account into the separate revenue beta.
6. **User mode inherits your blind spots.** If your user cannot see a team's records, neither can the CLI, and a "complete" export will be silently partial.
