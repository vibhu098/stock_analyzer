# Stock Analyzer - Agents & Modules Reference

## Overview

This document provides comprehensive context on all agents (modules) in the Stock Analyzer system, their responsibilities, dependencies, and integration patterns.

---

## Module Hierarchy

```
CORE LAYERS
───────────

┌─────────────────────────────────────┐
│  API Layer (Entry Point)            │
│  src/api/app.py                     │
└────────────────┬────────────────────┘
                 │
┌────────────────▼──────────────────┐
│  Application Services             │
│  • ChatManagers                   │
│  • LLMProvider                    │
└────────────┬──────────┬───────────┘
             │          │
    ┌────────▼──┐  ┌───▼──────────┐
    │ Analysis   │  │ Embeddings   │
    │ Agent      │  │ Agent        │
    └────────┬───┘  └───┬──────────┘
             │          │
    ┌────────▼──┐  ┌───▼──────────┐
    │ Data      │  │ Chat         │
    │ Agent     │  │ Agents       │
    └────────┬──┘  └───┬──────────┘
             │          │
             └────┬─────┘
                  │
        ┌─────────▼──────────┐
        │ Common Layer       │
        │ • Config           │
        │ • Cache            │
        │ • Logging          │
        └────────────────────┘
```

---

## Layer 1: Entry Point

### `src/api/app.py` - Flask Application

**Purpose:** REST API and web interface for the stock analyzer

**Responsibilities:**
- Route HTTP requests
- Manage sessions and user interactions
- Serve HTML templates
- Handle file uploads/downloads
- Error handling and logging

**Key Routes:**
```python
GET  /                      # Main web interface
POST /api/analyze           # Submit stock for analysis
GET  /api/analysis/{stock}  # Get analysis result
POST /api/chat             # Chat query
GET  /api/results          # List analysis results
```

**Dependencies:**
- `src.analysis.StockAnalysisEngine` - Single stock analysis
- `src.chat.StockAnalysisChat` - Single-stock Q&A
- `src.chat.MultiStockChat` - Cross-stock queries
- `src.common.settings` - Configuration

**Key Methods:**
```python
def analyze_stock(stock_symbol: str) -> dict
def chat_single_stock(stock: str, question: str) -> str
def chat_multi_stock(question: str) -> str
```

---

## Layer 2: Application Services

### `src/llm/llm_manager.py` - LLM Provider Manager

**Purpose:** Abstract LLM provider selection and inference

**Responsibilities:**
- Select Claude or OpenAI
- Manage credentials
- Handle inference
- Error handling for API calls
- Response parsing

**Key Classes:**
```python
class LLMManager:
    def __init__(provider: str = None)
    def get_llm() -> LLM
    def invoke(prompt: str) -> str
```

**Supported Providers:**
- `claude` - Anthropic Claude (default)
- `openai` - OpenAI GPT models

**Configuration:**
```env
LLM_PROVIDER=claude          # Provider selection
ANTHROPIC_API_KEY=sk-ant-... # Claude credentials
OPENAI_API_KEY=sk-...        # OpenAI credentials
```

**Usage Example:**
```python
from src.llm import LLMManager

manager = LLMManager(provider='claude')
llm = manager.get_llm()
response = llm.invoke("Analyze company X")
```

---

## Layer 3: Analysis Agent

### `src/analysis/` - Single Stock Analysis

**Purpose:** Comprehensive financial analysis of a single stock

**Architecture:** LangGraph-based state machine with 7 analysis sections

**Module Structure:**
```
analysis/
├── analysis_engine.py        # Core orchestration
├── prompts.py                # LLM prompts (7 sections)
├── comprehensive_prompt_new.py # HTML report generation
└── __init__.py
```

#### `analysis_engine.py` - Analysis Orchestrator

**Responsibilities:**
- Orchestrate multi-step analysis workflow
- Manage state transitions
- Cache results (7-day TTL)
- Handle errors gracefully

**Key Classes:**

