"""Clean and validate CSV data extracted from Screener."""

import re
import logging
from typing import List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class CSVCleaner:
    """Clean and validate financial data extracted from Screener."""
    
    @staticmethod
    def clean_numeric_value(value: str) -> str:
        """Clean numeric values - remove currency symbols, extra spaces."""
        if not value or not isinstance(value, str):
            return "N/A"
        
        value = value.strip()
        
        # Remove currency symbols and extra spaces
        value = re.sub(r'[₹$€£]', '', value)
        value = re.sub(r'\s+', '', value)
        
        # Handle percentage values
        if '%' in value:
            num_part = re.sub(r'%', '', value).strip()
            if num_part and num_part != '-':
                try:
                    float(num_part)
                    return f"{num_part}%"
                except ValueError:
                    return "N/A"
        
        # Handle Cr (Crore) values
        if 'Cr' in value:
            num_part = re.sub(r'Cr', '', value).strip()
            if num_part and num_part != '-':
                try:
                    float(num_part)
                    return f"{num_part}"  # Cr unit handled separately
                except ValueError:
                    return "N/A"
        
        # Handle regular numbers with commas
        if value and value != '-':
            # Try to parse as number
            cleaned = re.sub(r'[,\s]', '', value)
            try:
                float(cleaned)
                return cleaned
            except ValueError:
                return "N/A"
        
        return "N/A"
    
    @staticmethod
    def clean_key_metrics(data: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Clean key metrics data."""
        cleaned = []
        
        for row in data:
            if not row:
                continue
            
            cleaned_row = {}
            for key, value in row.items():
                if key == 'Value':
                    cleaned_row[key] = CSVCleaner.clean_numeric_value(value)
                elif key == 'Metric':
                    cleaned_row[key] = str(value).strip()
                else:
                    cleaned_row[key] = str(value).strip() if value else ""
            
            # Skip rows with N/A values
            if cleaned_row.get('Value') != 'N/A':
                cleaned.append(cleaned_row)
        
        return cleaned
    
    @staticmethod
    def clean_financial_table(data: List[Dict[str, str]], expected_metrics: List[str] = None) -> List[Dict[str, str]]:
        """
        Clean financial table data (P&L, Balance Sheet, etc.).
        
        Args:
            data: List of row dicts
            expected_metrics: Expected metric names to validate against
        
        Returns:
            Cleaned data rows
        """
        cleaned = []
        
        for row in data:
            if not row:
                continue
            
            cleaned_row = {}
            for key, value in row.items():
                if key == 'Metric':
                    cleaned_row[key] = str(value).strip()
                elif key in ['Unit', 'Source', 'Data Point']:
                    cleaned_row[key] = str(value).strip() if value else ""
                else:
                    # Numeric columns (years, quarters, etc.)
                    cleaned_row[key] = CSVCleaner.clean_numeric_value(value)
            
            # Validate metric if expected_metrics provided
            if expected_metrics:
                metric_name = cleaned_row.get('Metric', '').lower()
                if not any(exp.lower() in metric_name for exp in expected_metrics):
                    continue
            
            cleaned.append(cleaned_row)
        
        return cleaned
    
    @staticmethod
    def clean_ratios(data: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Clean ratio data with special handling for percentage values."""
        cleaned = []
        
        for row in data:
            if not row:
                continue
            
            cleaned_row = {}
            for key, value in row.items():
                if key == 'Metric':
                    cleaned_row[key] = str(value).strip()
                elif key in ['Unit', 'Source']:
                    cleaned_row[key] = str(value).strip() if value else ""
                else:
                    # For ratio values, preserve % if present
                    cleaned_value = CSVCleaner.clean_numeric_value(value)
                    # If metric is ROCE or ROE, ensure % is present
                    if 'ROCE' in cleaned_row.get('Metric', '') or 'ROE' in cleaned_row.get('Metric', ''):
                        if cleaned_value != 'N/A' and '%' not in cleaned_value:
                            cleaned_value = f"{cleaned_value}%"
                    cleaned_row[key] = cleaned_value
            
            cleaned.append(cleaned_row)
        
        return cleaned
    
    @staticmethod
    def clean_shareholding(data: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Clean shareholding pattern data."""
        cleaned = []
        
        for row in data:
            if not row:
                continue
            
            cleaned_row = {}
            for key, value in row.items():
                if key == 'Category':
                    cleaned_row[key] = str(value).strip()
                elif key in ['Source', 'Source Currency']:
                    cleaned_row[key] = str(value).strip() if value else ""
                else:
                    # Percentage columns
                    cleaned_value = CSVCleaner.clean_numeric_value(value)
                    # Ensure % is present for shareholding
                    if cleaned_value != 'N/A' and '%' not in cleaned_value:
                        cleaned_value = f"{cleaned_value}%"
                    cleaned_row[key] = cleaned_value
            
            cleaned.append(cleaned_row)
        
        return cleaned
    
    @staticmethod
    def standardize_headers(headers: List[str]) -> List[str]:
        """Standardize column headers for consistency."""
        standardized = []
        
        for header in headers:
            h = str(header).strip()
            # Clean up month-year format (e.g., "Mar-2024" or "Mar 2024")
            h = re.sub(r'\s+', ' ', h)
            standardized.append(h)
        
        return standardized
    
    @staticmethod
    def validate_data_completeness(data: List[Dict[str, str]], min_percent_complete: float = 0.7) -> bool:
        """
        Validate that data is reasonably complete.
        
        Args:
            data: Data rows to validate
            min_percent_complete: Minimum percentage of non-N/A values required (0.0-1.0)
        
        Returns:
            True if data meets completeness threshold
        """
        if not data or len(data) == 0:
            return False
        
        total_cells = 0
        non_na_cells = 0
        
        for row in data:
            for value in row.values():
                total_cells += 1
                if value and value != "N/A" and value != "-":
                    non_na_cells += 1
        
        if total_cells == 0:
            return False
        
        completeness = non_na_cells / total_cells
        return completeness >= min_percent_complete
