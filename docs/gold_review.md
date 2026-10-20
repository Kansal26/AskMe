# Benchmark Gold Queries Review & Ambiguity Audit

**Repository**: `AskMe` (`Ask-the-Business`)  
**Auditor**: Aditya Kansal  
**Date**: 2026-10-20  
**Purpose**: Document all 40 curated questions in `eval/benchmarks/gold_queries.json` with their exact business intent, gold SQL, and ambiguity risks for interview defense.

---

## 1. Easy Difficulty Tier (10 Questions)

### `q01`: Total Net Revenue
* **Question**: "What is our total net revenue?"
* **Intent**: Sum of completed transaction net revenue (`SUM(net_amount)`).
* **Gold SQL**: `SELECT ROUND(SUM(net_amount), 2) AS total_net_revenue FROM orders;`
* **Ambiguity Risk**: Low. Models without metric definitions often confuse `net_amount` with `gross_amount`.

### `q02`: Total Orders Count
* **Question**: "How many total orders have been placed?"
* **Intent**: Count of distinct transactions (`COUNT(DISTINCT order_id)`).
* **Gold SQL**: `SELECT COUNT(DISTINCT order_id) AS total_orders FROM orders;`
* **Ambiguity Risk**: Low. `orders` rows are line-items; naive `COUNT(*)` counts line items instead of distinct orders.

### `q03`: Product Count by Category
* **Question**: "How many products do we have in each category?"
* **Intent**: Count of SKUs per category sorted descending.
* **Gold SQL**: `SELECT category, COUNT(sku) AS product_count FROM products GROUP BY category ORDER BY product_count DESC;`
* **Ambiguity Risk**: Low. Standard aggregation.

### `q04`: Promotional Discounts Total
* **Question**: "What is the total discount amount given to customers?"
* **Intent**: Total monetary value of discounts granted across all orders.
* **Gold SQL**: `SELECT ROUND(SUM(discount_amount), 2) AS total_discounts FROM orders;`
* **Ambiguity Risk**: Low.

### `q05`: Overall Average Order Value (AOV)
* **Question**: "What is our overall Average Order Value (AOV)?"
* **Intent**: Total net revenue divided by distinct completed orders.
* **Gold SQL**: `SELECT ROUND(SUM(net_amount) * 1.0 / COUNT(DISTINCT order_id), 2) AS aov FROM orders;`
* **Ambiguity Risk**: Medium. If a model calculates `AVG(net_amount)`, it computes average line item value rather than corporate AOV.

### `q06`: Amazon Order Count
* **Question**: "How many orders were placed through Amazon?"
* **Intent**: Total line items fulfilled through the Amazon channel.
* **Gold SQL**: `SELECT COUNT(*) AS amazon_order_count FROM orders WHERE channel = 'Amazon';`
* **Ambiguity Risk**: Medium. Question asks for "orders" while SQL counts line items `COUNT(*)`.

### `q07`: Total Refund Amount Processed
* **Question**: "What is the total refund amount processed?"
* **Intent**: Sum of processed refunds in `returns` table.
* **Gold SQL**: `SELECT ROUND(SUM(refund_amount), 2) AS total_refunds FROM returns;`
* **Ambiguity Risk**: Low.

### `q08`: 5-Star Review Count
* **Question**: "How many 5-star reviews have we received?"
* **Intent**: Count of ratings equal to 5 in `reviews`.
* **Gold SQL**: `SELECT COUNT(*) AS five_star_count FROM reviews WHERE rating = 5;`
* **Ambiguity Risk**: Low.

### `q09`: Highest MRP Product
* **Question**: "Which product has the highest MRP?"
* **Intent**: Identify the top-priced SKU by Maximum Retail Price.
* **Gold SQL**: `SELECT name, brand, mrp FROM products ORDER BY mrp DESC LIMIT 1;`
* **Ambiguity Risk**: High. 
  1. `LIMIT 1` without deterministic tie-breaking produces arbitrary selection if multiple SKUs share the max price.
  2. Mandates `brand` in the SELECT clause even though the question only asks for the product.

### `q10`: Unique Customer Count
* **Question**: "How many unique customers have purchased from us?"
* **Intent**: Count of distinct `customer_id` values in `orders`.
* **Gold SQL**: `SELECT COUNT(DISTINCT customer_id) AS unique_customers FROM orders;`
* **Ambiguity Risk**: Low.

