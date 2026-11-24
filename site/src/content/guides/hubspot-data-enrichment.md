---
title: 'HubSpot Data Enrichment: Native, Vendors or Waterfall'
description: 'HubSpot data enrichment explained: what the native feature (formerly Breeze Intelligence) fills, where it stops, and when a waterfall vendor is worth paying.'
heading: 'HubSpot data enrichment: native, vendors, or waterfall'
updated: 2026-11-25
order: 4
skills:
  - waterfall-enrich-contacts
  - enrich-company-name
  - enrich-industry
---

HubSpot data enrichment fills empty contact and company fields from outside data. You have three options. HubSpot's native enrichment covers firmographics and job data from a work email or a company domain, and doesn't use HubSpot Credits. A third-party vendor covers emails and phone numbers. A waterfall tries several vendors in turn for better hit rates.

Before paying anyone, copy what your portal already knows from company records to contacts. It's free and often closes the biggest gaps. The skills below do that first, then hand the rest to a vendor of your choice. **[Install the skills](/install)** to run the scripted path.

## What is HubSpot data enrichment?

Enrichment means adding data you didn't collect yourself: industry, company size, job title, location, sometimes email and phone. The point isn't a fuller record. The point is that routing, segmentation and lead scoring all filter on fields that are usually empty.

There are two kinds, and people mix them up. **Internal enrichment** copies data you already hold, such as the company record's industry, onto the contact. **External enrichment** buys data you don't have. Do the first before the second.

## What does HubSpot's native enrichment do?

HubSpot's own enrichment, sold earlier as Breeze Intelligence, looks up contacts by first name, last name and work email, and companies by domain. HubSpot's help docs now just call it data enrichment, and the old Breeze Intelligence help URL opens the data enrichment article.

The facts, from HubSpot's knowledge base (checked November 2026):

- **Plans:** Starter, Professional or Enterprise on Marketing, Sales, Service, Data or Content Hub. Smart CRM and Revenue Hub need Professional or Enterprise.
- **Cost:** "Data enrichment does not consume HubSpot Credits." Smart properties do.
- **Data sources:** HubSpot's commercial dataset, third-party providers and public web information.
- **Eligibility:** contacts need a business email. Gmail, Yahoo and other personal addresses are not enriched. Companies need a domain.
- **Default:** automatic enrichment is off for both contacts and companies. A Super Admin turns it on.
- **Overwrites:** automatic enrichment only fills blank properties and doesn't overwrite values set by a user or another system. Manual enrichment can overwrite if you choose.
- **Bulk:** up to 100 records at a time from an index page, a whole segment via **Actions > Enrich segment**, or a workflow's **Enrich record** action.

HubSpot also uses the enrichment dataset for form shortening: a form shows only the fields it can't fill in itself.

## Which fields does HubSpot enrichment fill?

HubSpot publishes the list of default enrichment properties. The short version: firmographics on companies, role and location on contacts.

| Object  | Fields HubSpot lists                                                                                                                                                                                                                                         |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Contact | First and last name, job title, employment role, sub-role and seniority, LinkedIn URL, city, state/region, country                                                                                                                                           |
| Company | Name, domain, industry, industry group, number of employees, employee range, annual revenue, revenue range, total money raised, year founded, description, keywords, web technologies, phone, full address, LinkedIn and Facebook pages, X handle, is public |

Note what's missing on the contact side: email address and phone number. Native enrichment needs a work email as its input, so it can't find one for you, and it doesn't list contact phone numbers. That gap is where vendors earn their money.

## Is there a HubSpot data enrichment API?

Not one I could find. HubSpot's developer reference index (the 2026-09, 2027-03 beta and legacy API sections) lists no enrichment endpoint. The documented ways to trigger enrichment are the UI, segments and the workflow **Enrich record** action.

So "enrichment by API" in HubSpot means one of two things. Either a workflow calls the Enrich record action for records your script flags. Or you call a vendor's API yourself and write the results back through HubSpot's CRM objects API, which is what the waterfall skill does.

## When do you need a third-party enrichment vendor?

You need a vendor when the field you're missing is one HubSpot doesn't supply, or when the contact fails HubSpot's eligibility rules.

- **Emails** for contacts you only have a name and company for.
- **Mobile and direct-dial phone numbers.**
- **Contacts on personal email addresses**, which HubSpot skips.
- **A vendor you already pay for**, where you want the data in HubSpot without a separate integration.

The cost model is different from HubSpot's. Vendors charge per lookup or per hit, so a careless bulk run spends real money on records you were about to delete. Clean first. The [HubSpot data hygiene checklist](/guides/hubspot-data-hygiene-checklist) covers that.

## What is waterfall enrichment?

