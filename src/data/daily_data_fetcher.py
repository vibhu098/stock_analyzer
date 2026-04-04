"""Fetch current/today's stock data from Yahoo Finance for real-time analysis."""

import logging
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def get_yfinance():
    """Lazy import yfinance to avoid import errors if not installed."""
    try:
        import yfinance
        return yfinance
    except ImportError:
        raise ImportError(
            "yfinance not installed. Install with: pip install yfinance\n"
            "Use: pip install yfinance --upgrade"
        )


def fetch_current_stock_data(symbol: str, nsind_code: Optional[str] = None) -> Dict[str, any]:
    """
    Fetch today's real-time stock data from Yahoo Finance.
    
    Args:
        symbol: Stock symbol (e.g., 'ASIANPAINT' for ASIANPAINT.NS)
        nsind_code: Optional NSE/BSE code (not needed if symbol is correct)
    
    Returns:
        Dict with keys:
        - current_price: Today's closing price (or last available)
        - market_cap: Current market capitalization in crores
        - pe_ratio: Current P/E ratio
        - prev_close: Previous close price
        - day_high: Today's high
        - day_low: Today's low
        - 52week_high: 52-week high
        - 52week_low: 52-week low
        - dividend_yield: Annual dividend yield (%)
        - volume: Daily volume
        - fetch_timestamp: When data was fetched
        - error: Error message if fetch failed
    """
    yf = get_yfinance()
    
    # Format symbol for Yahoo Finance (Indian stocks)
    if not symbol.endswith('.NS'):
        yf_symbol = f"{symbol}.NS"  # NSE (National Stock Exchange)
    else:
        yf_symbol = symbol
    
    try:
        logger.info(f"Fetching current data for {yf_symbol}...")
        
        # Fetch ticker data
        ticker = yf.Ticker(yf_symbol)
        
        # Get latest quote
        data = ticker.history(period='1d')
        
        if data.empty:
            logger.warning(f"No data found for {yf_symbol}")
            return {
                'error': f"No data found for {yf_symbol}",
                'fetch_timestamp': datetime.now().isoformat()
            }
        
        # Get info (includes P/E, market cap, dividend yield, etc.)
        info = ticker.info
        
        # Extract current price (last close or most recent)
        current_price = info.get('currentPrice') or info.get('regularMarketPrice') or data['Close'].iloc[-1]
        
        # Extract market cap (in dollars, convert to crores)
        market_cap_dollars = info.get('marketCap', 0)
        market_cap_crores = (market_cap_dollars / 10_000_000) if market_cap_dollars else None
        
        # Extract P/E ratio
        pe_ratio = info.get('trailingPE') or info.get('forwardPE')
        
        # Extract dividend yield (Yahoo Finance gives as decimal, convert to percentage)
        dividend_yield_raw = info.get('dividendYield', 0)
        dividend_yield = (dividend_yield_raw * 100) if dividend_yield_raw else 0
        
        # Extract price range
        prev_close = info.get('previousClose') or data['Close'].iloc[-1] if len(data) > 0 else None
        day_high = info.get('dayHigh') or data['High'].iloc[-1] if len(data) > 0 else None
        day_low = info.get('dayLow') or data['Low'].iloc[-1] if len(data) > 0 else None
        fifty_two_week_high = info.get('fiftyTwoWeekHigh')
        fifty_two_week_low = info.get('fiftyTwoWeekLow')
        
        # Extract volume
        volume = info.get('volume') or data['Volume'].iloc[-1] if len(data) > 0 else None
        
        result = {
            'current_price': current_price,
            'market_cap_crores': market_cap_crores,
            'pe_ratio': pe_ratio,
            'prev_close': prev_close,
            'day_high': day_high,
            'day_low': day_low,
            'week52_high': fifty_two_week_high,
            'week52_low': fifty_two_week_low,
            'dividend_yield': dividend_yield,
            'volume': volume,
            'fetch_timestamp': datetime.now().isoformat(),
            'data_age': 'Real-time (2-min delayed NSE)',
            'source': 'Yahoo Finance'
        }
        
        logger.info(f"✓ Fetched data for {symbol}: Price={current_price}, P/E={pe_ratio}, MarketCap={market_cap_crores}Cr")
        return result
    
    except Exception as e:
        logger.error(f"Error fetching data for {yf_symbol}: {e}")
        return {
            'error': str(e),
            'fetch_timestamp': datetime.now().isoformat()
        }


