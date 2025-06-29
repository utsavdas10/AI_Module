import logging
from typing import Union, Set, Dict, Any
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine
from pymongo.database import Database as MongoDatabase

logger = logging.getLogger(__name__)

class DatabaseInspector:
    def __init__(self, db_connection: Union[AsyncEngine, MongoDatabase], db_type: str):
        self.db_connection = db_connection
        self.db_type = db_type

    async def get_schema_representation(self) -> dict:
        if self.db_type in ['postgresql', 'mysql']:
            return await self._get_sql_schema()
        elif self.db_type == 'mongodb':
            return await self._get_mongo_schema()
        else:
            raise ValueError(f"Unsupported database type for inspection: {self.db_type}")

    async def _get_sql_schema(self) -> dict:
        engine: AsyncEngine = self.db_connection
        async with engine.connect() as connection:
            # Call the sync schema inspector logic inside run_sync
            schema = await connection.run_sync(self._inspect_sql_sync)

            example_data = {}
            for table_name in schema.keys():
                result = await connection.execute(text(f"SELECT * FROM {table_name} LIMIT 5"))
                rows = [dict(row) for row in result.mappings().all()]
                example_data[table_name] = rows

            return {"schema": schema, "example_data": example_data}


    def _inspect_sql_sync(self, sync_connection) -> dict:
        inspector = inspect(sync_connection)
        schema = {}
        for table_name in inspector.get_table_names():
            columns = []
            for col in inspector.get_columns(table_name):
                columns.append({"name": col['name'], "type": str(col['type'])})
            fks = inspector.get_foreign_keys(table_name)
            foreign_keys = [
                {
                    "column": fk['constrained_columns'][0],
                    "referred_table": fk['referred_table'],
                    "referred_column": fk['referred_columns'][0]
                }
                for fk in fks
            ]
            schema[table_name] = {
                "columns": columns,
                "foreign_keys": foreign_keys
            }
        return schema


    async def _get_mongo_schema(self, sample_size: int = 5) -> dict:
        db: MongoDatabase = self.db_connection
        schema = {}
        example_data = {}
        collection_names = await db.list_collection_names()
        for name in collection_names:
            collection = db[name]
            pipeline = [{"$sample": {"size": sample_size}}]
            try:
                sample_docs = await collection.aggregate(pipeline).to_list(length=sample_size)
            except Exception:
                sample_docs = await collection.find().limit(sample_size).to_list(length=sample_size)
            if not sample_docs:
                schema[name] = {"fields": {}, "note": "No documents found to infer schema"}
                example_data[name] = []
                continue
            field_types: Dict[str, Set[str]] = {}

        # deep nesting handling
        def extract_field_types(doc, parent_key=None):
            field_types = {}
            for key, value in doc.items():
                full_key = f"{parent_key}.{key}" if parent_key else key
                if isinstance(value, dict):
                    # Recurse into nested dicts
                    nested = extract_field_types(value, full_key)
                    for nkey, ntypes in nested.items():
                        if nkey not in field_types:
                            field_types[nkey] = set()
                        field_types[nkey].update(ntypes)
                elif isinstance(value, list):
                    # For lists, check the type of the first element (if any)
                    if value and isinstance(value[0], dict):
                        nested = extract_field_types(value[0], full_key)
                        for nkey, ntypes in nested.items():
                            if nkey not in field_types:
                                field_types[nkey] = set()
                            field_types[nkey].update(ntypes)
                    else:
                        field_types[full_key] = set([f"list[{type(value[0]).__name__}]" if value else "list"])
                else:
                    if full_key not in field_types:
                        field_types[full_key] = set()
                    field_types[full_key].add(type(value).__name__)
            return field_types

        # deep nesting handling
        field_types = {}
        for doc in sample_docs:
            doc_field_types = extract_field_types(doc)
            for key, types in doc_field_types.items():
                if key not in field_types:
                    field_types[key] = set()
                field_types[key].update(types)
        fields = {key: list(types) for key, types in field_types.items()}
        schema[name] = {"fields": fields}
        example_data[name] = sample_docs
        return {"schema": schema, "example_data": example_data}
