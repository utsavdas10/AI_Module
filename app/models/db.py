from pydantic import BaseModel, ConfigDict, Field, SecretStr
from typing import Literal, Optional


# DB connection params
class DBConnectionParams(BaseModel):
    id: str = Field(..., description="A unique identifier for this database connection, e.g., 'postgres_prod' or 'mongo_logs'.")
    db_type: Literal["postgresql", "mysql", "mongodb"]
    ssl_mode: Optional[str] = "prefer"
    connection_string: Optional[str] = None

    host: Optional[str] = None  # For Mongo Atlas, this will be the cluster URI (e.g., "cluster0.abcde.mongodb.net")
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[SecretStr] = None
    database: Optional[str] = None
    

    model_config = ConfigDict(extra="forbid")