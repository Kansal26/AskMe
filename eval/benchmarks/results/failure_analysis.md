# SQL Agent Failure Analysis Report (Prompt v3)

**Total Failing Questions (Lenient)**: 4 of 40 (Lenient Accuracy: 90.0% | Strict: 37.5%)  

## 1. Summary of Failure Categories

| Failure Category | Count | Percentage of Failures | Primary Root Cause |
| :--- | :---: | :---: | :--- |
| `false_refusal` | 2 | 50.0% | Model falsely claimed the data was missing for an answerable query. |
| `wrong_metric` | 1 | 25.0% | Generated SQL used an alternate aggregation or failed to adhere to corporate data dictionary formulas. |
| `ambiguity` | 1 | 25.0% | Question wording allows multiple valid interpretations or gold SQL requires arbitrary extra columns. |

## 2. Granular Breakdown of Every Failing Question

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
  - Gold Results: `[{'sku': 'SKU-FRA-0064', 'name': 'GlowBotanica Saffron & Cardamom Noir (Refill Pack)', 'ret_cnt': 23, 'avg_rating': 4.38}, {'sku': 'SKU-SKI-0141', 'name': 'DermaBloom Retinol 0.5% Night Recovery Oil (Original)', 'ret_cnt': 21, 'avg_rating': 3.88}, {'sku': 'SKU-SKI-0036', 'name': 'VelvetPetal Niacinamide 10% Blemish Toner (Refill Pack)', 'ret_cnt': 21, 'avg_rating': 4.33}]`

---

### `q31` (hard): What was the quarterly Average Order Value by channel in 2024?
- **Assigned Category**: `false_refusal`
- **Diagnosis**: Model refused answerable question.
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
- **Assigned Category**: `false_refusal`
- **Diagnosis**: Model refused answerable question.
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