---

## 2. Medium Difficulty Tier (12 Questions)

### `q11`: Net Revenue by Channel
* **Question**: "What is the total net revenue broken down by sales channel?"
* **Intent**: Channel breakdown ranked descending by net revenue.
* **Gold SQL**: `SELECT channel, ROUND(SUM(net_amount), 2) AS channel_net_revenue FROM orders GROUP BY channel ORDER BY channel_net_revenue DESC;`
* **Ambiguity Risk**: Low.

### `q12`: AOV by City
* **Question**: "What is the Average Order Value (AOV) for each city?"
* **Intent**: AOV per destination delivery city ranked descending.
* **Gold SQL**: `SELECT city, ROUND(SUM(net_amount) * 1.0 / COUNT(DISTINCT order_id), 2) AS city_aov FROM orders GROUP BY city ORDER BY city_aov DESC;`
* **Ambiguity Risk**: Medium. Same grain risk as `q05` (`AVG(net_amount)` vs `SUM(net_amount) / COUNT(DISTINCT order_id)`).

### `q13`: Top 3 Brands by Revenue
* **Question**: "Who are the top 3 brands by net revenue?"
* **Intent**: Join `orders` with `products` to find the top 3 brands by net revenue.
* **Gold SQL**: `SELECT p.brand, ROUND(SUM(o.net_amount), 2) AS brand_revenue FROM orders o JOIN products p ON o.sku = p.sku GROUP BY p.brand ORDER BY brand_revenue DESC LIMIT 3;`
* **Ambiguity Risk**: Low. Standard join and aggregation.

### `q14`: Return Rate by Category
* **Question**: "What is the return rate percentage for each product category?"
* **Intent**: Ratio of returned orders to total orders per category.
* **Gold SQL**: `SELECT p.category, ROUND(COUNT(DISTINCT r.order_id) * 100.0 / COUNT(DISTINCT o.order_id), 2) AS return_rate_pct FROM orders o JOIN products p ON o.sku = p.sku LEFT JOIN returns r ON o.order_id = r.order_id GROUP BY p.category ORDER BY return_rate_pct DESC;`
* **Ambiguity Risk**: High. Returns are recorded at the `order_id` level, not line-item SKU level. An order containing items across multiple categories has its return attributed to all joined categories.

### `q15`: Monthly Net Revenue for 2024
* **Question**: "Show me monthly net revenue for 2024."
* **Intent**: Monthly net revenue time series for calendar year 2024.
* **Gold SQL**: `SELECT strftime(order_date, '%Y-%m') AS month, ROUND(SUM(net_amount), 2) AS monthly_revenue FROM orders WHERE strftime(order_date, '%Y') = '2024' GROUP BY month ORDER BY month ASC;`
* **Ambiguity Risk**: Medium. String date extraction vs date_trunc; models may format month as integer `1..12` instead of `'2024-01'`.

### `q16`: Frequent Return Reasons
* **Question**: "What are the most frequent return reasons and their counts?"
* **Intent**: Distribution of return causes ranked descending.
* **Gold SQL**: `SELECT reason, COUNT(*) AS count FROM returns GROUP BY reason ORDER BY count DESC;`
* **Ambiguity Risk**: Low.

### `q17`: Average Customer Rating by Brand
* **Question**: "What is the average customer rating for each brand?"
* **Intent**: Average review score per product brand.
* **Gold SQL (Updated)**: `SELECT p.brand, ROUND(AVG(r.rating), 2) AS avg_rating FROM products p JOIN reviews r ON p.sku = r.sku GROUP BY p.brand ORDER BY avg_rating DESC;`
* **Original Gold SQL**: `SELECT p.brand, ROUND(AVG(r.rating), 2) AS avg_rating, COUNT(r.review_id) AS review_count FROM products p JOIN reviews r ON p.sku = r.sku GROUP BY p.brand ORDER BY avg_rating DESC;`
* **Reason for Change**: The user question asks: "What is the average customer rating for each brand?". The original Gold SQL arbitrarily included `COUNT(r.review_id) AS review_count`, penalizing correct agents that projected only the requested brand and average rating. Removed `COUNT(r.review_id)` to accurately reflect the business prompt.
* **Ambiguity Risk**: Low.

