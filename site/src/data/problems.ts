/**
 * The problem index: things HubSpot admins actually search for, each mapped
 * to the skill that fixes it. Powers /problems, per-problem landing pages,
 * FAQ structured data, and the agent-readable endpoints.
 *
 * `skill` must be a valid skill slug — pages silently skip problems whose
 * skill is missing, so a typo here means a vanished page, not a build error.
 */

export interface ProblemFaq {
  question: string;
  answer: string;
}

export interface Problem {
  slug: string;
  title: string;
  description: string;
  intro: string;
  skill: string;
  faqs: ProblemFaq[];
}

export const PROBLEMS: Problem[] = [
  {
    slug: 'hubspot-contacts-without-email',
    title: 'HubSpot is full of contacts with no email address',
    description:
      'Contacts without an email address cannot receive marketing, inflate your billed contact count, and clutter every report. How to find and delete them safely.',
    intro:
      'Contacts with no email cannot be marketed to, sequenced, or deduplicated reliably — but they still count toward your marketing contact bill and pollute segmentation. The fix is a scripted search-and-archive with a CSV audit trail and a safety threshold.',
    skill: 'delete-no-email-contacts',
    faqs: [
      {
        question: 'Is it safe to delete HubSpot contacts with no email?',
        answer:
          'Usually yes, but first check why they exist — an integration or form may be creating them intentionally. Deleted contacts are recoverable for 90 days via Settings > Data Management > Deleted Objects, and the skill exports a CSV of every record before deleting.',
      },
      {
        question: 'Do contacts without an email count toward my HubSpot bill?',
        answer:
          'Contacts set as marketing contacts count toward your billed tier whether or not they have an email. No-email marketing contacts are pure dead weight: unreachable but billed.',
      },
      {
        question: 'Can I bulk-delete contacts via the HubSpot API?',
        answer:
          'Yes — the CRM batch archive endpoint deletes up to 100 contacts per call. The skill paginates the Search API, exports an audit CSV, then batch-archives with rate limiting.',
      },
    ],
  },
  {
    slug: 'hubspot-hard-bounces-hurting-deliverability',
    title: 'Hard-bounced contacts are wrecking our email deliverability',
    description:
      'Repeatedly emailing hard-bounced addresses damages sender reputation. How to find every hard-bounced contact in HubSpot and suppress them for good.',
    intro:
      'Every send to a hard-bounced address tells inbox providers you do not clean your list. Left alone, this drags down deliverability for the contacts who do want your email. The fix: find every hard bounce, suppress them from marketing sends, and automate the suppression going forward.',
    skill: 'suppress-hard-bounced',
    faqs: [
      {
        question: 'How do I find all hard-bounced contacts in HubSpot?',
        answer:
          'Search on the hs_email_hard_bounce_reason_enum property — any contact where it is set has hard-bounced at least once. The skill runs this search via the API and exports the full list to CSV.',
      },
      {
        question: 'Can I set contacts as non-marketing via the HubSpot API?',
        answer:
          'No — hs_marketable_status is read-only via the API. The supported route is a workflow that sets marketing status, which the skill builds for you (created disabled, for review).',
      },
      {
        question: 'Should I delete hard-bounced contacts or just suppress them?',
        answer:
          'Suppress first: the record keeps its history and stays available for sales. Delete only if the record has no other value — deletion is covered by a separate skill with its own audit trail.',
      },
    ],
  },
  {
    slug: 'hubspot-still-emailing-unsubscribed-contacts',
    title: 'Globally unsubscribed contacts still count as marketing contacts',
    description:
      'Contacts who unsubscribed from all email still consume marketing contact slots. How to find and suppress them for compliance and cost.',
    intro:
      'A globally unsubscribed contact can never be emailed again, but if they are still set as a marketing contact you are paying for the privilege. Suppressing them cuts waste and keeps your consent posture clean.',
    skill: 'suppress-global-unsubscribes',
    faqs: [
      {
        question: 'How do I find all globally unsubscribed contacts in HubSpot?',
        answer:
          'Filter on hs_email_optout being true. The skill runs the search via the API, exports the list, and walks you through the suppression workflow.',
      },
      {
        question: 'Why can I not just delete unsubscribed contacts?',
        answer:
          'You need the unsubscribe record to honor consent — deleting a contact and later re-importing them can re-enable email by accident. Suppression preserves the opt-out.',
      },
    ],
  },
  {
    slug: 'hubspot-ghost-contacts-never-engaged',
    title: 'Thousands of contacts have never opened, clicked, or visited',
    description:
      'Ghost contacts — no opens, no clicks, no visits, no sales activity — dilute engagement metrics and inflate costs. How to identify and suppress them.',
    intro:
      'Ghosts are contacts with no recorded engagement of any kind. They depress open rates, skew attribution, and pad your bill. The skill finds them with layered API searches and suppresses them with a review-first workflow.',
    skill: 'suppress-ghost-contacts',
    faqs: [
      {
        question: 'What counts as a ghost contact in HubSpot?',
        answer:
          'No email opens or clicks, no page views, no form submissions, and no sales activity — checked via engagement properties like hs_email_last_open_date, hs_analytics_num_page_views, and hs_last_sales_activity_timestamp.',
      },
      {
        question: 'Should ghosts be deleted or suppressed?',
        answer:
          'Suppress first and watch for 90 days — some “ghosts” are data-sync artifacts of real accounts. The quarterly cleanup skill prunes confirmed dead weight later.',
      },
    ],
  },
  {
    slug: 'hubspot-duplicate-companies',
    title: 'Duplicate company records are splitting our account data',
    description:
      'Duplicate companies split deal history, confuse ownership, and break ABM reporting. How to detect duplicates by domain and merge them safely.',
    intro:
      'When one real company exists as three HubSpot records, deals, contacts, and activity scatter across them and every account-level report lies. Detection is scriptable (shared domains, similar names); merging needs care because company merges cannot be undone.',
    skill: 'merge-duplicate-companies',
    faqs: [
      {
        question: 'How do I find duplicate companies in HubSpot?',
        answer:
          'Group companies by the domain property — shared domains are near-certain duplicates. The skill also flags similar names for manual review, since the API cannot fuzzy-match natively.',
      },
      {
        question: 'Can company merges in HubSpot be undone?',
        answer:
          'No. Merges are permanent, which is why the skill exports a full before-state CSV of every property on both records before any merge, and merges one reviewed pair at a time.',
      },
    ],
  },
  {
    slug: 'hubspot-contacts-owned-by-deactivated-users',
    title: 'Contacts and deals are owned by people who left the company',
    description:
      'Deactivated HubSpot users still own thousands of records, so routing, alerts, and rotation silently fail. How to find and reassign orphaned records.',
    intro:
      'When someone leaves, deactivating their seat does not reassign their records. Workflows route leads to an inbox nobody reads, tasks fire into the void, and pipeline reviews miss deals. The fix is a scripted sweep of every object type owned by archived users.',
    skill: 'reassign-deactivated-owners',
    faqs: [
      {
        question: 'How do I find records owned by deactivated users in HubSpot?',
        answer:
          'The Owners API returns archived owners when you pass archived=true; the skill then searches contacts, companies, and deals for each archived owner ID and batch-reassigns them.',
      },
      {
        question: 'Who should orphaned records be reassigned to?',
        answer:
          'Map each departed user to a successor (territory or team based). The skill asks for the mapping up front and applies it with batch updates, with a CSV of every change.',
      },
    ],
  },
  {
    slug: 'hubspot-lifecycle-stages-wrong-or-missing',
    title: 'Lifecycle stages are missing, stuck, or plain wrong',
    description:
      'Contacts with no lifecycle stage, customers still marked as leads, MQLs that never progressed — how to audit and fix lifecycle stage data at scale.',
    intro:
      'Lifecycle stage drives routing, reporting, and automation — and it is one of the most commonly broken properties in any portal. The skill detects violations (missing stages, regressions, customers without won deals) and fixes them via the API, respecting HubSpot’s forward-only rule.',
    skill: 'fix-lifecycle-stages',
    faqs: [
      {
        question: 'Why can I not set a contact’s lifecycle stage backwards in HubSpot?',
        answer:
          'HubSpot only moves lifecycle stage forward. To regress a stage via the API you must clear the property first (set it to an empty string), then set the target stage in a second call — the skill handles both calls.',
      },
      {
        question: 'How do I find contacts with no lifecycle stage?',
        answer:
          'Search with the NOT_HAS_PROPERTY operator on lifecyclestage. Never-set is different from empty — HubSpot stores them differently, and the operator matters.',
      },
    ],
  },
  {
    slug: 'hubspot-contacts-missing-company-name',
    title: 'Contacts are missing company names their company records already have',
    description:
      'The associated company knows the name; the contact property is empty. How to backfill contact company names from associated companies via the API.',
    intro:
      'Personalization tokens, list filters, and lead scoring all read the contact-level company property — which is often empty even when the contact is associated to a fully populated company record. This is the cheapest enrichment you will ever run: your own data, copied across an association.',
    skill: 'enrich-company-name',
    faqs: [
      {
        question: 'Why is the contact company property empty when the contact has an associated company?',
        answer:
          'HubSpot does not automatically sync the company record’s name into the contact’s company property for existing records. The skill reads each association via the API and backfills the property, never overwriting non-empty values.',
      },
    ],
  },
  {
    slug: 'hubspot-country-state-values-inconsistent',
    title: '“USA”, “U.S.” and “united states” are three different countries in our reports',
    description:
      'Inconsistent country and state spellings break list filters, territory routing, and geo reports. How to standardize geographic values portal-wide.',
    intro:
      'Every list filter on country now needs six OR clauses, and your geo report has four Germanys. The skill inventories every distinct spelling, maps them to canonical values, and batch-updates with a full audit trail.',
    skill: 'standardize-geo-values',
    faqs: [
      {
        question: 'What is the best canonical format for country values in HubSpot?',
        answer:
          'Pick one standard — full English names (ISO short names) work best with HubSpot’s own IP-enrichment values — and normalize everything to it. The skill ships a default mapping you can edit before running.',
      },
    ],
  },
  {
    slug: 'hubspot-contact-data-incomplete-enrichment',
    title: 'We need phones, emails, and titles our CRM just does not have',
    description:
      'When internal data is exhausted, external enrichment fills the gaps. How to enrich HubSpot contacts with waterfall providers — FullEnrich, Apollo, Hunter, Dropcontact, or your own.',
    intro:
      'Internal backfills can only copy what you already know. For net-new emails, mobile numbers, and job titles you need an external provider — ideally a waterfall that tries many sources and only charges for hits. This skill makes the provider pluggable: FullEnrich by default, adapters for Apollo, Hunter, and Dropcontact, and a template for whatever you already pay for.',
    skill: 'waterfall-enrich-contacts',
    faqs: [
      {
        question: 'What is waterfall enrichment?',
        answer:
          'Instead of querying one data vendor, a waterfall tries a sequence of sources until one returns a verified value — typically doubling hit rates for emails and mobiles. FullEnrich (the default adapter) waterfalls across 20+ premium sources.',
      },
      {
        question: 'Will enrichment overwrite data we already trust?',
        answer:
          'Not by default: the skill never overwrites a non-empty HubSpot value unless you explicitly set ENRICHMENT_OVERWRITE=true, and every run has a hard contact cap and cost preview before anything is written.',
      },
      {
        question: 'Can I use my existing enrichment vendor instead of FullEnrich?',
        answer:
          'Yes — copy the provider template, implement one enrich() function against your vendor’s API, register it, and set ENRICHMENT_PROVIDER to its name.',
      },
    ],
  },
  {
    slug: 'hubspot-no-icp-tiers',
    title: 'We cannot report on our best-fit accounts because ICP is not in the CRM',
    description:
      'Without an ICP tier property, targeting and reporting run on gut feel. How to create ICP tiers in HubSpot and assign them from firmographic data.',
    intro:
      'Everyone agrees on the ICP in a slide deck; nobody encoded it in the CRM. The skill creates a tier property and assigns values from firmographics you already have (industry, size, geography) via batch updates — the prerequisite for lead scoring and smart lists that mean anything.',
    skill: 'create-icp-tiers',
    faqs: [
      {
        question: 'What data do I need before assigning ICP tiers?',
        answer:
          'Reasonably complete industry, employee count, and geography on companies. Run the enrichment and standardization skills first — tiering on dirty data just encodes the dirt.',
      },
    ],
  },
  {
    slug: 'hubspot-lead-scoring-after-2025-changes',
    title: 'Our lead scoring broke when HubSpot retired the old score properties',
    description:
      'HubSpot retired legacy score properties in August 2025. How to build lead scoring in the current Lead Scoring tool — fit and engagement scores, decay, thresholds.',
    intro:
      'The legacy “HubSpot Score” property stopped updating in August 2025. The current tool models Fit and Engagement as separate scores with groups, rules, decay, and thresholds — and its generated score properties are readable via the API even though configuration is UI-only. The skill designs the model and walks the build.',
    skill: 'build-lead-scoring',
    faqs: [
      {
        question: 'Can I configure HubSpot lead scoring via the API?',
        answer:
          'No — scoring rules are configured only in the UI. But each score generates properties (value and threshold) you can read, filter, and automate on via the API, which is how the skill verifies the model.',
      },
      {
        question: 'What replaced the old HubSpot Score property?',
        answer:
          'The Lead Scoring tool (Marketing Pro/Enterprise): separate Fit and Engagement scores per object, with rule groups, time-frames, and score decay. Existing legacy properties stopped updating on August 31, 2025.',
      },
    ],
  },
  {
    slug: 'hubspot-segments-lists-missing',
    title: 'Every campaign starts with rebuilding the same lists from scratch',
    description:
      'A standard set of smart lists — marketable, lifecycle, engagement, suppression — is the backbone of segmentation. How to create them via the Lists API.',
    intro:
      'If every send begins with someone hand-building “Marketable + engaged in 90 days” again, you do not have segmentation, you have folklore. The skill creates a standard set of dynamic lists via the Lists v3 API in one scripted run.',
    skill: 'build-smart-lists',
    faqs: [
      {
        question: 'Can HubSpot active lists be created via the API?',
        answer:
          'Yes — the Lists v3 API creates dynamic (active) lists with full filter definitions. The skill ships the exact filter JSON for each standard segment.',
      },
    ],
  },
  {
    slug: 'hubspot-new-contacts-arrive-dirty',
    title: 'New contacts arrive with missing owners, stages, and bad data',
    description:
      'Cleanup is pointless if tomorrow’s contacts arrive dirty. How to build a new-contact hygiene workflow — via the v4 Automation API — that screens every new record.',
    intro:
      'A one-time cleanup decays immediately unless creation-time hygiene exists. This skill creates the screening workflow programmatically (v4 Automation API, created disabled for review): default lifecycle stage, data checks, and owner assignment for every new contact.',
    skill: 'new-contact-hygiene-workflow',
    faqs: [
      {
        question: 'Can HubSpot workflows be created via the API now?',
        answer:
          'Yes. The v4 Automation API (stable — the old “beta” caveats are outdated) supports creating, updating, and deleting workflows. The skills always create workflows disabled so you review them in the UI before enabling.',
      },
    ],
  },
  {
    slug: 'hubspot-workflows-no-version-control',
    title: 'Someone edited a workflow and nobody knows what changed',
    description:
      'HubSpot has no workflow version control or recycle bin. How to export every workflow to JSON, diff changes over time, and restore from backup.',
    intro:
      'Workflows are production logic with no history: an edit or deletion is just gone. This skill exports every workflow definition to versioned JSON via the v4 API’s batch reads, diffs exports over time, and can recreate a workflow from backup (disabled, for review).',
    skill: 'workflows-as-code',
    faqs: [
      {
        question: 'Does HubSpot have a recycle bin for deleted workflows?',
        answer:
          'No — a deleted workflow is unrecoverable. A scheduled JSON export is the only real safety net, which is why the cleanup-workflows skill requires an export before any deletion.',
      },
      {
        question: 'Can I restore a HubSpot workflow from an export?',
        answer:
          'Yes, with caveats: the skill recreates the workflow from its exported JSON via the v4 API, always disabled. A few UI-only action types may need manual re-adding; the restore report lists them.',
      },
    ],
  },
  {
    slug: 'hubspot-contacts-disengaged-sunset-policy',
    title: 'We keep emailing people who stopped engaging a year ago',
    description:
      'Mailing the long-disengaged erodes deliverability and inflates spend. How to build an automated sunset policy with re-engagement and suppression tiers.',
    intro:
      'A sunset policy is the difference between a list that ages well and one that rots: try to re-engage the fading, then suppress the gone. The skill creates the two-tier workflow system via the v4 API — re-engagement first, suppression only after continued silence.',
    skill: 'engagement-suppression-workflow',
    faqs: [
      {
        question: 'When should a contact be suppressed for disengagement?',
        answer:
          'A common baseline: no opens or clicks in 6 months triggers re-engagement; continued silence for 30–60 more days triggers suppression. The thresholds are configurable in the skill’s workflow definitions.',
      },
    ],
  },
  {
    slug: 'hubspot-audit-where-to-start',
    title: 'Our HubSpot portal is a mess and we do not know where to start',
    description:
      'Duplicates, bounces, missing data, dead workflows — but which problem first? Run a graded, eight-dimension portal audit that maps every finding to a fix.',
    intro:
      'You cannot prioritize what you have not measured. The audit runs read-only API queries across eight dimensions — size, deliverability, completeness, engagement, duplicates, owners, lists and workflows, pipeline — grades each A–F, and prescribes the exact skill to run for every finding.',
    skill: 'hubspot-audit',
    faqs: [
      {
        question: 'Is the audit safe to run on production?',
        answer:
          'Yes — it is read-only: searches and counts, no writes. It produces a markdown report and an ordered cleanup prescription.',
      },
      {
        question: 'How long does a HubSpot portal audit take?',
        answer:
          'The scripted audit typically runs in minutes even on six-figure databases; the Search API’s 10,000-result cap is handled by segmented queries.',
      },
    ],
  },
  {
    slug: 'hubspot-api-versions-2027-deadline',
    title: 'HubSpot is retiring v1–v4 APIs — is our stack ready for March 2027?',
    description:
      'HubSpot moved to date-based API versioning; legacy v1–v4 endpoints lose support March 30, 2027. How to inventory every integration that needs migrating.',
    intro:
      'Every private app, integration, and script calling /crm/v3/ or older has a deadline: March 30, 2027. This skill inventories your portal’s API surface — private apps, connected apps, webhooks — and flags everything on legacy versions with a migration checklist to the date-based releases.',
    skill: 'audit-api-usage',
    faqs: [
      {
        question: 'What replaced HubSpot’s v3 and v4 API versions?',
        answer:
          'Date-based versions (like 2026-03) released twice a year with an 18-month support window. Legacy v1–v4 endpoints remain supported until March 30, 2027.',
      },
    ],
  },
  {
    slug: 'hubspot-test-changes-without-production-risk',
    title: 'How do we test CRM automation without risking production data?',
    description:
      'Test destructive CRM operations on a free HubSpot developer sandbox. The self-test harness seeds fixtures, runs the toolkit end-to-end, and tears down — production-locked.',
    intro:
      'Nobody should trust bulk deletes and workflow creation with production on the first run. HubSpot gives every account free developer test accounts; this skill turns one into a proving ground — seeded fixtures, end-to-end runs, a graded report, marker-scoped teardown — and refuses, in code, to run against anything that is not a sandbox.',
    skill: 'sandbox-self-test',
    faqs: [
      {
        question: 'How do I get a HubSpot sandbox for free?',
        answer:
          'Any HubSpot account can create up to 10 developer test accounts under Settings > Testing > Developer test accounts — free, with Enterprise-trial features, expiring after 90 days of API inactivity.',
      },
      {
        question: 'How does the harness avoid touching production?',
        answer:
          'Two locks: it only reads its own HUBSPOT_SANDBOX_ACCESS_TOKEN variable, and every script checks the portal’s accountType via the account-info API and refuses anything that is not DEVELOPER_TEST or SANDBOX. The check fails closed and has no override.',
      },
    ],
  },
  {
    slug: 'hubspot-weekly-maintenance-routine',
    title: 'The portal gets messy again a month after every cleanup',
    description:
      'Clean portals decay without a cadence. A five-minute weekly routine plus a quarterly deep sweep keeps HubSpot data quality from regressing.',
    intro:
      'Cleanups create a clean moment, not a clean system. The weekly routine (five minutes: new bounces, unowned contacts, no-email records, failing workflows) catches drift while it is still small; the quarterly sweep re-audits everything.',
    skill: 'weekly-cleanup-routine',
    faqs: [
      {
        question: 'What HubSpot maintenance should be done weekly vs quarterly?',
        answer:
          'Weekly: triage new bounces, assign new unowned contacts, delete new no-email records, check workflow errors. Quarterly: full re-audit, ghost suppression review, list/form/property cleanup.',
      },
    ],
  },
];

export const getProblemsForSkill = (skillSlug: string): Problem[] =>
  PROBLEMS.filter((p) => p.skill === skillSlug);
