---
doc_id: refunds-and-disputes
title: Refunds and Disputes
version: 4.0.0
effective_date: 2026-03-01
supersedes: policy-archive-2024
authoritative_for:
  - fee.dispute
  - fee.refund
  - fee.chargeback_representment
  - policy.refund_window
owner: Risk and Disputes
synthetic: true
disclaimer: >-
  NovaPay is a fictional company. Every figure in this document is invented for
  evaluation purposes and describes no real product or service.
---

# Refunds and Disputes

Refunds and disputes are different mechanisms with different costs, different
timelines, and different failure modes. Merchants routinely conflate them, so this
document treats them separately throughout.

A **refund** is initiated by the merchant. A **dispute** (also called a chargeback)
is initiated by the cardholder through their bank, without the merchant's
involvement.

## Refunds

### Refund window

Refunds may be issued **within 120 days of the original transaction**.

> **Policy change, effective 1 March 2026.** The refund window was extended from
> 90 days to **120 days**. Transactions processed **before 1 March 2026** remain
> subject to the previous 90-day window; see **Policy Archive (2024–2026)** for the
> superseded text. The window is determined by the date of the original
> transaction, not the date the refund is requested.

After the window closes, a refund cannot be issued through NovaPay. Merchants who
need to return funds to a customer after that point must do so by other means.

### How to issue a refund

From the dashboard: **Transactions → select the transaction → Refund**. Partial
refunds are supported; enter an amount lower than the original.

From the API: `POST /v1/refunds` with the `payment_id` and, optionally, an
`amount` for a partial refund. Omitting `amount` refunds the full transaction.

A transaction may be partially refunded multiple times, up to the original total.
Once fully refunded, a transaction cannot be refunded again.

### Refund timing

Refunds are submitted to the card network immediately. The funds appear on the
cardholder's statement in **5 to 10 business days**, depending on their issuing
bank. NovaPay has no control over this interval and cannot expedite it.

The merchant balance is debited at the moment the refund is submitted, not when
the cardholder receives it.

### What a refund costs

**NovaPay charges nothing to issue a refund.** There is no refund fee.

However — and this is the part that surprises merchants — **the original
transaction fee is not returned**. A refunded payment leaves the merchant having
paid the processing cost of a transaction they ultimately did not keep.

For a $100 card payment on the Starter plan that is later refunded in full:

```
Original payment      +$100.00
Transaction fee         -$3.20   (2.9% + $0.30, retained by NovaPay)
Refund to customer    -$100.00
Refund fee              -$0.00
                       --------
Net position            -$3.20
```

The merchant is out **$3.20**, being the original fee. Refunding is free; having
processed the payment was not.

## Disputes

### What happens when a dispute is opened

When a cardholder disputes a payment, their issuing bank withdraws the funds from
NovaPay, which in turn debits the merchant balance. This happens **immediately on
notification** and before any review of the merit of the dispute. The merchant is
notified by email and by the `dispute.created` webhook.

The disputed amount is held, not lost. If the dispute is resolved in the
merchant's favour, the amount is returned to the balance.

### What a dispute costs

A **$15.00** dispute fee is charged per dispute.

**This fee is non-refundable even if the merchant wins the dispute.** It covers
the network's handling cost, which the card scheme levies regardless of outcome.
This is the single most common source of billing confusion in NovaPay support
tickets, and it is not an error when it appears on a statement alongside a won
dispute.

For a $200 card payment on the Starter plan that is disputed and lost:

```
Original payment      +$200.00
Transaction fee         -$6.10   (2.9% + $0.30, retained)
Disputed amount       -$200.00   (returned to cardholder)
Dispute fee            -$15.00   (non-refundable)
                       --------
Net position           -$21.10
```

If the same dispute were **won**, the $200.00 is returned and the $6.10
transaction fee is retained as normal, leaving the merchant down only the $15.00
dispute fee.

### Responding to a dispute (representment)

Merchants have **7 calendar days** from notification to submit evidence. Submitting
evidence is called *representment*.

Representment costs **$25.00** per submission. This is charged in addition to the
$15.00 dispute fee and is likewise non-refundable regardless of outcome. A merchant
who represents and loses pays $40.00 in fees on top of losing the disputed amount.

Because representment costs more than many small disputes are worth, the dashboard
displays a break-even indicator on each dispute. NovaPay does not automatically
represent on a merchant's behalf.

Evidence should include, at minimum: proof of delivery or service, the customer's
acceptance of terms, any communication with the customer, and the AVS and CVC
results from the original authorisation.

### Dispute outcomes

The issuing bank decides. NovaPay has no vote and cannot appeal on the merchant's
behalf. Decisions typically arrive **60 to 75 days** after representment, though
some card schemes take longer.

Outcomes are one of:

- **Won** — the disputed amount returns to the merchant balance. The $15.00 dispute
  fee and any $25.00 representment fee are retained.
- **Lost** — the disputed amount stays with the cardholder. All fees are retained.
- **Accepted** — the merchant chose not to represent. Equivalent to a loss, but
  with no representment fee.

### Dispute rate monitoring

Card schemes monitor dispute rates at the merchant level. Sustained rates above
**0.9% of monthly transaction count** place an account into a scheme monitoring
programme, which carries scheme-imposed fines that NovaPay passes through at cost.

Accounts approaching this threshold are contacted by Risk Operations before the
threshold is crossed. See **Fraud Controls** for the tooling available to reduce
dispute volume pre-emptively.

## Refund or dispute — which applies

| Situation | Mechanism |
|---|---|
| Customer asks the merchant for their money back | Refund |
| Customer contacts their bank instead | Dispute |
| Merchant spots their own error | Refund |
| Payment was fraudulent | Dispute (usually), initiated by the cardholder |
| Goods returned under a returns policy | Refund |

Issuing a refund **after** a dispute has been opened does not close the dispute and
results in the merchant paying twice. If a dispute is already open, respond to the
dispute; do not refund.

## Related documents

- **Pricing and Transaction Fees** — the transaction fee that a refund does not return
- **Fraud Controls** — reducing dispute volume before it happens
- **Policy Archive (2024–2026)** — the superseded 90-day refund window
- **Support Escalation** — raising a disputed dispute with NovaPay
