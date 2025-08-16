from pydantic import BaseModel, ConfigDict
from typing import Literal


# Accepts user question
class ChatHistory(BaseModel):
    role: Literal["user", "assistant"]
    content: str = None

    model_config = ConfigDict(extra="forbid")