# SQL Agent Failure Analysis Report (Prompt v3)

**Total Failing Questions**: 7 of 40 (Accuracy: 82.5%)  

## 1. Summary of Failure Categories

| Failure Category | Count | Percentage of Failures | Primary Root Cause |
| :--- | :---: | :---: | :--- |
| `ambiguity` | 3 | 42.9% | Question wording allows multiple valid interpretations or gold SQL requires arbitrary extra columns (e.g. brand in MRP query). |
| `false_refusal` | 2 | 28.6% | Model falsely claimed the data was missing for an answerable query. |
| `wrong_metric` | 1 | 14.3% | Generated SQL used an alternate aggregation or failed to adhere to corporate data dictionary formulas. |
| `date_handling` | 1 | 14.3% | Discrepancy in date formatting or year/month extraction syntax. |

## 2. Granular Breakdown of Every Failing Question

### `q09` (easy): Which product has the highest MRP?
- **Assigned Category**: `ambiguity`
- **Diagnosis**: Question wording has multiple valid interpretations or gold SQL requires arbitrary extra columns.
- **Generated SQL**:
  ```sql
  SELECT sku, name, brand, category, mrp FROM products ORDER BY mrp DESC LIMIT 1
  ```
- **Gold SQL**:
  ```sql
  SELECT name, brand, mrp FROM products ORDER BY mrp DESC LIMIT 1;
  ```
- **Result Diff Summary**:
  - Agent Results: `[{'sku': 'SKU-COL-0005', 'name': 'GlowBotanica Ultra-Fine Setting Powder (Travel Size)', 'brand': 'GlowBotanica', 'category': 'Color Cosmetics', 'mrp': 2499.0}]`
  - Gold Results: `[{'name': 'GlowBotanica Ultra-Fine Setting Powder (Travel Size)', 'brand': 'GlowBotanica', 'mrp': 2499.0}]`

---

### `q17` (medium): What is the average customer rating for each brand?
- **Assigned Category**: `ambiguity`
- **Diagnosis**: Question wording has multiple valid interpretations or gold SQL requires arbitrary extra columns.
- **Generated SQL**:
  ```sql
  SELECT p.brand, ROUND(AVG(r.rating), 2) AS avg_rating FROM reviews AS r JOIN products AS p ON r.sku = p.sku GROUP BY p.brand ORDER BY avg_rating DESC LIMIT 100
  ```
- **Gold SQL**:
  ```sql
  SELECT p.brand, ROUND(AVG(r.rating), 2) AS avg_rating, COUNT(r.review_id) AS review_count FROM products p JOIN reviews r ON p.sku = r.sku GROUP BY p.brand ORDER BY avg_rating DESC;
  ```
- **Result Diff Summary**:
  - Agent Results: `[{'brand': 'GlowBotanica', 'avg_rating': 4.14}, {'brand': 'SilkRadiance', 'avg_rating': 4.12}, {'brand': 'LuxeAura', 'avg_rating': 4.08}]`
  - Gold Results: `[{'brand': 'GlowBotanica', 'avg_rating': 4.14, 'review_count': 453}, {'brand': 'SilkRadiance', 'avg_rating': 4.12, 'review_count': 381}, {'brand': 'LuxeAura', 'avg_rating': 4.08, 'review_count': 425}]`

---

### `q24` (hard): What is the top-selling SKU by net revenue in each product category?
- **Assigned Category**: `wrong_metric`
- **Diagnosis**: Metric calculation formula did not align with corporate governance definition.
- **Generated SQL**:
  ```sql
  WITH revenue AS (SELECT p.category, o.sku, ROUND(SUM(o.net_amount), 2) AS net_rev FROM orders AS o JOIN products AS p ON o.sku = p.sku GROUP BY p.category, o.sku) SELECT category, sku, net_rev FROM (SELECT category, sku, net_rev, ROW_NUMBER() OVER (PARTITION BY category ORDER BY net_rev DESC) AS rn FROM revenue) AS t WHERE rn = 1 ORDER BY category LIMIT 100
  ```
- **Gold SQL**:
  ```sql
  WITH sku_rev AS (SELECT p.category, o.sku, p.name, ROUND(SUM(o.net_amount), 2) AS revenue, ROW_NUMBER() OVER (PARTITION BY p.category ORDER BY SUM(o.net_amount) DESC) AS rank FROM orders o JOIN products p ON o.sku = p.sku GROUP BY p.category, o.sku, p.name) SELECT category, sku, name, revenue FROM sku_rev WHERE rank = 1 ORDER BY revenue DESC;
  ```
- **Result Diff Summary**:
  - Agent Results: `[{'category': 'Bath & Body', 'sku': 'SKU-BAT-0103', 'net_rev': 472061.1}, {'category': 'Color Cosmetics', 'sku': 'SKU-COL-0040', 'net_rev': 503798.4}, {'category': 'Fragrance', 'sku': 'SKU-FRA-0129', 'net_rev': 444555.9}]`
  - Gold Results: `[{'category': 'Haircare', 'sku': 'SKU-HAI-0027', 'name': 'SilkRadiance Biotin Anti-Hairfall Mask (Travel Size)', 'revenue': 542907.75}, {'category': 'Color Cosmetics', 'sku': 'SKU-COL-0040', 'name': 'LuxeAura Peach Blossom Powder Blush (Original)', 'revenue': 503798.4}, {'category': 'Skincare', 'sku': 'SKU-SKI-0146', 'name': 'BotanicalBliss Niacinamide 10% Blemish Toner (Mini)', 'revenue': 495176.85}]`

