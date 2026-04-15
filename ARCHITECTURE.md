# Stock Analyzer - System Architecture

## Overview

Stock Analyzer is an AI-powered financial analysis system that generates comprehensive stock analysis reports and enables semantic search through AI-powered chat. The system uses a modular architecture with clear separation between data processing, analysis, embeddings, and user-facing APIs.

**Key Innovation:** Unified `/api/chat` endpoint that intelligently routes queries to the right backend (analysis embeddings for single-stock questions, screener embeddings for cross-stock queries).

```
┌─────────────────────────────────────┐
│  REST API Layer (Flask)             │
│  • /api/analyze  • /api/chat        │
│  • /api/results  • /report          │
└────────────┬────────────────────────┘
             │
┌────────────▼────────────────────────┐
│  Application Services               │
│  • Analysis Engine (LangGraph)      │
│  • Unified Chat Handler             │
│  • LLM Manager (Claude/OpenAI)      │
└────────────┬────────────────────────┘
             │
    ┌────────┴──────────┬──────────────┐
    │                   │              │
┌───▼────────┐  ┌──────▼──────┐  ┌───▼──────────┐
│ Analysis   │  │ Embeddings  │  │ Chat         │
│ (7-step)   │  │ • Analysis  │  │ • Unified    │
│ • LLM      │  │ • Screener  │  │   Router     │
│ • LangGraph│  │ • FAISS     │  │ • Analysis   │
│            │  │ • Metadata  │  │ • Multi-Stock│
└────────────┘  └─────────────┘  └──────────────┘
                       │
                ┌──────▼──────────┐
                │ Data Layer      │
                │ • CSV files     │
                │ • Cache         │
                │ • Logging       │
                └─────────────────┘
```

---

## Core Modules

### 1. API Layer (`src/api/app.py`)

**REST Endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Web interface |
| `/api/analyze` | POST | Submit stock for analysis |
| `/api/status/<stock>` | GET | Check analysis progress |
| `/api/results/<stock>` | GET | Retrieve analysis result |
| `/api/chat` | POST | **Unified chat endpoint** (all queries) |
| `/report/<stock>` | GET | View HTML report |
| `/report/<stock>/pdf` | GET | Export as PDF |
| `/api/health` | GET | System health |

**Key Feature:** Single `/api/chat` endpoint handles all chat varieties:
- Request: `{"query": "What is the target price for EICHERMOT?"}`
- Response: `{"success": true, "answer": "...", "sources": [...], "confidence": 0.85}`

### 2. Analysis Engine (`src/analysis/analysis_engine.py`)

Orchestrates multi-step stock analysis using **LangGraph state machine**.

**Workflow (7 Analysis Sections):**
1. **Company Overview** - Business, markets, competitors
2. **Quantitative Analysis** - Metrics, ratios, growth
3. **Qualitative Analysis** - Management, advantages, risks
4. **Shareholding** - Promoter, FII, DII holdings
5. **Investment Thesis** - Case and triggers
6. **Valuation & Recommendation** - Fair value and rating
7. **Conclusion** - Summary and outlook

**Features:**
- Caching: 7-day TTL
- HTML report generation
- Auto-embedding after completion
- Error handling and logging

### 3. Unified Chat Handler (`src/chat/unified_chat.py`)

Smart router that detects query intent and routes appropriately.

**Algorithm:**
```
Query: "What is the target price for EICHERMOT?"
  ↓
Extract stocks: ['EICHERMOT'] (supports 2-12 char symbols)
  ↓
Classify: Single-stock analysis query
  ↓
Route to: StockAnalysisChat → Analysis embeddings
  ↓
Result: ₹7,695 (Weighted Average Fair Value)
```

**Routing Logic:**
- **Single-Stock Analysis:** Named stocks + analysis keywords (target price, fair value, ROE, etc.)
- **Multi-Stock Screener:** No named stock OR comparison/listing keywords (which, compare, top, etc.)

### 4. Chat Interfaces

#### StockAnalysisChat (`src/chat/analysis_chat.py`)
Single-stock Q&A using semantic search over analysis reports.

