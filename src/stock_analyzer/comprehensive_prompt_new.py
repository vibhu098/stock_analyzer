"""Generate complete HTML report by combining 7 detailed sections - RETURNS HTML DIRECTLY."""

def _validate_and_clean_html(html_content: str) -> str:
    """Validate and clean HTML content from LLM output.
    
    Fixes common issues:
    - Removes orphaned closing tags at the end
    - Closes any unclosed <table>, <tbody>, <tr> tags
    - Removes duplicate closing tags
    - Cleans malformed content
    """
    import re
    
    if not html_content:
        return ""
    
    # Remove null bytes and control characters
    html_content = html_content.replace('\x00', '').replace('\ufffd', '')
    
    # Remove orphaned closing tags at the end that don't have matching opening tags
    # and common garbage like </tr></thead></table></section></td></tr></tbody></table></section>
    while re.search(r'</\w+>\s*</\w+>\s*</\w+>\s*</\w+>\s*</\w+>\s*</\w+>\s*$', html_content):
        # Remove the last orphaned tag group
        html_content = re.sub(r'</\w+>\s*</\w+>\s*</\w+>\s*</\w+>\s*</\w+>\s*</\w+>\s*$', '', html_content)
    
    # Remove any remaining orphaned closing tags at the very end
    html_content = re.sub(r'(</\w+>\s*)+$', '', html_content)
    
    # Count opening and closing tags for tables and fix mismatches
    open_tables = html_content.count('<table')
    close_tables = html_content.count('</table>')
    if open_tables > close_tables:
        html_content += '</table>' * (open_tables - close_tables)
    
    open_tbody = html_content.count('<tbody')
    close_tbody = html_content.count('</tbody>')
    if open_tbody > close_tbody:
        html_content += '</tbody>' * (open_tbody - close_tbody)
    
    # Fix incomplete table rows
    # If a <tr> is opened but not closed, close it
    open_tr = html_content.count('<tr')
    close_tr = html_content.count('</tr>')
    if open_tr > close_tr:
        # Find incomplete rows and remove them or close them
        lines = html_content.split('\n')
        in_table = False
        last_tr_line = -1
        for i, line in enumerate(lines):
            if '<table' in line:
                in_table = True
            elif '</table>' in line:
                in_table = False
            elif in_table and '<tr' in line and '</tr>' not in line:
                last_tr_line = i
        
        # If we found an incomplete row, close it
        if last_tr_line >= 0 and last_tr_line < len(lines) - 1:
            lines[last_tr_line] = lines[last_tr_line].rstrip() + '</tr>'
            html_content = '\n'.join(lines)
        elif last_tr_line == len(lines) - 1:
            # Row is at the very end, just remove it
            lines.pop()
            html_content = '\n'.join(lines)
    
    # Remove '%' garbage character that sometimes appears at the end
    html_content = html_content.rstrip('%').rstrip()
    
    return html_content


def _extract_recommendation(valuation_html: str) -> dict:
    """Extract recommendation, target price, and upside from valuation section HTML."""
    import re

    valuation_html = _validate_and_clean_html(valuation_html)

    result = {
        'recommendation': 'HOLD',
        'recommendation_class': 'neutral',
        'target_price_range': '—',
        'upside_downside': '—',
    }

    if not valuation_html:
        return result

    # Strip HTML tags to plain text for easier parsing
    plain = re.sub(r'<[^>]+>', ' ', valuation_html)
    plain = re.sub(r'\s+', ' ', plain)

    # --- Recommendation (BUY / STRONG BUY / HOLD / REDUCE / SELL) ---
    rec_match = re.search(
        r'Recommendation[:\s]+([A-Z][A-Z\s/]{2,20}?)(?:\s*\||\s*<|\s+Target|\s+Price|\s+Upside)',
        plain, re.IGNORECASE
    )
    if not rec_match:
        # Fallback: look for standalone BUY/SELL/HOLD keywords near "recommendation"
        rec_match = re.search(
            r'\b(STRONG\s+BUY|STRONG\s+SELL|BUY|SELL|REDUCE|HOLD|ACCUMULATE)\b',
            plain, re.IGNORECASE
        )
    if rec_match:
        rec_text = rec_match.group(1).strip().upper()
        result['recommendation'] = rec_text
        if 'BUY' in rec_text or 'ACCUMULATE' in rec_text:
            result['recommendation_class'] = 'bullish'
        elif 'SELL' in rec_text or 'REDUCE' in rec_text:
            result['recommendation_class'] = 'bearish'
        else:
            result['recommendation_class'] = 'neutral'

    # --- Target Price Range (₹XXXX or ₹XXXX-XXXX) ---
    target_match = re.search(
        r'Target\s*(?:Price)?\s*(?:Range)?[:\s]+(₹[\d,]+(?:\s*[-–]\s*[\d,₹]+)?)',
        plain, re.IGNORECASE
    )
    if not target_match:
        target_match = re.search(r'(₹\s*[\d,]{3,}(?:\s*[-–]\s*[\d,]+)?)', plain)
    if target_match:
        result['target_price_range'] = target_match.group(1).strip()

    # --- Upside / Downside % ---
    upside_match = re.search(
        r'Upside[:/\s]+([+\-]?\s*\d+\.?\d*\s*%)',
        plain, re.IGNORECASE
    )
    if not upside_match:
        upside_match = re.search(
            r'(?:upside|downside|expected\s+return)[^\d%]*([+\-]?\d+\.?\d*\s*%)',
            plain, re.IGNORECASE
        )
    if upside_match:
        result['upside_downside'] = upside_match.group(1).strip()

    return result


