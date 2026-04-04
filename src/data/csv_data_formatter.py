"""Format CSV financial data into LLM-friendly table structures."""

import csv
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

def format_quantitative_data_for_llm(stock_symbol: str, project_root: Optional[Path] = None) -> str:
    """
    Load and format P&L and Ratios CSV data for LLM consumption.
    
    Creates organized table structures that the LLM can directly use to create
    proper financial analysis tables.
    
    Args:
        stock_symbol: Stock ticker symbol (e.g., 'ASIANPAINT')
        project_root: Root project directory (auto-detected if not provided)
    
    Returns:
        Formatted data string ready for LLM input
    """
    if project_root is None:
        project_root = Path(__file__).parent.parent.parent
    
    csv_dir = project_root / "static" / stock_symbol
    formatted_data = ""
    
    # Load P&L data
    pl_file = csv_dir / "profit_and_loss_annual.csv"
    if pl_file.exists():
        formatted_data += "=" * 80 + "\n"
        formatted_data += "P&L SUMMARY (Last 5 Years)\n"
        formatted_data += "=" * 80 + "\n"
        
        pl_data = _read_csv_file(pl_file)
        if pl_data:
            # Relevant P&L metrics (with exact names from CSV)
            relevant_metrics = ['Sales', 'Operating Profit', 'OPM %', 'Net Profit', 'EPS']
            formatted_data += _format_table_from_csv(pl_data, relevant_metrics, last_n_years=5)
    
    # Load Ratios data
    ratios_file = csv_dir / "ratios.csv"
    if ratios_file.exists():
        formatted_data += "\n" + "=" * 80 + "\n"
        formatted_data += "KEY RATIOS (Last 5 Years)\n"
        formatted_data += "=" * 80 + "\n"
        
        ratios_data = _read_csv_file(ratios_file)
        if ratios_data:
            # Relevant ratio metrics
            relevant_metrics = ['ROCE %', 'Debtor Days', 'Inventory Days', 'Cash Conversion Cycle']
            formatted_data += _format_table_from_csv(ratios_data, relevant_metrics, last_n_years=5)
    
    # Load Key Metrics for current values (ROE, P/E, etc.)
    key_metrics_file = csv_dir / "key_metrics.csv"
    if key_metrics_file.exists():
        formatted_data += "\n" + "=" * 80 + "\n"
        formatted_data += "CURRENT KEY METRICS (Latest Snapshot)\n"
        formatted_data += "=" * 80 + "\n"
        
        try:
            with open(key_metrics_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    metric = row.get('Metric', '')
                    value = row.get('Value', '')
                    if metric and value:
                        formatted_data += f"{metric:.<40} {value}\n"
        except Exception as e:
            logger.warning(f"Could not load key metrics: {e}")
    
    return formatted_data


def _read_csv_file(filepath: Path) -> list:
    """Read CSV file and return rows as list of dicts."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)  # Get header row
            rows = []
            for row in reader:
                rows.append(row)
            return rows, headers
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None


def _format_table_from_csv(csv_data, metric_names: list, last_n_years: int = 5) -> str:
    """
    Format CSV rows into a readable table showing last N years.
    
    Args:
        csv_data: Tuple of (rows list, headers list) from _read_csv_file
        metric_names: List of metric names to extract (rows starting with these)
        last_n_years: Number of recent years to include
    
    Returns:
        Formatted table string
    """
    rows, headers = csv_data
    
    if not headers:
        return ""
    
    formatted = ""
    
    # Get only year columns (skip Unit and Source columns typically at the end)
    year_columns = [h for h in headers if h not in ['Metric', 'Unit', 'Source', 'Data Point']][-last_n_years:]
    
    if not year_columns:
        return ""
    
    # Build header row with consistent column widths
    metric_col_width = 30
    year_col_width = 14
    
    header_row = "Metric".ljust(metric_col_width)
    for year in year_columns:
        header_row += f" | {year:>{year_col_width-3}}"
    formatted += header_row + "\n"
    formatted += "-" * len(header_row) + "\n"
    
    # Find and format matching metric rows
    for row in rows:
        if not row:
            continue
        
        metric_name = row[0].strip()
        
        # Check if this metric matches any of our requested metrics
        matches = False
        for metric_pattern in metric_names:
            if metric_pattern.lower() in metric_name.lower():
                matches = True
                break
        
        if matches:
            # Get metric name (up to metric_col_width chars)
            line = metric_name[:metric_col_width].ljust(metric_col_width)
            
            # Add values for each year column
            for year_col in year_columns:
                try:
                    col_idx = headers.index(year_col)
                    value = row[col_idx] if col_idx < len(row) else "—"
                    # Right-align numeric values
                    line += f" | {value:>{year_col_width-3}}"
                except (ValueError, IndexError):
                    line += f" | {'—':>{year_col_width-3}}"
            
            formatted += line + "\n"
    
    formatted += "\n"
    return formatted


def load_raw_csv_content(stock_symbol: str, filename: str, project_root: Optional[Path] = None) -> str:
    """Load raw CSV content as formatted text (for debug/fallback)."""
    if project_root is None:
        project_root = Path(__file__).parent.parent.parent
    
    csv_file = project_root / "static" / stock_symbol / filename
    
    if not csv_file.exists():
        return f"File not found: {filename}"
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"


def format_key_metrics_for_llm(stock_symbol: str, project_root: Optional[Path] = None) -> str:
    """Load and format current key metrics as a simple list for LLM."""
    if project_root is None:
        project_root = Path(__file__).parent.parent.parent
    
    csv_file = project_root / "static" / stock_symbol / "key_metrics.csv"
    
    if not csv_file.exists():
        return "Key metrics file not found"
    
    formatted = "CURRENT KEY METRICS (Latest Snapshot):\n"
    formatted += "=" * 60 + "\n"
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                metric = row.get('Metric', '')
                value = row.get('Value', '')
                if metric and value:
                    formatted += f"{metric:.<45} {value}\n"
    except Exception as e:
        logger.warning(f"Could not load key metrics: {e}")
        return f"Error loading key metrics: {str(e)}"
    
    return formatted


def format_shareholding_data_for_llm(stock_symbol: str, project_root: Optional[Path] = None) -> str:
    """Extract and format shareholding pattern data from screener content."""
    if project_root is None:
        project_root = Path(__file__).parent.parent.parent
    
    screener_file = project_root / "static" / stock_symbol / "screener_page_content.txt"
    
    if not screener_file.exists():
        return "Shareholding data not available"
    
    try:
        with open(screener_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        formatted = "SHAREHOLDING PATTERN (from Screener data):\n"
        formatted += "=" * 60 + "\n"
        
        # Extract shareholding section (raw text format from screener)
        if "Shareholding Pattern" in content:
            # Find the shareholding section
            start_idx = content.find("Shareholding Pattern")
            end_idx = content.find("\n2d -", start_idx)  # Stop before news/updates
            
            if start_idx != -1:
                shareholding_section = content[start_idx:end_idx] if end_idx != -1 else content[start_idx:start_idx+1000]
                
                # Clean up the text
                shareholding_section = shareholding_section.replace("Shareholding Pattern\n", "")
                shareholding_section = shareholding_section.replace("+", "").strip()
                
                formatted += shareholding_section + "\n\n"
        
        formatted += "NOTE: Categories = Promoters, FIIs, DIIs, Others\n"
        formatted += "Format: Latest holding% across recent quarters\n"
        
        return formatted
    except Exception as e:
        logger.warning(f"Could not load shareholding data: {e}")
        return f"Error loading shareholding data: {str(e)}"

