---
doc_id: product-overview
title: Product Overview
version: 2.0.0
effective_date: 2026-01-01
supersedes: null
authoritative_for:
  - api.sdk_languages
  - compliance.pci_level
  - compliance.saq_scope
  - region.currency_count
restates:
  - fraud.product_name
  - fee.card.standard
  - payout.standard_delay
  - region.supported_count
  - plan.starter_price
owner: Product Marketing
synthetic: true
disclaimer: >-
  NovaPay is a fictional company created for the evaluation of retrieval
  systems. It does not exist, offers no service, and processes no payments.
  Every fact in this corpus is invented.
---

# Product Overview

NovaPay is a payments platform for online businesses. It handles card payments,
bank transfers, and crypto settlement through one API and one dashboard, and pays
out to a merchant's bank account on a schedule they choose.

This document is an orientation. Where it restates a figure, the document named as
authoritative governs.

## What NovaPay does

- **Accept payments** - cards, bank transfers, crypto, and region-specific local
  methods, through a hosted checkout, embeddable elements, or a direct API integration.
- **Manage risk** - every transaction is scored in real time by **NovaPay Radar**,
  with configurable thresholds and rules. See **Fraud Controls**.
- **Handle the aftermath** - refunds, disputes, and representment, documented in
  **Refunds and Disputes**.
- **Settle** - automatic payouts on a daily, weekly, or monthly schedule. Standard
  payouts arrive **T+2 business days**; see **Payout Schedules** for the exceptions,
  including the hold on a new account's first payout.

## Coverage

NovaPay supports merchants in **45 countries** across North America, Europe, and
Asia-Pacific, and settles in over **120 fiat currencies and 15 cryptocurrencies**.

Availability depends on where the merchant is established, and some territories are
prohibited outright. **Regional Restrictions** is authoritative for both.

## Integration

### SDKs

Official server-side SDKs are published for **Python, Node.js, Ruby, Go, PHP, and
Java**. They handle authentication, retries, idempotency, and rate-limit backoff,
and are the recommended way to integrate.

These are server-side libraries. Client-side integration is through the hosted
checkout or the browser-based payment elements, both of which are framework-agnostic
JavaScript.

Full API reference: `docs.novapay.io`.

### Getting started

1. Sign up and complete verification - usually within 24 hours; see **Account Limits**.
2. Collect a `sk_test_` key from **Settings > API keys**.
3. Build against test mode, which simulates the full lifecycle and moves no money.
4. Switch to a `sk_live_` key.

Test mode is available immediately on signup and is not gated on verification, so
integration work can begin before the account is approved.

## Pricing at a glance

The Starter plan is **$0 per month** and charges **2.9% + $0.30** per successful
card transaction. Bank transfers and crypto are priced differently, and Pro reduces
the card rate.

**Pricing and Transaction Fees** is authoritative for every rate; **Subscription
Plans** is authoritative for monthly plan pricing. The figures above are a summary
and should not be quoted as terms.

## Security and compliance

NovaPay is certified **PCI DSS Level 1**, the highest level defined by the card
schemes, and is audited annually by a Qualified Security Assessor.

Merchants using the hosted checkout or payment elements never touch raw card data,
which reduces their own compliance scope to **SAQ-A** - the shortest
self-assessment questionnaire. Merchants who post card data directly to the API take
on a substantially larger scope and should confirm their obligations independently.

Card data is tokenised on capture. NovaPay stores tokens, not card numbers, and a
token is usable only by the account that created it.

## The dashboard

The dashboard covers payments, refunds, disputes, payouts, balances, risk rules,
API keys, webhooks, team access, and exports. Seat counts vary by plan.

Role-based access is available on all plans: Owner, Administrator, Developer,
Analyst, and Support, each with a fixed permission set. Custom roles are Enterprise
only.

## What NovaPay is not

To set expectations, and because these questions arrive regularly:

- NovaPay is not a bank and does not hold deposits. Balances are funds in transit.
- NovaPay is not an accounting system. It exports data; it does not do bookkeeping.
- NovaPay does not provide tax, legal, or compliance advice, and does not discharge
  a merchant's own regulatory obligations.
- NovaPay does not lend, advance funds, or offer merchant cash advances.

## Where to go next

| Question | Document |
|---|---|
| What will this cost me? | Pricing and Transaction Fees, Subscription Plans |
| When do I get paid? | Payout Schedules |
| How much can I process? | Account Limits |
| Can I operate in country X? | Regional Restrictions |
| How do I authenticate? | API Authentication and Errors |
| How do I receive events? | Webhook Delivery |
| A customer disputed a payment | Refunds and Disputes |
| How is fraud handled? | Fraud Controls |
| How long is my data kept? | Data Retention |
| Something is broken | Incident Response, Support Escalation |