def generate_comprehensive_html_report(stock_symbol: str, analysis_results: dict) -> str:
    """Generate complete HTML report by directly combining 7 detailed section outputs.
    
    CRITICAL CHANGE: This returns COMPLETE HTML directly, not a prompt.
    The 7 sections are ALREADY detailed from parallel LLM calls.
    We just combine them with professional styling.
    
    Args:
        stock_symbol: Stock ticker symbol
        analysis_results: Dict with all 7 ALREADY-DETAILED HTML sections
        
    Returns:
        Complete HTML report string - ready to save as .html file
    """
    from datetime import datetime
    
    # Extract sections - these are ALREADY detailed HTML from 7 parallel calls
    # CLEAN each section to fix any malformed HTML from LLM output
    co = _validate_and_clean_html(analysis_results.get('company_overview', '')) or '<p>Company overview data pending</p>'
    qa = _validate_and_clean_html(analysis_results.get('quantitative_analysis', '')) or '<p>Quantitative analysis pending</p>'
    qla = _validate_and_clean_html(analysis_results.get('qualitative_analysis', '')) or '<p>Qualitative analysis pending</p>'
    sa = _validate_and_clean_html(analysis_results.get('shareholding_analysis', '')) or '<p>Shareholding analysis pending</p>'
    it = _validate_and_clean_html(analysis_results.get('investment_thesis', '')) or '<p>Investment thesis pending</p>'
    vr = _validate_and_clean_html(analysis_results.get('valuation_recommendation', '')) or '<p>Valuation pending</p>'
    cncl = _validate_and_clean_html(analysis_results.get('conclusion', '')) or '<p>Conclusion pending</p>'
    
    # Extract recommendation for header box
    rec = _extract_recommendation(vr)
    
    report_date = datetime.now().strftime('%B %d, %Y')
    
    # Generate and return COMPLETE HTML directly
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{stock_symbol} — Equity Analysis Report</title>
<style>
:root {{
  --navy: #0D1B2A;
  --ink: #1A2B3C;
  --gold: #D4A017;
  --text: #2C3E50;
  --muted: #6B7C93;
  --light: #F5F7FA;
  --white: #FFFFFF;
}}

* {{ box-sizing: border-box; margin: 0; padding: 0; }}

body {{
  font-family: 'Segoe UI', Arial, sans-serif;
  background: var(--light);
  color: var(--text);
  font-size: 13px;
  line-height: 1.5;
}}

.page {{ max-width: 960px; margin: 0 auto; background: var(--white); box-shadow: 0 4px 30px rgba(0,0,0,0.1); }}

.header {{
  background: linear-gradient(135deg, var(--navy) 0%, var(--ink) 100%);
  color: var(--white);
  padding: 36px 50px;
}}

.header h1 {{
  font-size: 34px;
  font-weight: bold;
  margin-bottom: 6px;
}}

.header h2 {{
  font-size: 14px;
  font-weight: 300;
  color: rgba(255,255,255,0.7);
  margin-top: 4px;
}}

.header-meta {{
  display: flex;
  gap: 24px;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid rgba(255,255,255,0.2);
  flex-wrap: wrap;
  font-size: 11px;
}}

.meta-label {{
  color: var(--gold);
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 1px;
}}

.recommendation-box {{
  background: rgba(255, 255, 255, 0.95);
  border: 2px solid var(--gold);
  border-radius: 6px;
  padding: 18px 24px;
  margin: 18px 0 0 0;
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 16px;
}}

.rec-item {{
  text-align: center;
  border-right: 1px solid #E0E0E0;
  padding-right: 12px;
}}

