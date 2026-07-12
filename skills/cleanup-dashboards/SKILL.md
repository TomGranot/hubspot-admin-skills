---
name: cleanup-dashboards
description: "Audit and consolidate HubSpot reporting dashboards. Identifies unused, duplicate, or outdated dashboards. Must be performed manually — no dashboard API is available."
license: MIT
metadata:
  author: tomgranot
  version: "1.1"
  category: ongoing-maintenance
---

# Cleanup Dashboards

Audit HubSpot dashboards to remove clutter and consolidate reporting. Too many dashboards means nobody uses any of them effectively.

## Important Limitation

HubSpot does not provide a Dashboard API. This entire process must be performed manually in the HubSpot UI under Reports > Dashboards.

## Prerequisites

- HubSpot portal access with dashboard management permissions
- Input from team members on which dashboards they actively use

## Step-by-Step Instructions

### Stage 1: Before — Inventory All Dashboards

1. Navigate to Reports > Dashboards in HubSpot.
2. Create a spreadsheet listing every dashboard:
   - Name, owner/creator, number of reports, last viewed date (if visible), purpose

### Stage 2: Execute — Identify Candidates for Removal

Flag dashboards matching any of these criteria:

1. **Not viewed** in 90+ days (check with the owner first)
2. **Duplicate** dashboards covering the same metrics
3. **Test dashboards** (names containing "test", "draft", "copy of")
4. **Personal dashboards** belonging to departed employees
5. **Default dashboards** that were never customized

Consolidation targets:
- Merge dashboards with overlapping report widgets into a single comprehensive dashboard.
- Aim for 5-10 core dashboards maximum (e.g., Marketing Overview, Sales Pipeline, Email Health, Data Quality, Executive Summary).

### Stage 3: After — Clean Up and Reorganize

1. Delete confirmed unused dashboards.
2. Rename remaining dashboards with a clear naming convention (e.g., `[Team] - Purpose`).
3. Set appropriate sharing/visibility for each dashboard.
4. Communicate changes to the team — share links to the consolidated dashboards.

### Stage 4: Rollback

- Deleted dashboards cannot be restored.
- Before deleting, screenshot each dashboard or note which reports it contained.
- Individual reports within a dashboard are not deleted when the dashboard is removed — they remain available for re-use.

## Tips

- Assign a dashboard owner for each core dashboard — someone responsible for keeping it current.
- Review dashboards quarterly as part of the database cleanup routine.
- If a report on a dashboard shows stale or broken data, fix the underlying report rather than creating a new dashboard.