```python
class AnalysisState(TypedDict):
    """State for comprehensive analysis workflow"""
    stock_symbol: str
    files_loaded: dict
    market_snapshot: str
    price_performance: str
    company_overview: str
    quantitative_analysis: str
    qualitative_analysis: str
    shareholding_analysis: str
    investment_thesis: str
    valuation_recommendation: str
    conclusion: str
    final_report: str
    error: str

class StockAnalysisEngine:
    def __init__(stock_data_path: str = None, llm_provider: str = None)
    def analyze_stock(symbol: str) -> dict
```

**Analysis Workflow (7 Sections):**

1. **Company Overview** - Business description, markets, competitors
2. **Quantitative Analysis** - Financial metrics, ratios, growth
3. **Qualitative Analysis** - Management, competitive advantage, risks
4. **Shareholding Analysis** - Promoter, FII, DII holdings
5. **Investment Thesis** - Investment case, key triggers
6. **Valuation & Recommendation** - Fair value estimate, rating
7. **Conclusion** - Summary and outlook

**Data Flow:**
```
1. Load CSVs from static/{STOCK}/
   ├─ key_metrics.csv
   ├─ quarterly_results.csv
   ├─ profit_and_loss_annual.csv
   ├─ balance_sheet.csv
   ├─ cash_flow.csv
   ├─ growth_metrics.csv
   └─ ratios.csv

2. Create analysis state with loaded data

3. Run LangGraph workflow with 7 nodes

4. Generate HTML report

5. Embed sections for Q&A

6. Cache result (7 days)

7. Return analysis dict
```

**Caching Strategy:**
- TTL: 7 days
- Key: `analysis_{stock_symbol}`
- Invalidation: Manual or on 7-day expiry

#### `prompts.py` - LLM Prompt Templates

**Purpose:** Define system and section-specific prompts

**Key Prompts:**

```python
STOCK_ANALYST_SYSTEM_PROMPT = "You are a senior equity research analyst..."

COMPANY_OVERVIEW_PROMPT = "Analyze the company based on: [financial data]"

QUANTITATIVE_ANALYSIS_PROMPT = "Provide financial metrics analysis..."

QUALITATIVE_ANALYSIS_PROMPT = "Provide qualitative industry analysis..."

SHAREHOLDING_ANALYSIS_PROMPT = "Analyze shareholding patterns..."

INVESTMENT_THESIS_PROMPT = "Create investment thesis..."

VALUATION_AND_RECOMMENDATION_PROMPT = "Provide valuation and rating..."

CONCLUSION_PROMPT = "Summarize the analysis..."
```

#### `comprehensive_prompt_new.py` - HTML Report Generator

**Purpose:** Convert analysis sections to formatted HTML report

**Key Function:**
```python
def generate_comprehensive_html_report(analysis_data: dict) -> str:
    """Convert analysis dict to professional HTML report"""
```

**Output:** Styled HTML with tables, charts, and formatting

---

## Layer 3: Embeddings Agent

### `src/embeddings/` - Vector Search & Semantic Storage

**Purpose:** Store financial data and analysis reports as embeddings for semantic search

**Module Structure:**
```
embeddings/
├── analysis_embedding_store.py    # Q&A on reports
├── screener_embedding_store.py    # Cross-stock search
└── __init__.py
```

#### `analysis_embedding_store.py` - Report Embeddings

**Purpose:** Enable Q&A on analysis reports using semantic search

**Responsibilities:**
- Chunk analysis sections
- Create embeddings
- Store in FAISS
- Search and rank relevant chunks
- Synthesize LLM responses from search results

**Key Classes:**
```python
class AnalysisEmbeddingStore:
    def __init__()
    def embed_analysis(symbol: str, sections: dict) -> bool
    def search(symbol: str, query: str, top_k: int = 5) -> List[Tuple]
    def get_cached_embeddings(symbol: str) -> Optional[FAISS]
```

**Data Storage:**
```
embeddings/analysis/{STOCK}/
├── faiss_index.bin          # FAISS index
├── metadata.json            # Chunk metadata
└── model_info.json          # Embedding model info
```

**Usage:**
```python
store = AnalysisEmbeddingStore()

# Embed report sections
store.embed_analysis('ASIANPAINT', {
    'company_overview': '...',
    'quantitative_analysis': '...',
    ...
})

# Search for Q&A
results = store.search('ASIANPAINT', "What is the ROE?")
# Returns: [(chunk_text, score), ...]
```

