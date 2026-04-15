"""
Screener.in data extractor using Playwright.
Extracts key metrics, quarterly results, P&L, balance sheet, cash flow, and growth metrics.
"""

import asyncio
import re
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict
import logging

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("❌ Playwright not installed. Run: pip install playwright")
    exit(1)

from .csv_cleaner import CSVCleaner
from src.embeddings import ScreenerEmbeddingStore

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


async def fetch_and_save_screener_data(screener_url: str):
    """
    Fetch data from Screener.in, save as CSV files, and create embeddings.
    
    Args:
        screener_url: Full URL to screener.in company page
        Example: https://www.screener.in/company/HDFCBANK/
    """
    logger.info(f"📊 Fetching data from Screener: {screener_url}\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        try:
            # Navigate to page
            response = await page.goto(screener_url, wait_until='networkidle')
            logger.info(f"✅ Response status: {response.status}")
            
            # Wait for dynamic content to load
            logger.info("⏳ Waiting for dynamic content to load...")
            await page.wait_for_timeout(5000)
            
            # Scroll to load all content
            logger.info("📜 Scrolling to load all content...")
            for _ in range(12):
                await page.evaluate("() => window.scrollBy(0, 1200)")
                await page.wait_for_timeout(400)
            
            # Scroll back to top
            await page.evaluate("() => window.scrollTo(0, 0)")
            
            # Get full HTML and text
            page_html = await page.content()
            page_text = await page.evaluate("() => document.body.innerText")
            
            # Extract symbol from URL
            symbol_match = re.search(r'/company/([A-Z0-9&]+)/', screener_url)
            symbol = symbol_match.group(1) if symbol_match else 'STOCK'
            
            logger.info(f"📈 Stock Symbol: {symbol}\n")
            
            # Create directory
            base_path = Path(__file__).parent.parent.parent / 'static' / symbol
            base_path.mkdir(parents=True, exist_ok=True)
            
            # Save raw HTML and text
            with open(base_path / 'screener_page_content.html', 'w', encoding='utf-8') as f:
                f.write(page_html)
            with open(base_path / 'screener_page_content.txt', 'w', encoding='utf-8') as f:
                f.write(page_text)
            
            logger.info("✅ Saved: screener_page_content.html & screener_page_content.txt\n")
            
            # Extract all data
            csv_files = generate_all_csvs(page_text, screener_url, symbol)
            
            logger.info(f"📁 Extracting and cleaning CSV files to: {base_path}\n")
            
            # Save CSV files with cleaning
            saved_count = 0
            for file_info in csv_files:
                if file_info['data']:
                    logger.info(f"🔄 Processing {file_info['name']}...")
                    save_csv(base_path / file_info['name'], file_info['data'])
                    saved_count += 1
            
            logger.info(f"\n✅ Processed {saved_count} CSV files with data cleaning and validation")
            
            logger.info(f"\n✅ All CSV files saved successfully!")
            
            # Create embeddings for this stock
            logger.info(f"\n🔄 Creating embeddings for {symbol}...\n")
            store = ScreenerEmbeddingStore()
            success = store.embed_stock(symbol)
            
            if success:
                logger.info(f"✅ Embeddings created successfully for {symbol}!")
            else:
                logger.error(f"❌ Failed to create embeddings for {symbol}")
            
        except Exception as e:
            logger.error(f"❌ Error: {str(e)}")
            raise
        finally:
            await browser.close()


def generate_all_csvs(page_text: str, screener_url: str, symbol: str) -> List[Dict]:
    """Generate all CSV file data."""
    return [
        {
            'name': 'key_metrics.csv',
            'data': extract_key_metrics(page_text)
        },
        {
            'name': 'quarterly_results.csv',
            'data': extract_quarterly_results(page_text)
        },
        {
            'name': 'profit_and_loss_annual.csv',
            'data': extract_profit_and_loss_annual(page_text)
        },
        {
            'name': 'balance_sheet.csv',
            'data': extract_balance_sheet(page_text)
        },
        {
            'name': 'cash_flow.csv',
            'data': extract_cash_flow(page_text)
        },
        {
            'name': 'growth_metrics.csv',
            'data': extract_growth_metrics(page_text)
        },
        {
            'name': 'ratios.csv',
            'data': extract_ratios(page_text)
        },
        {
            'name': 'source_reference.csv',
            'data': [{
                'Data Source': 'Screener',
                'URL': screener_url,
                'Stock Symbol': symbol,
                'Fetch Date': datetime.now().strftime('%Y-%m-%d'),
                'Data Includes': 'Key Metrics, Quarterly Results, Annual P&L, Balance Sheet, Cash Flow, Growth Metrics, Ratios'
            }]
        }
    ]


def extract_ratios(text: str) -> List[Dict[str, str]]:
    """Extract year-wise financial ratios (ROCE%, efficiency ratios) from Ratios section."""
    results = []

    try:
        lines = text.split('\n')

        # Find the second 'Ratios' heading (after Cash Flows)
        ratios_indices = [i for i, l in enumerate(lines) if l.strip() == 'Ratios']
        if not ratios_indices:
            return results
        # Use the last occurrence (after Cash Flows section)
        ratios_start = ratios_indices[-1]

        # End boundary: Shareholding Pattern
        end_idx = next(
            (i for i, l in enumerate(lines[ratios_start:], start=ratios_start) if 'Shareholding' in l),
            len(lines)
        )

        # Find header row with years
        header_idx = -1
        years = []
        for i in range(ratios_start, end_idx):
            if any(x in lines[i] for x in ['Mar', 'Sep', 'Jun', 'Dec']) and re.search(r'\d{4}', lines[i]):
                year_cells = re.findall(r'(?:Mar|Jun|Sep|Dec)\s+\d{4}', lines[i])
                if year_cells:
                    header_idx = i
                    years = year_cells
                    break

        if header_idx < 0 or not years:
            return results

        metrics_to_find = [
            'Debtor Days', 'Inventory Days', 'Days Payable',
            'Cash Conversion Cycle', 'Working Capital Days', 'ROCE %',
        ]

        for i in range(header_idx + 1, end_idx):
            line = lines[i].strip()
            if not line:
                continue

            parts = line.split('\t')
            if len(parts) < 2:
                # Try splitting on multiple spaces as fallback
                parts = re.split(r'\s{2,}', line)
            if len(parts) < 2:
                continue

            metric = parts[0].strip()
            if any(m in metric for m in metrics_to_find):
                row = {'Metric': metric}
                for y_idx, year in enumerate(years):
                    if y_idx + 1 < len(parts):
                        row[year] = parts[y_idx + 1].strip()
                row['Unit'] = '%' if '%' in metric else 'Days'
                row['Source'] = 'Screener'
                results.append(row)

    except Exception as e:
        logger.error(f"Ratios error: {str(e)}")

    return results


def extract_key_metrics(text: str) -> List[Dict[str, str]]:
    """Extract key metrics from page text."""
    metrics = []
    patterns = [
        ('Market Cap', r'Market Cap\s+(₹[\s\d,]+\s+Cr)', 'Cr'),
        ('Current Price', r'Current Price\s+(₹\s+[\d,]+)', '₹'),
        ('Stock P/E', r'Stock P/E\s+([\d.]+)', 'x'),
        ('Book Value', r'Book Value\s+(₹\s+[\d,]+)', '₹'),
        ('Dividend Yield', r'Dividend Yield\s+([\d.]+\s*%)', '%'),
        ('ROCE', r'ROCE\s+([\d.]+\s*%)', '%'),
        ('ROE', r'ROE\s+([\d.]+\s*%)', '%'),
        ('Face Value', r'Face Value\s+(₹\s+[\d.]+)', '₹'),
    ]
    
    for name, pattern, unit in patterns:
        match = re.search(pattern, text)
        if match:
            metrics.append({
                'Metric': name,
                'Value': match.group(1).strip(),
                'Unit': unit,
                'Source': 'Screener',
                'Data Point': 'Current snapshot'
            })
    
    return metrics


def extract_quarterly_results(text: str) -> List[Dict[str, str]]:
    """Extract quarterly results."""
    results = []
    
    quarter_match = re.search(r'Quarterly Results[\s\S]*?(?=Profit & Loss)', text)
    if not quarter_match:
        return [{'Metric': 'No data found', 'Source': 'Screener'}]
    
    quarter_text = quarter_match.group(0)
    lines = quarter_text.split('\n')
    
    # Find header row
    header_idx = -1
    quarters = []
    for i, line in enumerate(lines):
        if any(q in line for q in ['Dec', 'Mar', 'Jun', 'Sep']) and '\t' in line:
            if re.search(r'\d{4}|[A-Z][a-z]{2}', line):
                header_idx = i
                quarters = [q.strip() for q in line.split('\t')[1:] if q.strip() and re.search(r'\d{4}|[A-Z][a-z]{2}', q.strip())]
                break
    
    if header_idx < 0 or not quarters:
        return [{'Metric': 'No data found', 'Source': 'Screener'}]
    
    metrics_to_find = [
        'Sales', 'Revenue', 'Operating Profit', 'OPM',
        'Other Income', 'Interest', 'Net Profit', 'EPS in Rs',
        'Expenses', 'Profit', 'Dividend', 'Depreciation',
    ]
    
    for i in range(header_idx + 1, len(lines)):
        line = lines[i].strip()
        if not line or line.startswith('View'):
            continue
        
        parts = line.split('\t')
        if len(parts) < 2:
            continue
        
        metric = parts[0].strip()
        
        # Check if this is a metric we want
        if any(m in metric for m in metrics_to_find):
            row = {'Metric': metric}
            for q_idx, quarter in enumerate(quarters):
                if q_idx + 1 < len(parts):
                    row[quarter] = parts[q_idx + 1].strip()
            if 'EPS' in metric:
                row['Unit'] = '₹'
            elif '%' in metric or 'OPM' in metric:
                row['Unit'] = '%'
            else:
                row['Unit'] = 'Cr'
            row['Source'] = 'Screener'
            results.append(row)
    
    return results if results else [{'Metric': 'No data found', 'Source': 'Screener'}]


def extract_profit_and_loss_annual(text: str) -> List[Dict[str, str]]:
    """Extract annual profit and loss data."""
    results = []
    
    try:
        lines = text.split('\n')
        
        # Find P&L section
        pl_start_idx = -1
        for i, line in enumerate(lines):
            if 'Profit & Loss' in line and i > 30:
                pl_start_idx = i
                break
        
        if pl_start_idx < 0:
            return results
        
        # Find Balance Sheet section (end boundary)
        bs_start_idx = next((i for i, l in enumerate(lines[pl_start_idx:], start=pl_start_idx) if 'Balance Sheet' in l), len(lines))
        end_idx = bs_start_idx if bs_start_idx > pl_start_idx else len(lines)
        
        # Find header row with years
        header_idx = -1
        years = []
        for i in range(pl_start_idx, end_idx):
            if any(x in lines[i] for x in ['Mar', 'FY']) and '\t' in lines[i]:
                if re.search(r'\d{4}|TTM|FY', lines[i]):
                    header_idx = i
                    year_cells = [y.strip() for y in lines[i].split('\t')[1:] if y.strip() and re.search(r'\d{4}|TTM|FY', y.strip())]
                    years = year_cells
                    break
        
        if header_idx < 0 or not years:
            return results
        
        metrics_to_find = [
            'Sales', 'Revenue', 'Operating Profit', 'OPM', 'Other Income',
            'Depreciation', 'Interest', 'Profit before tax',
            'Tax', 'Net Profit', 'EPS in Rs', 'Dividend',
        ]
        
        for i in range(header_idx + 1, end_idx):
            line = lines[i].strip()
            if not line or line.startswith('View'):
                continue
            
            parts = line.split('\t')
            if len(parts) < 2:
                continue
            
            metric = parts[0].strip()
            
            if any(m in metric for m in metrics_to_find):
                row = {'Metric': metric}
                for y_idx, year in enumerate(years):
                    if y_idx + 1 < len(parts):
                        row[year] = parts[y_idx + 1].strip()
                
                if 'EPS' in metric:
                    row['Unit'] = '₹'
                elif '%' in metric or 'OPM' in metric:
                    row['Unit'] = '%'
                else:
                    row['Unit'] = 'Cr'
                
                row['Source'] = 'Screener'
                results.append(row)
    
    except Exception as e:
        logger.error(f"P&L error: {str(e)}")
    
    return results


def extract_balance_sheet(text: str) -> List[Dict[str, str]]:
    """Extract balance sheet data."""
    results = []
    
    try:
        lines = text.split('\n')
        
        # Find Balance Sheet section
        bs_start_idx = -1
        for i, line in enumerate(lines):
            if 'Balance Sheet' in line and i > 100:
                bs_start_idx = i
                break
        
        if bs_start_idx < 0:
            return results
        
        # Find Cash Flows section (end boundary)
        cf_start_idx = next((i for i, l in enumerate(lines[bs_start_idx:], start=bs_start_idx) if 'Cash Flows' in l), len(lines))
        end_idx = cf_start_idx if cf_start_idx > bs_start_idx else len(lines)
        
        # Find header row with years
        header_idx = -1
        years = []
        for i in range(bs_start_idx, end_idx):
            if any(x in lines[i] for x in ['Mar', 'Sep']) and '\t' in lines[i]:
                if re.search(r'\d{4}', lines[i]):
                    header_idx = i
                    year_cells = [y.strip() for y in lines[i].split('\t')[1:] if y.strip() and re.search(r'\d{4}', y.strip())]
                    years = year_cells
                    break
        
        if header_idx < 0 or not years:
            return results
        
        metrics_to_find = ['Equity Capital', 'Reserves', 'Deposits', 'Borrowing', 'Other Liabilities', 
                          'Total Liabilities', 'Fixed Assets', 'CWIP', 'Investments', 'Other Assets', 'Total Assets']
        
        for i in range(header_idx + 1, end_idx):
            line = lines[i].strip()
            if not line or line.startswith('View'):
                continue
            
            parts = line.split('\t')
            if len(parts) < 2:
                continue
            
            metric = parts[0].strip()
            
            if any(m in metric for m in metrics_to_find):
                row = {'Metric': metric}
                for y_idx, year in enumerate(years):
                    if y_idx + 1 < len(parts):
                        row[year] = parts[y_idx + 1].strip()
                row['Unit'] = 'Cr'
                row['Source'] = 'Screener'
                results.append(row)
    
    except Exception as e:
        logger.error(f"Balance Sheet error: {str(e)}")
    
    return results


def extract_cash_flow(text: str) -> List[Dict[str, str]]:
    """Extract cash flow data."""
    results = []
    
    try:
        lines = text.split('\n')
        
        # Find Cash Flows section
        cf_start_idx = -1
        for i, line in enumerate(lines):
            if 'Cash Flows' in line and i > 150:
                cf_start_idx = i
                break
        
        if cf_start_idx < 0:
            return results
        
        # Find Ratios section (end boundary)
        ratios_idx = next((i for i, l in enumerate(lines[cf_start_idx:], start=cf_start_idx) if 'Ratios' in l), len(lines))
        end_idx = ratios_idx if ratios_idx > cf_start_idx else len(lines)
        
        # Find header row
        header_idx = -1
        years = []
        for i in range(cf_start_idx, end_idx):
            if any(x in lines[i] for x in ['Mar', 'Sep']) and '\t' in lines[i]:
                if re.search(r'\d{4}', lines[i]):
                    header_idx = i
                    year_cells = [y.strip() for y in lines[i].split('\t')[1:] if y.strip() and re.search(r'\d{4}', y.strip())]
                    years = year_cells
                    break
        
        if header_idx < 0 or not years:
            return results
        
        metrics_to_find = ['Cash from Operating Activity', 'Cash from Investing Activity', 
                          'Cash from Financing Activity', 'Net Cash Flow']
        
        for i in range(header_idx + 1, end_idx):
            line = lines[i].strip()
            if not line or line.startswith('View'):
                continue
            
            parts = line.split('\t')
            if len(parts) < 2:
                continue
            
            metric = parts[0].strip()
            
            if any(m in metric for m in metrics_to_find):
                row = {'Metric': metric}
                for y_idx, year in enumerate(years):
                    if y_idx + 1 < len(parts):
                        row[year] = parts[y_idx + 1].strip()
                row['Unit'] = 'Cr'
                row['Source'] = 'Screener'
                results.append(row)
    
    except Exception as e:
        logger.error(f"Cash Flow error: {str(e)}")
    
    return results


def extract_growth_metrics(text: str) -> List[Dict[str, str]]:
    """Extract growth metrics."""
    results = []
    
    periods = ['10 Years', '5 Years', '3 Years', 'TTM', '1 Year', 'Last Year']
    
    # Compounded Sales Growth
    sales_growth_match = re.search(r'Compounded Sales Growth[\s\S]*?(?=Compounded Profit Growth|Stock Price|Return)', text)
    if sales_growth_match:
        sales_text = sales_growth_match.group(0)
        for period in periods:
            match = re.search(rf'{period}:?\s+(\d+)', sales_text, re.IGNORECASE)
            if match:
                results.append({
                    'Metric': f'Compounded Sales Growth ({period})',
                    'Value': match.group(1),
                    'Unit': '%',
                    'Category': 'Growth',
                    'Source': 'Screener'
                })
    
    # Compounded Profit Growth
    profit_growth_match = re.search(r'Compounded Profit Growth[\s\S]*?(?=Stock Price CAGR|Return on)', text)
    if profit_growth_match:
        profit_text = profit_growth_match.group(0)
        for period in periods:
            match = re.search(rf'{period}:?\s+(\d+)', profit_text, re.IGNORECASE)
            if match:
                results.append({
                    'Metric': f'Compounded Profit Growth ({period})',
                    'Value': match.group(1),
                    'Unit': '%',
                    'Category': 'Growth',
                    'Source': 'Screener'
                })
    
    # Stock Price CAGR
    cagr_match = re.search(r'Stock Price CAGR[\s\S]*?(?=Return on Equity)', text)
    if cagr_match:
        cagr_text = cagr_match.group(0)
        for period in periods:
            match = re.search(rf'{period}:?\s+(\d+)', cagr_text, re.IGNORECASE)
            if match:
                results.append({
                    'Metric': f'Stock Price CAGR ({period})',
                    'Value': match.group(1),
                    'Unit': '%',
                    'Category': 'Valuation',
                    'Source': 'Screener'
                })
    
    # Return on Equity
    roe_match = re.search(r'Return on Equity[\s\S]*?(?=Balance Sheet|Shareholding)', text)
    if roe_match:
        roe_text = roe_match.group(0)
        for period in periods:
            match = re.search(rf'{period}:?\s+(\d+)', roe_text, re.IGNORECASE)
            if match:
                results.append({
                    'Metric': f'Return on Equity ({period})',
                    'Value': match.group(1),
                    'Unit': '%',
                    'Category': 'Profitability',
                    'Source': 'Screener'
                })
    
    return results


def save_csv(file_path: Path, data: List[Dict[str, str]]):
    """Save data to CSV file with automatic cleaning based on file type."""
    if not data:
        return
    
    # Clean data based on file type
    filename = file_path.name
    cleaned_data = data
    
    try:
        if filename == 'key_metrics.csv':
            cleaned_data = CSVCleaner.clean_key_metrics(data)
            if not CSVCleaner.validate_data_completeness(cleaned_data, min_percent_complete=0.5):
                logger.warning(f"⚠️  {filename}: Data completeness low, proceeding anyway")
        
        elif filename == 'ratios.csv':
            cleaned_data = CSVCleaner.clean_ratios(data)
            if not CSVCleaner.validate_data_completeness(cleaned_data):
                logger.warning(f"⚠️  {filename}: Data completeness low, proceeding anyway")
        
        elif filename in ['profit_and_loss_annual.csv', 'quarterly_results.csv']:
            cleaned_data = CSVCleaner.clean_financial_table(data, expected_metrics=['Sales', 'Revenue', 'Profit', 'EPS'])
            if not CSVCleaner.validate_data_completeness(cleaned_data):
                logger.warning(f"⚠️  {filename}: Data completeness low, proceeding anyway")
        
        elif filename == 'balance_sheet.csv':
            cleaned_data = CSVCleaner.clean_financial_table(data, expected_metrics=['Assets', 'Liabilities', 'Equity'])
            if not CSVCleaner.validate_data_completeness(cleaned_data):
                logger.warning(f"⚠️  {filename}: Data completeness low, proceeding anyway")
        
        elif filename == 'cash_flow.csv':
            cleaned_data = CSVCleaner.clean_financial_table(data, expected_metrics=['Operating', 'Investing', 'Financing', 'Cash'])
            if not CSVCleaner.validate_data_completeness(cleaned_data):
                logger.warning(f"⚠️  {filename}: Data completeness low, proceeding anyway")
        
        else:
            # For other files, apply general cleaning
            cleaned_data = data
    
    except Exception as e:
        logger.warning(f"⚠️  Error cleaning {filename}: {str(e)}, saving raw data")
        cleaned_data = data
    
    # Write to CSV
    if cleaned_data:
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=cleaned_data[0].keys())
            writer.writeheader()
            writer.writerows(cleaned_data)
        logger.info(f"   📊 Cleaned and saved: {len(cleaned_data)} rows")
    else:
        logger.warning(f"   ⚠️  No data to save after cleaning: {filename}")


