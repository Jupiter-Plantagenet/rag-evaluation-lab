---
doc_id: fraud-controls
title: Fraud Controls
version: 3.2.0
effective_date: 2026-04-01
supersedes: null
authoritative_for:
  - fraud.score_range
  - fraud.default_block_threshold
  - fraud.default_review_threshold
  - fraud.review_queue_sla
restates:
  - fraud.product_name
owner: Risk Operations
synthetic: true
disclaimer: >-
  NovaPay is a fictional company. Every score, threshold and signal in this
  document is invented for evaluation purposes and describes no real fraud
  system.
---

# Fraud Controls

**NovaPay Radar** scores every transaction in real time and acts on the score
according to thresholds the merchant controls.

Radar is enabled by default on all plans at no additional charge.

## Risk scores

Every transaction receives a score from **0 to 100**, where 0 is lowest risk and
100 is highest.

The score is computed before authorisation from signals including the card's
history across the NovaPay network, the relationship between billing and shipping
addresses, IP geolocation and reputation, device fingerprint, velocity of attempts
from the same card or device, the AVS and CVC results, and the transaction's
similarity to previously disputed transactions.

The score is a probability estimate, not a verdict. A score of 80 does not mean the
transaction is fraudulent; it means transactions scoring 80 are disputed
substantially more often than transactions scoring 20.

Scores appear on every transaction in the dashboard and in the API response as
`risk.score`, alongside `risk.signals` listing the factors that contributed most.

## Default thresholds

| Score | Default action |
|---|---|
| 0–49 | allow |
| **50–74** | **hold for review** |
| **75–100** | **block** |

By default, transactions scoring **75 or above are blocked** outright, and
transactions scoring **50 to 74 are held for manual review**.

Both thresholds are adjustable in **Risk → Thresholds**. Raising the block
threshold accepts more fraud in exchange for fewer false declines; lowering it does
the reverse. There is no universally correct setting, and NovaPay does not
recommend one — it depends on margin, dispute cost, and tolerance for turning away
good customers.

Blocked transactions are declined at authorisation. They incur no transaction fee,
because no payment was captured.

## The review queue

Transactions in the review band are authorised but **not captured**, and appear in
**Risk → Review**. The merchant approves or declines each one.

A transaction left in the queue is **auto-released after 24 hours**. Auto-release
means the transaction is *captured*, not cancelled — the default is to accept, on
the reasoning that an unattended queue should not silently reject good customers.

Merchants who prefer the opposite should set the queue policy to auto-decline in
**Risk → Thresholds**. This is the single most consequential setting in Radar and
it is worth deciding deliberately rather than inheriting.

The authorisation itself expires after 7 days regardless, after which a held
transaction can no longer be captured and must be recreated.

## Custom rules

Beyond thresholds, merchants can write rules in **Risk → Rules**:

```
BLOCK   IF :card_country: != :ip_country: AND :amount: > 500
REVIEW  IF :risk_score: > 40 AND :card_brand: == 'prepaid'
ALLOW   IF :customer_id: IN :trusted_list:
```

Rules evaluate in order: `ALLOW` rules first, then `BLOCK`, then `REVIEW`. The
first match wins, and an explicit `ALLOW` overrides both the thresholds and any
later rule — which is how a known-good customer is exempted from scoring entirely.

Available attributes include `risk_score`, `amount`, `currency`, `card_country`,
`ip_country`, `card_brand`, `card_funding`, `customer_id`, `email_domain`,
`is_first_transaction`, and any custom metadata attached to the payment.

Rules can be tested against the last 30 days of traffic before activation, which
reports how many past transactions each rule would have caught and how many of
those were subsequently disputed.

## 3-D Secure

3-D Secure shifts liability for fraudulent transactions from the merchant to the
issuing bank. NovaPay supports 3DS2 on all card transactions.

Three modes, set in **Risk → 3-D Secure**:

- **Off** — never request. The merchant retains liability.
- **Risk-based** (default) — request when Radar's score or a regional requirement
  calls for it.
- **Always** — request on every transaction. Maximum liability shift, highest
  friction, measurably lower conversion.

Some regions require 3DS regardless of this setting; see **Regional Restrictions**.

A successful 3DS authentication does not prevent a dispute being opened. It changes
who bears the loss, and only for disputes on fraud grounds — not for
goods-not-received or product-quality disputes, which remain with the merchant.

## Radar and disputes

Radar reduces dispute volume but does not eliminate it. Fraud that clears scoring
still becomes a dispute, and non-fraud disputes are unaffected by risk scoring
entirely.

Merchants with a rising dispute rate should tighten thresholds *and* address the
non-fraud causes, since scheme monitoring programmes count all disputes regardless
of cause. **Refunds and Disputes** covers the monitoring thresholds and the cost of
each dispute.

## What Radar does not do

- It does not review chargebacks or represent on the merchant's behalf.
- It does not screen for sanctions or prohibited territories — that is a separate,
  non-optional control described in **Regional Restrictions**.
- It does not guarantee any fraud rate, and NovaPay publishes no accuracy figure
  for it. Performance depends on the merchant's traffic.

## Related documents

- **Refunds and Disputes** — dispute costs and scheme monitoring thresholds
- **Regional Restrictions** — sanctions screening and regional 3DS requirements
- **Account Limits** — velocity controls, which are absolute and not tunable
- **Product Overview** — where Radar sits in the platform