### `q18`: Total Units Sold by Category
* **Question**: "How many total units were sold in each category?"
* **Intent**: Sum of purchase quantities per category.
* **Gold SQL**: `SELECT p.category, SUM(o.quantity) AS total_units FROM orders o JOIN products p ON o.sku = p.sku GROUP BY p.category ORDER BY total_units DESC;`
* **Ambiguity Risk**: Low.

### `q19`: Combined Net Revenue from Mumbai and Delhi
* **Question**: "What is the combined net revenue from Mumbai and Delhi?"
* **Intent**: Revenue generated in Mumbai and Delhi.
* **Gold SQL**: `SELECT city, ROUND(SUM(net_amount), 2) AS revenue FROM orders WHERE city IN ('Mumbai', 'Delhi') GROUP BY city ORDER BY revenue DESC;`
* **Ambiguity Risk**: High. "Combined revenue" naturally implies a single aggregate scalar sum (`SUM(net_amount)` across both cities), but the gold SQL groups by city and returns two separate rows.

### `q20`: Average Discount Percentage by Channel
* **Question**: "What is the average discount percentage by channel?"
* **Intent**: Average line item discount percentage (`discount_amount / gross_amount * 100`).
* **Gold SQL**: `SELECT channel, ROUND(AVG(discount_amount * 100.0 / gross_amount), 2) AS avg_discount_pct FROM orders GROUP BY channel ORDER BY avg_discount_pct DESC;`
* **Ambiguity Risk**: Medium. Can be interpreted as average of line-item percentages vs total channel discount divided by total gross sales (`SUM(discount) / SUM(gross)`).

### `q21`: Large QuickCommerce Orders
* **Question**: "How many orders had 3 or more units in QuickCommerce channels?"
* **Intent**: Count of high-unit transactions in Blinkit/Zepto channels.
* **Gold SQL**: `SELECT COUNT(*) AS large_quickcommerce_orders FROM orders WHERE channel IN ('QuickCommerce-Blinkit', 'QuickCommerce-Zepto') AND quantity >= 3;`
* **Ambiguity Risk**: Medium. Uses `COUNT(*)` (counting line-item records) rather than `COUNT(DISTINCT order_id)`.

### `q22`: Difference Between Gross and Net Revenue
* **Question**: "What is the difference between our gross revenue and net revenue?"
* **Intent**: Total discount impact between gross and net sales.
* **Gold SQL**: `SELECT ROUND(SUM(gross_amount), 2) AS gross_revenue, ROUND(SUM(net_amount), 2) AS net_revenue, ROUND(SUM(gross_amount - net_amount), 2) AS total_discount_deductions FROM orders;`
* **Ambiguity Risk**: High. Returns 3 separate columns instead of just the requested difference scalar.

---

## 3. Hard Difficulty Tier (10 Questions)

### `q23`: Repeat Customer Rate Percentage
* **Question**: "What is our overall repeat customer rate percentage?"
* **Intent**: Percentage of distinct customers with 2 or more orders.
* **Gold SQL**: `WITH cust_orders AS (SELECT customer_id, COUNT(DISTINCT order_id) AS order_cnt FROM orders GROUP BY customer_id) SELECT ROUND(COUNT(CASE WHEN order_cnt >= 2 THEN 1 END) * 100.0 / COUNT(*), 2) AS repeat_customer_rate_pct FROM cust_orders;`
* **Ambiguity Risk**: Low. Formulated in accordance with the corporate data dictionary.

### `q24`: Top-Selling SKU by Category
* **Question**: "What is the top-selling SKU by net revenue in each product category?"
* **Intent**: Window partition rank 1 SKU per category.
* **Gold SQL**: `WITH sku_rev AS (SELECT p.category, o.sku, p.name, ROUND(SUM(o.net_amount), 2) AS revenue, ROW_NUMBER() OVER (PARTITION BY p.category ORDER BY SUM(o.net_amount) DESC) AS rank FROM orders o JOIN products p ON o.sku = p.sku GROUP BY p.category, o.sku, p.name) SELECT category, sku, name, revenue FROM sku_rev WHERE rank = 1 ORDER BY revenue DESC;`
* **Ambiguity Risk**: Medium. Tie-breaking across top SKUs using `ROW_NUMBER()` vs `RANK()`.

