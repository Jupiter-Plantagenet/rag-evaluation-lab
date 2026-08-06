---
doc_id: api-authentication
title: API Authentication and Errors
version: 5.2.0
effective_date: 2026-05-15
supersedes: null
authoritative_for:
  - api.auth_scheme
  - api.key_prefix.live
  - api.key_prefix.test
  - api.key_rotation_grace
  - api.rate_limit.starter
  - api.rate_limit.pro
  - api.rate_limit.response_code
  - api.test_card.success
  - api.test_card.decline
  - error.pay_001
  - error.pay_002
  - error.pay_003
owner: Developer Platform
synthetic: true
disclaimer: >-
  NovaPay is a fictional company. Every endpoint, key format, and error code in
  this document is invented for evaluation purposes. The test card numbers are
  industry-standard non-functional test values and process nothing.
---

# API Authentication and Errors

The NovaPay API is a JSON over HTTPS API. All requests must be authenticated; there
are no anonymous endpoints.

## Authentication

Authenticate with a **Bearer token in the `Authorization` header**:

```http
POST /v1/payments HTTP/1.1
Host: api.novapay.io
Authorization: Bearer sk_live_4f8a2c9e1b7d3506
Content-Type: application/json
```

NovaPay does not support HTTP Basic authentication, query-string API keys, or
cookie-based sessions for the API. A request without a valid `Authorization`
header returns `401 Unauthorized`.

## API keys

Keys are issued per environment and carry a prefix identifying which:

| Environment | Prefix | Effect |
|---|---|---|
| Live | **`sk_live_`** | moves real money |
| Test | **`sk_test_`** | simulates, moves nothing |

The prefix is not decorative — it is the only reliable way to tell at a glance
which environment a key belongs to, and logging or committing a `sk_live_` key
should be treated as a production incident.

Keys are shown in full exactly once, at creation. NovaPay stores only a hash and
cannot recover a lost key; a lost key must be rotated.

### Key rotation

Rotate from **Settings → API keys → Rotate**. On rotation a new key is issued
immediately and **the old key remains valid for 24 hours**.

The grace period exists so a deployment can roll out without downtime. It cannot
be extended. To revoke immediately instead — after a suspected leak, for example —
use **Revoke** rather than **Rotate**, which invalidates the old key at once and
will break anything still using it.

### Key scoping

Keys can be restricted to a set of permissions (`payments:read`, `payments:write`,
`refunds:write`, `payouts:read`, and so on) and to a list of source IP addresses.
A restricted key used outside its scope returns `403 Forbidden` with the required
permission named in the response body.

Restricting keys is strongly recommended for server-to-server integrations and is
required for accounts under enhanced due diligence.

## Rate limits

| Plan | Limit |
|---|---|
| Starter | **100 requests per second** |
| Pro | **1,000 requests per second** |
| Enterprise | contractual, typically higher |

Limits are applied per account, not per key, so splitting traffic across several
keys does not raise the ceiling.

Exceeding the limit returns **HTTP 429 with a `Retry-After` header** giving the
number of seconds to wait. Clients should honour `Retry-After` and back off
exponentially; NovaPay's own SDKs do this automatically.

Rate limiting is measured over a one-second sliding window. Brief bursts above the
limit are tolerated up to twice the rate for up to two seconds before 429s begin.

Read endpoints and write endpoints share the same budget.

## Testing

Use a `sk_test_` key. Test mode is a complete simulation: it has its own data, its
own dashboard view, and never contacts a card network.

Two test card numbers cover the common paths:

| Card number | Result |
|---|---|
| **4242424242424242** | approved |
| **4000000000000002** | declined |

Any future expiry date and any three-digit CVC are accepted with these. Test mode
supports the full payment lifecycle, including refunds, disputes, and webhooks.

Test-mode data is never migrated to live mode, and test keys cannot be used against
live endpoints.

## Payment error codes

Failed payments return a `PAY_` code in `error.code`:

| Code | Meaning | Retry? |
|---|---|---|
| **`PAY_001`** | **insufficient funds** | Yes, later. The customer may add funds. |
| **`PAY_002`** | **card expired** | No. Collect new card details. |
| **`PAY_003`** | **issuer declined, do not retry** | No. Retrying risks scheme penalties. |
| `PAY_004` | account limit reached | Not until the limit resets or is raised. |
| `PAY_005` | prohibited territory | No. Absolute. |

`PAY_003` is emphatic for a reason: card schemes penalise merchants who retry
hard declines, and repeated retries against the same card can place an account
into a monitoring programme. Where an issuer says no without a reason, treat it as
final.

Note that `PAY_003` is also returned by NovaPay's own velocity controls, which are
described in **Account Limits**. The two cases are indistinguishable from the API
response by design, so that probing cannot be used to map the control thresholds.

## Idempotency

Send an `Idempotency-Key` header on every write request. NovaPay stores the result
of the first request with a given key for **24 hours** and replays it for
duplicates, so a retried request after a network timeout cannot double-charge.

Keys must be unique per logical operation. Reusing a key with a different request
body returns `409 Conflict`.

## Versioning

The API version is pinned per account at the version current when the account was
created, and is visible in **Settings → API**. Breaking changes ship in a new
version; accounts are never moved automatically.

Override per request with the `NovaPay-Version` header. Versions are supported for
a minimum of **24 months** after superseding.

## SDKs

Official server-side SDKs are listed in **Product Overview**. They handle
authentication, retries, idempotency, and rate-limit backoff.

## Related documents

- **Webhook Delivery** — signature verification, which uses a different secret
- **Account Limits** — volume limits and velocity controls
- **Product Overview** — the SDK language list
- **Subscription Plans** — which plan carries which rate limit