```python
chat = StockAnalysisChat(llm_provider='claude')
result = chat.answer_question("What is the target price?", "EICHERMOT")
# Returns: {answer: "₹7,695...", sources: ["valuation_recommendation"], confidence: 0.85}
```

#### MultiStockChat (`src/chat/multi_stock_chat.py`)
Cross-stock queries using screener embeddings with hybrid scoring.

```python
chat = MultiStockChat(llm_provider='claude')
result = chat.answer_screener_query("Stocks with P/E < 30")
# Returns: Top 10 stocks with synthesis
```

### 5. Embedding Stores

#### AnalysisEmbeddingStore (`src/embeddings/analysis_embedding_store.py`)
- Chunks analysis sections (500-char chunks, 100-char overlap)
- HTML-to-plain-text conversion (improves semantic quality)
- FAISS indexing (384-dim hash-based vectors, L2 distance)
- Storage: `embeddings/{STOCK}/faiss_index.bin`

#### ScreenerEmbeddingStore (`src/embeddings/screener_embedding_store.py`)
- Embeds financial metrics from CSV files
- Hybrid scoring: Vector (40%) + Keyword (60%)
- Numeric filtering: Range-based for P/E, ROE, etc.
- Example: "P/E between 50 to 80" with 1.5x boost for matches

### 6. Data Pipeline

#### extractor (`src/data/screener_data_extractor.py`)
- Fetches HTML from Screener.in
- Extracts financial tables (regex-based)
- Creates CSVs in `static/{STOCK}/`
- Auto-triggers embedding creation

#### Cleaner (`src/data/csv_cleaner.py`)
- Validates financial data
- Removes nulls, duplicates
- Checks completeness (80%+ threshold)
- Standardizes units

#### Formatter (`src/data/csv_data_formatter.py`)
- Converts CSVs to LLM-friendly tables
- Output: Markdown/text suitable for context

### 7. LLM Manager (`src/llm/llm_manager.py`)

Abstracts provider selection and inference.

**Supported Providers:**
- `claude` - Anthropic Claude (default, recommended)
- `openai` - OpenAI GPT models

---

## Data Flows

### Single-Stock Analysis
```
POST /api/analyze {stock: "EICHERMOT"}
  ↓
StockAnalysisEngine
  ├─ Load CSVs from static/EICHERMOT/
  ├─ Check 7-day cache
  ├─ Run LangGraph workflow (7 sections)
  ├─ Each section: Format data → LLM → Parse response
  ├─ Generate HTML report
  ├─ Save embeddings via AnalysisEmbeddingStore
  └─ Cache result (7 days)
  ↓
Return HTML report
```

### Chat - Single Stock
```
POST /api/chat {query: "What is the target price for EICHERMOT?"}
  ↓
UnifiedChatHandler.answer()
  ├─ Extract stocks: ['EICHERMOT']
  ├─ Classify: Single-stock analysis
  └─ Route: StockAnalysisChat
  ↓
StockAnalysisChat.answer_question()
  ├─ Search: Find 5 similar chunks in EICHERMOT embeddings
  ├─ Context: Chunks from valuation_recommendation section
  └─ LLM: "Based on this analysis, the target price is..."
  ↓
Return {answer: "₹7,695...", sources: [...], confidence: 0.85}
```

### Chat - Multi-Stock
```
POST /api/chat {query: "Which stocks have P/E between 50 to 80?"}
  ↓
UnifiedChatHandler.answer()
  ├─ Extract stocks: [] (no named stocks)
  ├─ Classify: Multi-stock screener
  └─ Route: MultiStockChat
  ↓
ScreenerEmbeddingStore.answer_screener_query()
  ├─ Search all stocks' embeddings
  ├─ Hybrid score: Vector (40%) + Keyword (60%) + Numeric filter
  ├─ Boost 1.5x if 50 ≤ P/E ≤ 80
  └─ Return top 10 stocks
  ↓
LLM: Synthesize results with explanation
  ↓
Return {answer: "Top stocks: ...", sources: [...], confidence: 0.78}
```

---

## File Structure

