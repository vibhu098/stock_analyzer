# Stock Equity Analysis System

An AI-powered equity research platform that generates comprehensive financial analysis reports for Indian stocks, powered by LLMs (Claude or OpenAI).

## Features

- **Automated Data Extraction**: Scrapes Screener.in for financial data (P&L, balance sheet, cash flows, ratios)
- **7-Section Analysis**: Parallel LLM pipeline analyzing company overview, quantitative metrics, qualitative factors, shareholding, investment thesis, valuation, and conclusion
- **Compact Reports**: Auto-generated 8-10 page HTML equity reports with recommendations
- **PDF Export**: Download reports as professionally formatted PDFs
- **Web Interface**: Flask app for stock selection and report generation

## Quick Start

### 1. Prerequisites

- **Python 3.14+** with venv
- **LLM API Key** (Claude via Anthropic or OpenAI)
- **Playwright** (for browser automation and PDF rendering)

### 2. Setup

```bash
cd "/Users/macos/projects/coding challenges/rtfm"
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Configuration

Copy and edit the configuration:

```bash
cp .env.example .env
```

Then set in `.env`:

```env
LLM_PROVIDER=claude          # or 'openai'
ANTHROPIC_API_KEY=sk-ant-... # if using Claude
OPENAI_API_KEY=sk-...        # if using OpenAI
LOG_LEVEL=INFO
```

### 5a. Extract NIFTY 50 Stock Data (First Time Setup)

```bash
python src/utils/screener_data_extractor.py --regen-all
```

Or extract individual stocks:

```bash
python src/utils/screener_data_extractor.py "https://www.screener.in/company/INFY/"
python src/utils/screener_data_extractor.py "https://www.screener.in/company/TCS/"
```

Data is saved to `static/{STOCK_SYMBOL}/` with:
- `key_metrics.csv` — Market cap, P/E, ROE, ROCE
- `profit_and_loss_annual.csv` — 10+ years of P&L, Sales, OPM%, Net Profit
- `quarterly_results.csv` — Last 6 quarters
- `balance_sheet.csv` — Assets, liabilities, equity
- `cash_flow.csv` — Operating, investing, financing activities
- `growth_metrics.csv` — CAGR, ROE/ROCE trends (10Y/5Y/3Y/1Y)
- `ratios.csv` — ROCE%, Debtor Days, Inventory Days, Cash Conversion Cycle (year-wise)

### 5b. Run Web Interface

```bash
python run.py --provider claude  # or 'openai'
```

Then open: http://localhost:5000

**Steps:**
1. Select a stock from the dropdown
2. Click "Analyze Stock" 
3. Wait for LLM pipeline (2-3 minutes for 7 sections in parallel)
4. View HTML report in browser
5. Click "📥 Export as PDF" to download

### 6. Run Headless (CLI)

Generate a report directly:

```bash
python -c "
from src.stock_analyzer.analysis_engine import StockAnalysisEngine
engine = StockAnalysisEngine(llm_provider='claude')
report = engine.get_analysis_report('ASIANPAINT')
with open('ASIANPAINT_report.html', 'w') as f:
    f.write(report['final_report'])
