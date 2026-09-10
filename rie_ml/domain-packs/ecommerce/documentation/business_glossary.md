# E-Commerce Business Glossary

Domain pack: `ecommerce_v0.1.0`  
Schema: [`schema/schema.json`](../schema/schema.json)

This glossary maps business terminology to schema entities for classification, rule extraction, and schema validation.

---

## Revenue Metrics

### revenue
- **Definition:** Total recognized sales value from completed, non-excluded orders.
- **Tables/columns:** `orders.total_amount`, `orders.status`, `orders.is_test`, `payments.amount`, `payments.status`
- **Related rules:** EC_R001, EC_R002, EC_R012
- **Notes:** Excludes cancelled, test, and high-discount orders per active rules.

### gross_sales
- **Definition:** Sum of successful payment amounts before refunds.
- **Tables/columns:** `payments.amount`, `payments.status`, `orders.order_id`
- **Related rules:** EC_R004
- **Notes:** Uses `payments.status = successful` only.

### net_revenue
- **Definition:** Gross sales minus successful refund amounts.
- **Tables/columns:** `payments.amount`, `refunds.amount`, `refunds.status`
- **Related rules:** EC_R003
- **Notes:** Refunds with `status = successful` are subtracted.

---

## Order Lifecycle

### cancelled_order
- **Definition:** An order whose status is `cancelled`.
- **Tables/columns:** `orders.status`
- **Related rules:** EC_R001
- **Notes:** Must not contribute to revenue.


### open_order
- **Definition:** An order in a pre-fulfillment state (pending or confirmed).
- **Tables/columns:** `orders.status`
- **Related rules:** EC_FB012
- **Notes:** Opposite of completed_order; used for open/in-progress order reporting.

### completed_order
- **Definition:** An order treated as fulfilled for reporting.
- **Tables/columns:** `orders.status`, `orders.completed_at`
- **Related rules:** EC_R007
- **Notes:** `shipped` and `delivered` both map to completed.

### test_transaction
- **Definition:** Sandbox or QA order not representing real commerce.
- **Tables/columns:** `orders.is_test`
- **Related rules:** EC_R002
- **Notes:** Excluded from production metrics when `is_test = true`.

---

## Customer Metrics

### active_customer
- **Definition:** A customer who purchased within a defined lookback window.
- **Tables/columns:** `customers.last_purchase_at`, `customers.customer_id`
- **Related rules:** EC_R009
- **Notes:** Default window is 90 days; conflicts with 30-day variant (EC_CR006).


### customer_email
- **Definition:** Access control rule restricting visibility of customer email addresses.
- **Tables/columns:** `customers.email`
- **Related rules:** EC_FB016
- **Scope:** Role-based (finance_analyst, support_analyst, etc.)
- **Notes:** Example of field-level access restriction where entire column is hidden from specific roles.

### customer_count
- **Definition:** Count of distinct external customers.
- **Tables/columns:** `customers.customer_id`, `customers.is_internal`
- **Related rules:** EC_R010
- **Notes:** Internal accounts (`is_internal = true`) are excluded.

---

## Payments and Refunds

### payment_reconciliation
- **Definition:** Matching order records to gateway payment records.
- **Tables/columns:** `payments.transaction_id`, `payments.order_id`, `orders.order_id`
- **Related rules:** EC_R008
- **Notes:** Preferred join uses `transaction_id`, not order_id alone.

### successful_refund
- **Definition:** A refund that has been processed and finalized.
- **Tables/columns:** `refunds.status`, `refunds.amount`, `refunds.refund_date`
- **Related rules:** EC_R003
- **Notes:** Only `status = successful` affects net revenue.

---

## Promotions and Shipping

### free_shipping
- **Definition:** Shipping fee waiver for qualifying order totals.
- **Tables/columns:** `orders.total_amount`
- **Related rules:** EC_R005, EC_CR003 (threshold conflict)
- **Notes:** Active threshold is ₹999; conflicting rule proposes ₹500.

### high_discount_order
- **Definition:** Order with discount percentage above policy limit.
- **Tables/columns:** `orders.discount_pct`, `order_items.discount_pct`
- **Related rules:** EC_R012
- **Notes:** Orders above 50% discount excluded from standard revenue.

---

## Geography and Access

### regional_orders
- **Definition:** Orders scoped to a specific geographic region.
- **Tables/columns:** `orders.region_id`, `regions.name`, `regions.region_id`
- **Related rules:** EC_R006
- **Notes:** Used for region-restricted reporting and access rules.

### region
- **Definition:** Geographic sales territory.
- **Tables/columns:** `regions.region_id`, `regions.name`, `regions.country_code`
- **Related rules:** EC_R006
- **Notes:** Linked from `customers.region_id` and `orders.region_id`.

---

## Time and Reporting

### monthly_revenue
- **Definition:** Revenue aggregated by calendar month.
- **Tables/columns:** `orders.order_date`, `orders.total_amount`
- **Related rules:** EC_R011
- **Notes:** Uses calendar month boundaries on `order_date`.

