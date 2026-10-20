# SQL Agent Failure Analysis Report (Prompt v3)

**Total Failing Questions (Lenient)**: 36 of 40 (Lenient Accuracy: 10.0% | Strict: 7.5%)  

## 1. Summary of Failure Categories

| Failure Category | Count | Percentage of Failures | Primary Root Cause |
| :--- | :---: | :---: | :--- |
| `infrastructure_error` | 36 | 100.0% | Transient API rate limit (429), timeout, or network connection failure. |

## 2. Granular Breakdown of Every Failing Question

### `q04` (easy): What is the total discount amount given to customers?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 199074, Requested 2742. Please try again in 13m4.512s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  SELECT ROUND(SUM(discount_amount), 2) AS total_discounts FROM orders;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q05` (easy): What is our overall Average Order Value (AOV)?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 199002, Requested 2769. Please try again in 12m45.072s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  SELECT ROUND(SUM(net_amount) * 1.0 / COUNT(DISTINCT order_id), 2) AS aov FROM orders;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q06` (easy): How many orders were placed through Amazon?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 198930, Requested 2719. Please try again in 11m52.368s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  SELECT COUNT(*) AS amazon_order_count FROM orders WHERE channel = 'Amazon';
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q07` (easy): What is the total refund amount processed?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 198858, Requested 2706. Please try again in 11m15.648s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  SELECT ROUND(SUM(refund_amount), 2) AS total_refunds FROM returns;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q08` (easy): How many 5-star reviews have we received?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 198786, Requested 2742. Please try again in 11m0.096s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  SELECT COUNT(*) AS five_star_count FROM reviews WHERE rating = 5;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q09` (easy): Which product has the highest MRP?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 198714, Requested 2705. Please try again in 10m13.007999999s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  SELECT name, brand, mrp FROM products ORDER BY mrp DESC LIMIT 1;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q10` (easy): How many unique customers have purchased from us?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 198641, Requested 2741. Please try again in 9m57.024s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  SELECT COUNT(DISTINCT customer_id) AS unique_customers FROM orders;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q11` (medium): What is the total net revenue broken down by sales channel?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 198568, Requested 2767. Please try again in 9m36.72s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  SELECT channel, ROUND(SUM(net_amount), 2) AS channel_net_revenue FROM orders GROUP BY channel ORDER BY channel_net_revenue DESC;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q12` (medium): What is the Average Order Value (AOV) for each city?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 198496, Requested 2722. Please try again in 8m46.176s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  SELECT city, ROUND(SUM(net_amount) * 1.0 / COUNT(DISTINCT order_id), 2) AS city_aov FROM orders GROUP BY city ORDER BY city_aov DESC;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q13` (medium): Who are the top 3 brands by net revenue?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 198424, Requested 2833. Please try again in 9m3.024s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  SELECT p.brand, ROUND(SUM(o.net_amount), 2) AS brand_revenue FROM orders o JOIN products p ON o.sku = p.sku GROUP BY p.brand ORDER BY brand_revenue DESC LIMIT 3;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q14` (medium): What is the return rate percentage for each product category?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 198350, Requested 2816. Please try again in 8m23.712s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  SELECT p.category, ROUND(COUNT(DISTINCT r.order_id) * 100.0 / COUNT(DISTINCT o.order_id), 2) AS return_rate_pct FROM orders o JOIN products p ON o.sku = p.sku LEFT JOIN returns r ON o.order_id = r.order_id GROUP BY p.category ORDER BY return_rate_pct DESC;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q15` (medium): Show me monthly net revenue for 2024.
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 198278, Requested 2791. Please try again in 7m41.808s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  SELECT strftime(order_date, '%Y-%m') AS month, ROUND(SUM(net_amount), 2) AS monthly_revenue FROM orders WHERE strftime(order_date, '%Y') = '2024' GROUP BY month ORDER BY month ASC;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q16` (medium): What are the most frequent return reasons and their counts?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 198203, Requested 2887. Please try again in 7m50.88s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  SELECT reason, COUNT(*) AS count FROM returns GROUP BY reason ORDER BY count DESC;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q17` (medium): What is the average customer rating for each brand?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 198131, Requested 2937. Please try again in 7m41.376s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  SELECT p.brand, ROUND(AVG(r.rating), 2) AS avg_rating FROM products p JOIN reviews r ON p.sku = r.sku GROUP BY p.brand ORDER BY avg_rating DESC;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q18` (medium): How many total units were sold in each category?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 198058, Requested 2919. Please try again in 7m2.063999999s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  SELECT p.category, SUM(o.quantity) AS total_units FROM orders o JOIN products p ON o.sku = p.sku GROUP BY p.category ORDER BY total_units DESC;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q19` (medium): What is the combined net revenue from Mumbai and Delhi?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 197985, Requested 2943. Please try again in 6m40.896s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  SELECT city, ROUND(SUM(net_amount), 2) AS revenue FROM orders WHERE city IN ('Mumbai', 'Delhi') GROUP BY city ORDER BY revenue DESC;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q20` (medium): What is the average discount percentage by channel?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 197912, Requested 2756. Please try again in 4m48.576s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  SELECT channel, ROUND(AVG(discount_amount * 100.0 / gross_amount), 2) AS avg_discount_pct FROM orders GROUP BY channel ORDER BY avg_discount_pct DESC;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q21` (medium): How many orders had 3 or more units in QuickCommerce channels?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 197839, Requested 2766. Please try again in 4m21.36s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  SELECT COUNT(*) AS large_quickcommerce_orders FROM orders WHERE channel IN ('QuickCommerce-Blinkit', 'QuickCommerce-Zepto') AND quantity >= 3;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q22` (medium): What is the difference between our gross revenue and net revenue?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 197767, Requested 2802. Please try again in 4m5.808s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  SELECT ROUND(SUM(gross_amount), 2) AS gross_revenue, ROUND(SUM(net_amount), 2) AS net_revenue, ROUND(SUM(gross_amount - net_amount), 2) AS total_discount_deductions FROM orders;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q23` (hard): What is our overall repeat customer rate percentage?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 197695, Requested 2813. Please try again in 3m39.456s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  WITH cust_orders AS (SELECT customer_id, COUNT(DISTINCT order_id) AS order_cnt FROM orders GROUP BY customer_id) SELECT ROUND(COUNT(CASE WHEN order_cnt >= 2 THEN 1 END) * 100.0 / COUNT(*), 2) AS repeat_customer_rate_pct FROM cust_orders;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q24` (hard): What is the top-selling SKU by net revenue in each product category?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 197622, Requested 2826. Please try again in 3m13.535999999s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  WITH sku_rev AS (SELECT p.category, o.sku, p.name, ROUND(SUM(o.net_amount), 2) AS revenue, ROW_NUMBER() OVER (PARTITION BY p.category ORDER BY SUM(o.net_amount) DESC) AS rank FROM orders o JOIN products p ON o.sku = p.sku GROUP BY p.category, o.sku, p.name) SELECT category, sku, name, revenue FROM sku_rev WHERE rank = 1 ORDER BY revenue DESC;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q25` (hard): What is the return rate percentage for each sales channel?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 197548, Requested 2750. Please try again in 2m8.735999999s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  SELECT o.channel, ROUND(COUNT(DISTINCT r.order_id) * 100.0 / COUNT(DISTINCT o.order_id), 2) AS return_rate_pct FROM orders o LEFT JOIN returns r ON o.order_id = r.order_id GROUP BY o.channel ORDER BY return_rate_pct DESC;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q26` (hard): Show the cumulative running monthly net revenue for 2023.
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 197473, Requested 2807. Please try again in 2m0.96s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  WITH monthly AS (SELECT strftime(order_date, '%Y-%m') AS month, SUM(net_amount) AS revenue FROM orders WHERE strftime(order_date, '%Y') = '2023' GROUP BY month) SELECT month, ROUND(revenue, 2) AS monthly_revenue, ROUND(SUM(revenue) OVER (ORDER BY month), 2) AS cumulative_revenue FROM monthly ORDER BY month;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q28` (hard): Which brand has the highest return rate percentage?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 199928, Requested 2999. Please try again in 21m4.464s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  SELECT p.brand, ROUND(COUNT(DISTINCT r.order_id) * 100.0 / COUNT(DISTINCT o.order_id), 2) AS brand_return_rate FROM orders o JOIN products p ON o.sku = p.sku LEFT JOIN returns r ON o.order_id = r.order_id GROUP BY p.brand ORDER BY brand_return_rate DESC LIMIT 1;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q29` (hard): What is the average review rating of our top 5 most returned products?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 199854, Requested 2986. Please try again in 20m26.88s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  WITH top_returned AS (SELECT o.sku, COUNT(r.return_id) AS ret_cnt FROM orders o JOIN returns r ON o.order_id = r.order_id GROUP BY o.sku ORDER BY ret_cnt DESC LIMIT 5) SELECT tr.sku, p.name, tr.ret_cnt, ROUND(AVG(rev.rating), 2) AS avg_rating FROM top_returned tr JOIN products p ON tr.sku = p.sku LEFT JOIN reviews rev ON tr.sku = rev.sku GROUP BY tr.sku, p.name, tr.ret_cnt ORDER BY tr.ret_cnt DESC;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q30` (hard): List our top 5 most frequent customers with their order count and total spend.
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 199781, Requested 2770. Please try again in 18m22.032s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  SELECT customer_id, COUNT(DISTINCT order_id) AS total_orders, ROUND(SUM(net_amount), 2) AS total_spend FROM orders GROUP BY customer_id ORDER BY total_orders DESC, total_spend DESC LIMIT 5;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q31` (hard): What was the quarterly Average Order Value by channel in 2024?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 199706, Requested 2768. Please try again in 17m48.768s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  SELECT channel, year(order_date) || '-Q' || quarter(order_date) AS quarter, ROUND(SUM(net_amount) * 1.0 / COUNT(DISTINCT order_id), 2) AS aov FROM orders WHERE year(order_date) = 2024 GROUP BY channel, quarter ORDER BY channel, quarter;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q32` (hard): Calculate the month-over-month revenue growth rate for 2024.
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 199633, Requested 2741. Please try again in 17m5.568s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  WITH m_rev AS (SELECT strftime(order_date, '%Y-%m') AS month, SUM(net_amount) AS revenue FROM orders WHERE strftime(order_date, '%Y') = '2024' GROUP BY month) SELECT month, ROUND(revenue, 2) AS revenue, ROUND((revenue - LAG(revenue) OVER (ORDER BY month)) * 100.0 / LAG(revenue) OVER (ORDER BY month), 2) AS mom_growth_pct FROM m_rev ORDER BY month;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q33` (unanswerable): What was our customer acquisition cost (CAC) for Instagram marketing campaigns in 2024?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 199560, Requested 2754. Please try again in 16m39.648s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  (Unanswerable - Expected Refusal)
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q34` (unanswerable): How many orders were shipped to customers in London and Paris?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 199487, Requested 2722. Please try again in 15m54.287999999s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  (Unanswerable - Expected Refusal)
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q35` (unanswerable): What is the current remaining warehouse inventory stock for SKU-SKI-0001?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 199412, Requested 2726. Please try again in 15m23.616s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  (Unanswerable - Expected Refusal)
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q36` (unanswerable): What are our competitor's prices for hyaluronic acid serum on Nykaa?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 199332, Requested 2782. Please try again in 15m13.247999999s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  (Unanswerable - Expected Refusal)
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q37` (unanswerable): What was the average delivery time in minutes for QuickCommerce-Blinkit orders?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 199257, Requested 2783. Please try again in 14m41.28s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  (Unanswerable - Expected Refusal)
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q38` (unanswerable): What is the average salary of employees in our digital marketing department?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 199185, Requested 2741. Please try again in 13m52.031999999s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  (Unanswerable - Expected Refusal)
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q39` (unanswerable): Which supplier provided the organic rosemary oil for our haircare line?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 199113, Requested 2693. Please try again in 13m0.192s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  (Unanswerable - Expected Refusal)
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q40` (unanswerable): What is the legal warranty return policy clause for opened cosmetics?
- **Assigned Category**: `infrastructure_error`
- **Diagnosis**: Infrastructure/API Failure: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01kz9heksge36a8gjmdcgkawv2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 199040, Requested 2831. Please try again in 13m28.272s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  (Unanswerable - Expected Refusal)
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---