#### `screener_embedding_store.py` - Screener Data Embeddings

**Purpose:** Enable cross-stock search with hybrid scoring and numeric filtering

**Responsibilities:**
- Load CSV financial data
- Create embeddings for each stock
- Implement hybrid search (vector + keyword + numeric)
- Support numeric range filtering
- Rank results by relevance and metrics

**Key Classes:**
```python
class ScreenerEmbeddingStore:
    def __init__()
    def embed_stock(symbol: str) -> bool
    def embed_all_stocks() -> dict
    def search_stocks(query: str, top_k: int = 10) -> List[Tuple]
```

**Hybrid Search Scoring:**
```
Final Score = (Vector_Similarity * 0.4 + Keyword_Match * 0.6) × Numeric_Filter

Numeric_Filter:
  - If value in range: multiply by 1.5 (50% boost)
  - If value outside range: multiply by 0.2 (80% penalty)
```

**Supported Metrics for Filtering:**
- P/E (Price-to-Earnings)
- ROE (Return on Equity)
- ROCE (Return on Capital Employed)
- Dividend Yield
- EPS (Earnings Per Share)
- Price
- Market Cap

**Example Query:**
```python
# "Find stocks with P/E between 50 to 80"
results = store.search_stocks("P/E between 50 to 80")
# Returns ranked list: [(stock, metadata, score), ...]
```

**Data Storage:**
```
embeddings/screener/{STOCK}/
├── faiss_index.bin          # FAISS vector index
├── metadata.json            # Chunk metadata
└── embedding_config.json    # Configuration
```

---

## Layer 3: Data Agent

### `src/data/` - Data Pipeline

**Purpose:** Extract, clean, validate, and format financial data

**Module Structure:**
```
data/
├── screener_data_extractor.py   # Fetch & extract
├── csv_cleaner.py               # Validate & clean
├── csv_data_formatter.py        # Format for LLM
├── daily_data_fetcher.py        # Real-time data
└── __init__.py
```

#### `screener_data_extractor.py` - Data Extraction

**Purpose:** Unified pipeline for extracting, cleaning, and embedding stock data

**Responsibilities:**
- Fetch HTML from Screener.in
- Extract financial tables using regex
- Create CSV files
- Clean & validate data
- **Automatically create embeddings** ✨

**Key Functions:**

```python
async def fetch_and_save_screener_data(screener_url: str):
    """
    Complete pipeline:
    1. Fetch Screener.in HTML
    2. Extract financial metrics
    3. Create CSV files
    4. Clean & validate
    5. Auto-embed for search
    """

def regen_all_csvs():
    """
    Regenerate CSVs for all stocks and re-embed
    Useful after extractor logic changes
    """
```

**Supported Extracts:**
```
key_metrics.csv
├─ Market Cap, P/E, Book Value
├─ Dividend Yield, ROCE, ROE
└─ Face Value

quarterly_results.csv
├─ Sales, Expenses, Operating Profit
├─ Net Profit, EPS
└─ Dividend per share

profit_and_loss_annual.csv
├─ Revenue, Operating Profit
├─ Profit before Tax, Net Profit
└─ Dividend Payout %

balance_sheet.csv
├─ Assets, Liabilities, Equity
└─ Reserves, Borrowings

cash_flow.csv
├─ Operating Cash Flow
├─ Investing Cash Flow
└─ Financing Cash Flow

growth_metrics.csv
├─ CAGR (10Y, 5Y, 3Y)
├─ ROE trends
└─ Profit growth

ratios.csv
├─ ROCE %, efficiency ratios
├─ Days: Debtor, Inventory, Payable
└─ Cash Conversion Cycle
```

**Usage:**
```bash
# Extract single stock + embed
python -m src.data.screener_data_extractor "https://www.screener.in/company/ASIANPAINT/"

# Regenerate all CSVs + re-embed
python -m src.data.screener_data_extractor --regen-all
```

#### `csv_cleaner.py` - Data Validation

