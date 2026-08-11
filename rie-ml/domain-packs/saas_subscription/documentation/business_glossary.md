# SaaS Subscription Domain — Business Glossary

**Domain:** `saas_subscription`  
**Version:** `saas_subscription_v0.1.0`

This glossary defines normalized business terms used in the SaaS Subscription pack and maps them to schema fields.

- `active_subscription`: A subscription with `subscriptions.status = active` and `cancel_at_period_end = false`.
- `cancelled_subscription`: A subscription where `subscriptions.status = cancelled` or `cancelled_at` is not null.
- `trial_subscription`: A subscription with `subscriptions.status = trialing` or within `subscription_plans.trial_days` from `start_date`.
- `recurring_revenue`: Sum of `invoices.amount_cents` for `invoices.status = paid` during a period, attributable to active subscriptions.
- `failed_payment`: A payment row with `payments.status = failed` and a non-null `failure_code`.
- `successful_payment`: A payment row with `payments.status = succeeded`.
- `invoice_open`: An invoice with `invoices.status = open` (outstanding balance) and no `paid_date`.
- `subscription_renewal`: When `current_period_end` advances and a new billing period starts without cancellation.
- `plan_change`: A change of `subscriptions.plan_id` with associated proration and invoice adjustments.
- `churn`: A time-windowed calculation of customers moving from `active` to `cancelled` over the observation window.
- `access_restriction`: Business rule that limits `users.role` visibility into `invoices` or `payments` (e.g., `billing` role allowed).
- `duplicate_subscription`: Two or more `subscriptions` rows with the same `external_subscription_ref` but separate `subscription_id` values.
- `usage_event`: `product_events.event_type = "usage"`, with `product_events.amount` representing usage quantity or cents.

Each glossary term above directly corresponds to one or more fields in `schema/schema.json` and can be referenced in `active_rules.json` and seed annotations.
