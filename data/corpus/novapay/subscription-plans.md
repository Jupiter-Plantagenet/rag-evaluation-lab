---
doc_id: subscription-plans
title: Subscription Plans
version: 3.3.0
effective_date: 2026-03-01
supersedes: null
authoritative_for:
  - plan.starter_price
  - plan.pro_price
  - plan.enterprise_price
  - plan.downgrade_timing
  - plan.upgrade_timing
restates:
  - fee.card.standard
  - fee.card.pro
  - fee.express_payout
  - api.rate_limit.starter
  - api.rate_limit.pro
owner: Revenue Operations
synthetic: true
disclaimer: >-
  NovaPay is a fictional company. Every price and feature in this document is
  invented for evaluation purposes.
---

# Subscription Plans

Three plans. The subscription fee is separate from per-transaction pricing, which
is authoritative in **Pricing and Transaction Fees**; figures restated here are for
comparison and that document governs if the two ever disagree.

## Plan comparison

| | Starter | Pro | Enterprise |
|---|---|---|---|
| Monthly fee | **$0 per month** | **$49 per month** | **custom, contracted annually** |
| Card rate | 2.9% + $0.30 | 2.5% + $0.30 | negotiated |
| Monthly volume limit | $50,000 | $500,000 | no fixed ceiling |
| API rate limit | 100 req/s | 1,000 req/s | contractual |
| Express payouts | — | 0.5% fee | 0.5% fee |
| Support response | 1 business day | 4 hours | 15 minutes, 24/7 for P1 |
| Dashboard seats | 3 | 15 | unlimited |
| Custom contract terms | — | — | yes |
| Dedicated account manager | — | — | yes |

## Starter

Free. No monthly fee, no minimum, no contract. Intended for launching and for
low-volume operation.

Starter includes the full API, all payment methods available in the merchant's
region, webhooks, the dashboard, fraud scoring, and standard payouts. It is not a
trial or a feature-limited tier — the differences from Pro are the rate, the
ceilings, and the support response time.

## Pro

**$49 per month**, billed monthly, cancellable at any time.

Pro reduces the card rate from 2.9% to **2.5%**, raises the monthly volume ceiling
tenfold, raises the API rate limit tenfold, and unlocks express payouts.

### When Pro pays for itself

The rate saving is 0.4 percentage points on card volume. The $49 monthly fee is
therefore recovered at:

```
$49.00 / 0.004 = $12,250 of monthly card volume
```

Below roughly **$12,250 per month**, Starter costs less overall. Above it, Pro
does. The calculation ignores the fixed $0.30 component, which is identical on both
plans and so does not affect the comparison.

Merchants near the threshold should also weigh the support response time and the
express payout access, which have no equivalent on Starter.

## Enterprise

**Custom pricing, contracted annually.** Rates, limits, and terms are negotiated
and recorded in an order form.

Enterprise adds a dedicated account manager, a 15-minute P1 response commitment,
custom contract terms, unlimited dashboard seats, and negotiated rate-limit and
volume ceilings. Enterprise volume limits have no published default — there is no
standard figure, because there is no standard contract.

Contact sales through the dashboard or at `sales@novapay.io`.

## Changing plan

### Upgrading

Upgrades take effect **immediately, with the monthly fee prorated** for the
remainder of the current billing period.

The new card rate applies to transactions processed from the moment of upgrade. It
is not applied retroactively. The raised volume and rate limits also take effect
immediately, which is the usual reason to upgrade mid-cycle.

### Downgrading

Downgrades take effect **at the end of the current billing period**. The higher
plan's rate and limits remain in force until then, and no partial refund of the
monthly fee is issued.

A downgrade that would put the account over the lower plan's volume limit is
accepted, but processing stops once the account reaches the new ceiling. The
dashboard warns before confirming a downgrade in this situation.

Downgrading from Enterprise requires the contract's notice period, typically 30
days, and cannot be done from the dashboard.

## Billing

The monthly fee is charged to the card on file on the same day each month, or
deducted from the merchant balance where one is configured.

A failed subscription charge is retried after 3 and 7 days. After the second
failure the account moves to Starter terms until payment succeeds; processing is
not interrupted.

Invoices are in the dashboard under **Billing → Invoices** and are issued in the
account's settlement currency.

## Related documents

- **Pricing and Transaction Fees** — authoritative per-transaction rates
- **Account Limits** — how volume ceilings behave and how to raise one
- **Payout Schedules** — express payout mechanics and the 0.5% fee
- **Support Escalation** — what each response commitment actually covers