### `q25`: Return Rate Percentage by Channel
* **Question**: "What is the return rate percentage for each sales channel?"
* **Intent**: Proportion of orders returned per channel.
* **Gold SQL**: `SELECT o.channel, ROUND(COUNT(DISTINCT r.order_id) * 100.0 / COUNT(DISTINCT o.order_id), 2) AS return_rate_pct FROM orders o LEFT JOIN returns r ON o.order_id = r.order_id GROUP BY o.channel ORDER BY return_rate_pct DESC;`
* **Ambiguity Risk**: Low.

### `q26`: Cumulative Running Monthly Revenue for 2023
* **Question**: "Show the cumulative running monthly net revenue for 2023."
* **Intent**: Monthly running sum window function.
* **Gold SQL**: `WITH monthly AS (SELECT strftime(order_date, '%Y-%m') AS month, SUM(net_amount) AS revenue FROM orders WHERE strftime(order_date, '%Y') = '2023' GROUP BY month) SELECT month, ROUND(revenue, 2) AS monthly_revenue, ROUND(SUM(revenue) OVER (ORDER BY month), 2) AS cumulative_revenue FROM monthly ORDER BY month;`
* **Ambiguity Risk**: Low.

### `q27`: High-Value Customers (Spend > 15K INR)
* **Question**: "How many high-value customers have spent more than 15,000 INR in total?"
* **Intent**: Aggregated customer spend exceeding 15,000 INR threshold.
* **Gold SQL**: `WITH customer_spend AS (SELECT customer_id, SUM(net_amount) AS total_spend FROM orders GROUP BY customer_id) SELECT COUNT(*) AS high_value_customer_count FROM customer_spend WHERE total_spend > 15000;`
* **Ambiguity Risk**: Low.

### `q28`: Brand with Highest Return Rate
* **Question**: "Which brand has the highest return rate percentage?"
* **Intent**: Top 1 brand by return rate percentage.
* **Gold SQL**: `SELECT p.brand, ROUND(COUNT(DISTINCT r.order_id) * 100.0 / COUNT(DISTINCT o.order_id), 2) AS brand_return_rate FROM orders o JOIN products p ON o.sku = p.sku LEFT JOIN returns r ON o.order_id = r.order_id GROUP BY p.brand ORDER BY brand_return_rate DESC LIMIT 1;`
* **Ambiguity Risk**: High. Same multi-item order join attribution issue as `q14`, plus `LIMIT 1` tie-breaking.

### `q29`: Average Review Rating of Top 5 Most Returned Products
* **Question**: "What is the average review rating of our top 5 most returned products?"
* **Intent**: Join reviews with top 5 returned SKUs.
* **Gold SQL**: `WITH top_returned AS (SELECT o.sku, COUNT(r.return_id) AS ret_cnt FROM orders o JOIN returns r ON o.order_id = r.order_id GROUP BY o.sku ORDER BY ret_cnt DESC LIMIT 5) SELECT tr.sku, p.name, tr.ret_cnt, ROUND(AVG(rev.rating), 2) AS avg_rating FROM top_returned tr JOIN products p ON tr.sku = p.sku LEFT JOIN reviews rev ON tr.sku = rev.sku GROUP BY tr.sku, p.name, tr.ret_cnt ORDER BY tr.ret_cnt DESC;`
* **Ambiguity Risk**: High. Mandates `sku, name, ret_cnt, avg_rating` output columns. A query returning just `name, avg_rating` fails evaluation.

### `q30`: Top 5 Frequent Customers
* **Question**: "List our top 5 most frequent customers with their order count and total spend."
* **Intent**: Top 5 customers ordered by distinct order count and net spend.
* **Gold SQL**: `SELECT customer_id, COUNT(DISTINCT order_id) AS total_orders, ROUND(SUM(net_amount), 2) AS total_spend FROM orders GROUP BY customer_id ORDER BY total_orders DESC, total_spend DESC LIMIT 5;`
* **Ambiguity Risk**: Low.

