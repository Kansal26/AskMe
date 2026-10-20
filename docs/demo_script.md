# Ask-the-Business: 2-Minute Portfolio Video Demo Script

**Role**: Analytics & AI Engineer Intern (Consumer Goods / E-Commerce)  
**Presenter**: Aditya Kansal  
**Target Duration**: 120 seconds (2 minutes)  

---

## Timeline & Step-by-Step Walkthrough

### 0:00 - 0:20 | Introduction & The Problem
* **Visual**: Show Streamlit app landing page with the **Synthetic Data Disclaimer** banner.
* **Talking Points**:
  > "Hi, I'm Aditya. Today I'm demonstrating **Ask-the-Business**, an end-to-end data pipeline built for consumer-goods analytics. 
  > In enterprise analytics, the two biggest risks with AI are: LLMs hallucinating data alterations during cleaning, and LLMs generating insecure or incorrect SQL for business metrics. 
  > I built this system around a strict architectural thesis: **The AI proposes, deterministic code executes, and the human approves**."

---

### 0:20 - 0:50 | Tab 1: Human-in-the-Loop Data Cleaning
* **Visual**: 
  1. Click **Tab 1: Data Cleaning**.
  2. Select `orders` table. Show the instant statistical profile cards (highlighting **487 Ambiguous Dates**, **503 Duplicates**, and **2,535 Dirty Numerics**).
  3. Show the **Ambiguous Date Format Guard** warning callout (`03/04/2024`).
  4. Show the proposed cleaning plan with step toggles.
  5. Click **Apply Approved Steps**. Show the generated audit log and the downloadable Python replay script.
* **Talking Points**:
  > "In Tab 1, we ingest raw, messy e-commerce data. Our Pandas profiler flags duplicate clones, currency formatting, and critically—ambiguous dates like `03/04/2024` where month and day are both under 12. 
  > Instead of guessing or letting an LLM rewrite values, our engine validates steps against an 8-operation whitelist. 
  > The operator can review and toggle steps. Notice that monetary amounts and IDs are guarded against imputation. 
  > When I click 'Apply', deterministic code executes, producing an audit log, an exportable Python replay script, and loading clean data directly into DuckDB."

---

### 0:50 - 1:30 | Tab 2: Natural Language SQL Agent & Governance Citations
* **Visual**:
  1. Switch to **Tab 2: Ask the Business**.
  2. Click the quick example: `"What is our total net revenue broken down by sales channel?"`
  3. Click **Ask Question**.
  4. Show the result: Natural language answer, the **`[Net Revenue]`** citation pill, the collapsible verified SQL query, and the interactive Plotly bar chart.
  5. Next, click an unanswerable question: `"What was our customer acquisition cost (CAC) for Instagram marketing campaigns in 2024?"`
  6. Show the amber **Data Governance Refusal Card**.
* **Talking Points**:
  > "In Tab 2, business users can query the data in plain English. 
  > Behind the scenes, our agent queries DuckDB through an MCP tool interface locked in read-only mode with external file access physically disabled. 
  > Queries are validated by `sqlglot` to enforce single SELECT statements. 
  > When we ask for revenue by channel, the agent retrieves the official metric formula—`SUM(net_amount)` rather than gross sales—cites the definition, runs the query, and renders an interactive Plotly chart.
  > If a user asks for data outside our schema, like Customer Acquisition Cost, the agent doesn't hallucinate; it returns a polite governance refusal."

---

### 1:30 - 2:00 | Rigorous Evaluation & Production Wrap-Up
* **Visual**: Show the evaluation benchmark table in the terminal or README.
* **Talking Points**:
  > "To validate this system scientifically, I built real evaluations:
  > In our data cleaning benchmark against 16,000+ ground-truth corruptions, our targeted canonical mapping achieved a **0.00% False-Fix Rate**, ensuring zero valid customer data was damaged. 
  > In our SQL agent benchmark across 40 curated questions, adding schema and metric governance improved execution accuracy significantly while maintaining 100% precision on refusals.
  > The full project is containerized with Docker, verifiable via the MCP Inspector, and open-source on my GitHub. Thank you!"

---

## Practice Tips for Recording
1. **Resolution**: Record at 1080p (1920x1080) with 125% browser zoom for crisp table readability.
2. **Audio**: Use a dedicated microphone with noise suppression.
3. **Pacing**: Speak at a steady, confident pace; pause briefly when clicking tabs to allow the viewer to absorb the UI.
