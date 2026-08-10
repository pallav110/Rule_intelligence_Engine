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
