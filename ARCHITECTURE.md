# Stock Equity Analysis System — Architecture

## Overview

A **7-section parallel LLM pipeline** that generates comprehensive equity research reports. Data flows from Screener.in → CSV extraction → LLM analysis → HTML composition → PDF export.

```
┌─────────────────────────────────────────────────────────────────────┐
│  WEB UI (Flask)                                                     │
│  ├─ Stock selection dropdown (NIFTY50)                             │
│  ├─ "Analyze" button → Background thread                           │
│  └─ Report viewer + PDF export button                              │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Data Loading (analysis_engine.py)                                  │
│  ├─ Load CSVs from static/{SYMBOL}/                                │
│  ├─ Trim to last 7 year-columns (token budget)                     │
│  └─ Format as strings for LLM input                                │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LangGraph 7-Section Pipeline (Parallel + Sequential)               │
│                                                                      │
│  Stage 1: Load Data (blocking)                                      │
│  ├─ balance_sheet.csv (7-year snapshot)                            │
│  ├─ cash_flow.csv (7-year snapshot)                                │
│  ├─ profit_and_loss_annual.csv (7-year: Sales, OPM%, Net Profit) │
│  ├─ quarterly_results.csv (6 quarters)                            │
│  ├─ growth_metrics.csv (CAGR, ROE/ROCE trends)                   │
│  ├─ key_metrics.csv (P/E, Book Value, current ROE, ROCE)         │
│  └─ ratios.csv (ROCE% year-wise, efficiency metrics)             │
│                                                                      │
│  Stage 2: 4 Parallel LLM Calls (concurrent)                        │
│  ├─ Company Overview (system + user prompt)                        │
│  ├─ Quantitative Analysis (all financial data)                     │
│  ├─ Qualitative Analysis (moat, mgmt, growth, risks)              │
│  └─ Shareholding Analysis (promoter/FII/DII patterns)             │
│                                                                      │
│  Stage 3: Merge Results → Investment Thesis (blocking)             │
│  └─ Synthesize 4 outputs into unified investment case             │
│                                                                      │
│  Stage 4: Valuation & Recommendation (blocking)                    │
│  └─ Fair value, rating (BUY/HOLD/SELL), target price              │
│                                                                      │
│  Stage 5: Conclusion (blocking)                                    │
│  └─ Bull/base/bear scenarios, key risks, guidance                 │
│                                                                      │
│  Stage 6: Executive Summary (blocking)                             │
│  └─ Not used in final output (legacy)                             │
│                                                                      │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  HTML Composition (comprehensive_prompt_new.py)                     │
│  ├─ Validate & clean LLM HTML output                               │
│  ├─ Extract recommendation (regex on valuation section)            │
│  ├─ Compose final report:                                          │
│  │  ├─ Header (stock, price, recommendation box with target)       │
│  │  ├─ 7 sections (CO, QA, QLA, SA, IT, VAL, CONC)               │
│  │  ├─ Compact CSS (13px font, 30px padding, 12-36px margins)    │
│  │  └─ Print-optimized (page-break-inside: avoid)                 │
│  └─ Return HTML string                                            │
│                                                                      │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PDF Export (app.py route /report/<symbol>/pdf)                     │
│  ├─ Launch Playwright Chromium                                      │
│  ├─ Render HTML to PDF (A4, 15mm margins, print_background=true)  │
│  ├─ Return file download (attachment; filename=...)               │
│  └─ Browser downloads PDF                                          │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Pipeline

### 1. Data Extraction (screener_data_extractor.py)

**Source**: Screener.in company pages (via Playwright → saved HTML)

**Extraction Process**:
```python
async fetch_and_save_screener_data(url):
  ├─ Launch Chromium browser
  ├─ Navigate to Screener URL
  ├─ Wait for dynamic content (5s)
  ├─ Scroll to load all sections (12 × 1200px)
  ├─ Save raw HTML + full page text
  └─ Extract + save 7 CSV files
