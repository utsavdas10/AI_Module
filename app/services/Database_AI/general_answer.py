from app.utils.exceptions import LLMNotConfiguredError
from typing import List, Dict, Any
from app.prompts.general_answer_prompt import get_general_answer_prompt
from app.utils.LLM_configuration import LLMConfig
import logging

logger = logging.getLogger(__name__)



async def generate_general_llm_response(model: LLMConfig, question: str) -> dict:
    if not model:
        logger.error("LLM needs to be configured")
        raise LLMNotConfiguredError("LLM needs to be configured")
    try:
        prompt = get_general_answer_prompt(question)
        response = model.generate_response(prompt)
        return response  
    except Exception as e:
        return {"error": str(e)}