def regen_all_csvs():
    """Regenerate P&L, quarterly, and ratios CSVs for all stocks from saved page text.

    Also creates embeddings for each stock after regenerating CSVs.
    Useful after extractor logic changes — no browser / re-scraping needed.
    Usage: python src/utils/screener_data_extractor.py --regen-all
    """
    base = Path(__file__).parent.parent.parent / 'static'
    updated, skipped = [], []
    
    # Initialize embedding store once
    store = ScreenerEmbeddingStore()

    for stock_dir in sorted(base.iterdir()):
        txt_file = stock_dir / 'screener_page_content.txt'
        if not txt_file.exists():
            skipped.append(stock_dir.name)
            continue
        try:
            text = txt_file.read_text(encoding='utf-8')
            for extractor, filename in [
                (extract_profit_and_loss_annual, 'profit_and_loss_annual.csv'),
                (extract_quarterly_results,      'quarterly_results.csv'),
                (extract_ratios,                 'ratios.csv'),
            ]:
                data = extractor(text)
                if data:
                    save_csv(stock_dir / filename, data)
            
            # Create embeddings for this stock
            logger.info(f"🔄 Creating embeddings for {stock_dir.name}...")
            if store.embed_stock(stock_dir.name):
                logger.info(f"✅ Regenerated and embedded: {stock_dir.name}")
                updated.append(stock_dir.name)
            else:
                logger.warning(f"⚠️  Regenerated CSVs but failed to embed: {stock_dir.name}")
                updated.append(stock_dir.name)
        except Exception as e:
            logger.error(f"❌ Error regenerating {stock_dir.name}: {e}")

    print(f"\n✅ Done. Updated {len(updated)} stocks, skipped {len(skipped)} (no page text).")
    if skipped:
        print(f"⏭️  Skipped: {', '.join(skipped)}")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python src/utils/screener_data_extractor.py <screener_url>")
        print('  python src/utils/screener_data_extractor.py "https://www.screener.in/company/HDFCBANK/"')
        print("\n  python src/utils/screener_data_extractor.py --regen-all")
        print("    Re-generates P&L / quarterly / ratios CSVs and embeddings for all stocks from saved page text.")
        print("\nThis script:")
        print("  1️⃣  Extracts from Screener.in:")
        print("     • Key Metrics (Market Cap, P/E, ROE, ROCE, etc.)")
        print("     • Quarterly Results")
        print("     • Profit & Loss (Annual)")
        print("     • Balance Sheet")
        print("     • Cash Flow")
        print("     • Growth Metrics (CAGR, ROE trends, etc.)")
        print("     • Ratios (ROCE% year-wise, efficiency ratios)")
        print("\n  2️⃣  Cleans CSV data with validation")
        print("\n  3️⃣  Creates FAISS embeddings for cross-stock search")
        print("\nYou can then query: 'Which stocks have P/E < 20?' or 'Show stocks with ROE > 25%'")
        sys.exit(1)

    if sys.argv[1] == '--regen-all':
        regen_all_csvs()
    else:
        asyncio.run(fetch_and_save_screener_data(sys.argv[1]))


if __name__ == '__main__':
    main()