```

**Output CSVs** (saved to `static/{SYMBOL}/`):

| File | Rows | Columns | Key Metrics |
|---|---|---|---|
| `key_metrics.csv` | 9 | 5 | Market Cap, P/E, ROE, ROCE, Div Yield |
| `profit_and_loss_annual.csv` | 12 | 14 | Sales, OPM%, Operating Profit, Net Profit, EPS, Dividend Payout% (10+ years) |
| `quarterly_results.csv` | 11 | 8 | Sales, Expenses, Operating Profit, OPM%, Net Profit, EPS (6 quarters) |
| `balance_sheet.csv` | 11 | 10 | Equity, Reserves, Borrowings, Deposits, Assets (10+ years) |
| `cash_flow.csv` | 5 | 10 | Operating, Investing, Financing, Net CF (10+ years) |
| `growth_metrics.csv` | 15 | 4 | CAGR (Sales/Profit/Stock Price), ROE/ROCE trends (10Y/5Y/3Y/1Y) |
| `ratios.csv` | 7 | 10 | **NEW**: ROCE% (year-wise), Debtor Days, Inventory Days, Days Payable, CCC, WCD (10+ years) |

**Key Improvements** (session 2):
- Extracts **Sales** (was missing)
- Extracts **Operating Profit** and **OPM%** (margin %) 
- Extracts **ROCE% year-wise** (was only snapshot before)
- Extracts efficiency ratios (Debtor/Inventory Days, CCC)

### 2. Data Loading (analysis_engine.py)

```python
def load_stock_data(stock_symbol):
  ├─ Read CSVs from static/{symbol}/
  ├─ Identify year-columns (regex: "Mar 2024", "TTM", etc.)
  ├─ Keep ALL metric-rows (rows = metrics, columns = years)
  ├─ Trim to last N year-columns (token budget):
  │  ├─ P&L, Balance Sheet, Cash Flow, Quarterly: last 7 years
  │  ├─ Ratios: last 7 years
  │  └─ Growth/Key Metrics: all (wide format, low token cost)
  └─ Return as formatted strings
```

**Rationale**: Earlier loader used `df.tail(5)` on metrics → dropped all sales/OPM rows. Fixed to keep metric-rows, trim year-columns instead.

### 3. LLM Pipeline (analysis_engine.py + prompts.py)

**LangGraph Workflow** (src/stock_analyzer/analysis_engine.py):

```
load_data (blocking)
  │
  ├─→ company_overview (parallel, 2 min)
  ├─→ quantitative_analysis (parallel, 2 min)
  ├─→ qualitative_analysis (parallel, 2 min)
  └─→ shareholding_analysis (parallel, 2 min)
       ↓ (merge all 4)
  investment_thesis (blocking, 1 min)
       ↓
  valuation_recommendation (blocking, 1 min)
       ↓
  conclusion (blocking, 1 min)
       ↓
  executive_summary (blocking, legacy, not used)

