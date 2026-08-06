---
doc_id: data-retention
title: Data Retention
version: 2.1.0
effective_date: 2026-02-15
supersedes: null
authoritative_for:
  - retention.transaction_records
  - retention.api_logs
  - retention.webhook_delivery_logs
  - retention.deletion_sla
owner: Compliance
synthetic: true
disclaimer: >-
  NovaPay is a fictional company. Every retention period in this document is
  invented for evaluation purposes and reflects no real regulatory requirement.
  This is not legal advice.
---

# Data Retention

Different categories of data are kept for very different periods. The differences
are not arbitrary: transaction records are held to meet financial record-keeping
obligations, while operational logs are held only as long as they are useful for
debugging.

Reading one period from this document and assuming it applies to another category
is the most common mistake made with this page.

## Retention periods

| Data category | Retained for |
|---|---|
| Transaction records | **7 years** |
| Payout records | 7 years |
| Dispute records and evidence | 7 years |
| Account and KYC records | 7 years after account closure |
| **API request logs** | **90 days** |
| **Webhook delivery logs** | **30 days** |
| Dashboard audit logs | 12 months |
| Risk scores and signals | 12 months |

### Transaction records — 7 years

Transaction records are retained for **7 years** from the transaction date. This
covers the payment, its amount, currency, timestamps, status history, associated
refunds and disputes, and the payment-method token — never the full card number,
which is not stored at any point.

Seven years is driven by financial record-keeping requirements across the regions
NovaPay operates in. It is not shortened by account closure, and it is not
shortened by a data-deletion request; see **Deletion requests** below.

### API request logs — 90 days

Metadata for every API request — endpoint, timestamp, response status, latency,
key used, source IP — is retained for **90 days**. Request and response *bodies*
are not retained at all.

These logs are available in **Developers → Logs** and are the basis of any support
investigation into API behaviour. A problem reported more than 90 days after it
occurred cannot be investigated from them.

### Webhook delivery logs — 30 days

Delivery records — attempt timestamps, response status, response time, retry
count — are retained for **30 days**. This is the shortest retention period of any
category here.

The practical consequence: an endpoint outage discovered more than 30 days later
cannot be reconstructed. The underlying events still exist as transaction records
for 7 years, but the record of *what NovaPay tried to deliver and when* does not.
Merchants who need longer webhook history should log receipts on their own side.

**Webhook Delivery** describes the retry schedule and the events API used to
backfill within this window.

## Data export

Merchants can export their data at any time from **Reports → Export**, in CSV or
JSON, for any date range within the retention period for that category.

Exports over roughly 100,000 rows are generated asynchronously and emailed as a
download link, which expires after 7 days.

Exporting before closing an account is strongly recommended. Access to the
dashboard ends at closure even though NovaPay's own retention obligations continue.

## Deletion requests

Data subjects may request erasure of personal data. NovaPay completes verified
requests **within 30 days**.

What is deleted: contact details, marketing preferences, support correspondence,
and any custom metadata containing personal data.

What is **not** deleted: transaction records subject to the 7-year obligation.
These are pseudonymised — direct identifiers are replaced with an opaque reference —
but the financial record itself is retained, because the obligation to keep it
overrides the request to remove it. This is explained to the requester in the
confirmation.

Requests are made through **Settings → Privacy → Erasure request** or by writing to
`privacy@novapay.io`. Identity verification is required before any request is
actioned.

## Account closure

On closure NovaPay stops processing immediately, pays out the remaining balance on
the ordinary schedule, and retains records per the table above. Any funds held in
reserve are released on the reserve's original schedule, not accelerated by closure.

Dashboard access ends at closure, so export first.

An account with open disputes cannot be closed until they resolve, because
representment deadlines and potential debits are still live.

## Sub-processors and location

Data is processed in the region where the merchant is established, with
cross-region transfer only where necessary for card-scheme settlement.

The current sub-processor list is published at `novapay.io/legal/subprocessors`.
Changes are announced 30 days in advance, and merchants may object in writing.

## Related documents

- **Webhook Delivery** — the retry window that the 30-day log period bounds
- **Regional Restrictions** — regulatory reporting and export for filings
- **Account Limits** — KYC documents, retained for 7 years after closure
- **Support Escalation** — investigations bounded by the 90-day API log window
