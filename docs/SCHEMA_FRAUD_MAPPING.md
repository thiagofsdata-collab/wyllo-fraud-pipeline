# Olist Dataset → Return Fraud Prevention Schema Mapping

This document explains how the Brazilian E-Commerce dataset from Olist
(a clean transactional dataset originally meant for retail analytics) is
reshaped into a **return-fraud-prevention feature store** that mirrors the
kind of signals Wyllo may would compute over real merchant traffic.

---

## 1. Why Olist for a Return Fraud Pipeline?

The Olist dataset has three properties that make it a strong substrate:

1. **Real transactional granularity.** ~100k orders across ~3k sellers and
   ~99k unique customers, with multi-table normalization (orders, items,
   payments, reviews, sellers, customers, products, geolocation).
2. **Real behavioural variance.** Order status transitions (`canceled`,
   `unavailable`, `delivered`), payment installments up to 24x, multi-payment
   orders, and low review scores all exist naturally.
3. **No fraud labels.** This is a *feature*, not a bug. Production fraud
   teams rarely get clean labels — they engineer **proxies** from correlated
   signals and use rule-based + semi-supervised scoring. We replicate that
   constraint here.

### Mapping Olist's marketplace model to Wyllo's DTC model

Wyllo serves **direct-to-consumer** merchants (Caraway, Everlane, Super73).
Olist is a **marketplace** (many sellers, one platform). I treat **each Olist
seller as if it were one Wyllo-merchant tenant** — this gives the pipeline
naturally multi-tenant test conditions without inventing fake data. The
behavioural features (velocity, cancel rate, review patterns) transfer
cleanly between the two models.

### What Olist does NOT have (and how we handle it)

| Missing signal | Decision |
|---|---|
| Explicit `returns` table | Use `order_status='canceled'` post-approval as **proxy** |
| Explicit `chargebacks` flag | Same proxy as above (cancel-post-approval = chargeback proxy) |
| Explicit refund flag | Inferred from cancel-post-approval |
| Device fingerprint / IP / user-agent | **Out of scope.** Not simulated. Discussed as future work / interview question. |
| BIN / card issuer country | Out of scope |

The decision to **not simulate** device/IP is deliberate. Simulated identity
data adds little value to the demo and creates a weak spot to defend.
Instead, we flag this as a known limitation and a discussion point: how does
Wyllo's identity layer work in production?

---

## 2. Source Tables (Bronze layer — 1:1 with Olist CSVs)

| Source Table              | Rows    | Key Columns                                       | Used For                                  |
|---------------------------|---------|---------------------------------------------------|-------------------------------------------|
| `olist_orders`            | ~99k    | `order_id`, `customer_id`, `order_status`, ts     | Velocity, cancellation proxy              |
| `olist_order_items`       | ~112k   | `order_id`, `seller_id`, `product_id`, `price`    | Per-seller exposure, basket value         |
| `olist_order_payments`    | ~104k   | `order_id`, `payment_type`, `installments`        | Payment risk score, installment anomaly   |
| `olist_order_reviews`     | ~99k    | `order_id`, `review_score`, `review_comment`      | Item-not-received & friendly-fraud proxy  |
| `olist_customers`         | ~99k    | `customer_id`, `customer_unique_id`, `zip`        | Customer dedup, geo velocity              |
| `olist_sellers`           | ~3k     | `seller_id`, `seller_zip_prefix`, `state`         | Per-tenant aggregations                   |
| `olist_products`          | ~33k    | `product_id`, `category`, `weight`, dimensions    | Category-level risk priors                |
| `olist_geolocation`       | ~1M     | `zip_prefix`, `lat`, `lng`, `city`, `state`       | Haversine distance for geo features       |
| `product_category_translation` | ~71 | `category_name`, `category_name_english`          | English category labels                   |

---

## 3. The Four Feature Families (Gold layer)