Total: ~8-10 minutes (4 parallel + 4 sequential sections)
```

**7 Section Prompts** (src/stock_analyzer/prompts.py):

Each prompt is **compact** (fit within 1 page; 3-15 lines of output):

1. **Company Overview**
   - Business snapshot (1 para)
   - Key metrics table (3 rows)
   - Recent developments (≤4 bullets)

2. **Quantitative Analysis**
   - P&L summary table (3 rows)
   - Key ratios table (5 ratios)
   - 5 analysis bullets

3. **Qualitative Analysis**
   - Moat bullets (≤5)
   - Management paragraph
   - Growth drivers bullets (≤5)
   - Risks table (3 rows)

4. **Shareholding Analysis**
   - Shareholding table (3 quarters, 3 categories)
   - 4 key observations

5. **Investment Thesis**
   - Core thesis paragraph
   - Growth catalysts table
   - Risk bullets (≤5)

6. **Valuation & Recommendation** ⭐
   - Fair value estimate (₹/share)
   - **Machine-parseable format**:
     ```html
     <p><strong>Recommendation: BUY</strong> | <strong>Target Price Range: ₹XXXX-XXXX</strong> | <strong>Upside: XX%</strong> | ...</p>
     ```

7. **Conclusion**
   - Bull/base/bear scenarios (table)
   - Key risks to monitor (≤5)
   - Investment guidance paragraph

**System Prompt** (applies to all 7 sections):
- "CONCISE, high-signal analysis"
- "Max 4-5 items per list"
- "Tables > paragraphs"
- "Latest 5 years focus"

**LLM Model Options**:
- **Claude 3.5 Sonnet** (recommended) — excellent financial reasoning
- **GPT-4** — alternative, similar quality

### 4. HTML Report Composition (comprehensive_prompt_new.py)

**Input**: 7 LLM responses (HTML fragments)

**Processing**:

```python
def generate_comprehensive_html_report(lzm_outputs):
  ├─ Validate & fix HTML structure
  │  ├─ Close unclosed <table>, <tr>, <td>
  │  ├─ Fix broken table rows
  │  └─ Strip common garbage tags
  │
  ├─ Extract recommendation from valuation section
  │  ├─ _extract_recommendation(valuation_html)
  │  ├─ Strip HTML tags → plain text
  │  ├─ Multi-pattern regex:
  │  │  ├─ Pattern 1: "Recommendation: BUY | Target Price..."
  │  │  └─ Fallback: Match standalone **STRONG BUY/BUY/HOLD/SELL/REDUCE**
  │  └─ Return dict: {recommendation, class, target_price_range, upside_downside}
  │
  ├─ Compose final HTML
  │  ├─ Header section
  │  │  ├─ Stock name & date
  │  │  └─ **Recommendation box** (3-column grid)
  │  │     ├─ Recommendation (colored: bullish/bearish/neutral)
  │  │     ├─ 12M Target Price
  │  │     └─ Upside/Downside %
  │  ├─ 7 Content sections (from LLM outputs)
  │  └─ Footer (disclaimer)
  │
  ├─ Apply compact CSS
  │  ├─ Font: 13px (was 14px)
  │  ├─ Header padding: 36px (was 50px)
  │  ├─ Section margins: 36px (was 50px)
  │  ├─ Table margins: 12px (was 20px)
  │  ├─ Line-heights: 1.5 (was 1.7)
  │  └─ List spacing: 4-8px (tight, no bloat)
  │
  └─ Return HTML string
```

**CSS Optimizations**:
- **Compact typography**: 13px font, 1.5 line-height
- **Tight spacing**: 30px content padding, 36px section margins, 12px table margins
- **Print-friendly**: `page-break-inside: avoid` on sections
- **Data visibility**: Tables only (no narrative paragraphs except intro)

**Result**: 8-10 page HTML (was 34 pages before compact refactor)

### 5. PDF Export (app.py)

**Route**: `GET /report/{symbol}/pdf`

```python
@app.route('/report/<stock_symbol>/pdf')
def export_pdf(stock_symbol):
  ├─ Fetch cached HTML report
  ├─ Launch Playwright Chromium
  ├─ Set page content to HTML
  ├─ Render to PDF
  │  ├─ Format: A4
  │  ├─ Margins: 15mm all
  │  ├─ print_background: true (colors/gradients preserved)
  │  └─ Size: ~3-5 MB
  └─ Return file download (attachment header)