---

### `q26` (hard): Show the cumulative running monthly net revenue for 2023.
- **Assigned Category**: `date_handling`
- **Diagnosis**: Discrepancy in date grouping or formatting logic.
- **Generated SQL**:
  ```sql
  SELECT month, month_net, SUM(month_net) OVER (ORDER BY month) AS cumulative_net FROM (SELECT CAST(DATE_TRUNC('MONTH', order_date) AS DATE) AS month, SUM(net_amount) AS month_net FROM orders WHERE STRFTIME(order_date, '%Y') = '2023' GROUP BY month) AS sub ORDER BY month LIMIT 100
  ```
- **Gold SQL**:
  ```sql
  WITH monthly AS (SELECT strftime(order_date, '%Y-%m') AS month, SUM(net_amount) AS revenue FROM orders WHERE strftime(order_date, '%Y') = '2023' GROUP BY month) SELECT month, ROUND(revenue, 2) AS monthly_revenue, ROUND(SUM(revenue) OVER (ORDER BY month), 2) AS cumulative_revenue FROM monthly ORDER BY month;
  ```
- **Result Diff Summary**:
  - Agent Results: `[{'month': datetime.date(2023, 1, 1), 'month_net': 1266469.3500000013, 'cumulative_net': 1266469.3500000013}, {'month': datetime.date(2023, 2, 1), 'month_net': 1205395.9500000004, 'cumulative_net': 2471865.3000000017}, {'month': datetime.date(2023, 3, 1), 'month_net': 1373817.1500000036, 'cumulative_net': 3845682.4500000053}]`
  - Gold Results: `[{'month': '2023-01', 'monthly_revenue': 1266469.35, 'cumulative_revenue': 1266469.35}, {'month': '2023-02', 'monthly_revenue': 1205395.95, 'cumulative_revenue': 2471865.3}, {'month': '2023-03', 'monthly_revenue': 1373817.15, 'cumulative_revenue': 3845682.45}]`

---

### `q29` (hard): What is the average review rating of our top 5 most returned products?
- **Assigned Category**: `ambiguity`
- **Diagnosis**: Question wording has multiple valid interpretations or gold SQL requires arbitrary extra columns.
- **Generated SQL**:
  ```sql
  WITH return_counts AS (SELECT o.sku, COUNT(*) AS return_count FROM returns AS ret JOIN orders AS o ON ret.order_id = o.order_id GROUP BY o.sku ORDER BY return_count DESC LIMIT 5) SELECT ROUND(AVG(r.rating), 2) AS avg_rating FROM reviews AS r JOIN return_counts AS rc ON r.sku = rc.sku LIMIT 100
  ```
- **Gold SQL**:
  ```sql
  WITH top_returned AS (SELECT o.sku, COUNT(r.return_id) AS ret_cnt FROM orders o JOIN returns r ON o.order_id = r.order_id GROUP BY o.sku ORDER BY ret_cnt DESC LIMIT 5) SELECT tr.sku, p.name, tr.ret_cnt, ROUND(AVG(rev.rating), 2) AS avg_rating FROM top_returned tr JOIN products p ON tr.sku = p.sku LEFT JOIN reviews rev ON tr.sku = rev.sku GROUP BY tr.sku, p.name, tr.ret_cnt ORDER BY tr.ret_cnt DESC;
  ```
- **Result Diff Summary**:
  - Agent Results: `[{'avg_rating': 4.16}]`
  - Gold Results: `[{'sku': 'SKU-FRA-0064', 'name': 'GlowBotanica Saffron & Cardamom Noir (Refill Pack)', 'ret_cnt': 23, 'avg_rating': 4.38}, {'sku': 'SKU-SKI-0141', 'name': 'DermaBloom Retinol 0.5% Night Recovery Oil (Original)', 'ret_cnt': 21, 'avg_rating': 3.88}, {'sku': 'SKU-HAI-0142', 'name': 'AuraBotanics Onion & Fenugreek Hair Oil (Intense)', 'ret_cnt': 21, 'avg_rating': 4.15}]`

---

### `q31` (hard): What was the quarterly Average Order Value by channel in 2024?
- **Assigned Category**: `false_refusal`
- **Diagnosis**: Falsely refused answerable question: Failed to produce a valid SQL query after 3 self-correction attempts.
- **Generated SQL**:
  ```sql
  (Refused or No SQL)
  ```
- **Gold SQL**:
  ```sql
  SELECT channel, strftime(order_date, '%Y-Q') || ((CAST(strftime(order_date, '%m') AS INTEGER) - 1) / 3 + 1) AS quarter, ROUND(SUM(net_amount) * 1.0 / COUNT(DISTINCT order_id), 2) AS aov FROM orders WHERE strftime(order_date, '%Y') = '2024' GROUP BY channel, quarter ORDER BY channel, quarter;
  ```
- **Result Diff Summary**:
  - Agent Results: `None`
  - Gold Results: `None`

---

### `q32` (hard): Calculate the month-over-month revenue growth rate for 2024.
- **Assigned Category**: `false_refusal`
- **Diagnosis**: Falsely refused answerable question: Failed to produce a valid SQL query after 3 self-correction attempts.
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