All features land in `gold.fct_customer_return_risk_features`. The grain is
documented in Section 4 (it's deliberately temporal — read that section).

### 3.1 Velocity Features (real data, no proxy)

How active is this customer in a rolling time window?

| Feature                          | Logic                                                    | Why it matters for return fraud |
|----------------------------------|----------------------------------------------------------|----------------------------------|
| `customer_orders_24h`            | COUNT orders by customer in trailing 24h                 | Serial returners batch their orders before mass-returning |
| `customer_orders_7d`             | Same, 7d window                                          | Same logic, longer horizon |
| `customer_orders_30d`            | Same, 30d window                                         | Baseline activity level |
| `customer_distinct_sellers_7d`   | DISTINCT seller_ids in 7d                                | Spreading across sellers can indicate card testing or arbitrage |
| `customer_total_spent_30d`       | SUM payment_value in 30d                                 | Risk exposure |

### 3.2 Cancellation Proxy (chargeback / refund signal)

Olist has no explicit chargeback flag, but `order_status='canceled'`
combined with `order_approved_at IS NOT NULL` is a tight proxy: the
customer paid, the payment cleared, then the order was cancelled — the
same behavioural pattern as a chargeback or post-payment refund request.

| Feature                                     | Logic                                                            |
|---------------------------------------------|------------------------------------------------------------------|
| `customer_cancel_rate_lifetime`             | canceled_orders / total_orders                                   |
| `customer_cancel_post_approval_count_30d`   | orders where status='canceled' AND approved_at IS NOT NULL, 30d  |
| `customer_avg_hours_purchase_to_cancel`     | AVG(canceled_at - purchase_ts) across customer's canceled orders |

### 3.3 Review-Based Signals (INR claim / friendly fraud proxy)

A `review_score <= 2` on a `delivered` order is a behavioural proxy for an
item-not-received (INR) claim or friendly fraud dispute. The actual dispute
would happen with the payment processor; the review is what we can see.

| Feature                                  | Logic                                                              |
|------------------------------------------|--------------------------------------------------------------------|
| `customer_avg_review_score`              | AVG over all reviews                                               |
| `customer_low_review_on_delivered_rate`  | reviews_with_score_le_2 / delivered_orders                         |
| `customer_no_review_rate`                | delivered_orders_without_review / delivered_orders                 |

### 3.4 Geographic Features (real data, haversine over olist_geolocation)

Geographic velocity and customer↔seller distance are classic fraud signals.
Drop-address fraud (where stolen goods are shipped to an address far from
the billing zone) produces high distances and rapid state-hopping.

| Feature                                     | Logic                                                                 |
|---------------------------------------------|-----------------------------------------------------------------------|
| `avg_customer_seller_distance_km`           | AVG haversine(customer_zip, seller_zip) across the customer's orders  |
| `distinct_shipping_states_30d`              | DISTINCT customer_state across customer's orders in 30d               |
| `max_geographic_velocity_kmh`               | MAX(distance / hours_between_consecutive_orders) — implausible if > 800 |

---

## 4. The Temporal Grain — Why `(customer_unique_id, snapshot_date)`

This is the single most important design choice in this pipeline.

### The problem

If the feature store has 1 row per customer with their *current* state, you
cannot train any predictive model on it without leaking the future into the
past. A customer who has 0.85 cancel rate today obviously **already became
a fraudster** — the model would learn "high cancel rate ↔ fraud" tautologically.

### The solution: point-in-time correctness

The feature store has **1 row per (customer, snapshot_date)**. Each row
answers: *"what did this customer look like on this date, using only data
that existed on or before this date?"*

```
customer_unique_id  | snapshot_date | total_orders_lifetime | orders_30d | cancel_rate_lifetime | ...
abc123              | 2018-01-01    | 1                     | 1          | 0.00                 | ...
abc123              | 2018-02-01    | 2                     | 2          | 0.00                 | ...
abc123              | 2018-03-01    | 3                     | 1          | 0.33                 | ...  ← cancelled one
abc123              | 2018-04-01    | 4                     | 1          | 0.25                 | ...
```

### Snapshot frequency

**Monthly snapshots** (first day of each month). Rationale:

- Captures behavioural evolution at meaningful resolution for return fraud,
  which plays out over weeks-to-months.
- Storage is bounded: 99k customers × 24 months ≈ 2.4M rows — trivial for DuckDB.
- In production, real-time scoring would use a managed feature store
  (Feast, Tecton) with TTL-based recomputation. Monthly batch is the
  simpler, defensible MVP.

### Implementation pattern (dbt + DuckDB)

```sql
-- conceptual sketch, real model lives in models/gold/
WITH calendar AS (
  SELECT generate_series('2017-01-01'::date, '2018-09-01'::date, INTERVAL '1 month') AS snapshot_date
),
customer_snapshots AS (
  SELECT c.customer_unique_id, cal.snapshot_date
  FROM {{ ref('dim_customers') }} c
  CROSS JOIN calendar cal
  WHERE c.first_order_date <= cal.snapshot_date
)
SELECT
  cs.customer_unique_id,
  cs.snapshot_date,
  COUNT(o.order_id) FILTER (
    WHERE o.order_purchase_timestamp <= cs.snapshot_date
  ) AS total_orders_lifetime,
  COUNT(o.order_id) FILTER (
    WHERE o.order_purchase_timestamp
      BETWEEN cs.snapshot_date - INTERVAL '30 days' AND cs.snapshot_date
  ) AS orders_last_30d,
  -- ... 18 other features following same FILTER pattern
FROM customer_snapshots cs
LEFT JOIN {{ ref('stg_orders') }} o
  ON o.customer_unique_id = cs.customer_unique_id
GROUP BY 1, 2
```

The `FILTER (WHERE timestamp <= snapshot_date)` clause is the guarantee
of point-in-time correctness. Every feature uses it. Tests in `dbt/tests/`
verify it.

---

## 5. Final Gold Schema — `fct_customer_return_risk_features`

```
fct_customer_return_risk_features
├── customer_unique_id                       -- PK part 1
├── snapshot_date                            -- PK part 2
│
├── -- Identity / dimensions ----------------
├── customer_state                           -- most recent shipping state
├── days_since_first_order                   -- as of snapshot_date
├── days_since_last_order                    -- NULL if never ordered before
│
├── -- Family 1: Velocity -------------------
├── total_orders_lifetime
├── orders_last_30d
├── orders_last_7d
├── orders_last_24h
├── distinct_sellers_last_7d
├── total_spent_last_30d
│
├── -- Family 2: Cancellation proxy ---------
├── cancel_rate_lifetime
├── cancel_post_approval_count_30d
├── avg_hours_purchase_to_cancel
│
├── -- Family 3: Review proxy ---------------
├── avg_review_score
├── low_review_on_delivered_rate
├── no_review_rate
│
└── -- Family 4: Geographic ------------------
    ├── avg_customer_seller_distance_km
    ├── distinct_shipping_states_30d
    └── max_geographic_velocity_kmh
```

~20 columns. Each one defendable in one sentence. No filler.

---

## 6. Reference Tables (`seeds/`)

| Seed File                       | Purpose                                                        |
|---------------------------------|----------------------------------------------------------------|
| `payment_method_risk.csv`       | payment_type → base risk score (0-1)                           |
| `risk_thresholds.csv`           | tier boundaries: low<0.3, medium<0.6, high<0.85, critical≥0.85 |
| `category_risk_priors.csv`      | product_category → historical fraud-prone categories prior     |

Versioned in git, tested for not-null and uniqueness in dbt, and reviewed
via PR. This is how a real fraud team manages threshold drift.

---

## 7. What's Explicitly Out of Scope (and Why)

Documenting limits is engineering. These are interview discussion points,
not failures:

| Out of scope                          | Why                                                                  |
|---------------------------------------|----------------------------------------------------------------------|
| Device / IP / browser fingerprint     | Olist has none; simulation would be theater                          |
| Real-time scoring (sub-second)        | Wyllo pre-checkout needs this; batch feature store is the MVP for DE |
| ML model training                     | Data Scientist's job. Pipeline produces the input, not the output    |
| Rule engine business logic            | Fraud Analyst's job. Pipeline exposes the features they query        |
| Cross-merchant identity resolution    | The Wyllo moat. Requires data from multiple tenants we don't have    |
| Chargeback ground-truth labels        | Would arrive 60-120d post-purchase from payment processors           |

Each row above is a **question to ask Wyllo in the conversation**.