```

**Frontend** (index.html + main.js):
- "📥 Export as PDF" button
- On click: `window.location.href = /report/{symbol}/pdf`
- Browser downloads as `{SYMBOL}_equity_analysis.pdf`

## Directory Structure

```
rtfm/
├── src/
│   ├── config.py                           # Global settings (LLM, logging)
│   ├── run.py                              # Flask app + arg parsing
│   │
│   ├── stock_analyzer/
│   │   ├── __init__.py
│   │   ├── app.py                          # Flask routes
│   │   │   ├─ GET  /                       # Serve index.html
│   │   │   ├─ GET  /api/stocks             # List NIFTY50 stocks
│   │   │   ├─ POST /api/analyze            # Start background analysis
│   │   │   ├─ GET  /api/status/{symbol}    # Poll status
│   │   │   ├─ GET  /api/results/{symbol}   # Get analysis results
│   │   │   ├─ GET  /report/{symbol}        # View HTML report
│   │   │   └─ GET  /report/{symbol}/pdf    # PDF download
│   │   │
│   │   ├── analysis_engine.py              # LangGraph 7-section pipeline
│   │   │   ├─ load_stock_data()            # CSV loader
│   │   │   ├─ _build_graph()               # LangGraph setup
│   │   │   ├─ _*_node()                     # 7 section functions + summary
│   │   │   └─ get_analysis_report()        # Main entry
│   │   │
│   │   ├── prompts.py                      # LLM prompts
│   │   │   ├─ STOCK_ANALYST_SYSTEM_PROMPT
│   │   │   ├─ COMPANY_OVERVIEW_PROMPT
│   │   │   ├─ QUANTITATIVE_ANALYSIS_PROMPT
│   │   │   ├─ QUALITATIVE_ANALYSIS_PROMPT
│   │   │   ├─ SHAREHOLDING_ANALYSIS_PROMPT
│   │   │   ├─ INVESTMENT_THESIS_PROMPT
│   │   │   ├─ VALUATION_AND_RECOMMENDATION_PROMPT  ⭐ (has machine-parseable format)
│   │   │   ├─ CONCLUSION_PROMPT
│   │   │   └─ __all__ (export list)
│   │   │
│   │   ├── comprehensive_prompt_new.py     # Report composition
│   │   │   ├─ validate_html()              # Clean LLM HTML
│   │   │   ├─ _extract_recommendation()    # Parse rec box
│   │   │   ├─ generate_comprehensive_html_report()
│   │   │   └─ CSS (compact styling)
│   │   │
│   │   └── report_generator.py             # (unused, legacy)
│   │
│   ├── utils/
│   │   ├── screener_data_extractor.py      # ⭐ Main data source
│   │   │   ├─ fetch_and_save_screener_data()  # Async Playwright scraper
│   │   │   ├─ extract_key_metrics()
│   │   │   ├─ extract_quarterly_results()
│   │   │   ├─ extract_profit_and_loss_annual()
│   │   │   ├─ extract_balance_sheet()
│   │   │   ├─ extract_cash_flow()
│   │   │   ├─ extract_growth_metrics()
│   │   │   ├─ extract_ratios()             # ⭐ NEW: ROCE% year-wise
│   │   │   ├─ regen_all_csvs()             # ⭐ NEW: Batch regen
│   │   │   └─ main() with --regen-all flag
│   │   │
│   │   └── helpers.py                      # pretty_print_dict, batch_list, truncate_text
│   │
│   ├── templates/
│   │   ├── index.html                      # Web UI
│   │   └── report_template.html            # (not used, report composed in Python)
│   │
│   └── static/
│       ├── css/
│       │   └── style.css                   # Web UI styles
│       ├── js/
│       │   └── main.js                     # Web UI logic + PDF export button
│       └── *NO STOCK DATA HERE*             (see static/ below)
│
├── static/                                 # ⭐ Main stock data directory
│   ├── NIFTY50.csv                         # Stock universe (51 stocks: 50 + 1 test)
│   ├── EQUITY_L.csv                        # Equity list (for reference)
│   ├── nifty50.csv                         # Alternative format
│   │
│   ├── ASIANPAINT/
│   │   ├─ key_metrics.csv
│   │   ├─ profit_and_loss_annual.csv       # ✓ Has Sales, OPM%, Operating Profit
│   │   ├─ quarterly_results.csv            # ✓ Has Sales, Operating Profit, OPM%
│   │   ├─ balance_sheet.csv
│   │   ├─ cash_flow.csv
│   │   ├─ growth_metrics.csv
│   │   ├─ ratios.csv                       # ✓ NEW: ROCE%, Debtor/Inventory Days, CCC
│   │   ├─ screener_page_content.html       # Saved raw HTML
│   │   ├─ screener_page_content.txt        # Saved raw text
│   │   └─ source_reference.csv
│   │
│   ├── HDFCBANK/
│   ├── INFY/
│   ├── TCS/
│   └── ... (51 stocks total)
│
├── llm_responses/                          # Cached LLM section outputs
│   ├── {SYMBOL}/
│   │   ├─ company_overview.txt
│   │   ├─ quantitative_analysis.txt
│   │   ├─ qualitative_analysis.txt
│   │   ├─ shareholding_analysis.txt
│   │   ├─ investment_thesis.txt
│   │   ├─ valuation_recommendation.txt     # ⭐ Contains extraction source
│   │   └─ conclusion.txt
│   └─ ... (for each analyzed stock)
│
├── ARCHITECTURE.md                         # This file
├── README.md                               # Quick start & usage
├── requirements.txt                        # Dependencies
├── pyproject.toml                          # Project config
├── run.py                                  # Entry point: python run.py --provider claude
│
└── tests/                                  # Test suite
    ├── __init__.py
    └── test_config.py
