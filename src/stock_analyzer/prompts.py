"""Concise stock analysis prompts for compact equity research reports."""

# ============================================================================
# SYSTEM PROMPT
# ============================================================================
STOCK_ANALYST_SYSTEM_PROMPT = """You are a professional equity research analyst. Generate CONCISE, high-signal analysis.

CRITICAL RULES:
1. Indian FY = April 1 - March 31. Latest annual = FY24 (Apr 2023 - Mar 2024).
2. Use ONLY provided data. If unavailable, state N/A.
3. OUTPUT: HTML fragments ONLY (no <!DOCTYPE>, <html>, <head>, <style>, <body>, code fences).
4. Use semantic HTML: <h3>, <h4>, <p>, <table>, <ul>, <li>, <strong>, <em>.
5. BE CONCISE: Each section is max 1 page. Avoid repetition. Prioritize insights over description.
6. Tables: max 5-6 columns, use actual numbers, no filler text in cells.
7. Bullets over paragraphs wherever possible.

STRICT HTML RULES:
8. Every opening tag MUST have a matching closing tag.
9. Every <table> MUST have <thead>...</thead> and <tbody>...</tbody>.
10. Every <tr> MUST have </tr>. Every <td>/<th> MUST have closing tag.
11. NO partial tags or incomplete content at the end of output.
12. All text must be inside a tag — never raw text outside tags."""

# ============================================================================
# SECTION PROMPTS — COMPACT FORMAT
# ============================================================================

COMPANY_OVERVIEW_PROMPT = """Write a compact Company Overview for {stock_symbol} using:
{company_data}

OUTPUT 3 PARTS — be brief:

1. SNAPSHOT (1 short paragraph)
   - What the company does, sector, market position, scale (Market Cap, revenue)

2. KEY METRICS TABLE
   <table><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>
   Include: Market Cap, CMP, P/E, Book Value, ROE, ROCE, Div Yield, Face Value
   </tbody></table>

3. RECENT DEVELOPMENTS (bullet list, max 4 items)
   - Only significant: new launches, acquisitions, regulatory events, management changes

HTML only. No CSS. No style tags."""

QUANTITATIVE_ANALYSIS_PROMPT = """Write compact Quantitative Analysis for {stock_symbol}:
{quantitative_data}

OUTPUT 3 PARTS:

1. P&L SUMMARY TABLE (5 years)
   Columns: Metric | FY20 | FY21 | FY22 | FY23 | FY24
   Rows: Revenue (₹Cr), Operating Profit (₹Cr), Net Profit (₹Cr), EPS (₹), OPM %

2. KEY RATIOS TABLE (5 years)
   Columns: Ratio | FY20 | FY21 | FY22 | FY23 | FY24
   Rows: ROE %, ROCE %, Debt/Equity, Current Ratio, P/E

3. ANALYSIS BULLETS (max 5 bullets)
   - Key trend observations
   - Notable improvements or deteriorations
   - Cash flow quality (OCF vs PAT)
   - Peer comparison if data available

HTML only. Tables only where data is available. No filler rows."""

QUALITATIVE_ANALYSIS_PROMPT = """Write compact Qualitative Analysis for {stock_symbol}:
{qualitative_data}

OUTPUT 4 SHORT PARTS:

1. COMPETITIVE MOAT (bullet list, max 4 items)
   - Key competitive advantages (brand, scale, cost, technology, distribution)

2. MANAGEMENT QUALITY (1 short paragraph)
   - Track record, capital allocation, governance highlights

3. GROWTH STRATEGY (bullet list, max 4 items)
   - Key growth initiatives and expected timelines

4. RISKS (two-column table)
   Columns: Risk | Severity (High/Medium/Low)
   Max 5 risks across: regulatory, competitive, operational, financial

HTML only. Keep each part concise — no lengthy sub-paragraphs."""

SHAREHOLDING_ANALYSIS_PROMPT = """Write compact Shareholding Analysis for {stock_symbol}:
{shareholding_data}

OUTPUT 2 PARTS:

1. SHAREHOLDING TABLE (latest 3 quarters)
   Columns: Category | Q-2 | Q-1 | Latest | Change
   Rows: Promoter, FII, DII, Public/Others

2. KEY OBSERVATIONS (bullet list, max 4 items)
   - Promoter pledge status
   - FII/DII trend direction
   - Any notable buying/selling
   - Free float and liquidity note

HTML only. No lengthy paragraphs."""

INVESTMENT_THESIS_PROMPT = """Write compact Investment Thesis for {stock_symbol}.

OUTPUT 4 SHORT PARTS:

1. CORE THESIS (1 paragraph)
   - Why invest? Key return driver. Current valuation context.

2. GROWTH DRIVERS (bullet list, max 4 items)
   - Specific driver, expected timeline, financial impact

3. CATALYSTS (two-column table)
   Columns: Catalyst | Timeline
   Rows: 3-4 near/medium-term catalysts

4. RISKS (bullet list, max 4 items)
   - Specific risk + probability (High/Medium/Low)

HTML only. Keep every part tight — no repetition from earlier sections."""

VALUATION_AND_RECOMMENDATION_PROMPT = """Write compact Valuation & Recommendation for {stock_symbol}.

OUTPUT 3 PARTS:

1. VALUATION TABLE
   Columns: Method | Fair Value (₹) | Weight | Implied Return (%)
   Rows: P/E Multiple | P/B Multiple | DCF/Earnings Growth | Weighted Average
   Use actual estimated numbers based on data available.

2. RECOMMENDATION SUMMARY BLOCK
   Output this EXACT format (machine-readable, critical for report header):
   <p><strong>Recommendation: BUY</strong> | <strong>Target Price Range: ₹XXXX-XXXX</strong> | <strong>Upside: XX%</strong> | Horizon: 12 months | Risk: Medium</p>
   Replace BUY/HOLD/SELL/REDUCE with actual recommendation.
   Replace ₹XXXX-XXXX with actual 12-month target price range.
   Replace XX% with actual expected upside or downside percentage.

3. RATIONALE (bullet list, max 4 items)
   - Key reasons supporting recommendation with specific data points

CRITICAL HTML RULES:
- Every <table>/<tr>/<td>/<th> MUST have matching closing tag
- NO orphaned or incomplete tags at end of output"""

CONCLUSION_PROMPT = """Write a compact Conclusion for {stock_symbol}.
Do NOT repeat what was covered in Company Overview, Financials, or Valuation sections.

OUTPUT 3 SHORT PARTS:

1. SCENARIO TABLE
   Columns: Scenario | Key Assumption | Fair Value (₹) | Return (%)
   Rows: Bull Case | Base Case | Bear Case

2. KEY RISKS TO MONITOR (bullet list, max 4 items)
   - Specific risk + what metric to watch

3. INVESTMENT GUIDANCE (1 short paragraph)
   - Suitable investor profile, holding period, entry/exit levels

HTML only. Half-page maximum. No repetition.

CRITICAL HTML RULES:
- Every <table>/<tr>/<td>/<th> MUST have matching closing tag
- NO orphaned or incomplete tags at end of output"""

# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'STOCK_ANALYST_SYSTEM_PROMPT',
    'COMPANY_OVERVIEW_PROMPT',
    'QUANTITATIVE_ANALYSIS_PROMPT',
    'QUALITATIVE_ANALYSIS_PROMPT',
    'SHAREHOLDING_ANALYSIS_PROMPT',
    'INVESTMENT_THESIS_PROMPT',
    'VALUATION_AND_RECOMMENDATION_PROMPT',
    'CONCLUSION_PROMPT'
]
