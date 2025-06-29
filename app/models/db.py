from pydantic import BaseModel, ConfigDict, Field, SecretStr
from typing import Literal, Optional


# DB connection params
class DBConnectionParams(BaseModel):
    id: str = Field(..., description="A unique identifier for this database connection, e.g., 'postgres_prod' or 'mongo_logs'.")
    db_type: Literal["postgresql", "mysql", "mongodb"]
    host: str # For Mongo Atlas, this will be the cluster URI (e.g., "cluster0.abcde.mongodb.net")
    port: Optional[int] = None
    username: str
    password: SecretStr
    database: str
    ssl_mode: Optional[str] = "prefer"

    model_config = ConfigDict(extra="forbid")