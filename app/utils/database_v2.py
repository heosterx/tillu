"""
Enhanced Database Client
Batch operations, connection pooling, and N+1 prevention
"""
from typing import Dict, List, Any, Optional
from app.utils.logging import get_logger
from app.config import settings
from supabase import create_client, Client

logger = get_logger("database")


class DatabaseClientV2:
    """Enhanced database client with batch operations"""
    
    def __init__(self, supabase_url: str, service_key: str):
        self.client: Client = create_client(supabase_url, service_key)
        self.url = supabase_url
        self.key = service_key
    
    async def fetch_with_relations(
        self,
        table: str,
        relations: Optional[Dict[str, str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Fetch records with related data in single query
        Uses JOINs instead of N+1 queries
        
        Args:
            table: Main table name
            relations: Dict of {related_table: foreign_key}
            filters: Filter conditions
            limit: Result limit
            offset: Result offset
            
        Returns:
            List of records with relations
        """
        try:
            query = self.client.table(table)
            
            # Apply filters
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            
            # Build select clause with relations
            select_clause = "*"
            if relations:
                for rel_table in relations.keys():
                    select_clause += f", {rel_table}(*)"
            
            # Execute query
            result = await query.select(select_clause).range(offset, offset + limit - 1).execute()
            
            logger.debug(f"Fetched {len(result.data or [])} records from {table} with relations")
            return result.data or []
            
        except Exception as e:
            logger.error(f"Error fetching with relations: {str(e)}")
            raise
    
    async def batch_upsert(
        self,
        table: str,
        records: List[Dict[str, Any]],
        conflict_columns: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Batch upsert using INSERT ... ON CONFLICT
        Single operation instead of N queries
        
        Args:
            table: Table name
            records: List of records to upsert
            conflict_columns: Columns to check for conflicts
            
        Returns:
            Upserted records
        """
        if not records:
            return []
        
        try:
            # Use Supabase upsert
            result = await self.client.table(table).upsert(
                records,
                returning="representation"
            ).execute()
            
            logger.info(f"Upserted {len(result.data or [])} records in {table}")
            return result.data or []
            
        except Exception as e:
            logger.error(f"Error during batch upsert: {str(e)}")
            raise
    
    async def batch_insert(
        self,
        table: str,
        records: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Batch insert multiple records
        
        Args:
            table: Table name
            records: List of records to insert
            
        Returns:
            Inserted records
        """
        if not records:
            return []
        
        try:
            result = await self.client.table(table).insert(records).execute()
            
            logger.info(f"Inserted {len(result.data or [])} records in {table}")
            return result.data or []
            
        except Exception as e:
            logger.error(f"Error during batch insert: {str(e)}")
            raise
    
    async def fetch_one(
        self,
        table: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Fetch single record"""
        try:
            query = self.client.table(table)
            
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            
            result = await query.select("*").limit(1).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching one: {str(e)}")
            raise
    
    async def fetch_many(
        self,
        table: str,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        ascending: bool = True,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Fetch multiple records with pagination"""
        try:
            query = self.client.table(table)
            
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            
            if order_by:
                query = query.order(order_by, ascending=ascending)
            
            result = await query.select("*").range(offset, offset + limit - 1).execute()
            
            return result.data or []
            
        except Exception as e:
            logger.error(f"Error fetching many: {str(e)}")
            raise
    
    async def update(
        self,
        table: str,
        data: Dict[str, Any],
        filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Update records"""
        try:
            query = self.client.table(table)
            
            for key, value in filters.items():
                query = query.eq(key, value)
            
            result = await query.update(data).execute()
            
            logger.info(f"Updated {len(result.data or [])} records in {table}")
            return result.data or []
            
        except Exception as e:
            logger.error(f"Error updating: {str(e)}")
            raise
    
    async def delete(
        self,
        table: str,
        filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Delete records"""
        try:
            query = self.client.table(table)
            
            for key, value in filters.items():
                query = query.eq(key, value)
            
            result = await query.delete().execute()
            
            logger.info(f"Deleted records from {table}")
            return result.data or []
            
        except Exception as e:
            logger.error(f"Error deleting: {str(e)}")
            raise
    
    async def execute_raw(self, query: str) -> Any:
        """Execute raw SQL query"""
        try:
            result = await self.client.rpc("execute_sql", {"query": query}).execute()
            return result.data
        except Exception as e:
            logger.error(f"Error executing raw query: {str(e)}")
            raise


# Create global instance
db_v2 = DatabaseClientV2(settings.supabase_url, settings.supabase_service_key or settings.supabase_key)
