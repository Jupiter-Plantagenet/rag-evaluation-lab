---
doc_id: webhook-delivery
title: Webhook Delivery
version: 4.1.0
effective_date: 2026-04-20
supersedes: null
authoritative_for:
  - webhook.signature_header
  - webhook.signature_algorithm
  - webhook.tolerance_window
  - webhook.retry_count
  - webhook.retry_schedule
  - webhook.total_retry_window
  - webhook.disable_threshold
  - webhook.timeout
owner: Developer Platform
synthetic: true
disclaimer: >-
  NovaPay is a fictional company. Every header name, interval and threshold in
  this document is invented for evaluation purposes.
---

# Webhook Delivery

Webhooks notify a merchant's server of events that happen outside a request/response
cycle: a payment captured asynchronously, a dispute opened, a payout failing.

Configure endpoints in **Settings → Webhooks → Add endpoint**. Each endpoint
subscribes to a chosen set of event types and receives a POST with a JSON body.

## Signature verification

**Every webhook is signed. Verify the signature before acting on the payload.** An
unverified endpoint will accept anything anyone posts to it, and the payload
contains payment state.

The signature is sent in the **`NovaPay-Signature`** header:

```
NovaPay-Signature: t=1780358400,v1=5257a869e7ecebeda32affa62cdca3fa51cad7e77a0e56ff536d0ce8e108d8bd
```

`t` is the Unix timestamp at signing. `v1` is an **HMAC-SHA256** of the string
`{t}.{raw_request_body}`, keyed with the endpoint's signing secret, hex-encoded.

To verify:

1. Extract `t` and `v1`.
2. Build the signed payload: the timestamp, a literal `.`, then the **raw** body —
   exactly as received. Do not parse and re-serialise the JSON; key order and
   whitespace both change the hash.
3. Compute HMAC-SHA256 over that string with the signing secret.
4. Compare to `v1` using a constant-time comparison.
5. Reject if `t` is outside the tolerance window.

The signing secret is per endpoint, is shown once at creation, and is **not** the
API key. Endpoints have their own secrets so that rotating an API key does not
break webhook verification, and vice versa.

### Timestamp tolerance

Reject any webhook whose timestamp is more than **5 minutes** from the current
time. This is what prevents replay: without it, a captured payload could be
resent indefinitely and would still verify.

Clock skew on the receiving server counts against this window, so keep NTP running.

## Delivery and retries

An endpoint must return a **2xx status within 10 seconds**. Anything else — a
non-2xx status, a timeout, a connection failure, a TLS error — counts as a failure.

Return 2xx as soon as the payload is *stored*, then process asynchronously. Doing
the work before responding is the most common cause of timeout-driven retries, and
it produces duplicate processing rather than preventing it.

### Retry schedule

A failed delivery is retried **6 times** on a fixed backoff:

| Attempt | Delay after previous | Elapsed since first failure |
|---|---|---|
| 1st retry | 1 minute | 1 minute |
| 2nd retry | 5 minutes | 6 minutes |
| 3rd retry | 30 minutes | 36 minutes |
| 4th retry | 2 hours | 2 hours 36 minutes |
| 5th retry | 6 hours | 8 hours 36 minutes |
| 6th retry | 24 hours | **32 hours 36 minutes** |

After the sixth retry, delivery of that event is abandoned. **The total retry
window is 32 hours and 36 minutes** from the first failure. An endpoint down for a
day and a half loses events permanently.

Retries carry the same event ID and a fresh signature. Because the timestamp is
regenerated per attempt, a retried event verifies against the tolerance window
normally.

### Endpoint disabling

An endpoint failing **every** delivery for **7 consecutive days** is disabled
automatically. The account owner is emailed at disabling and at 3 and 6 days
beforehand.

A disabled endpoint must be re-enabled manually. Events that occurred while it was
disabled are not replayed on re-enable — they are gone. Use the events API to
backfill.

## Idempotency on the receiving side

Design the receiver to tolerate duplicates. A 2xx that NovaPay never sees — because
the connection dropped after the response was written — results in a retry of an
event already processed.

Every event carries a unique `id`. Record processed IDs and ignore repeats.

Events are **not** guaranteed to arrive in order. A `payment.captured` may arrive
after the `payment.refunded` that followed it. Use the event `created` timestamp
and the object's own state rather than arrival order.

## Recovering missed events

`GET /v1/events` lists events with their delivery status, filterable by type, date
range, and delivery outcome. This is the supported way to backfill after an outage,
and it is bounded by the retention period below.

**Webhook delivery logs are retained for 30 days** — see **Data Retention**, which
is authoritative for retention periods. An outage discovered more than 30 days
later cannot be reconstructed from NovaPay's records. Note that this 30-day window
is much shorter than the 7-year retention on transaction records; the underlying
transactions survive, but the delivery history does not.

## Event types

Common types include `payment.captured`, `payment.failed`, `refund.created`,
`dispute.created`, `dispute.closed`, `payout.paid`, `payout.failed`,
`limit.threshold_reached`, and `account.updated`.

Subscribe only to what is consumed. Subscribing to everything is the second most
common cause of timeout-driven retries.

The full list is in the dashboard when configuring an endpoint. New event types are
added over time; a receiver should ignore unknown types rather than erroring.

## Local testing

Test-mode events are delivered to endpoints configured in test mode, so an
integration can be exercised end to end without live traffic. Use a tunnelling tool
to reach a local server, and note that the 10-second timeout applies to tunnelled
endpoints too.

## Related documents

- **API Authentication and Errors** — API keys, which are distinct from signing secrets
- **Data Retention** — authoritative retention periods, including delivery logs
- **Incident Response** — what happens when NovaPay itself is the cause of delivery failure