### order_date
- **Definition:** Timestamp when the customer placed the order.
- **Tables/columns:** `orders.order_date`
- **Related rules:** EC_R011
- **Notes:** Not the same as `orders.completed_at` (see column_meaning rules).

### completed_at
- **Definition:** Timestamp when the order reached a terminal completed state.
- **Tables/columns:** `orders.completed_at`
- **Related rules:** EC_R007
- **Notes:** Differs from `order_date`; used for fulfillment-based reporting.

---

## Catalog

### product
- **Definition:** A sellable item in the catalog.
- **Tables/columns:** `products.product_id`, `products.name`, `products.category`, `products.is_active`
- **Related rules:** (line-item metrics via `order_items`)
- **Notes:** Inactive products (`is_active = false`) excluded from active catalog views.

### order_line_revenue
- **Definition:** Revenue at line-item granularity.
- **Tables/columns:** `order_items.quantity`, `order_items.unit_price`, `order_items.discount_pct`
- **Related rules:** EC_R012 (when discount at order level)
- **Notes:** Computed as `quantity * unit_price` adjusted for discounts.

---

## Data Quality

### duplicate_customer_id
- **Definition:** Multiple customer records sharing the same logical identity.
- **Tables/columns:** `customers.customer_id`, `customers.email`
- **Related rules:** (data_quality_issue feedback)
- **Notes:** Flagged for manual cleanup; not auto-merged by RIE.

---

## Synonyms and Aliases

| Business term | Accepted aliases |
|---------------|------------------|
| revenue | gross revenue, sales, top line |
| net_revenue | net sales, revenue after refunds |
| gross_sales | gross revenue, total sales |
| cancelled_order | canceled order, void order |
| active_customer | engaged customer, recent buyer |
| free_shipping | zero shipping, shipping waiver |
| orders / purchases | purchases, purchase, sale, sales |
| payments / transactions | transactions, transaction |
| refunds / returns | refund, return |
| customers / buyers | customer, buyer, clients |
| products / items | product, item, items, catalog_items |


### access_restriction
- **Definition:** Business term related to access restriction.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Users with role=billing should be able to view invoices and payments, others sho..."


### active_subscription
- **Definition:** Business term related to active subscription.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Active subscription includes paused subscriptions...."


### agent_access
- **Definition:** Business term related to agent access.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Support managers should not see tickets from other departments...."


### agent_workload
- **Definition:** Business term related to agent workload.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Agent workload should count assigned open tickets, not total ticket_event record..."


### average_resolution_time
- **Definition:** Business term related to average resolution time.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "average resolution time should rely on resolved at being present going forward...."


### average_revenue_per_user
- **Definition:** Business term related to average revenue per user.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "We need to aRPU should sum revenue and divide by paying users, not all registere..."


### bulk_discount
- **Definition:** Business term related to bulk discount.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "bulk discount must include quantity above 10...."


### churn
- **Definition:** Business term related to churn.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "cancelled subscriptions should be part of churn...."


### closed_ticket
- **Definition:** Business term related to closed ticket.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "resolved_at is not the same as closed_at; use closed_at for final closure report..."


### conversion_rate
- **Definition:** Business term related to conversion rate.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Exclude cancelled orders and exclude test transactions from revenue as well as r..."


### customer_lifetime_value
- **Definition:** Business term related to customer lifetime value.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Customer lifetime value should sum all paid invoices per organization, not count..."


### customer_satisfaction
- **Definition:** Business term related to customer satisfaction.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Customer satisfaction should only include received survey responses from resolve..."


### department_queue
- **Definition:** Business term related to department queue.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Department queue excludes active records...."


### duplicate_customer_email
- **Definition:** Business term related to duplicate customer email.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Duplicate customer email addresses should be reviewed as potential data quality ..."


### duplicate_event
- **Definition:** Business term related to duplicate event.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Duplicate event excludes event type of upgrade...."


### enterprise_subscription
- **Definition:** Business term related to enterprise subscription.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "name contains enterprise should be part of enterprise subscription...."


### escalated_ticket
- **Definition:** Business term related to escalated ticket.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Make sure escalated ticket accounts for priority in ['high', 'urgent'] and assig..."


### escalation_rate
- **Definition:** Business term related to escalation rate.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Can we make sure escalation rate should divide escalated tickets by total ticket..."


### failed_payment
- **Definition:** Business term related to failed payment.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Failed payments with a failure_code should trigger automatic retry logic and be ..."


### first_contact_resolution
- **Definition:** Business term related to first contact resolution.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "first contact resolution calculation mein reopen count of 0 include karna zaroor..."


### first_response_time
- **Definition:** Business term related to first response time.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Please ensure that first response time should be measured from opened_at to firs..."


### free_express_shipping
- **Definition:** Business term related to free express shipping.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "We need to orders above ₹1500 should qualify for free express shipping...."


### fulfillment_time
- **Definition:** Business term related to fulfillment time.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "fulfillment time should rely on order date being present going forward...."


### gross_merchandise_value
- **Definition:** Business term related to gross merchandise value.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Hey, can we gross merchandise value should sum order_items.unit_price times quan..."


