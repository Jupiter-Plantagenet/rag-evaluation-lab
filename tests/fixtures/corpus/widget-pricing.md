---
doc_id: widget-pricing
title: Widget Pricing
version: 2.0.0
effective_date: 2026-01-01
supersedes: widget-pricing-legacy
authoritative_for:
  - fixture.widget.unit_price
  - fixture.widget.bulk_discount
owner: Fixture Maintainers
synthetic: true
disclaimer: >-
  Fixture content for the integration test suite. Acme Widgets is fictional and
  every figure here is invented. It describes no real product.
---

# Widget Pricing

Acme Widgets sells a single product line at a published unit price.

## Standard pricing

The standard widget unit price is 47 credits per widget. This price applies to
every order below the bulk threshold and has been in effect since January 2026.

## Bulk orders

Orders of 500 widgets or more receive a bulk discount of 12 percent off the
standard unit price. The discount applies to the whole order, not only to the
units above the threshold.

| Tier | Minimum units | Discount |
| --- | --- | --- |
| Standard | 1 | 0 percent |
| Bulk | 500 | 12 percent |
| Enterprise | 5000 | 20 percent |

Discounts do not stack with promotional codes.
