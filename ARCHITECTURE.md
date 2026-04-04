# Stock Analyzer - Architecture

## Project Structure

```
stock_annalyzer/
├── src/
│   ├── analysis/                    # Single Stock Analysis Engine
│   │   ├── __init__.py
│   │   ├── analysis_engine.py       # LangGraph-based analysis workflow
│   │   ├── prompts.py               # LLM prompts for each analysis section
│   │   └── comprehensive_prompt_new.py  # HTML report generation
│   │
│   ├── embeddings/                  # Vector Storage & Embedding Management
│   │   ├── __init__.py
│   │   ├── analysis_embedding_store.py    # Q&A embeddings on analysis reports
│   │   └── screener_embedding_store.py    # Cross-stock search embeddings
│   │
│   ├── chat/                        # Chat Interfaces
│   │   ├── __init__.py
│   │   ├── analysis_chat.py         # Single-stock Q&A chat
│   │   └── multi_stock_chat.py      # Cross-stock comparison chat
│   │
│   ├── data/                        # Data Extraction & Processing
│   │   ├── __init__.py
│   │   ├── screener_data_extractor.py    # Fetch & extract from Screener.in
│   │   ├── csv_cleaner.py           # Data validation & cleaning
│   │   ├── csv_data_formatter.py    # Format for LLM consumption
│   │   └── daily_data_fetcher.py    # Real-time data integration
│   │
│   ├── llm/                         # Language Model Management
│   │   ├── __init__.py
│   │   └── llm_manager.py           # Provider selection (Claude/OpenAI)
│   │
│   ├── api/                         # REST API & Web Interface
│   │   ├── __init__.py
│   │   └── app.py                   # Flask application & routes
│   │
│   ├── common/                      # Shared Utilities
│   │   ├── __init__.py
│   │   ├── config.py                # Configuration & settings
│   │   ├── cache_manager.py         # Analysis result caching
│   │   ├── helpers.py               # Utility functions
│   │   ├── debug_logger.py          # Prompt & response logging
│   │   └── realtime_data_integration.py  # Market data integration
│   │
│   ├── static/                      # Stock Financial Data (CSV)
│   │   └── {STOCK}/
│   │       ├── key_metrics.csv
│   │       ├── quarterly_results.csv
│   │       ├── profit_and_loss_annual.csv
│   │       ├── balance_sheet.csv
│   │       ├── cash_flow.csv
│   │       ├── growth_metrics.csv
│   │       ├── ratios.csv
│   │       └── screener_page_content.{html,txt}
│   │
│   ├── templates/                   # HTML Templates
│   │   └── index.html               # Web UI
│   │
│   ├── run.py                       # Entry point for Flask server
│   │
│   ├── __init__.py
│   └── config.py (copied to common/)
│
├── embeddings/screener/             # Vector Indices
│   └── {STOCK}/                     # Per-stock FAISS indices
│
├── llm_responses/                   # LLM Response Cache
│   └── response_*.txt
│
├── run.py                           # Project root launcher
├── embed_screener_data.py           # Batch embedding script
├── pyproject.toml
├── requirements.txt
├── README.md
└── .env, .gitignore, etc.

```

## Module Breakdown

### `analysis/`
**Responsible for:** Single-stock financial analysis
- **analysis_engine.py** - Orchestrates multi-step analysis using LangGraph state machine
- **prompts.py** - LLM prompts for each analysis section (7 sections total)
- **comprehensive_prompt_new.py** - HTML report generation

### `embeddings/`
**Responsible for:** Semantic search and vector storage
- **analysis_embedding_store.py** - Embeds analysis reports for Q&A (FAISS)
- **screener_embedding_store.py** - Embeds screener CSV data for cross-stock search with hybrid scoring

### `chat/`
**Responsible for:** Conversational interfaces
- **analysis_chat.py** - Single-stock Q&A using report embeddings
- **multi_stock_chat.py** - Cross-stock queries with numeric filtering (e.g., "P/E between 50-80")

