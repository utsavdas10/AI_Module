import time
import json
from typing import Dict, List, Any, Union
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from pymongo.database import Database as MongoDatabase
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.utils.exceptions import SecurityError, QueryExecutionError
import logging

logger = logging.getLogger(__name__)



class SafeQueryExecutor:

    PROHIBITED_SQL_KEYWORDS = {
        "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE",
        "TRUNCATE", "GRANT", "REVOKE", "EXEC", "EXECUTE", "CALL"
    }

    def __init__(self, db_connection: Union[AsyncEngine, MongoDatabase], db_type: str, db_id: str):
        self.db_connection = db_connection
        self.db_type = db_type
        self.db_id = db_id

    async def execute(self, query: Union[str, Dict[str, Any]], query_type: str) -> Dict[str, Any]:
        """Validates and executes the query, dispatching to the correct handler."""

        if self.db_type in ['postgresql', 'mysql']:
            if not self._is_sql_safe(query):
                logger.error(f"SQL query contains prohibited or dangerous keywords: {query}")
                raise SecurityError("SQL query contains prohibited or dangerous keywords.")
            result_data = await self._execute_sql(query)
        elif self.db_type == 'mongodb':
            result_data = await self._execute_mongo(query, query_type)
        else:
            logger.error(f"Unsupported database type for execution: {self.db_type}")
            raise ValueError(f"Unsupported database type for execution: {self.db_type}")

        return result_data

    def _is_sql_safe(self, query: str) -> bool:
        """A whitelist/blacklist approach to SQL query safety."""
        query_upper = query.upper().strip()
        if not query_upper.startswith("SELECT"):
            return False
        if any(keyword in query_upper.split() for keyword in self.PROHIBITED_SQL_KEYWORDS):
            return False
        return True

    async def _execute_sql(self, query: str) -> Dict[str, Any]:
        """Executes a safe SQL query."""
        engine: AsyncEngine = self.db_connection
        try:
            async with engine.connect() as connection:
                result_proxy = await connection.execute(text(query))
                
                columns = [{"name": key, "type": str(getattr(result_proxy.cursor.description[i], 'type_code', 'UNKNOWN'))} for i, key in enumerate(result_proxy.keys())]
                rows = [dict(row) for row in result_proxy.mappings()]
                
                return {"columns": columns, "rows": rows, "row_count": len(rows)}
        except Exception as e:
            logger.error(f"SQL query execution failed: {e}")
            raise QueryExecutionError(self.db_id, f"SQL query execution failed: {e}")





    async def _execute_mongo(self, query_input: Union[str, Dict[str, Any]], query_type: str) -> Dict[str, Any]:
        """Parses and executes a safe MongoDB query from a JSON object."""
        db: AsyncIOMotorDatabase = self.db_connection
        try:
            query_obj: Dict[str, Any]
            if isinstance(query_input, str):
            # Sanitize LLM output: remove markdown code block markers and strip whitespace
                cleaned = query_input.strip()
                if cleaned.startswith("```"):
                    # Remove code block markers (e.g., ```json ... ```)
                    cleaned = cleaned.split('\n', 1)[-1]
                    if cleaned.endswith("```"):
                        cleaned = cleaned.rsplit('```', 1)[0]
                    cleaned = cleaned.strip()
                # Now try to parse
                query_obj = json.loads(cleaned)
            elif isinstance(query_input, dict):
                query_obj = query_input
            else:
                raise QueryExecutionError(self.db_id, f"Invalid type for MongoDB query. Must be a JSON string or a dictionary. Found {type(query_input)}")
                
            collection_name = query_obj.get("collection")

            if not collection_name:
                raise QueryExecutionError(self.db_id, "MongoDB query JSON missing 'collection' key.")
            if not query_type:
                raise QueryExecutionError(self.db_id, "MongoDB query JSON missing 'query_type' key.")

            collection = db[collection_name]
            cursor = None # Initialize cursor to None

            if query_type == "find":
                find_filter = query_obj.get("filter", {})
                projection = query_obj.get("projection") # Can be None or dict
                limit = query_obj.get("limit", 10000) # Default limit to 10000 if not specified
                cursor = collection.find(find_filter, projection).limit(limit)
            elif query_type == "aggregate":
                pipeline = query_obj.get("pipeline")
                if not isinstance(pipeline, list):
                    raise QueryExecutionError(self.db_id, "Aggregation query missing 'pipeline' array or it's not a list.")
                cursor = collection.aggregate(pipeline)
            else:
                raise QueryExecutionError(self.db_id, f"Unsupported query_type: {query_type}. Must be 'find' or 'aggregate'.")

            # Important: Convert ObjectId to str for JSON serialization and normalize data
            rows = []
            if cursor: # Ensure cursor exists before iterating
                for doc in await cursor.to_list(length=10000): # Limit result size for safety
                    for key, value in doc.items():
                        if isinstance(value, ObjectId):
                            doc[key] = str(value)
                    rows.append(doc)
                
            # Infer columns from the first row if available
            columns = []
            if rows:
                # Create a set to keep track of unique column names to avoid duplicates
                seen_columns = set()
                for key, value in rows[0].items():
                    if key not in seen_columns:
                        columns.append({"name": key, "type": type(value).__name__})
                        seen_columns.add(key)
                
            return {"columns": columns, "rows": rows, "row_count": len(rows)}
        except json.JSONDecodeError:
            raise QueryExecutionError(self.db_id, "Failed to decode MongoDB query JSON from LLM.")
        except QueryExecutionError: # Re-raise custom exceptions directly
            raise
        except Exception as e:
            raise QueryExecutionError(self.db_id, f"MongoDB query execution failed: {e}")