### `q31`: Quarterly AOV by Channel
* **Question**: "What was the quarterly Average Order Value by channel in 2024?"
* **Intent**: Group by channel and quarter.
* **Gold SQL (Updated)**: `SELECT channel, year(order_date) || '-Q' || quarter(order_date) AS quarter, ROUND(SUM(net_amount) * 1.0 / COUNT(DISTINCT order_id), 2) AS aov FROM orders WHERE year(order_date) = 2024 GROUP BY channel, quarter ORDER BY channel, quarter;`
* **Original Gold SQL**: `SELECT channel, strftime(order_date, '%Y-Q') || ((CAST(strftime(order_date, '%m') AS INTEGER) - 1) / 3 + 1) AS quarter, ROUND(SUM(net_amount) * 1.0 / COUNT(DISTINCT order_id), 2) AS aov FROM orders WHERE strftime(order_date, '%Y') = '2024' GROUP BY channel, quarter ORDER BY channel, quarter;`
* **Reason for Change**: Critical DuckDB mathematical bug in original gold SQL. In DuckDB, `/` performs floating-point division; dividing integer months by `3` produced non-integer quarter strings such as `'2024-Q1.3333333333333333'` and `'2024-Q1.6666666666666665'`, creating 12 pseudo-month groups rather than 4 quarters. Replaced with standard canonical DuckDB `quarter(order_date)` and `year(order_date)`.
* **Ambiguity Risk**: Low.

### `q32`: Month-over-Month Revenue Growth Rate
* **Question**: "Calculate the month-over-month revenue growth rate for 2024."
* **Intent**: `(revenue - LAG(revenue)) / LAG(revenue) * 100` window function.
* **Gold SQL**: `WITH m_rev AS (SELECT strftime(order_date, '%Y-%m') AS month, SUM(net_amount) AS revenue FROM orders WHERE strftime(order_date, '%Y') = '2024' GROUP BY month) SELECT month, ROUND(revenue, 2) AS revenue, ROUND((revenue - LAG(revenue) OVER (ORDER BY month)) * 100.0 / LAG(revenue) OVER (ORDER BY month), 2) AS mom_growth_pct FROM m_rev ORDER BY month;`
* **Ambiguity Risk**: Medium. First month (Jan 2024) has NULL growth because the WHERE clause filtered out Dec 2023.

---

## 4. Unanswerable Refusal Tier (8 Questions)

### `q33`: Customer Acquisition Cost (CAC)
* **Question**: "What was our customer acquisition cost (CAC) for Instagram marketing campaigns in 2024?"
* **Intent**: Must refuse; ad marketing spend is not tracked in relational schema.
* **Expected Refusal**: `true` | **Ambiguity Risk**: None.

### `q34`: Orders Shipped to London and Paris
* **Question**: "How many orders were shipped to customers in London and Paris?"
* **Intent**: Must refuse; company only operates in India (12 Indian cities).
* **Expected Refusal**: `true`
* **Ambiguity Risk**: High. Because `city` exists in `orders`, models often execute `WHERE city IN ('London', 'Paris')` which returns `0`, rather than recognizing the cities are outside corporate scope.

### `q35`: Warehouse Inventory Stock
* **Question**: "What is the current remaining warehouse inventory stock for SKU-SKI-0001?"
* **Intent**: Must refuse; warehouse physical stock is not tracked.
* **Expected Refusal**: `true` | **Ambiguity Risk**: None.

### `q36`: Competitor Prices
* **Question**: "What are our competitor's prices for hyaluronic acid serum on Nykaa?"
* **Intent**: Must refuse; competitor external pricing is not tracked.
* **Expected Refusal**: `true` | **Ambiguity Risk**: None.

### `q37`: Delivery Time in Minutes
* **Question**: "What was the average delivery time in minutes for QuickCommerce-Blinkit orders?"
* **Intent**: Must refuse; fulfillment duration in minutes is not tracked.
* **Expected Refusal**: `true` | **Ambiguity Risk**: None.

### `q38`: Employee Salary
* **Question**: "What is the average salary of employees in our digital marketing department?"
* **Intent**: Must refuse; HR / payroll data is not in consumer goods schema.
* **Expected Refusal**: `true` | **Ambiguity Risk**: None.