```
stock_annalyzer/
├── src/
│   ├── api/
│   │   └── app.py                       # Flask REST API
│   ├── analysis/
│   │   ├── analysis_engine.py           # Orchestrates 7-step analysis
│   │   ├── prompts.py                   # LLM prompts
│   │   └── comprehensive_prompt_new.py  # HTML report generation
│   ├── chat/
│   │   ├── unified_chat.py              # Unified router (entry point)
│   │   ├── analysis_chat.py             # Single-stock Q&A (NO unused methods)
│   │   └── multi_stock_chat.py          # Multi-stock Q&A (NO unused methods)
│   ├── embeddings/
│   │   ├── analysis_embedding_store.py  # Report embeddings + FAISS
│   │   └── screener_embedding_store.py  # Screener embeddings + hybrid search
│   ├── data/
│   │   ├── screener_data_extractor.py   # Data extraction pipeline
│   │   ├── csv_cleaner.py               # Data validation
│   │   ├── csv_data_formatter.py        # Data formatting
│   │   └── daily_data_fetcher.py        # Real-time data
│   ├── llm/
│   │   └── llm_manager.py               # Provider abstraction
│   ├── common/
│   │   ├── config.py                    # Configuration
│   │   ├── cache_manager.py             # Result caching (7-day TTL)
│   │   └── debug_logger.py              # Prompt/response logging
│   ├── templates/
│   │   └── index.html                   # Web interface
│   └── static/
│       ├── js/main.js                   # Frontend (uses /api/chat)
│       └── css/style.css                # Styling
├── static/
│   ├── ASIANPAINT/                      # Financial data (CSV)
│   ├── EICHERMOT/
│   └── ... (50 stocks total)
├── embeddings/
│   ├── ASIANPAINT/                      # Analysis embeddings
│   ├── EICHERMOT/
│   └── screener/                        # Screener embeddings
├── debug_prompts/                       # LLM prompts (debug mode)
├── llm_responses/                       # LLM responses + cache
├── requirements.txt
└── ARCHITECTURE.md                      # This file
```

---

## Key Design Decisions

### 1. Unified Chat Endpoint
Instead of 6 specialized endpoints (`/api/chat/ask`, `/api/chat/search`, `/api/chat/compare`, etc.), we have ONE endpoint that intelligently routes:
- **Benefit:** Single source of truth, less confusion, easier to maintain
- **Trade-off:** Slight added complexity in routing logic (well worth it)

### 2. HTML-to-Plain-Text Conversion
Analysis sections are converted from HTML to plain text BEFORE embedding:
- **Benefit:** Better semantic quality, LLM can read text easily
- **Implementation:** `_html_to_plain_text()` in AnalysisEmbeddingStore

### 3. Stock Symbol Length (2-12 chars)
Supports both short (INFY, TCS) and long (EICHERMOT, TATAMOTORS) symbols:
- **Previous limit:** 2-6 chars (too restrictive)
- **Current limit:** 2-12 chars (covers all Indian stocks)

### 4. Embedding Architecture
Separate stores for different data:
- **Analysis Embeddings:** Text chunks from reports (RAG for Q&A)
- **Screener Embeddings:** Financial metrics (hybrid scoring for cross-stock)
- **Benefit:** Optimized for each use case

### 5. Caching Strategy
- **Analysis results:** 7-day TTL (expensive LLM operations)
- **Embeddings:** Persisted to disk (recreated on data changes)
- **LLM responses:** Logged for debugging and monitoring

---

## Cleaned-Up Code

**Removed Unused Methods:**
- `StockAnalysisChat.multi_stock_search()` - Legacy cross-stock search
- `StockAnalysisChat.get_comparative_answer()` - Legacy comparison
- `StockAnalysisChat.interactive_chat()` - Legacy CLI interface
- `MultiStockChat.detect_query_type()` - Routing now in UnifiedChatHandler
- `MultiStockChat.answer_analysis_query()` - Not called anywhere

**Removed Unused Exports:**
- `interactive_chat` from `src/chat/__init__.py`

**Result:** Cleaner codebase with no dead code, easier to understand and maintain.

---

## Performance Optimization

### Caching
- Analysis results: 7-day TTL
- Embeddings: FAISS binary format (.bin) cached to disk
- LLM responses: Logged for monitoring

