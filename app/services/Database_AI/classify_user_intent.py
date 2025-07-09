import json
import logging
import re

from app.prompts.classify_user_intent_prompt import get_classify_user_intent_prompt
from app.utils.LLM_configuration import LLMConfig
from app.utils.exceptions import LLMNotConfiguredError


logger = logging.getLogger(__name__)

async def classify_user_intent(model: LLMConfig, schemas_str, question, state):
    if not model:
        logger.error("LLM needs to be configured")
        raise LLMNotConfiguredError

    try:
        prompt = get_classify_user_intent_prompt(schemas_str, question)
        response = model.generate_response(prompt)
        result = response

        intent = result.get("intent")
        if intent in ["general", "dangerous"]:
            return {"question_type": intent, "target_db_ids": []}


        db_ids = result.get("db_ids") 

        if intent not in ["query", "analysis", "general", "dangerous"]:
            return {"error": [f"Classifier returned an unknown intent: {intent}"]}

        # --- VALIDATION LOGIC ---
        # Validate that db_ids is a list and that all items in it are valid.
        if not isinstance(db_ids, list):
            return {"error": [f"Classifier response for 'db_ids' was not a list, but {type(db_ids)}"]}

        # Check if any of the returned db_ids are invalid
        invalid_dbs = [db_id for db_id in db_ids if db_id not in state["db_schemas"]]
        if invalid_dbs:
            return {"error": [f"Classifier selected one or more invalid db_ids: {', '.join(invalid_dbs)}"]}

        # For 'general' intent, ensure db_ids is empty
        if intent == "general" and db_ids:
             logger.warning(f"Classifier returned 'general' intent but non-empty db_ids: {db_ids}. Overriding to empty list.")
             db_ids = []

        
        return {"question_type": intent, "target_db_ids": db_ids} 

    except Exception as e:
        return {"error": [f"Failed to parse classifier response: {e}"]}