### `data/`
**Responsible for:** Financial data pipeline
- **screener_data_extractor.py** - Fetches Screener.in data → extracts → cleans → embeds (unified pipeline)
- **csv_cleaner.py** - Validates & cleans financial data
- **csv_data_formatter.py** - Formats CSV data for LLM consumption (tables, metrics)
- **daily_data_fetcher.py** - Real-time market data integration

### `llm/`
**Responsible for:** LLM provider management
- **llm_manager.py** - Handles Claude and OpenAI provider selection

### `api/`
**Responsible for:** REST API and web interface
- **app.py** - Flask application with routes for analysis, chat, and results

### `common/`
**Responsible for:** Shared utilities and configuration
- **config.py** - Application settings and environment variables
- **cache_manager.py** - Caches analysis results (7-day expiry)
- **helpers.py** - Utility functions
- **debug_logger.py** - Logs prompts and responses for debugging
- **realtime_data_integration.py** - Market snapshot and performance data

## Data Flow

### Adding a New Stock

```
1. screener_data_extractor.py
   ├─ Browser fetches Screener.in HTML
   ├─ Extracts financial tables
   ├─ Creates CSV files in static/{STOCK}/
   └─ Auto-triggers: ScreenerEmbeddingStore.embed_stock()

2. ScreenerEmbeddingStore (embeddings/screener_embedding_store.py)
   ├─ Loads CSV files
   ├─ Chunks financial data
   ├─ Creates embeddings
   └─ Saves FAISS indices to embeddings/screener/{STOCK}/
```

### Single Stock Analysis

```
1. User submits stock symbol
2. StockAnalysisEngine (analysis/analysis_engine.py)
   ├─ Checks cache (7-day TTL)
   ├─ If hit: Return cached result
   └─ If miss: Run full analysis
3. Analysis workflow (7 sections):
   ├─ Company Overview
   ├─ Quantitative Analysis
   ├─ Qualitative Analysis
   ├─ Shareholding Analysis
   ├─ Investment Thesis
   ├─ Valuation & Recommendation
   └─ Conclusion
4. AnalysisEmbeddingStore embeds report sections
5. Render HTML report + cache result
```

### Cross-Stock Search

```
1. User query: "Stocks with P/E between 50-80"
2. MultiStockChat (chat/multi_stock_chat.py)
   ├─ ScreenerEmbeddingStore.search_stocks()
   │  ├─ Extract range: P/E 50-80
   │  ├─ Search all stocks' FAISS indices
   │  ├─ Apply hybrid scoring: Vector(40%) + Keyword(60%) + Numeric_filter
   │  └─ Return ranked results
   └─ LLMManager synthesizes answer via Claude/OpenAI
```

## Key Features

- **Unified Data Pipeline** - Extract → Clean → Embed in single command
- **Hybrid Search** - Vector similarity + keyword matching + numeric filtering
- **Multi-Provider LLM** - Support for Claude and OpenAI
- **Semantic Search** - Q&A on reports using embeddings
- **Caching** - 7-day cache on analysis results
- **Real-time Integration** - Daily data snapshots and price tracking

## Environment Variables

```
LLM_PROVIDER=claude           # or openai
ANTHROPIC_API_KEY=...        # For Claude
OPENAI_API_KEY=...           # For OpenAI
FLASK_DEBUG=False            # Flask debug mode
```

## Running the Application

```bash
# Start web server
python run.py                          # Uses default provider (Claude)
python run.py --provider openai        # Use OpenAI

# Add new stock
python -m src.data.screener_data_extractor "https://www.screener.in/company/ASIANPAINT/"

# Regenerate all embeddings
python -m src.data.screener_data_extractor --regen-all

# Embed all stock data
python embed_screener_data.py
```

## Design Principles

1. **Separation of Concerns** - Each module has a single responsibility
2. **Clear Dependencies** - Unidirectional imports (e.g., analysis depends on embeddings, chat depends on search)
3. **Reusable Components** - Modules can be used independently
4. **Clean Imports** - Relative imports within modules, absolute from root
5. **Type Hints** - All functions have proper type annotations
