"""Utility functions for the application."""

from typing import List, Dict, Any
import json


def pretty_print_dict(data: Dict[str, Any]) -> None:
    """Pretty print a dictionary.
    
    Args:
        data: Dictionary to print
    """
    print(json.dumps(data, indent=2))


def batch_list(items: List[Any], batch_size: int) -> List[List[Any]]:
    """Batch a list into smaller lists.
    
    Args:
        items: List to batch
        batch_size: Size of each batch
        
    Returns:
        List of batches
    """
    return [items[i:i + batch_size] for i in range(0, len(items), batch_size)]


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to a maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."
