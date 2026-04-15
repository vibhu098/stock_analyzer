"""Integration utilities for supplementing analysis with today's real-time data."""

import logging
import pandas as pd
from pathlib import Path
from typing import Dict, Optional, Tuple
from src.data.daily_data_fetcher import (
    fetch_current_stock_data,
    fetch_historical_prices,
    create_realtime_metrics_csv
)

logger = logging.getLogger(__name__)


def prepare_today_market_snapshot(symbol: str) -> str:
    """
    Fetch today's real-time stock data and format it for LLM analysis.
    
    Returns a formatted string with:
    - Current price and day's change
    - Market cap and P/E ratio
    - 52-week ranges
    - Volume
    - Dividend yield
    
    This can be injected into prompts to provide real-time context.
    """
    data = fetch_current_stock_data(symbol)
    
    if 'error' in data and len(data) == 2:
        return f"⚠️  Could not fetch today's market data: {data.get('error')}"
    
    # Calculate day change
    prev_close = data.get('prev_close', 0)
    current = data.get('current_price', 0)
    
    if prev_close and current:
        change = current - prev_close
        change_pct = (change / prev_close) * 100 if prev_close != 0 else 0
        direction = "↑" if change > 0 else "↓"
        change_str = f"{direction} ₹{abs(change):.2f} ({change_pct:+.2f}%)"
    else:
        change_str = "N/A"
    
    # Format the snapshot
    snapshot = f"""
TODAY'S MARKET SNAPSHOT FOR {symbol}
{'=' * 70}

Current Price:          ₹{data.get('current_price', 'N/A'):,.2f} {change_str if change_str != 'N/A' else ''}
Market Capitalization:  ₹{data.get('market_cap_crores', 'N/A'):,.0f} Crores
P/E Ratio:              {data.get('pe_ratio', 'N/A'):.2f}x (if numeric else 'N/A')
Dividend Yield:         {data.get('dividend_yield', 'N/A'):.2f}%

Day's Range:            ₹{data.get('day_low', 'N/A'):,.2f} - ₹{data.get('day_high', 'N/A'):,.2f}
52-Week Range:          ₹{data.get('week52_low', 'N/A'):,.2f} - ₹{data.get('week52_high', 'N/A'):,.2f}
Volume:                 {data.get('volume', 'N/A'):,}

Data Source:            {data.get('source', 'Yahoo Finance')} ({data.get('data_age', 'Delayed')})
Fetched At:             {data.get('fetch_timestamp', 'N/A')}
{'=' * 70}
"""
    
    return snapshot


def get_price_performance_summary(symbol: str, days: int = 30) -> str:
    """
    Fetch historical price data and calculate performance metrics.
    
    Returns:
        Formatted string with:
        - Returns over various periods (1W, 1M, 3M, 6M, 1Y)
        - Volatility (standard deviation)
        - Current drawdown from 52W high
    """
    prices = fetch_historical_prices(symbol, days=365)
    
    if prices.empty:
        return f"⚠️  Could not fetch price history for {symbol}"
    
    # Get latest close
    latest_close = prices['Close'].iloc[-1]
    
    # Calculate returns
    returns = {}
    
    # 1 week (5 trading days)
    if len(prices) >= 5:
        week_1_start = prices['Close'].iloc[-5]
        returns['1W'] = ((latest_close - week_1_start) / week_1_start) * 100
    
    # 1 month (20 trading days)
    if len(prices) >= 20:
        month_1_start = prices['Close'].iloc[-20]
        returns['1M'] = ((latest_close - month_1_start) / month_1_start) * 100
    
    # 3 months (60 trading days)
    if len(prices) >= 60:
        month_3_start = prices['Close'].iloc[-60]
        returns['3M'] = ((latest_close - month_3_start) / month_3_start) * 100
    
    # 6 months (120 trading days)
    if len(prices) >= 120:
        month_6_start = prices['Close'].iloc[-120]
        returns['6M'] = ((latest_close - month_6_start) / month_6_start) * 100
    
    # 1 year
    if len(prices) >= 252:
        year_1_start = prices['Close'].iloc[-252]
        returns['1Y'] = ((latest_close - year_1_start) / year_1_start) * 100
    
    # Volatility (30-day rolling std dev of returns)
    daily_returns = prices['Close'].pct_change().tail(30)
    volatility = daily_returns.std() * 100
    
    # Drawdown from 52W high
    high_52w = prices['Close'].tail(252).max() if len(prices) >= 252 else prices['Close'].max()
    drawdown = ((latest_close - high_52w) / high_52w) * 100
    
    # Format output
    perf_summary = f"""
PRICE PERFORMANCE ANALYSIS FOR {symbol}
{'=' * 70}

Returns:
"""
    for period, ret in sorted(returns.items()):
        direction = "↑" if ret > 0 else "↓"
        perf_summary += f"  {period:5s}: {direction} {abs(ret):6.2f}%\n"
    
    perf_summary += f"""
Volatility (30D):       {volatility:.2f}% (daily std dev)
Drawdown from 52W High: {drawdown:.2f}%

Latest Close:           ₹{latest_close:,.2f}
52-Week High:           ₹{high_52w:,.2f}
Days with Data:         {len(prices)}
{'=' * 70}
"""
    
    return perf_summary


def inject_today_data_into_analysis(
    symbol: str,
    screener_csv_path: Optional[Path] = None
) -> Dict[str, any]:
    """
    Comprehensive function to gather ALL today's data for analysis:
    1. Fetch real-time price, P/E, market cap, dividend yield
    2. Load historical screener data (ROE, ROCE, P&L, etc.)
    3. Get price performance metrics
    4. Save real-time metrics to CSV
    
    Returns:
        Dict with keys:
        - market_snapshot: Formatted string for LLM
        - price_performance: Performance metrics
        - realtime_metrics: Raw data from yfinance
        - screener_metrics: Loaded from CSVs
    """
    logger.info(f"Gathering complete real-time data for {symbol}...")
    
    # Fetch real-time market data
    market_snapshot = prepare_today_market_snapshot(symbol)
    
    # Get price performance
    price_performance = get_price_performance_summary(symbol)
    
    # Fetch raw real-time data
    realtime_data = fetch_current_stock_data(symbol)
    
    # Save to CSV for record-keeping
    success, msg = create_realtime_metrics_csv(symbol)
    if not success:
        logger.warning(f"Could not save real-time metrics: {msg}")
    
    # Load screener data if available
    screener_metrics = {}
    if screener_csv_path is None:
        screener_csv_path = Path('static') / symbol / 'key_metrics.csv'
    
    if screener_csv_path.exists():
        try:
            screener_df = pd.read_csv(screener_csv_path)
            screener_metrics = screener_df.to_dict('records')[0] if not screener_df.empty else {}
            logger.info(f"Loaded screener metrics for {symbol}")
        except Exception as e:
            logger.warning(f"Could not load screener metrics: {e}")
    
    return {
        'symbol': symbol,
        'market_snapshot': market_snapshot,
        'price_performance': price_performance,
        'realtime_metrics': realtime_data,
        'screener_metrics': screener_metrics,
        'ready_for_analysis': True
    }


if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Example usage
    symbol = 'ASIANPAINT'
    
    # Get all data
    print("Gathering real-time data...\n")
    data = inject_today_data_into_analysis(symbol)
    
    # Print market snapshot
    print(data['market_snapshot'])
    
    # Print price performance
    print(data['price_performance'])
    
    print("\n✓ All data ready for analysis")
