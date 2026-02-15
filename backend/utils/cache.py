"""
Simple in-memory cache implementation
"""
from datetime import datetime, timedelta
from typing import Optional, Any, Dict


class SimpleCache:
    """Simple in-memory cache with TTL support"""
    
    def __init__(self, ttl_seconds: int = 60):
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, tuple] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if key not in self.cache:
            return None
        
        value, timestamp = self.cache[key]
        
        # Check if expired
        if datetime.utcnow() - timestamp > timedelta(seconds=self.ttl_seconds):
            del self.cache[key]
            return None
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """Set value in cache"""
        self.cache[key] = (value, datetime.utcnow())
    
    def delete(self, key: str) -> None:
        """Delete value from cache"""
        if key in self.cache:
            del self.cache[key]
    
    def clear(self) -> None:
        """Clear all cache"""
        self.cache.clear()
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        return {
            "total_items": len(self.cache),
            "ttl_seconds": self.ttl_seconds
        }
