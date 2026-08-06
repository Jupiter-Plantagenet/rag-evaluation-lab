---
doc_id: regional-restrictions
title: Regional Restrictions and Availability
version: 2.2.0
effective_date: 2026-04-01
supersedes: null
authoritative_for:
  - region.supported_count
  - region.prohibited
  - region.high_risk_review
  - limit.single_transaction.eea
owner: Compliance
synthetic: true
disclaimer: >-
  NovaPay is a fictional company. Every country list, threshold and figure in
  this document is invented for evaluation purposes. Nothing here describes any
  real regulatory regime, and it is not legal or compliance advice.
---

# Regional Restrictions and Availability

NovaPay supports merchants established in **45 countries** across North America,
Europe, and Asia-Pacific.

Availability is determined by where the *merchant entity* is established, not by
where its customers are. A merchant in a supported country may accept payments
from customers anywhere that is not on the prohibited list below.

## Prohibited territories

NovaPay cannot process payments to or from **Cuba, Iran, North Korea, Syria, and
the Crimea, Donetsk and Luhansk regions**.

These are absolute. They cannot be enabled by support, are not subject to review,
and apply to both merchants and customers. A payment involving a prohibited
territory is declined at authorisation and is not recoverable.

Accounts are screened against this list at onboarding and continuously thereafter.
A merchant that relocates into a prohibited territory has their account closed with
funds returned through the ordinary payout process.

## Enhanced due diligence

Merchants establishing in **Brazil, India, Indonesia, Nigeria, and Vietnam**
require enhanced due diligence at onboarding.

Enhanced due diligence is not a prohibition. These are supported countries, and
accounts in them operate normally once approved. The additional requirements are:

- a certified copy of the business registration, not a scan;
- identity verification for all beneficial owners at 10% or above, rather than the
  usual 25%;
- a documented source of funds for the settlement account;
- a manual review, which invokes the up-to-5-business-day approval window described
  in **Account Limits** rather than the usual 24 hours.

## Regional transaction ceilings

The default single-transaction ceiling is $10,000, as documented in **Account
Limits**. Three regions override it:

| Region | Single-transaction ceiling | Basis |
|---|---|---|
| European Economic Area | **$5,000** | SCA step-up thresholds |
| India | **$2,000** | local card-not-present rules |
| Brazil | **$3,000** | instalment-mandate interaction |
| Everywhere else | $10,000 | default |

The regional ceiling always takes precedence over the default. A merchant
established in the EEA is subject to $5,000 even on the Enterprise plan — these
ceilings do not vary by plan, because they arise from local requirements rather
than from NovaPay's risk position.

Payments above the applicable ceiling are declined, not held. Splitting a payment
to circumvent a regional ceiling is a breach of the acceptable-use policy.

### Countries subject to both enhanced due diligence and a reduced ceiling

Cross-referencing the two lists above: **India** and **Brazil** appear on both the
enhanced-due-diligence list and the reduced-ceiling table. Merchants establishing
there should plan for a longer onboarding and a lower per-payment maximum.
Indonesia, Nigeria and Vietnam require enhanced due diligence but retain the
$10,000 default ceiling.

## Currency availability by region

Not every settlement currency is available in every supported country. Settlement
is available in the local currency of each supported country, plus USD and EUR
everywhere.

Merchants who wish to settle in a currency other than their local currency, USD, or
EUR should contact support before onboarding, as it may require an additional
banking arrangement.

## Local payment methods

Beyond cards and bank transfers, some regions have local methods enabled by default:

- **European Economic Area** — SEPA Direct Debit, iDEAL (Netherlands),
  Bancontact (Belgium)
- **United Kingdom** — Faster Payments, Bacs Direct Debit
- **Australia** — BECS Direct Debit, PayID
- **Singapore** — PayNow, GIRO
- **India** — UPI, NetBanking
- **Brazil** — Pix, Boleto

Local methods are subject to the bank-transfer pricing in **Pricing and Transaction
Fees** rather than card pricing, and settle on their own timelines, which can exceed
the standard T+2.

## Regulatory reporting

NovaPay files the reports required of it as a payment institution in each region it
operates in. Merchants remain responsible for their own regulatory obligations,
which NovaPay does not discharge on their behalf and does not advise on.

Merchants requiring documentation for their own filings can export transaction data
in full from **Reports → Export**, subject to the retention periods in **Data
Retention**.

## Changes to availability

Country availability changes as licensing and sanctions positions change. Material
changes are announced at least **60 days** before taking effect, by email to the
account owner and by dashboard notice.

Where a change makes an existing merchant ineligible, NovaPay provides a wind-down
period of no less than 90 days and processes all outstanding payouts in full.

## Related documents

- **Account Limits** — the default ceiling these regional figures override
- **Product Overview** — supported country and currency counts
- **Data Retention** — export windows for regulatory documentation
- **Support Escalation** — pre-onboarding questions about a specific country