Waterfall enrichment asks a sequence of data providers for the same field and stops at the first verified answer. One vendor's database has gaps; several in a row have fewer. FullEnrich, the default provider in the skill, says it orchestrates "20+ providers" in one call.

Expect misses anyway. The skill's docs treat a 40-70% match rate as normal, and input quality drives the hit rate: contacts with no company domain enrich poorly. Fill company names and domains internally before you start the waterfall.

## Which enrichment fields actually matter?

Enrich the fields something downstream reads. Everything else is decoration you paid for.

| Use                        | Fields                                                    | Cheapest source                                    |
| -------------------------- | --------------------------------------------------------- | -------------------------------------------------- |
| Territory routing          | Country, state                                            | Associated company, then `ip_country` / `ip_state` |
| Segmentation               | Industry, company size                                    | Associated company, then HubSpot enrichment        |
| ICP tiers and lead scoring | Industry, employee count, geography, job title, seniority | HubSpot enrichment                                 |
| Outreach                   | Email, mobile phone                                       | Third-party vendor or waterfall                    |
| Personalization            | Company name                                              | Associated company                                 |

Standardize values before enriching. If your portal holds "USA", "U.S." and "United States", adding a fourth spelling from a vendor makes it worse. Run `/standardize-geo-values` first.

## In what order should you enrich HubSpot data?

Go from free to paid, and from data you trust to data you buy.

1. **Copy company name to contacts** from the associated company (`/enrich-company-name`).
2. **Copy industry to contacts** from the associated company (`/enrich-industry`). Run it after step 1, because step 1 can create new associations.
3. **Backfill geography** from the associated company or HubSpot's IP fields (`/backfill-geo-data`).
4. **Turn on HubSpot's native enrichment** for firmographics and job data, if your plan includes it.
5. **Run a vendor or waterfall** only for what's still empty, starting with 25-50 contacts (`/waterfall-enrich-contacts`).

### Doing steps 1 and 2 by hand

Create a contact-based workflow. Trigger: Company name is unknown. Add a 10-minute delay so HubSpot's auto-association can link the contact to a company from its email domain. Then an if/then branch: if the associated company's name is known, **Copy property** from Company > Name to Contact > Company name.

Turn on re-enrollment when the associated company changes. When activating, choose to enroll existing contacts so the backlog runs too. The industry workflow is the same with the property swapped. Check that the contact and company industry dropdown values match exactly, or the copy fails.

## The scripted path

The internal skills measure the gap before and after, and build the workflows above. The waterfall skill handles the expensive part with guardrails:

- **Pluggable providers:** FullEnrich by default, with Apollo, Hunter and Dropcontact adapters, or your own vendor via a one-function template. Switch with `ENRICHMENT_PROVIDER`.
- **Cost ceiling:** a hard cap per run (100 contacts by default) and a cost preview before anything runs.
- **Two confirmations:** type `ENRICH` before credits are spent, `WRITE` before HubSpot is touched.
- **No overwrites** unless you set `ENRICHMENT_OVERWRITE=true`.
- **Audit CSV** with old value, new value and source for every field. The old values are your rollback.

Install in Claude Code:

```
/plugin marketplace add tomgranot/hubspot-admin-skills
/plugin install hubspot-admin@hubspot-admin-skills
```

## FAQ

### How much does HubSpot data enrichment cost?

HubSpot says native data enrichment doesn't consume HubSpot Credits; it comes with eligible Starter, Professional and Enterprise plans. Third-party vendors charge per lookup or per result, priced by each vendor. The skills are free and MIT-licensed.

### Will enrichment overwrite data we already trust?

Not by default, on either path. HubSpot's automatic enrichment fills blank properties only. The skills never overwrite a non-empty value unless you explicitly allow it, and every write is logged with the previous value.

### Is external enrichment GDPR-safe?

That depends on your agreements, not the tool. External enrichment sends names and company data to a third party and brings personal data back. Check your data processing agreements and the applicable privacy rules before the first run. A found email is not consent to market to it.

### How do we handle an enrichment deletion request?

HubSpot lets individuals opt out of its enrichment through a form, and records carry "Enrichment opt-out" properties. Turning enrichment off stops future enrichment but doesn't remove data already written. Removing that data is a separate step you handle like any other deletion request.

### Do I need a developer?

No. The internal workflows are built in the HubSpot UI. The scripted path needs a service key in a `.env` file and a vendor API key. Claude asks for the rest.

### What is this not for?

It doesn't fix records that are wrong rather than empty, and it won't make a dirty database worth enriching. Delete, suppress and merge first. It's also not a prospecting tool for finding new leads: it fills gaps on contacts you already have.

**Fill the free gaps first, then buy the rest. [Install the HubSpot Admin Skills](/install)** and start with `/enrich-company-name`.