**Purpose:** Validate and clean financial data before use

**Key Classes:**
```python
class CSVCleaner:
    @staticmethod
    def clean_key_metrics(data: List[Dict]) -> List[Dict]
    
    @staticmethod
    def clean_financial_table(data: List[Dict], expected_metrics: List[str]) -> List[Dict]
    
    @staticmethod
    def validate_data_completeness(data: List[Dict], min_percent_complete: float = 0.8) -> bool
```

**Validation Rules:**
- Remove null/empty values
- Standardize units (₹, %)
- Remove duplicates
- Check data completeness (80%+ threshold)
- Validate numeric ranges

#### `csv_data_formatter.py` - LLM Formatting

**Purpose:** Format CSV data into LLM-friendly table structures

**Key Functions:**
```python
def format_key_metrics_for_llm(stock_symbol: str) -> str
    """Format key metrics into readable table"""

def format_quantitative_data_for_llm(stock_symbol: str) -> str
    """Format P&L and ratios into financial tables"""

def format_shareholding_data_for_llm(stock_symbol: str) -> str
    """Format shareholding patterns into tables"""
```

**Output Format:** Markdown/text tables suitable for LLM input

#### `daily_data_fetcher.py` - Real-Time Data

**Purpose:** Integrate real-time market data with analysis

**Key Functions:**
```python
def create_realtime_metrics_csv(stock_symbol: str) -> str
    """Create CSV with today's market snapshot"""
```

**Data Included:**
- Current price
- Volume traded
- Price change %
- Market cap
- 52-week range

---

## Layer 3: Chat Agents

### `src/chat/` - Conversational Interfaces

**Purpose:** Chat interfaces for stock querying and analysis

**Module Structure:**
```
chat/
├── analysis_chat.py         # Single-stock Q&A
├── multi_stock_chat.py      # Cross-stock queries
└── __init__.py
```

#### `analysis_chat.py` - Single-Stock Chat

**Purpose:** Ask questions about a specific stock's analysis report

**Key Classes:**
```python
class StockAnalysisChat:
    def __init__(llm_provider: str = None)
    def ask(stock_symbol: str, question: str) -> str
```

**Flow:**
```
1. User asks: "What is the ROE?"
2. Search analysis embeddings for stock
3. Find relevant chunks via semantic search
4. Build context from top 5 chunks
5. Send to LLM: "Based on this data, [question]"
6. Return synthesized answer
```

**Example:**
```python
chat = StockAnalysisChat()
answer = chat.ask('ASIANPAINT', 'What is the dividend yield?')
# Returns: "As per the latest analysis, the dividend yield is 1.04%..."
```

#### `multi_stock_chat.py` - Cross-Stock Chat

**Purpose:** Compare stocks and answer cross-stock queries

**Key Classes:**
```python
class MultiStockChat:
    def __init__(llm_provider: str = None)
    def ask(question: str) -> str
```

**Supported Queries:**
```
• "Which stocks have P/E < 30?"
• "Stocks with dividend yield > 2%"
• "Which companies have ROE > 25%?"
• "Compare ASIANPAINT vs HDFCBANK"
• "Top 5 stocks by market cap"
• "Stocks with P/E between 50 to 80"
```

**Query Processing:**
```
1. User asks: "Stocks with P/E between 50 to 80"

2. Extract metrics:
   - metric: 'P/E'
   - range: [50, 80]

3. Search all stocks' embeddings:
   - Vector similarity search
   - Keyword matching for 'P/E'
   - Numeric filtering (50 ≤ P/E ≤ 80)

4. Score results:
   - Vector (40%) + Keyword (60%) + Numeric filter
   - Boost by 1.5x if in range
   - Penalize by 0.2x if outside range

5. Return top stocks with LLM synthesis

6. LLM formats answer with table
```

---

## Layer 4: Common/Utility Agents

### `src/common/` - Shared Utilities

**Module Structure:**
```
common/
├── config.py                      # Configuration
├── cache_manager.py               # Result caching
├── helpers.py                     # Utility functions
├── debug_logger.py                # Prompt/response logging
├── realtime_data_integration.py   # Market data
└── __init__.py
```

