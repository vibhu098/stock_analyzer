"""Redis and RedisVL integration utilities."""

import redis
from src.config import settings
from typing import List, Dict, Any, Optional

# Optional imports for advanced RedisVL features
try:
    from redisvl.index.index import Index
except ImportError:
    try:
        from redisvl.index import Index
    except ImportError:
        Index = None


class RedisVLManager:
    """Manager for RedisVL operations."""
    
    def __init__(self, index_name: str = "langchain-embeddings"):
        """Initialize RedisVL manager.
        
        Args:
            index_name: Name of the Redis index
        """
        self.redis_url = settings.redis_url
        self.index_name = index_name
        self.index: Optional[Index] = None
        self.client: Optional[redis.Redis] = None
    
    def connect(self) -> None:
        """Establish connection to Redis."""
        try:
            self.client = redis.from_url(self.redis_url)
            self.client.ping()
            print(f"✓ Connected to Redis at {settings.redis_host}:{settings.redis_port}")
        except Exception as e:
            print(f"✗ Failed to connect to Redis: {e}")
            raise
    
    def initialize_index(self, schema: Dict[str, Any]) -> None:
        """Initialize a RedisVL index.
        
        Args:
            schema: Index schema definition
        """
        if not self.client:
            self.connect()
        
        try:
            self.index = Index.from_dict(schema)
            self.index.connect(self.redis_url)
            print(f"✓ Initialized index: {self.index_name}")
        except Exception as e:
            print(f"✗ Failed to initialize index: {e}")
            raise
    
    def store_vector(self, key: str, vector: List[float], metadata: Dict[str, Any]) -> bool:
        """Store a vector with metadata in Redis.
        
        Args:
            key: Unique identifier for the vector
            vector: Vector to store
            metadata: Associated metadata
            
        Returns:
            True if successful
        """
        if not self.client:
            self.connect()
        
        try:
            # Store as hash with metadata
            data = {f"vector": str(vector)}
            data.update({f"meta_{k}": str(v) for k, v in metadata.items()})
            self.client.hset(key, mapping=data)
            return True
        except Exception as e:
            print(f"✗ Failed to store vector: {e}")
            return False
    
    def retrieve_vector(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve a vector and its metadata.
        
        Args:
            key: Vector identifier
            
        Returns:
            Vector and metadata or None
        """
        if not self.client:
            self.connect()
        
        try:
            data = self.client.hgetall(key)
            if data:
                return {k.decode(): v.decode() for k, v in data.items()}
            return None
        except Exception as e:
            print(f"✗ Failed to retrieve vector: {e}")
            return None
    
    def delete_vector(self, key: str) -> bool:
        """Delete a vector from Redis.
        
        Args:
            key: Vector identifier
            
        Returns:
            True if deleted
        """
        if not self.client:
            self.connect()
        
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            print(f"✗ Failed to delete vector: {e}")
            return False
    
    def flush_index(self) -> None:
        """Flush all data from Redis."""
        if not self.client:
            self.connect()
        
        try:
            self.client.flushdb()
            print("✓ Flushed Redis database")
        except Exception as e:
            print(f"✗ Failed to flush database: {e}")
    
    def close(self) -> None:
        """Close Redis connection."""
        if self.client:
            self.client.close()
            print("✓ Closed Redis connection")