### `q39`: Raw Material Suppliers
* **Question**: "Which supplier provided the organic rosemary oil for our haircare line?"
* **Intent**: Must refuse; procurement vendors are not tracked.
* **Expected Refusal**: `true` | **Ambiguity Risk**: None.

### `q40`: Legal Warranty Clauses
* **Question**: "What is the legal warranty return policy clause for opened cosmetics?"
* **Intent**: Must refuse; legal contract text is not stored in relational tables.
* **Expected Refusal**: `true` | **Ambiguity Risk**: None.

---

## 5. Stage 2b Audit of Disputed Queries (`q09`, `q17`, `q24`, `q26`, `q31`, `q32`)

Below is the definitive, honest audit of the 6 disputed benchmark queries, detailing whether the agent or the gold standard was at fault, and recording the written justification for any gold SQL changes:

| Query ID | Question | Verdict | Fault Attribution | Action Taken & Written Justification |
| :--- | :--- | :--- | :--- | :--- |
| **`q09`** | Which product has the highest MRP? | **Gold SQL Correct** | **Neither** (Comparator Sensitivity). Agent returned `sku, name, brand, category, mrp` while Gold returned `name, brand, mrp`. | **No Change to Gold SQL**. The question asks for the product; returning extra descriptive columns (`sku`, `category`) is helpful rather than incorrect. Under the new lenient comparator (evaluating only columns present in Gold), the agent passes cleanly. |
| **`q17`** | What is the average customer rating for each brand? | **Gold SQL Wrong** | **Gold Standard Error**. Gold SQL arbitrarily included `COUNT(r.review_id) AS review_count`, which was never requested in the question prompt. | **Changed Gold SQL**. Removed `COUNT(r.review_id) AS review_count`. New Gold SQL: `SELECT p.brand, ROUND(AVG(r.rating), 2) AS avg_rating FROM products p JOIN reviews r ON p.sku = r.sku GROUP BY p.brand ORDER BY avg_rating DESC;`. |
| **`q24`** | What is the top-selling SKU by net revenue in each product category? | **Gold SQL Correct** | **Agent Incomplete**. Agent projected `category, sku, net_rev` but omitted product `name` from the projection. | **No Change to Gold SQL**. Including product `name` alongside `sku` in a business ranking is standard practice. The agent legitimately failed strict evaluation for omitting `name`. |
| **`q26`** | Show the cumulative running monthly net revenue for 2023. | **Gold SQL Correct** | **Neither** (Type Formatting). Agent used DuckDB native `DATE_TRUNC('month', order_date)` returning a `datetime.date(2023, 1, 1)` object, while Gold used `strftime('%Y-%m')` returning string `'2023-01'`. The numeric sums were identical to the cent. | **No Change to Gold SQL**. Gold SQL is valid. The lenient comparator's date normalizer aligns date objects with `'YYYY-MM'` strings, allowing semantic equivalence. |
| **`q31`** | What was the quarterly Average Order Value by channel in 2024? | **Gold SQL Wrong** | **Gold Standard Error (Critical DuckDB Math Bug)**. The original Gold query used `/ 3` in DuckDB: `strftime(order_date, '%Y-Q') || ((CAST(strftime(order_date, '%m') AS INTEGER) - 1) / 3 + 1)`. In DuckDB, `/` performs floating-point division, producing decimal quarter names like `'2024-Q1.3333333333333333'` and `'2024-Q1.6666666666666665'`. It grouped orders into 12 pseudo-months rather than 4 quarters! | **Changed Gold SQL**. Updated to use canonical DuckDB functions: `SELECT channel, year(order_date) \|\| '-Q' \|\| quarter(order_date) AS quarter, ROUND(SUM(net_amount) * 1.0 / COUNT(DISTINCT order_id), 2) AS aov FROM orders WHERE year(order_date) = 2024 GROUP BY channel, quarter ORDER BY channel, quarter;`. |
| **`q32`** | Calculate the month-over-month revenue growth rate for 2024. | **Gold SQL Correct** | **Model Dialect Gap**. Agent struggled with DuckDB window syntax `LAG(revenue) OVER (ORDER BY month)` when filtering by year. | **No Change to Gold SQL**. Gold SQL correctly expresses the window function calculation. Prompt v3 has been updated with general DuckDB window dialect instructions. |
