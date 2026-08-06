---
doc_id: incident-response
title: Incident Response
version: 1.4.0
effective_date: 2026-05-01
supersedes: null
authoritative_for:
  - incident.severity_levels
  - incident.sev1_notification
  - incident.postmortem_deadline
  - incident.status_page
owner: Site Reliability
synthetic: true
disclaimer: >-
  NovaPay is a fictional company. Every severity definition, interval and
  commitment in this document is invented for evaluation purposes.
note_for_readers: >-
  This document deliberately describes incident PROCESS without committing to any
  uptime percentage. That omission is intentional and is part of the corpus
  design; see fact_ledger.yaml, gaps.gap_sla_uptime_number.
---

# Incident Response

This document describes how NovaPay classifies, communicates, and reviews incidents
affecting the platform.

## Severity levels

Incidents are classified **SEV1 through SEV4**.

| Level | Definition | Example |
|---|---|---|
| **SEV1** | Payment processing is unavailable or funds are at risk | The payments API returns errors for all merchants |
| **SEV2** | Major degradation with a workaround, or a single region affected | Payouts delayed in one settlement region |
| **SEV3** | Minor degradation, limited scope | Dashboard reporting is slow; payments unaffected |
| **SEV4** | Cosmetic or informational | A display error in an export header |

Severity is assigned at declaration by the on-call engineer and may be revised as
scope becomes clear. It is set by *impact*, not by cause: a small bug that stops
payments is a SEV1, and a large infrastructure failure that no merchant notices is
not.

## Notification

| Severity | Merchant notification |
|---|---|
| SEV1 | **within 30 minutes of declaration** |
| SEV2 | within 2 hours |
| SEV3 | on the status page only |
| SEV4 | in release notes |

**SEV1 incidents are communicated within 30 minutes of declaration.** Note that the
clock starts at *declaration*, not at the first symptom — detection time is not
included, and is reported separately in the post-incident review.

Notification goes to the status page, to the account owner by email, and — for
SEV1 and SEV2 — to any additional addresses configured in **Settings →
Notifications**.

## Status page

Live status is at **status.novapay.io**, covering the payments API, dashboard,
webhook delivery, payouts, and each settlement region independently.

The status page is hosted separately from the main platform so it stays available
during a total outage. Subscribe there for updates by email, SMS, or webhook —
subscription is open and does not require a NovaPay account.

Updates during an active incident are posted at least every 30 minutes for SEV1 and
every 2 hours for SEV2, even when the update is only that the investigation
continues.

## During an incident

The on-call engineer becomes incident commander at declaration and holds that role
until resolution or handover. For SEV1 a separate communications lead is assigned so
that updates are not competing with remediation for the same person's attention.

Merchants do not need to do anything during an incident. Specifically:

- **Do not retry failed payments in bulk.** Retry storms extend recovery and can
  trigger scheme penalties for repeated declines. See `PAY_003` in **API
  Authentication and Errors**.
- **Do not reconfigure webhook endpoints.** Undelivered events retry on the ordinary
  schedule described in **Webhook Delivery**, and reconfiguration loses queued
  attempts.
- Queued webhook deliveries resume automatically once delivery is restored, within
  the ordinary retry window.

## After an incident

A public post-incident review is published for every SEV1 and SEV2 within
**5 business days** of resolution.

Reviews are blameless and cover: what happened, the timeline including detection
and declaration times, the impact in scope and duration, the contributing causes,
what was done to resolve it, and the specific remediation items with owners.

Reviews are published at `status.novapay.io/incidents` and remain available
indefinitely. Merchants requiring a review for their own compliance purposes can
request a signed copy through support.

SEV3 and SEV4 incidents are reviewed internally without publication.

## Merchant-side incidents

An incident affecting a single merchant — an endpoint failing, a settlement account
rejecting payouts, unexpected declines on one account — is a support matter rather
than a platform incident, and is handled through **Support Escalation**.

If a merchant believes a problem affecting them is a platform incident that has not
been declared, raising it with support is the fastest route: support can page
on-call directly.

## Scheduled maintenance

Maintenance requiring downtime is announced at least **7 days** in advance on the
status page and by email, and is scheduled during the lowest-traffic window for the
affected region.

Most maintenance requires no downtime and is not announced.

## Related documents

- **Support Escalation** — response commitments and how to reach a human
- **Webhook Delivery** — what happens to events during an outage
- **API Authentication and Errors** — why not to retry hard declines
- **Data Retention** — how long incident-period logs remain available
