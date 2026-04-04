"""Cache manager for analysis results - prevents re-analysis within 7 days."""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class AnalysisCacheManager:
    """Manages caching of analysis results to avoid re-analysis within 7 days."""
    
    def __init__(self, cache_dir: str = None):
        """Initialize cache manager.
        
        Args:
            cache_dir: Directory to store cache files. Defaults to .cache/analysis
        """
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            # Use .cache/analysis in project root
            self.cache_dir = Path(__file__).parent.parent.parent / ".cache" / "analysis"
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl_days = 7  # Cache valid for 7 days
    
    def get_cache_file(self, stock_symbol: str) -> Path:
        """Get path to cache file for a stock."""
        return self.cache_dir / f"{stock_symbol.upper()}_cache.json"
    
    def is_cache_fresh(self, stock_symbol: str) -> bool:
        """Check if cached analysis is still fresh (within 7 days).
        
        Args:
            stock_symbol: Stock symbol
            
        Returns:
            True if valid cache exists and is fresh, False otherwise
        """
        cache_file = self.get_cache_file(stock_symbol)
        
        if not cache_file.exists():
            return False
        
        try:
            # Check file modification time
            mtime = cache_file.stat().st_mtime
            cache_time = datetime.fromtimestamp(mtime)
            days_old = (datetime.now() - cache_time).days
            
            if days_old <= self.cache_ttl_days:
                logger.info(f"✓ Found fresh cache for {stock_symbol} ({days_old} day(s) old)")
                return True
            else:
                logger.info(f"✗ Cache for {stock_symbol} is stale ({days_old} day(s) old, TTL: {self.cache_ttl_days})")
                return False
        except Exception as e:
            logger.warning(f"Error checking cache freshness: {e}")
            return False
    
    def load_cache(self, stock_symbol: str) -> Optional[Dict]:
        """Load cached analysis results.
        
        Args:
            stock_symbol: Stock symbol
            
        Returns:
            Cached analysis dict if available and fresh, None otherwise
        """
        if not self.is_cache_fresh(stock_symbol):
            return None
        
        cache_file = self.get_cache_file(stock_symbol)
        
        try:
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            
            logger.info(f"✓ Loaded analysis cache for {stock_symbol}")
            return cache_data
        except Exception as e:
            logger.error(f"Error loading cache for {stock_symbol}: {e}")
            return None
    
    def save_cache(self, stock_symbol: str, analysis_result: Dict) -> Tuple[bool, str]:
        """Save analysis results to cache.
        
        Args:
            stock_symbol: Stock symbol
            analysis_result: Analysis result dictionary to cache
            
        Returns:
            Tuple of (success, message)
        """
        cache_file = self.get_cache_file(stock_symbol)
        
        try:
            with open(cache_file, 'w') as f:
                json.dump(analysis_result, f, indent=2)
            
            logger.info(f"✓ Saved analysis cache for {stock_symbol}")
            return True, f"Cache saved for {stock_symbol}"
        except Exception as e:
            logger.error(f"Error saving cache for {stock_symbol}: {e}")
            return False, f"Error saving cache: {str(e)}"
    
    def clear_cache(self, stock_symbol: str = None) -> Tuple[bool, str]:
        """Clear cache for a stock or all stocks.
        
        Args:
            stock_symbol: Stock symbol to clear. If None, clears all cache.
            
        Returns:
            Tuple of (success, message)
        """
        try:
            if stock_symbol:
                cache_file = self.get_cache_file(stock_symbol)
                if cache_file.exists():
                    cache_file.unlink()
                    logger.info(f"✓ Cleared cache for {stock_symbol}")
                    return True, f"Cache cleared for {stock_symbol}"
                else:
                    return True, f"No cache found for {stock_symbol}"
            else:
                # Clear all cache
                for cache_file in self.cache_dir.glob("*_cache.json"):
                    cache_file.unlink()
                logger.info("✓ Cleared all analysis caches")
                return True, "All caches cleared"
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False, f"Error clearing cache: {str(e)}"
    
    def get_cache_info(self, stock_symbol: str) -> Dict:
        """Get cache information for a stock.
        
        Args:
            stock_symbol: Stock symbol
            
        Returns:
            Dictionary with cache info (exists, fresh, age, path)
        """
        cache_file = self.get_cache_file(stock_symbol)
        
        info = {
            'stock_symbol': stock_symbol.upper(),
            'exists': cache_file.exists(),
            'path': str(cache_file),
            'fresh': self.is_cache_fresh(stock_symbol),
            'ttl_days': self.cache_ttl_days
        }
        
        if cache_file.exists():
            try:
                mtime = cache_file.stat().st_mtime
                cache_time = datetime.fromtimestamp(mtime)
                age_days = (datetime.now() - cache_time).days
                info['created'] = cache_time.isoformat()
                info['age_days'] = age_days
                info['expires_in'] = max(0, self.cache_ttl_days - age_days)
            except Exception as e:
                logger.warning(f"Error getting cache info: {e}")
        
        return info