### Search
- FAISS IndexFlatL2: Fast similarity search
- Hybrid scoring: Balances vector + keyword + numeric relevance
- Top-k limitation: Prevents excessive results

### API
- Async analysis: Doesn't block frontend (polling-based)
- Sync chat: Immediate response via RAG
- Streaming: HTML reports sent directly

---

## Extension Points

### Add Analysis Section
1. Add prompt in `src/analysis/prompts.py`
2. Add node in `src/analysis/analysis_engine.py` workflow
3. Update report generator in `src/analysis/comprehensive_prompt_new.py`

### Add LLM Provider
1. Extend `src/llm/llm_manager.py`
2. Add config in `src/common/config.py`

### Add Embedding Store
1. Create new class inheriting base pattern
2. Register in API: `src/api/app.py`

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| Chat returns wrong stock | Symbol extraction failed | Check `unified_chat.py` line 37-40 |
| Embeddings not found | Analysis run without embedding | Run `AnalysisEmbeddingStore.save_analysis_embeddings()` |
| LLM returns wrong format | Prompt template mismatch | Check `src/analysis/prompts.py` or chat files |
| Analysis takes too long | Cache miss + LLM processing | Check logging; consider increasing cache TTL |

---

## Dependencies & Packages

### Core LLM & AI Framework

#### **langchain** (>=0.1.0)
- **Purpose:** Universal framework for building LLM applications
- **Why Required:** Provides abstraction layer for prompts, chains, memory, and document loaders
- **Used In:**
  - `src/llm/llm_manager.py` - LLM provider abstraction
  - `src/chat/analysis_chat.py` - Q&A chains with context
  - `src/chat/multi_stock_chat.py` - Cross-stock query processing
  - `src/analysis/analysis_engine.py` - Prompt templating
- **Key Benefits:** Standardized interfaces, makes LLM switching easy (Claude ↔ OpenAI)

#### **langchain-anthropic** (>=0.1.0)
- **Purpose:** Official Anthropic Claude integration for LangChain
- **Why Required:** Enables using Claude as primary LLM provider
- **Used In:** `src/llm/llm_manager.py` when `provider='claude'`
- **Key Benefits:** Full support for Claude 3 models, streaming support, token counting

#### **langchain-openai** (>=0.0.1)
- **Purpose:** Official OpenAI GPT integration for LangChain
- **Why Required:** Enables using OpenAI as alternative LLM provider
- **Used In:** `src/llm/llm_manager.py` when `provider='openai'`
- **Key Benefits:** Support for GPT-4, GPT-3.5-turbo, function calling

#### **langchain-community** (>=0.1.0)
- **Purpose:** Community integrations for various tools and services
- **Why Required:** Provides HuggingFace embeddings integration
- **Used In:** `src/embeddings/analysis_embedding_store.py` - text embedding fallback
- **Key Benefits:** Lightweight embeddings locally without external APIs

