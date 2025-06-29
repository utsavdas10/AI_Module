import logging
from typing import Dict, Any, Union

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.database import Database as MongoDatabase

from AI_Module.models.db import DBConnectionParams
from AI_Module.utils.exceptions import ConnectionError

logger = logging.getLogger(__name__)


async def get_db_connection(
    params: DBConnectionParams
) -> Union[AsyncEngine, MongoDatabase]:
    """
    Creates and caches a database connection object for a given session.
    
    This function acts as a factory, returning the correct type of connection
    object (a SQLAlchemy AsyncEngine or a PyMongo Database) based on the
    provided parameters.
    """
    try:
        connection_object: Union[AsyncEngine, MongoDatabase]
        
        # SQL connection logic 
        if params.db_type in ['postgresql', 'mysql']:
            # Assign default ports if not provided
            default_ports = {
                'postgresql': 5432,
                'mysql': 3306,
            }
            port = params.port or default_ports[params.db_type]

            driver_map = {
                'postgresql': 'postgresql+asyncpg',
                'mysql': 'mysql+aiomysql'
            }
            driver = driver_map[params.db_type]
            password = params.password.get_secret_value()

            connection_string = (
                f"{driver}://{params.username}:{password}@"
                f"{params.host}:{port}/{params.database}"
            )

            engine = create_async_engine(connection_string, echo=False)
            connection_object = engine

        # --- MONGODB LOGIC ---
        elif params.db_type == 'mongodb':
            password = params.password.get_secret_value()
            # Construct the SRV URI using the `host` field for the cluster address.
            # Example params.host: "cluster0.yvyg3bm.mongodb.net"
            mongo_uri = (
                f"mongodb+srv://{params.username}:{password}@"
                f"{params.host}/?retryWrites=true&w=majority"
            )
            client = AsyncIOMotorClient(mongo_uri)
            try:
                # Attempt to access the database to ensure the connection is valid.
                await client.admin.command('ping')  # This will raise an error if the connection fails.
            except Exception as e:
                logger.error(f"MongoDB connection failed: {e}")
                raise ConnectionError(f"MongoDB connection failed: {e}")

            db = client[params.database]
            connection_object = db
        
        else:
            raise ConnectionError(f"Unsupported database type: {params.db_type}")

        return connection_object

    except Exception as e:
        logger.error(f"Failed to create database connection: {e}")
        raise ConnectionError(f"Database connection failed: {e}")