### high_priority_ticket
- **Definition:** Business term related to high priority ticket.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Enterprise support tickets should be treated as high priority...."


### high_risk_order
- **Definition:** Business term related to high risk order.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Refund status 'pending' should display as 'under review' to customers and orders..."


### high_value_customer
- **Definition:** Business term related to high value customer.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "High-value customers are organizations with monthly spend over $1000...."


### invoice_open
- **Definition:** Business term related to invoice open.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Invoices should join to subscriptions via invoice.subscription_id, not by custom..."


### invoice_status_display
- **Definition:** Business term related to invoice status display.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Remove draft invoices when calculating invoice status display...."


### open_ticket
- **Definition:** Business term related to open ticket.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Open tickets should include open, pending, and waiting_on_customer states...."


### order_completion_status
- **Definition:** Business term related to order completion status.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Can you please orders with status 'shipped' or 'delivered' should both be labele..."


### order_status_display
- **Definition:** Business term related to order status display.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "order status display must not include confirmed orders...."


### payment_status_display
- **Definition:** Business term related to payment status display.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Translate payment status 'requires_action' to 'authentication needed' in the UI...."


### payment_success_rate
- **Definition:** Business term related to payment success rate.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Switch payment success rate over to successful payments...."


### plan_change
- **Definition:** Business term related to plan change.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Hey, can we when a user upgrades plan, generate a plan_change event and prorate ..."


### premium_tier
- **Definition:** Business term related to premium tier.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Premium tier discount should apply to customers with lifetime spend over ₹5000.0..."


### priority_display
- **Definition:** Business term related to priority display.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Translate ticket priority 'urgent' to 'critical' in escalation reports...."


### priority_support
- **Definition:** Business term related to priority support.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "I was wondering if we could priority support should be granted to customers with..."


### quality_review_ticket
- **Definition:** Business term related to quality review ticket.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "It would be great if tickets with reopen_count greater than 2 should be flagged ..."


### recurring_revenue
- **Definition:** Business term related to recurring revenue.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Can you please mRR should divide total monthly revenue by distinct organization ..."


### refund_rate
- **Definition:** Business term related to refund rate.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Can we make sure refund rate calculation should divide refund amount by gross re..."


### refund_status_display
- **Definition:** Business term related to refund status display.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Refund status 'pending' should display as 'under review' to customers and orders..."


### renewal_rate
- **Definition:** Business term related to renewal rate.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Renewal rate should divide renewed subscriptions by subscriptions up for renewal..."


### reopen_rate
- **Definition:** Business term related to reopen rate.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "I think ticket reopen rate should divide reopened ticket count by total closed t..."


### repeat_customer_rate
- **Definition:** Business term related to repeat customer rate.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "repeat customer rate should rely on customer id being present going forward...."


### revenue_per_customer
- **Definition:** Business term related to revenue per customer.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "I think revenue per customer should use distinct customer_id count in the denomi..."


### sell_through_rate
- **Definition:** Business term related to sell through rate.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "sell through rate should use quantity being present instead...."


### sla_compliance_rate
- **Definition:** Business term related to sla compliance rate.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "SLA compliance rate should count tickets meeting SLA divided by tickets with SLA..."


### subscription_renewal
- **Definition:** Business term related to subscription renewal.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Renewals should be detected when current_period_end rolls over and subscription ..."


### successful_payment
- **Definition:** Business term related to successful payment.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "succeeded payments and external payment ref is_null None ko bhi successful payme..."


### ticket_backlog
- **Definition:** Business term related to ticket backlog.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Please make sure ticket backlog does not count internal accounts...."


### ticket_event
- **Definition:** Business term related to ticket event.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Resolved and closed should both count as closed tickets, and ticket events shoul..."


### ticket_status_display
- **Definition:** Business term related to ticket status display.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Map ticket status 'waiting_on_customer' to 'awaiting response' in agent views...."


### tickets_per_agent
- **Definition:** Business term related to tickets per agent.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Tickets per agent should count distinct tickets assigned, not total ticket_event..."


### trial_conversion_rate
- **Definition:** Business term related to trial conversion rate.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Trial conversion rate should divide trials that became paid by total trials star..."


### trial_subscription
- **Definition:** Business term related to trial subscription.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Please make sure trial subscription does not count trialing subscriptions...."


### unassigned_ticket
- **Definition:** Business term related to unassigned ticket.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Tickets with null assigned_agent_id and status 'pending' for over 24 hours need ..."


### units_per_transaction
- **Definition:** Business term related to units per transaction.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Units per transaction should sum order_items.quantity per order_id, not count li..."


### vip_customer
- **Definition:** Business term related to vip customer.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "We need to vIP customers are those with support_tier equal to 'enterprise'...."


### vip_subscription
- **Definition:** Business term related to vip subscription.
- **Tables/columns:** (to be defined)
- **Related rules:** (to be defined)
- **Notes:** Auto-generated from dataset analysis.
- **Example:** "Use subscriptions.nonexistent_field to classify VIP accounts...."