print('Report saved to ASIANPAINT_report.html')
"
```

## Project Structure

```
rtfm/
├── src/
│   ├── config.py                           # Settings & LLM config
│   ├── run.py                              # Flask app entry
│   ├── stock_analyzer/
│   │   ├── app.py                          # Flask routes + PDF export
│   │   ├── analysis_engine.py              # LangGraph 7-section pipeline
│   │   ├── prompts.py                      # LLM system & section prompts
│   │   ├── comprehensive_prompt_new.py     # HTML report composition
│   │   └── report_generator.py             # Report formatting
│   ├── utils/
│   │   ├── screener_data_extractor.py      # Data scraping from Screener.in
│   │   └── helpers.py                      # Utility functions
│   ├── templates/
│   │   ├── index.html                      # Web UI
│   │   └── report_template.html            # Report HTML template
│   └── static/
│       ├── css/ & js/                      # Frontend assets
│       ├── NIFTY50.csv                     # Nifty 50 list
│       └── {STOCK}/                        # Stock data CSVs
├── static/                                 # Main data directory
│   ├── ASIANPAINT/
│   ├── HDFCBANK/
│   ├── INFY/
│   └── ... (50+ stocks)
├── llm_responses/                          # Cached LLM section outputs
├── ARCHITECTURE.md                         # System design
├── README.md                               # This file
├── requirements.txt                        # Python packages
├── pyproject.toml                          # Project config
└── run.py                                  # Main entry point
```

## System Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system design, data flow, and pipeline stages.

## Data Sources

**Screener.in** — Comprehensive Indian equity data including:
- Annual P&L (10+ years)
- Balance sheet (10+ years)
- Cash flows (10+ years)  
- Quarterly results (6 quarters)
- Key ratios (ROCE%, efficiency metrics year-wise)
- Growth metrics (CAGR, ROE/ROCE trends)
- Shareholding patterns

## LLM Models

**Claude** (recommended):
```bash
python run.py --provider claude
```
Uses Claude 3.5 Sonnet — excellent for financial analysis & report writing.

**OpenAI**:
```bash
python run.py --provider openai
```
Uses GPT-4 — alternative with similar quality.

## Report Output

Each report includes:

1. **Company Overview** — Business snapshot, key metrics, recent developments
2. **Quantitative Analysis** — P&L trends, ratios, ROE/ROCE year-wise, efficiency metrics
3. **Qualitative Analysis** — Moat, management, growth drivers, risks
4. **Shareholding Analysis** — Promoter/FII/DII patterns
5. **Investment Thesis** — Core thesis, catalysts, risks
6. **Valuation & Recommendation** — Fair value estimate, rating (BUY/HOLD/SELL), target price, upside
7. **Conclusion** — Bull/base/bear scenarios, key risks, investment guidance

**Format**: HTML (browser-viewable) or PDF (downloadable)

## Configuration

### Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `claude` | LLM to use (claude or openai) |
| `ANTHROPIC_API_KEY` | - | Claude API key (required if provider=claude) |
| `OPENAI_API_KEY` | - | OpenAI API key (required if provider=openai) |
| `LOG_LEVEL` | `INFO` | Logging verbosity (DEBUG/INFO/WARNING/ERROR) |

### Advanced: Stock Metadata

Edit `static/NIFTY50.csv` to add/remove stocks from the web UI list:

```csv
Symbol,Company Name,Sector
INFY,Infosys,Technology
TCS,Tata Consultancy Services,Technology
...
```

## Troubleshooting

### Report has missing details

CSVs may need regeneration if extractor logic was updated:

```bash
python src/utils/screener_data_extractor.py --regen-all
```

### PDF export fails

Ensure Playwright is installed with Chromium:

```bash
playwright install chromium
```

### LLM API errors

Check:
1. API key set in `.env`
2. Account has credits
3. Rate limits not exceeded

## Development

### Run Tests

```bash
pytest tests/
```

### Debug Mode

Set in code:

```python
engine = StockAnalysisEngine(llm_provider='claude', debug_mode=True)
```

Prompts will be printed without making API calls.

### Regenerate Data

After scraper fixes:

```bash
python src/utils/screener_data_extractor.py --regen-all
```

## License

Proprietary. See LICENSE for details.

## Support

For issues or questions, check:
- [ARCHITECTURE.md](ARCHITECTURE.md) — System design details
- `llm_responses/` — Cached LLM outputs for debugging
- Console logs with `LOG_LEVEL=DEBUG`
- `DEBUG`: Debug mode (default: False)

## Troubleshooting

### Redis Connection Error

Ensure Redis is running:
```bash
redis-cli ping
```

Should return `PONG`.

### OpenAI API Error

1. Verify your API key is correct in `.env`
2. Check your account has credits
3. Ensure the model name is correct

### Import Errors

Make sure you're in the virtual environment:
```bash
source venv/bin/activate
```

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