```

## Data Flow Summary

```
Stock Selection (Web UI)
         ↓
   Screener.in (live or cached HTML)
         ↓
   screener_data_extractor.py
   (Playwright scraper)
         ↓
   CSVs: static/{SYMBOL}/*.csv
   ├─ Key Metrics
   ├─ P&L Annual (Sales, OPM%, Net Profit)
   ├─ Quarterly Results
   ├─ Balance Sheet
   ├─ Cash Flow
   ├─ Growth Metrics
   └─ Ratios (ROCE% year-wise)
         ↓
   analysis_engine.load_stock_data()
   (Trim to 7-year columns)
         ↓
   LangGraph Pipeline
   (7 concurrent→sequential LLM calls)
         ↓
   7 HTML fragments
   (1 per section)
         ↓
   comprehensive_prompt_new.py
   (HTML validation + recommendation extraction)
         ↓
   Final HTML report
   (8-10 pages, compact CSS)
         ↓
   Browser OR Playwright.pdf export
```

## Key Design Decisions

| Decision | Rationale |
|---|---|
| **7 parallel → sequential sections** | Parallel = speed (4 min), sequential = context reuse (thesis depends on 4 analyses) |
| **Keep all metric-rows, trim year-columns** | Metrics = rows (Sales, OPM, Net Profit). Years = columns. Old `df.tail(5)` dropped metrics. |
| **Compact CSS** | 34-page verbose → 8-10 page actionable reports. Tighter spacing, smaller fonts, tables over prose. |
| **Machine-parseable rec format** | Valuation section outputs specific format so regex reliably extracts Recommendation, Target, Upside. |
| **Playwright for PDF** | No extra library (already used for scraping). Uses Chromium (reliable) vs. WeasyPrint (CSS gaps). |
| **Static CSV data** | Scraper runs once, CSVs cached. Fast iteration on prompts/pipeline without re-scraping.  |
| **Save LLM responses** | `llm_responses/{symbol}/*.txt` for debugging recommendation box issues, tweaking prompts. |

## Extending the System

### Add a New Stock
```bash
python src/utils/screener_data_extractor.py "https://www.screener.in/company/NEWSTOCK/"
```

### Regenerate All CSVs After Extractor Fix
```bash
python src/utils/screener_data_extractor.py --regen-all
```

### Adjust Report Compactness
Edit `comprehensive_prompt_new.py` CSS section:
- `font-size: 12px` (smaller)
- `padding: 20px` (tigher)
- `margin: 10px` (tighter)

### Tweak Prompts
Edit `src/stock_analyzer/prompts.py` section prompts, then regenerate or re-run analysis.

### Switch LLM Model
```bash
python run.py --provider openai  # Switches to GPT-4
```

Or edit `src/config.py` to change default model/provider.

## Performance Metrics

| Metric | Value |
|---|---|
| Data extraction per stock | 1-2 min (Playwright + parsing) |
| LLM pipeline total | 8-10 min (4 parallel 2min + 4 sequential 1min) |
| Report file size | ~50-80 KB HTML, ~3-5 MB PDF |
| Token usage per report | ~10K-15K tokens (compact prompts) |
| Cost per report (Claude) | ~$0.15-0.20 |
| Cost per report (GPT-4) | ~$0.30-0.50 |

## Troubleshooting

**Issue**: Missing ROCE% year-wise or Sales/OPM%

→ CSVs need regeneration after extractor fix:
  ```bash
  python src/utils/screener_data_extractor.py --regen-all
  ```

**Issue**: Recommendation box empty in HTML report

→ Check `llm_responses/{symbol}/valuation_recommendation.txt`

→ Ensure LLM output includes: `Recommendation: BUY | Target Price Range: ₹X-X | Upside: X%`

→ Regex fallback is in `_extract_recommendation()`

**Issue**: PDF export fails

→ Install Playwright Chromium:
  ```bash
  playwright install chromium
  ```

**Issue**: Report too long or too short

→ Adjust prompt word limits in `prompts.py`

→ Or adjust CSS padding/font-size in `comprehensive_prompt_new.py`
