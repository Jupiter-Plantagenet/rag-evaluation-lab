---
doc_id: pricing-and-fees
title: Pricing and Transaction Fees
version: 3.1.0
effective_date: 2026-03-01
supersedes: null
authoritative_for:
  - fee.card.standard
  - fee.card.pro
  - fee.bank_transfer
  - fee.crypto
  - fee.currency_conversion
owner: Revenue Operations
synthetic: true
disclaimer: >-
  NovaPay is a fictional company. Every figure in this document is invented for
  evaluation purposes and describes no real product or service.
---

# Pricing and Transaction Fees

NovaPay charges per successful transaction. There is no setup fee, no monthly
minimum on the Starter plan, and no charge for failed or declined payments.

Plan subscription costs are documented separately in **Subscription Plans**. This
document covers only per-transaction pricing.

## Card payments

| Plan | Rate | Fixed component |
|---|---|---|
| Starter | 2.9% | $0.30 |
| Pro | 2.5% | $0.30 |
| Enterprise | negotiated | negotiated |

The standard rate for a successful card transaction is **2.9% + $0.30**. This
applies to all card brands, all card types (credit, debit, prepaid), and both
one-off and recurring payments. NovaPay does not price differently by card brand.

Pro-plan merchants pay **2.5% + $0.30** on the same transactions. The reduced rate
applies from the moment the upgrade takes effect and is not applied retroactively
to transactions already processed.

Declined transactions are free. A transaction that is authorised and then voided
before capture is also free. Once a payment is captured, the fee is incurred, and
it is not returned if the payment is later refunded — see **Refunds and Disputes**.

## Bank transfers

Bank transfers (ACH in the United States, SEPA in the euro area, and Faster
Payments in the United Kingdom) are charged at **1.0%, capped at $5.00** per
transfer. The cap makes large transfers substantially cheaper than cards; a
$10,000 bank transfer costs $5.00 where the same amount on a card would cost
$290.30.

Bank transfers settle more slowly than cards and are subject to the same payout
schedule described in **Payout Schedules**.

## Crypto settlement

Crypto payments are charged at **1.5% flat**, with no fixed component. The rate is
identical across all supported assets. Network and gas fees are borne by the
payer, not by the merchant, and are not collected or remitted by NovaPay.

## Currency conversion

When a payment is taken in a currency other than the merchant's settlement
currency, NovaPay applies a **1.0%** currency-conversion fee on the converted
amount. This is charged **in addition to** the transaction fee for the payment
method used.

A worked example, because this is the most frequently misread line in this
document. A $100 card payment from a customer paying in euros, settling to a
US-dollar account on the Starter plan:

```
Transaction fee     2.9% × $100.00  +  $0.30   =  $3.20
Conversion fee      1.0% × $100.00            =  $1.00
                                                 ------
Total                                            $4.20
```

The conversion fee is **not** a separate international-card surcharge. NovaPay
does not levy a cross-border card fee. If a customer abroad pays in the
merchant's own settlement currency, no conversion fee applies at all, and the
cost is the ordinary 2.9% + $0.30.

## What is not charged

NovaPay does not charge for:

- issuing a refund (the refund itself is free — but see below);
- failed, declined, or expired payment attempts;
- payouts on the standard schedule;
- API calls, webhook deliveries, or dashboard seats;
- storing a card for later use.

Two fees that merchants frequently expect to find in this document are documented
elsewhere because they are not transaction fees:

- **Dispute fees** are charged per dispute, not per transaction, and are
  documented in **Refunds and Disputes**.
- **Express payout fees** are charged on the payout, not on the underlying
  transactions, and are documented in **Payout Schedules**.

## Fee timing

Fees are deducted from the transaction at the point of capture, so the amount that
reaches the merchant balance is already net. NovaPay does not invoice fees
separately and does not debit them from a bank account.

A monthly fee statement is available in the dashboard under **Billing → Statements**
from the third business day of the following month.

## Related documents

- **Subscription Plans** — monthly plan pricing and what each plan includes
- **Refunds and Disputes** — refund mechanics, dispute fees, and representment costs
- **Payout Schedules** — payout timing, express payouts, and minimums
- **Account Limits** — volume and per-transaction ceilings