#### `config.py` - Configuration Management

**Purpose:** Centralized configuration from environment variables

**Key Variables:**
```python
class Settings:
    llm_provider: str = "claude"        # LLM provider
    debug_mode: bool = False             # Debug logging
    cache_ttl_days: int = 7             # Cache expiry
    embedding_model: str = "all-MiniLM-L6-v2"
    faiss_metric: str = "L2"            # FAISS distance metric
    log_level: str = "INFO"             # Logging level
    max_chunk_size: int = 512           # Embedding chunk size
    embedding_dimension: int = 384      # Embedding output dimension
```

#### `cache_manager.py` - Analysis Caching

**Purpose:** Cache analysis results to avoid re-analysis within TTL

**Key Classes:**
```python
class AnalysisCacheManager:
    def __init__(ttl_days: int = 7)
    def get(stock_symbol: str) -> Optional[dict]
    def set(stock_symbol: str, analysis: dict) -> None
    def is_valid(stock_symbol: str) -> bool
    def clear(stock_symbol: str) -> None
```

**Storage:** File-based JSON cache in `llm_responses/`

**Cache Entry:**
```json
{
    "stock_symbol": "ASIANPAINT",
    "timestamp": "2026-04-04T10:30:00",
    "ttl_days": 7,
    "sections": {
        "company_overview": "...",
        "quantitative_analysis": "...",
        ...
    }
}
```

#### `debug_logger.py` - Prompt/Response Logging

**Purpose:** Log all LLM prompts and responses for debugging

**Key Functions:**
```python
def save_prompt_to_files(stock_symbol: str, section: str, prompt: str):
    """Save prompt as .md and .html"""

def save_llm_response(stock_symbol: str, section: str, response: str):
    """Save LLM response to file"""
```

**Output Location:** `debug_prompts/` and `llm_responses/`

**File Naming:**
```
debug_prompts/prompt_ASIANPAINT_company_overview_20260403_190037.md
llm_responses/response_ASIANPAINT_company_overview_20260403_190133.txt
```

#### `realtime_data_integration.py` - Market Data

**Purpose:** Integrate real-time market snapshots into analysis

**Key Functions:**
```python
def prepare_today_market_snapshot(stock_symbol: str) -> str
    """Get current price, volume, change %"""

def get_price_performance_summary(stock_symbol: str) -> str
    """Get 1Y, 3Y, 5Y, 10Y price CAGRs"""
```

---

## Integration Patterns

### Data Flow: Single Stock Analysis

```
User Request
    ↓
[API] app.py
    ↓
[Analysis] StockAnalysisEngine
    ├─ Load CSVs from static/{STOCK}/
    ├─ Check cache (7-day TTL)
    ├─ If cached → Return cached result
    ├─ If not cached:
    │   ├─ LangGraph workflow (7 steps)
    │   ├─ Each step: Format data → LLM → Parse response
    │   ├─ Generate HTML report
    │   ├─ Embed sections → AnalysisEmbeddingStore
    │   └─ Cache result (7 days)
    ├─ Return analysis dict
    └─ API serves HTML report
```

### Data Flow: Cross-Stock Search

```
User Query
    ↓
[API] app.py
    ↓
[Chat] MultiStockChat.ask(query)
    ├─ Extract numeric range (if any)
    ├─ Extract keywords
    ├─ [Embeddings] ScreenerEmbeddingStore.search_stocks()
    │   ├─ Search all stocks' FAISS indices
    │   ├─ Hybrid scoring: Vector(40%) + Keyword(60%)
    │   ├─ Apply numeric filtering
    │   └─ Rank by final score
    ├─ Build context from top results
    ├─ [LLM] LLMManager.invoke()
    │   └─ Synthesize answer
    └─ Return formatted response
```

### Data Flow: New Stock Addition

```
Add new stock
    ↓
[Data] screener_data_extractor.py
    ├─ Fetch Screener.in HTML
    ├─ Extract tables (regex)
    ├─ Create CSVs in static/{STOCK}/
    ├─ [Data] csv_cleaner.py - Validate data
    ├─ [Embeddings] ScreenerEmbeddingStore
    │   └─ embed_stock(STOCK) - Create FAISS index
    └─ Ready for analysis & search
```