def fetch_historical_prices(symbol: str, days: int = 365) -> pd.DataFrame:
    """
    Fetch historical daily price data for technical analysis.
    
    Args:
        symbol: Stock symbol (e.g., 'ASIANPAINT')
        days: Number of days of history to fetch (default: 1 year)
    
    Returns:
        DataFrame with columns: Open, High, Low, Close, Volume, Dividends, Stock Splits
    """
    yf = get_yfinance()
    
    if not symbol.endswith('.NS'):
        yf_symbol = f"{symbol}.NS"
    else:
        yf_symbol = symbol
    
    try:
        logger.info(f"Fetching {days}-day price history for {yf_symbol}...")
        
        ticker = yf.Ticker(yf_symbol)
        history = ticker.history(period=f'{days}d')
        
        if history.empty:
            logger.warning(f"No historical data found for {yf_symbol}")
            return pd.DataFrame()
        
        logger.info(f"✓ Fetched {len(history)} days of price history for {symbol}")
        return history
    
    except Exception as e:
        logger.error(f"Error fetching price history for {yf_symbol}: {e}")
        return pd.DataFrame()


def supplement_key_metrics_with_today_data(
    symbol: str,
    screener_csv_path: Optional[Path] = None
) -> Dict[str, any]:
    """
    Load screener key_metrics.csv and supplement with today's real-time data.
    
    This merges:
    - Historical financial metrics from screener CSV (ROCE, ROE, DEB/EQ, etc.)
    - TODAY's real-time data from Yahoo Finance (Current Price, P/E, Market Cap)
    
    Args:
        symbol: Stock symbol (e.g., 'ASIANPAINT')
        screener_csv_path: Path to key_metrics.csv. If None, loads from static/{symbol}/
    
    Returns:
        Dict with merged data from both sources
    """
    # Load screener data if available
    screener_data = {}
    
    if screener_csv_path is None:
        screener_csv_path = Path(__file__).parent.parent.parent / 'static' / symbol / 'key_metrics.csv'
    
    if screener_csv_path and screener_csv_path.exists():
        try:
            df = pd.read_csv(screener_csv_path)
            # Convert to dict for easier access
            screener_data = df.set_index(df.columns[0]).T.to_dict('list')
            logger.info(f"Loaded screener metrics for {symbol} from {screener_csv_path.name}")
        except Exception as e:
            logger.warning(f"Could not load screener CSV: {e}")
    
    # Fetch today's data
    today_data = fetch_current_stock_data(symbol)
    
    # Merge both sources
    merged = {
        'symbol': symbol,
        'screener_data': screener_data,
        'today_data': today_data,
        'merged_at': datetime.now().isoformat()
    }
    
    return merged


def create_realtime_metrics_csv(symbol: str, output_path: Optional[Path] = None) -> Tuple[bool, str]:
    """
    Create a CSV file with today's real-time metrics from Yahoo Finance.
    
    Useful for:
    1. Supplementing screener's static key_metrics.csv
    2. Tracking daily price changes for reports
    3. Providing current P/E, market cap, etc. to LLM analysis
    
    Args:
        symbol: Stock symbol
        output_path: Where to save. Default: static/{symbol}/realtime_metrics.csv
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    # Fetch data
    data = fetch_current_stock_data(symbol)
    
    if 'error' in data and len(data) == 2:  # Only error and timestamp
        return False, f"Failed to fetch data: {data.get('error')}"
    
    # Create DataFrame
    df = pd.DataFrame([data])
    
    # Set output path
    if output_path is None:
        output_path = Path(__file__).parent.parent.parent / 'static' / symbol / 'realtime_metrics.csv'
    
    # Ensure directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save
    try:
        df.to_csv(output_path, index=False)
        logger.info(f"✓ Saved real-time metrics to {output_path}")
        return True, f"Saved to {output_path}"
    except Exception as e:
        logger.error(f"Error saving metrics: {e}")
        return False, str(e)


if __name__ == '__main__':
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    # Fetch current data
    symbol = 'ASIANPAINT'
    data = fetch_current_stock_data(symbol)
    
    print(f"\nCurrent data for {symbol}:")
    for key, value in data.items():
        print(f"  {key}: {value}")
    
    # Save to CSV
    success, msg = create_realtime_metrics_csv(symbol)
    print(f"\n{msg}")
    
    # Fetch historical prices
    prices = fetch_historical_prices(symbol, days=90)
    print(f"\nFetched {len(prices)} days of price history")
    print(prices.tail(5))
