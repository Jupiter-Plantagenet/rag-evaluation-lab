---
doc_id: support-escalation
title: Support and Escalation
version: 2.0.0
effective_date: 2026-03-01
supersedes: null
authoritative_for:
  - support.tier1_response
  - support.tier2_response
  - support.p1_response
  - support.channels
owner: Customer Operations
synthetic: true
disclaimer: >-
  NovaPay is a fictional company. Every response commitment and contact detail
  in this document is invented for evaluation purposes. The addresses and phone
  number are placeholders and must not be contacted.
---

# Support and Escalation

## Channels

Support is available by **email, in-dashboard live chat, and phone**.

| Channel | How | Availability |
|---|---|---|
| Email | `support@novapay.io` | always open |
| Live chat | dashboard, bottom right | Mon–Fri, 09:00–18:00 in the account's region |
| Phone | `+1-888-NOVAPAY` | Mon–Fri, 09:00–18:00 EST |
| Emergency | P1 escalation, see below | Enterprise, 24/7 |

Live chat is the fastest route during business hours. Email carries the most
context and is the right channel for anything requiring evidence — a dispute
query, a reconciliation discrepancy, a bug with a request ID.

Phone support cannot action account changes. Identity verification for account
changes requires the dashboard or a verified email address, so a phone call will
end in being asked to write in.

## Response commitments

| Plan | First response |
|---|---|
| Starter | **one business day** |
| Pro | **four hours** |
| Enterprise | four hours, and **15 minutes for P1, 24/7** |

These are commitments to a **first response from a person**, not to resolution. An
acknowledgement that a human has read the ticket and taken ownership satisfies the
commitment; a resolution time depends on the problem.

Business hours are those of the account's region. A Starter ticket raised on Friday
evening is answered on Monday.

The four-hour Pro commitment applies during business hours only. Enterprise P1 is
the only commitment that runs overnight and at weekends.

## What counts as P1

P1 is reserved for Enterprise accounts and means: **payment processing is failing
for this merchant, and money is affected.**

Qualifying: all payments declining, payouts not arriving when due, a suspected
security compromise of the account, or a data-integrity problem in transaction
records.

Not qualifying, regardless of urgency: a launch deadline, a dashboard display
problem, a question about pricing, an integration that has never worked, or a
dispute the merchant disagrees with. These are real problems and are handled on the
ordinary commitment.

Raise a P1 through the dedicated line in the Enterprise onboarding pack. A P1
raised through ordinary channels is treated as ordinary until it is triaged, so use
the right route.

## Escalating

Escalate a ticket that is not progressing by replying with **"escalate"** in the
first line. This routes it to a team lead and is logged.

Escalation is appropriate when the commitment has been missed, when a ticket has
gone several rounds without progress, or when the impact has grown since the ticket
was opened. It is not a queue-jumping mechanism, and escalating on open is
counterproductive — it triggers a triage step that adds time.

Enterprise accounts should raise persistent problems with their account manager,
who can escalate directly.

## What to include

The information that most often determines whether a ticket takes one round or
five:

- **A transaction, payout, or dispute ID.** Not an amount and a date.
- **A request ID** (in the `NovaPay-Request-Id` response header) for API problems.
- **Timestamps with a timezone.**
- Whether the account is in test or live mode — a surprising proportion of reported
  bugs are test-mode behaviour working as designed.
- What was expected and what happened instead.

For API problems, note that request logs are retained for **90 days** and webhook
delivery logs for only **30 days** — see **Data Retention**. Investigations into
older events may be impossible, so report problems while the logs still exist.

## What support cannot do

- **Overturn a dispute.** The issuing bank decides. Support can check the
  representment was submitted correctly and nothing more.
- **Approve a payment above a regional ceiling.** The ceilings in **Regional
  Restrictions** are absolute.
- **Waive the first-payout hold.** See **Payout Schedules**.
- **Recover a lost API key.** Only a hash is stored. Rotate it.
- **Recover events past their retention window.**
- **Provide tax, legal, or compliance advice.**

Support will say so plainly rather than opening a ticket that cannot resolve.

## Platform-wide problems

If the problem affects more than one merchant, it is an incident and is tracked at
`status.novapay.io` rather than through individual tickets. Check the status page
before writing in — during an active incident, ticket volume rises sharply and
individual responses slow, while the status page updates on a fixed cadence.

**Incident Response** describes classification, notification timing, and
post-incident reviews.

## Feedback and feature requests

Feature requests go through **Dashboard → Feedback**, are read by the product team,
and are not answered individually. Support tickets are not a route to the roadmap,
and support cannot give delivery dates.

## Related documents

- **Incident Response** — platform-wide problems and status communication
- **Subscription Plans** — which commitment applies to which plan
- **Data Retention** — the log windows that bound an investigation
- **Refunds and Disputes** — what can and cannot be escalated about a dispute