#### **langchain-huggingface** (>=0.0.1)
- **Purpose:** HuggingFace embeddings through LangChain
- **Why Required:** Primary embeddings provider for semantic search
- **Used In:** `src/embeddings/analysis_embedding_store.py` and `src/embeddings/screener_embedding_store.py`
- **Model Used:** `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional vectors)
- **Key Benefits:** High-quality embeddings, no API key needed, runs locally on CPU

#### **langgraph** (>=0.1.0)
- **Purpose:** State machine framework for complex AI workflows
- **Why Required:** Orchestrates the 7-step analysis workflow
- **Used In:** `src/analysis/analysis_engine.py` - LangGraph workflow definition
- **Key Components:**
  - `StateGraph` - Defines workflow states and transitions
  - `Node` - Each analysis section (company overview, quantitative, etc.)
  - `edges` - Connections between nodes
- **Key Benefits:** Builds complex multi-step AI pipelines, handles conditionals and loops

---

### Vector Database & Semantic Search

#### **faiss-cpu** (>=1.7.4)
- **Purpose:** Facebook AI Similarity Search - vector similarity library
- **Why Required:** Enables semantic search over embeddings for Q&A
- **Used In:**
  - `src/embeddings/analysis_embedding_store.py` - Analysis report search
  - `src/embeddings/screener_embedding_store.py` - Cross-stock metrics search
- **How It Works:**
  - Stores 384-dimensional vectors (embeddings) in FAISS indices
  - Efficient L2 distance computation for finding similar chunks
  - Persists indices to disk as binary files (`embeddings/{STOCK}/faiss_index.bin`)
- **Key Benefits:** Extremely fast similarity search, low memory footprint, no external DB needed
- **Alternative:** `faiss-gpu` for GPU acceleration (optional)

#### **redisvl** (>=0.1.0)
- **Purpose:** Redis vector library for semantic search with Redis
- **Why Required:** Alternative vector DB backend (currently used for potential scaling)
- **Used In:** Configuration but not actively used in current implementation
- **Future Use:** When Redis becomes primary vector store for distributed caching

#### **redis** (>=5.0.0)
- **Purpose:** In-memory data store and cache
- **Why Required:** Potential caching layer for embeddings and LLM responses
- **Used In:** Could be used in `src/common/cache_manager.py` for distributed caching
- **Current Status:** Installed but file-based JSON caching used instead for simplicity

---

### Web Framework & API

#### **flask** (>=2.3.0)
- **Purpose:** Lightweight Python web framework
- **Why Required:** Builds REST API endpoints for analysis and chat
- **Used In:** `src/api/app.py` - main Flask application
- **Endpoints Provided:**
  - `GET /` - Web interface
  - `POST /api/analyze` - Submit stock for analysis
  - `POST /api/chat` - Unified chat endpoint
  - `GET /api/results/<stock>` - Retrieve results
  - `GET /report/<stock>` - HTML report viewer
- **Key Benefits:** Minimal dependencies, built-in thread support, easy to understand

#### **flask-cors** (>=4.0.0)
- **Purpose:** Enable Cross-Origin Resource Sharing for Flask
- **Why Required:** Allows frontend (JavaScript) to make API calls from different origin
- **Used In:** `src/api/app.py` - middleware for `/api/chat`, `/api/analyze` endpoints
- **Key Benefits:** Prevents CORS errors when frontend and API are on different domains

---

### Data Processing & Analysis

#### **pandas** (>=3.0.0)
- **Purpose:** Data manipulation and analysis library
- **Why Required:** Process financial CSV data (P&L, balance sheet, cash flow, etc.)
- **Used In:**
  - `src/data/csv_cleaner.py` - Data cleaning and validation
  - `src/data/csv_data_formatter.py` - Converting CSVs to LLM-friendly tables
  - `src/analysis/analysis_engine.py` - Loading stock data
- **Key Operations:**
  - Read CSV files from `static/{STOCK}/`
  - Handle missing values
  - Compute growth rates and trends
  - Format data as markdown/HTML tables

#### **scikit-learn** (>=1.3.0)
- **Purpose:** Machine learning library with text/data utilities
- **Why Required:** Text preprocessing and feature scaling for embeddings
- **Used In:**
  - `src/embeddings/screener_embedding_store.py` - Numeric filtering and normalization
  - Potential TF-IDF text preprocessing for hybrid search
- **Key Benefits:** Robust algorithms for text and numeric feature handling

#### **yfinance** (>=0.2.30)
- **Purpose:** Fetch real-time stock market data from Yahoo Finance
- **Why Required:** Get current stock prices, volume, and performance metrics
- **Used In:** `src/common/realtime_data_integration.py` - Market snapshot
- **Data Fetched:**
  - Current price and % change
  - 52-week range
  - Trading volume
  - Dividend yield
  - Market cap
- **Key Benefits:** Free API, no key required, widely used for real-time data

#### **playwright** (>=1.40.0)
- **Purpose:** Browser automation framework for scraping dynamic content
- **Why Required:** Fetch financial data from Screener.in (JavaScript-heavy site)
- **Used In:** `src/data/screener_data_extractor.py` - Data extraction pipeline
- **How It Works:**
  - Opens Screener.in URLs in headless browser
  - Waits for dynamic content to load
  - Extracts financial tables via DOM parsing
- **Key Benefits:** Handles JavaScript-rendered content (faster than Selenium)
- **Alternative:** Could switch to Selenium if needed

---

### Utilities & Configuration

#### **python-dotenv** (>=1.0.0)
- **Purpose:** Load environment variables from `.env` file
- **Why Required:** Manage API keys and configuration securely
- **Used In:** `src/common/config.py` - Load credentials
- **Environment Variables Configured:**
  - `LLM_PROVIDER` - Claude or OpenAI
  - `ANTHROPIC_API_KEY` - Claude API key
  - `OPENAI_API_KEY` - OpenAI API key
  - `DEBUG_MODE` - Enable debug logging
  - `CACHE_TTL_DAYS` - Analysis cache expiry
- **Key Benefits:** Keeps secrets out of code, easy to switch configs

#### **pydantic** (>=2.0.0)
- **Purpose:** Data validation and settings using Python type hints
- **Why Required:** Validate configuration, API request/response schemas
- **Used In:**
  - `src/common/config.py` - Settings validation
  - Chat request/response models
  - Analysis result schemas
- **Key Benefits:** Runtime validation, auto-generated docs, type safety

#### **requests** (>=2.31.0)
- **Purpose:** HTTP library for making API calls
- **Why Required:** Fetch data, make external API requests
- **Used In:**
  - `src/data/screener_data_extractor.py` - Fetch Screener.in URLs
  - Real-time data fetching
  - Fallback for API calls when LangChain not sufficient
- **Key Benefits:** Simple and robust HTTP handling

---

### Development & Testing

#### **pytest** (>=7.0.0)
- **Purpose:** Testing framework
- **Why Required:** Write and run unit tests for modules
- **Used In:** `tests/` directory - test suite
- **Key Features:** Fixtures, parametrization, detailed output
- **Example:** `pytest tests/ -v` runs all tests

#### **pytest-asyncio** (>=0.21.0)
- **Purpose:** Async test support for pytest
- **Why Required:** Test async functions in chat and analysis modules
- **Used In:** Tests for async LLM calls and embeddings

#### **black** (>=23.0.0)
- **Purpose:** Code formatter
- **Why Required:** Maintain consistent code style (PEP 8)
- **Usage:** `black src/` formats all Python files
- **Integrated:** Pre-commit hooks for automatic formatting

#### **isort** (>=5.12.0)
- **Purpose:** Import statement organizer
- **Why Required:** Sort and organize imports consistently
- **Usage:** `isort src/` organizes imports
- **Integrated:** Works with black for code consistency

#### **flake8** (>=6.0.0)
- **Purpose:** Style guide enforcement tool
- **Why Required:** Catch PEP 8 violations and code smells
- **Usage:** `flake8 src/` checks code quality
- **Config:** Can be configured via `.flake8` file

---

## Technology Stack Summary

| Tier | Component | Technology | Purpose |
|------|-----------|-----------|---------|
| **API** | REST Framework | Flask + Flask-CORS | HTTP endpoints, CORS handling |
| **LLM** | Model Providers | Claude, OpenAI | AI inference for analysis |
| **LLM Framework** | Orchestration | LangChain + LangGraph | Prompt management, workflows |
| **Vector Search** | Embeddings | HuggingFace (sentence-transformers) | Text-to-vector conversion |
| **Vector Search** | Similarity Index | FAISS | Fast semantic search |
| **Data Processing** | Analysis | Pandas | CSV processing, tables |
| **Data Processing** | Web Scraping | Playwright | Extract financial data |
| **Data Processing** | Real-time Data | YFinance | Stock prices & volumes |
| **Configuration** | Secrets | python-dotenv | Environment management |
| **Validation** | Schemas | Pydantic | Request/response validation |
| **Testing** | Unit Tests | Pytest + pytest-asyncio | Test suite |
| **Quality** | Code Style | Black, isort, flake8 | Code formatting & linting |

---

## Summary

Stock Analyzer is a **clean, modular system** that separates concerns effectively:

- **Analysis:** Multi-step LangGraph workflow for comprehensive reports
- **Embeddings:** FAISS-based semantic search with RAG for Q&A
- **Chat:** Unified router with intelligent query classification
- **API:** RESTful Flask interface for web and mobile

The removal of unused code and consolidation to a single chat endpoint resulted in a **cleaner, more maintainable codebase** that's easier to understand and extend.
