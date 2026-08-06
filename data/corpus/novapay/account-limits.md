---
doc_id: account-limits
title: Account Limits
version: 2.4.0
effective_date: 2026-02-01
supersedes: null
authoritative_for:
  - limit.starter.monthly_volume
  - limit.pro.monthly_volume
  - limit.enterprise.monthly_volume
  - limit.single_transaction.default
  - limit.kyc_approval_window
owner: Risk Operations
synthetic: true
disclaimer: >-
  NovaPay is a fictional company. Every figure in this document is invented for
  evaluation purposes and describes no real product or service.
---

# Account Limits

Limits exist for two reasons: card-scheme requirements on merchant exposure, and
NovaPay's own risk position on funds it has advanced but not yet settled.

There are two independent families of limit, and they are frequently confused:

- **Volume limits** cap the total processed in a calendar month. They vary by plan.
- **Transaction limits** cap any single payment. They vary by **region**, not by plan.

A merchant can be within their monthly volume limit and still have an individual
payment rejected, and vice versa.

## Monthly volume limits

| Plan | Monthly processing limit |
|---|---|
| Starter | **$50,000 per calendar month** |
| Pro | **$500,000 per calendar month** |
| Enterprise | **no fixed ceiling; set contractually** |

Volume limits reset at 00:00 UTC on the first day of each calendar month. They are
not prorated for accounts opened mid-month: an account opened on 28 March has the
full $50,000 available for the remainder of March.

When an account reaches 80% of its limit, a `limit.threshold_reached` webhook is
sent and a dashboard banner appears. At 100%, further payments are declined with
`PAY_004 — account limit reached` until the next cycle or an upgrade.

Enterprise limits are negotiated during contracting and recorded in the order
form. There is no default Enterprise ceiling, and no figure for it is published.

### Raising a volume limit

Upgrading the plan raises the limit immediately — see **Subscription Plans** for
upgrade timing.

Merchants who need more than their plan allows without upgrading can request a
temporary uplift through **Support → Account → Request limit review**. Reviews take
**2 business days** and require six months of processing history. Uplifts are
granted per calendar month and do not carry over.

## Single-transaction limits

The default maximum for a single transaction is **$10,000**.

> **This default does not apply everywhere.** Merchants in the European Economic
> Area are subject to a lower ceiling of $5,000 arising from Strong Customer
> Authentication step-up thresholds. The regional figure takes precedence over the
> default. See **Regional Restrictions** for the full regional table and for the
> other territories where the default is modified.

A payment above the applicable ceiling is declined outright. It is not held for
review, and it cannot be approved by support. The customer must split the payment
or use a bank transfer, which is not subject to the single-transaction ceiling.

Because the applicable ceiling depends on where the *merchant* is established —
not on where the customer is — a merchant cannot determine their own limit from
this document alone.

## Account approval and KYC

New accounts must complete Know Your Customer verification before processing any
live payment. Test-mode processing is available immediately on signup and is not
gated on verification.

Verification is completed **within 24 hours for most accounts**. Where a manual
review is triggered, it takes **up to 5 business days**.

Manual review is triggered by any of:

- a business type on the restricted-category list;
- an establishing country on the enhanced-due-diligence list (see **Regional
  Restrictions**);
- a beneficial owner who cannot be verified from the documents supplied;
- a previously closed NovaPay account associated with the same entity.

Required documents are a government-issued identity document for each beneficial
owner holding 25% or more, a business registration certificate, and a bank
statement or voided cheque for the settlement account dated within 90 days.

Note that verification approval is not the same as the first payout arriving.
Payout timing after approval is a separate matter, documented in **Payout
Schedules**, and the first payout carries an additional hold.

## Reserve requirements

Some accounts carry a rolling reserve — a percentage of processing volume held
back and released on a delay. Reserves are applied at onboarding or after a
material change in risk profile, and the merchant is notified in writing before
any reserve takes effect.

Typical terms are **5% of volume held for 90 days**, but the figure is set per
account and there is no standard rate. Reserve terms appear in the dashboard under
**Balance → Reserves** whenever a reserve is active.

Reserves are not fees. Reserved funds belong to the merchant and are released on
schedule provided the account remains in good standing.

## Velocity controls

Independently of the ceilings above, NovaPay applies velocity controls that decline
payments matching high-risk patterns — for example, many attempts against
sequential card numbers from one IP address.

Velocity declines return `PAY_003 — issuer declined, do not retry` and are not
counted against volume limits. They are distinct from fraud scoring, which is
documented in **Fraud Controls**; velocity controls are absolute and cannot be
tuned by the merchant.

## Related documents

- **Regional Restrictions** — where the single-transaction default is overridden
- **Subscription Plans** — plan limits and upgrade timing
- **Payout Schedules** — when approved funds actually arrive
- **Fraud Controls** — tunable risk scoring, as opposed to hard limits
