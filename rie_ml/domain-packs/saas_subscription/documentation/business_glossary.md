# SaaS Subscription Business Glossary

Domain pack: `saas_subscription_v0.1.0`  
Schema: [`schema/schema.json`](../schema/schema.json)

This glossary maps business terminology to schema entities for classification, rule extraction, and schema validation.

---

## Subscription Metrics

### active_subscription
- **Definition:** A subscription with `subscriptions.status = active` and `cancel_at_period_end = false`.
- **Tables/columns:** `subscriptions.status`, `subscriptions.cancel_at_period_end`, `subscriptions.current_period_end`
- **Related rules:** SS_R001
- **Notes:** Used for active customer reporting and churn calculations.

### cancelled_subscription
- **Definition:** A subscription where `subscriptions.status = cancelled` or `cancelled_at` is not null.
- **Tables/columns:** `subscriptions.status`, `subscriptions.cancelled_at`
- **Related rules:** SS_R002
- **Notes:** Excluded from active revenue calculations.

### trial_subscription
- **Definition:** A subscription with `subscriptions.status = trialing` or within `subscription_plans.trial_days` from `start_date`.
- **Tables/columns:** `subscriptions.status`, `subscriptions.start_date`, `subscription_plans.trial_days`
- **Related rules:** SS_R003
- **Notes:** Trial periods are typically free or discounted.

### recurring_revenue
- **Definition:** Sum of `invoices.amount_cents` for `invoices.status = paid` during a period, attributable to active subscriptions.
- **Tables/columns:** `invoices.amount_cents`, `invoices.status`, `invoices.subscription_id`, `subscriptions.status`
- **Related rules:** SS_R004
- **Notes:** Core SaaS revenue metric.

### churn
- **Definition:** A time-windowed calculation of customers moving from `active` to `cancelled` over the observation window.
- **Tables/columns:** `subscriptions.status`, `subscriptions.cancelled_at`, `subscriptions.created_at`
- **Related rules:** SS_R005
- **Notes:** Key metric for retention analysis.

---

## Billing & Payments

### failed_payment
- **Definition:** A payment row with `payments.status = failed` and a non-null `failure_code`.
- **Tables/columns:** `payments.status`, `payments.failure_code`, `payments.subscription_id`
- **Related rules:** SS_R006
- **Notes:** Triggers dunning processes.

### successful_payment
- **Definition:** A payment row with `payments.status = succeeded`.
- **Tables/columns:** `payments.status`, `payments.amount_cents`, `payments.subscription_id`
- **Related rules:** SS_R007
- **Notes:** Used for revenue recognition.

### invoice_open
- **Definition:** An invoice with `invoices.status = open` (outstanding balance) and no `paid_date`.
- **Tables/columns:** `invoices.status`, `invoices.paid_date`, `invoices.due_date`
- **Related rules:** SS_R008
- **Notes:** Represents unpaid invoices.

### payment_success_rate
- **Definition:** Percentage of payment attempts that succeed, calculated as `successful_payment / (successful_payment + failed_payment)`.
- **Tables/columns:** `payments.status`, `payments.attempt_count`
- **Related rules:** SS_R009
- **Notes:** Indicates payment processing health.

---

## Plan Management

### subscription_renewal
- **Definition:** When `current_period_end` advances and a new billing period starts without cancellation.
- **Tables/columns:** `subscriptions.current_period_end`, `subscriptions.cancel_at_period_end`
- **Related rules:** SS_R010
- **Notes:** Triggers renewal invoices.

### plan_change
- **Definition:** A change of `subscriptions.plan_id` with associated proration and invoice adjustments.
- **Tables/columns:** `subscriptions.plan_id`, `subscription_plans.price_cents`, `invoices.proration_amount`
- **Related rules:** SS_R011
- **Notes:** May generate prorated charges or credits.

---

## Access Control

### access_restriction
- **Definition:** Business rule that limits `users.role` visibility into `invoices` or `payments` (e.g., `billing` role allowed).
- **Tables/columns:** `users.role`, `invoices.subscription_id`, `users.subscription_id`
- **Related rules:** SS_R012
- **Notes:** Enforces data access policies.

---

## Data Quality

### duplicate_subscription
- **Definition:** Two or more `subscriptions` rows with the same `external_subscription_ref` but separate `subscription_id` values.
- **Tables/columns:** `subscriptions.external_subscription_ref`, `subscriptions.subscription_id`
- **Related rules:** SS_R013
- **Notes:** Indicates integration or import errors.

### usage_event
- **Definition:** `product_events.event_type = "usage"`, with `product_events.amount` representing usage quantity or cents.
- **Tables/columns:** `product_events.event_type`, `product_events.amount`, `product_events.subscription_id`
- **Related rules:** SS_R014
- **Notes:** Used for usage-based billing.

---

## Additional Metrics

### monthly_revenue
- **Definition:** Sum of `invoices.amount_cents` for `invoices.status = paid` in a calendar month.
- **Tables/columns:** `invoices.amount_cents`, `invoices.status`, `invoices.paid_at`
- **Related rules:** SS_R015
- **Notes:** Standard MRR calculation.

### average_revenue_per_user
- **Definition:** `monthly_revenue` divided by distinct `customers.customer_id` with active subscriptions.
- **Tables/columns:** `invoices.amount_cents`, `customers.customer_id`, `subscriptions.customer_id`
- **Related rules:** SS_R016
- **Notes:** ARPU metric for customer value analysis.

### trial_conversion_rate
- **Definition:** Percentage of `trial_subscription` that convert to paid `active_subscription` within the trial period.
- **Tables/columns:** `subscriptions.status`, `subscriptions.start_date`, `subscriptions.plan_id`
- **Related rules:** SS_R017
- **Notes:** Measures trial effectiveness.

### renewal_rate
- **Definition:** Percentage of active subscriptions that renew at the end of their billing period.
- **Tables/columns:** `subscriptions.status`, `subscriptions.current_period_end`, `subscriptions.cancel_at_period_end`
- **Related rules:** SS_R018
- **Notes:** Indicates customer retention.
