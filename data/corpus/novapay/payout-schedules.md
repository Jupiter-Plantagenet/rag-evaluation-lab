---
doc_id: payout-schedules
title: Payout Schedules
version: 3.0.0
effective_date: 2026-01-10
supersedes: policy-archive-2024
authoritative_for:
  - payout.standard_delay
  - payout.express_delay
  - payout.first_payout_delay
  - payout.minimum
  - payout.schedule_options
  - fee.express_payout
  - policy.payout_hold_new_merchants
owner: Treasury
synthetic: true
disclaimer: >-
  NovaPay is a fictional company. Every figure in this document is invented for
  evaluation purposes and describes no real product or service.
---

# Payout Schedules

A payout is the transfer of a merchant's available balance to their settlement
bank account. Payouts are separate from transactions: a payment captured today
becomes *available* on a schedule, and is *paid out* on another.

## Standard payouts

Standard payouts arrive **T+2 business days** after the funds become available.

"Business days" excludes weekends and the banking holidays of the settlement
country. A payment captured on Friday becomes available Friday and pays out on
Tuesday. A payment captured on the day before a two-day holiday pays out on the
third following working day.

Standard payouts are free. There is no charge on the standard schedule regardless
of plan or amount.

## Payout frequency

Merchants choose **daily, weekly, or monthly** payouts in **Settings → Payouts**.

- **Daily** — a payout is created each business day for all available balance.
- **Weekly** — payouts are created every Monday, or the next business day if
  Monday is a holiday.
- **Monthly** — payouts are created on the first business day of the month.

Changing frequency takes effect from the next cycle. A pending payout already
created is not cancelled by a frequency change.

## Payout minimum

The minimum payout is **$25.00**. Balances below this do not generate a payout;
they roll forward into the next cycle and accumulate until the minimum is met.

The minimum is applied per payout, not per transaction, and there is no maximum.

## Express payouts

Pro and Enterprise merchants can request an express payout, which arrives **within
30 minutes**, including outside banking hours and at weekends.

Express payouts cost an additional **0.5%** of the payout amount. On a $10,000
express payout the fee is $50.00.

Express payouts are requested manually per payout — they are not a schedule
setting — from **Balance → Pay out now**. They are unavailable on the Starter
plan, and unavailable for settlement accounts outside the merchant's own country.

## First payout on a new account

**The first payout on a new account is held until T+7 business days.**

> **Policy change, effective 10 January 2026.** New accounts previously had their
> **first three** payouts held to T+14 business days. That hold has been reduced to
> a single payout at T+7. Accounts onboarded before 10 January 2026 completed their
> hold under the previous terms; see **Policy Archive (2024–2026)**.

The hold applies once, to the first payout only. Every subsequent payout follows
the merchant's chosen schedule at the standard T+2.

The hold begins when the account is **verified**, not when it is created — so the
time from signing up to receiving money is the KYC approval interval documented in
**Account Limits**, plus the T+7 hold, plus the time to accumulate the $25.00
minimum. For a straightforward account approved within 24 hours, the first money
typically lands 8 to 9 calendar days after signup.

Express payout is not available for a held first payout. The hold cannot be waived
by support.

## Payout failures

A payout fails if the settlement account is closed, the details are wrong, or the
receiving bank rejects the transfer. Failed payouts return the funds to the
available balance within **2 business days** and raise a `payout.failed` webhook.

NovaPay retries a failed payout **once**, after the merchant updates their bank
details. It does not retry against details that have not changed, because the
receiving bank charges a rejection fee on each attempt.

Three consecutive failures suspend automatic payouts on the account until support
confirms the settlement details.

## Currency and settlement

Payouts settle in the merchant's configured settlement currency. Where the
processing currency differs, conversion occurs at payout time at the rate
described in **Pricing and Transaction Fees**.

A merchant may hold balances in multiple currencies and configure a separate
settlement account per currency. Cross-currency payouts to a single account are
converted; same-currency payouts are not.

## Reading the payout statement

Each payout has a detail view listing the transactions it comprises, the fees
deducted, any refunds and dispute debits applied in the period, and any reserve
withheld. The payout amount equals gross captures, minus fees, minus refunds,
minus disputes, minus reserve, plus reserve released.

Statements are available in the dashboard and via `GET /v1/payouts/{id}`.

## Related documents

- **Account Limits** — KYC approval, which precedes the first payout hold
- **Subscription Plans** — which plans include express payouts
- **Pricing and Transaction Fees** — conversion at payout time
- **Policy Archive (2024–2026)** — the superseded T+14 new-merchant hold