.rec-item:last-child {{
  border-right: none;
  padding-right: 0;
}}

.rec-label {{
  font-size: 10px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 1px;
  font-weight: 600;
  margin-bottom: 4px;
}}

.rec-value {{
  font-size: 16px;
  font-weight: bold;
  color: var(--navy);
}}

.rec-value.bullish {{ color: #27AE60; }}
.rec-value.bearish {{ color: #C0392B; }}
.rec-value.neutral {{ color: var(--navy); }}

.content {{ padding: 36px 50px; }}

.section {{
  margin-bottom: 36px;
  page-break-inside: avoid;
}}

.section h2 {{
  font-size: 18px;
  color: var(--navy);
  border-bottom: 2px solid var(--gold);
  padding-bottom: 8px;
  margin-bottom: 16px;
}}

.section h3 {{
  font-size: 14px;
  color: var(--ink);
  margin-top: 16px;
  margin-bottom: 8px;
}}

.section h4 {{
  font-size: 13px;
  color: var(--text);
  font-weight: bold;
  margin-top: 12px;
  margin-bottom: 6px;
}}

p {{ margin-bottom: 8px; line-height: 1.5; }}

table {{
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  background: var(--white);
  font-size: 12px;
}}

table thead tr {{
  background: var(--navy);
  color: var(--white);
}}

table th {{
  padding: 8px 10px;
  text-align: left;
  font-weight: 600;
}}

table tbody tr {{
  border-bottom: 1px solid #E0E0E0;
}}

table tbody tr:nth-child(even) {{
  background: var(--light);
}}

table tbody td {{
  padding: 7px 10px;
}}

.positive {{ color: #27AE60; font-weight: bold; }}
.negative {{ color: #C0392B; font-weight: bold; }}
.neutral {{ color: var(--muted); }}

.key-takeaways {{
  background: var(--light);
  border-left: 4px solid var(--gold);
  padding: 15px;
  margin: 15px 0;
  border-radius: 4px;
}}

.key-takeaways strong {{
  display: block;
  margin-bottom: 8px;
  color: var(--navy);
}}

.key-takeaways ul {{
  margin-left: 20px;
}}

.key-takeaways li {{
  margin-bottom: 4px;
  line-height: 1.4;
}}

ul, ol {{
  margin: 6px 0 8px 20px;
  padding: 0;
}}

li {{
  margin-bottom: 4px;
  line-height: 1.45;
}}

.footer {{
  background: var(--navy);
  color: var(--white);
  padding: 20px 50px;
  font-size: 11px;
  line-height: 1.5;
  margin-top: 30px;
}}

@media print {{
  body {{ background: white; }}
  .page {{ box-shadow: none; }}
  .section {{ page-break-inside: avoid; }}
}}
</style>
</head>
<body>

<div class="page">
  
  <div class="header">
    <h1>{stock_symbol}</h1>
    <h2>Equity Analysis Report</h2>
    <div class="header-meta">
      <div><span class="meta-label">Report Date:</span> {report_date}</div>
      <div><span class="meta-label">Analysis Type:</span> Fundamental Equity Research</div>
    </div>
    <div class="recommendation-box">
      <div class="rec-item">
        <div class="rec-label">Recommendation</div>
        <div class="rec-value {rec['recommendation_class']}">{rec['recommendation']}</div>
      </div>
      <div class="rec-item">
        <div class="rec-label">12M Target Price</div>
        <div class="rec-value">{rec['target_price_range']}</div>
      </div>
      <div class="rec-item">
        <div class="rec-label">Upside / Downside</div>
        <div class="rec-value">{rec['upside_downside']}</div>
      </div>
    </div>
  </div>

  <div class="content">

    <section class="section">
      <h2>1. Company Overview</h2>
      {co}
    </section>

    <section class="section">
      <h2>2. Quantitative Analysis</h2>
      {qa}
    </section>

    <section class="section">
      <h2>3. Qualitative Analysis</h2>
      {qla}
    </section>

    <section class="section">
      <h2>4. Shareholding Pattern Analysis</h2>
      {sa}
    </section>

    <section class="section">
      <h2>5. Investment Thesis</h2>
      {it}
    </section>

    <section class="section">
      <h2>6. Valuation and Recommendation</h2>
      {vr}
    </section>

    <section class="section">
      <h2>7. Conclusion</h2>
      {cncl}
    </section>

  </div>

  <div class="footer">
    <strong>Disclaimer:</strong> This report is for informational purposes only. It does not constitute investment advice. Please consult with a qualified financial advisor before making investment decisions.
  </div>

</div>

</body>
</html>"""
    
    return html