---

## Extension Points

### Add New Analysis Section

1. **Create Prompt** in `src/analysis/prompts.py`:
```python
NEW_SECTION_PROMPT = """Your prompt here..."""
```

2. **Add to Workflow** in `src/analysis/analysis_engine.py`:
```python
state['new_section'] = await new_section_node(state)
```

3. **Update Report Generator** in `src/analysis/comprehensive_prompt_new.py`:
```python
# Add HTML formatting for new section
```

### Add New Embedding Store

1. **Inherit from Base** - Create new class in `src/embeddings/`:
```python
class NewEmbeddingStore:
    def __init__(self):
        self.embedding_model = get_embedding_model()
        self.faiss_index = ...
    
    def embed(self, data: Dict) -> bool:
        ...
    
    def search(self, query: str, top_k: int = 5) -> List:
        ...
```

2. **Register in API** - Update `src/api/app.py`:
```python
new_store = NewEmbeddingStore()
```

### Add New LLM Provider

1. **Extend LLMManager** in `src/llm/llm_manager.py`:
```python
def get_llm(self):
    if self.provider == 'new_provider':
        return NewProviderLLM()
```

2. **Add Configuration** in `src/common/config.py`:
```python
NEW_PROVIDER_API_KEY = os.getenv('NEW_PROVIDER_API_KEY')
```

---

## Debugging & Logging

### Enable Debug Mode

```python
# In analysis
engine = StockAnalysisEngine(debug_mode=True)

# In chat
chat = MultiStockChat(debug_mode=True)
```

### View Logged Data

```bash
# Prompts sent to LLM
ls -la debug_prompts/prompt_*.md

# Responses from LLM
ls -la llm_responses/response_*.txt

# Analysis cache
ls -la llm_responses/ | grep -E "_{stock}_"
```

### Check Embeddings

```python
from src.embeddings import ScreenerEmbeddingStore

store = ScreenerEmbeddingStore()
embeddings_dir = store.embedding_folder / 'ASIANPAINT'
print(f"Index: {embeddings_dir / 'faiss_index.bin'}")
print(f"Metadata: {embeddings_dir / 'metadata.json'}")
```

---

## Performance Optimization

### Caching Strategy
- **Analysis Cache**: 7-day TTL (configurable)
- **Embedding Cache**: FAISS indices persisted to disk
- **LLM Response Cache**: in `llm_responses/`

### Search Optimization
- **Hybrid Scoring**: Balance vector + keyword + numeric
- **FAISS Configuration**: L2 distance, flat index
- **Chunk Size**: 512 tokens optimal for embedding

### API Optimization
- **Async Processing**: Flask-threaded for long operations
- **Response Streaming**: HTML reports generated once
- **Database**: JSON file-based (easily swap for SQL)

---

## Troubleshooting

### Analysis Takes Too Long
- Check if cached: `AnalysisCacheManager.is_valid(stock)`
- Run in debug mode to see step times
- Consider reducing LLM context size

### Search Returns No Results
- Check embeddings exist: `embeddings/screener/{STOCK}/`
- Verify CSV data: `static/{STOCK}/*.csv`
- Re-embed stock: `python embed_screener_data.py`

### LLM Responses Incorrect Format
- Check prompt in `src/analysis/prompts.py`
- Review LLM response in `llm_responses/`
- Test with different LLM provider

### Embedding Memory Issues
- Reduce `max_chunk_size` in config
- Embed stocks in batches
- Check disk space for FAISS indices

---

## Future Roadmap

- [ ] SQL database for caching (replace JSON)
- [ ] Real-time price updates via ticker API
- [ ] Multi-language support
- [ ] WebSockets for real-time chat
- [ ] Custom user dashboards
- [ ] Backtesting integration
- [ ] Portfolio analysis agent
- [ ] News sentiment analysis

---

## References

- **ARCHITECTURE.md** - System structure and organization
- **README.md** - Quick start and usage
- **Code comments** - Detailed function documentation
- **Type hints** - Function signatures and expected inputs/outputs
