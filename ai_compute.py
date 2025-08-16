import time
from app.models.query import NLQueryRequest, FinalResponse
from app.models.db import DBConnectionParams
from app.models.chat_history import ChatHistory
from app.services.Database_AI import orchestrator
from typing import List, Optional
import asyncio

from app.utils.exceptions import Error
from app.core.config import settings
import logging
import colorlog


handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S',
    log_colors={
        'DEBUG':    'cyan',
        'INFO':     'green',
        'WARNING':  'yellow',
        'ERROR':    'red',
        'CRITICAL': 'bold_red',
    }
))
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    handlers=[handler]
)
logger = logging.getLogger(__name__)








async def process_query(request: NLQueryRequest):
    try:
        start_time = time.time()
        response = await orchestrator.process_natural_language_query(request)
        if hasattr(response, 'model_dump'):
            data = response.model_dump()
        else:
            data = await dict(response)
        execution_time_ms = int((time.time() - start_time) * 1000)
        data["execution_time_ms"] = execution_time_ms
        return FinalResponse(**data)
    except Error as qe:
        return {
            "success": False,
            "error_type": type(qe).__name__,
            "error_message": str(qe),
            "suggestion": "Check DB connections or rephrase your question."
        }
    



request=NLQueryRequest(
        question = "Who owns XYZ company?y",
        connections = [
            {
                "id": "1",
                "db_type": "mongodb",
                "host": "cluster0.yvyg3bm.mongodb.net",
                "port": 0,
                "username": "utsavdas10",
                "password": "utsavdas10",
                "database": "sample_supplies",
                "ssl_mode": "prefer",
            }
        #     {
        #         "id": "2",
        #         "db_type": "postgresql",
        #         "host": "ep-shiny-dust-a1fynin8-pooler.ap-southeast-1.aws.neon.tech",
        #         "port": 0,
        #         "username": "neondb_owner",
        #         "password": "npg_6jzBpNGdbQ9l",
        #         "database": "neondb",
        #         "ssl_mode": "prefer"
        #     },
        ],
        chat_history = [
            {
                "role": "user",
                "content": "XYZ company is owned by ABC"
            },
            {
                "role": "assistant",
                "content": "Ok"
            }
        ]
)

response_data = asyncio.run(process_query(request=request))

print(response_data)

# # question = "I want to analyze the purchasing habits of customers who bought items online. For each store location, what is the total number of individual items sold online? Additionally, calculate the average customer satisfaction score for those online purchases. Only show me the store locations that had more than 15 individual items sold online. Also give me the name of any 5 books and their authors along with the author's current age",