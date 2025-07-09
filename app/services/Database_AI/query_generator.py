import logging
import json
from app.prompts.plan_generation_prompt import get_multi_db_query_plan_prompt
from app.utils.LLM_configuration import LLMConfig
from app.utils.exceptions import LLMNotConfiguredError

logger = logging.getLogger(__name__)

class QueryGenerator:
    def __init__(self):
        pass

    async def generate_query_plan(self, model: LLMConfig, intent: str, schemas_for_planning: dict, question: str) -> dict:
        if not model:
            logger.error("LLM for query generator is not configured.")
            raise LLMNotConfiguredError("LLM for query generator is not configured.")


        # 1. Get the new multi-db prompt
        try:
            prompt = get_multi_db_query_plan_prompt(
                schemas=schemas_for_planning,
                user_question=question,
                intent=intent
            )
        except Exception as e:
            logger.error(f"Error building the multi-db prompt: {e}")
            raise ValueError("Error building the multi-db prompt") from e

        # 2. Call the LLM
        try:
            plan = model.generate_response(prompt)  

            # The LLM should return a valid JSON object representing the plan
            if not isinstance(plan, dict):
                logger.error("LLM response is not a valid JSON object.")
                raise ValueError("LLM response is not a valid JSON object.")
            if 'join_on' not in plan or 'queries' not in plan:
                logger.error("LLM response does not contain required keys: 'join_on' and 'queries'.")
                raise ValueError("LLM response does not contain required keys: 'join_on' and 'queries'.")
            if not isinstance(plan['join_on'], list) or not isinstance(plan['queries'], list):
                logger.error("LLM response 'join_on' and 'queries' must be lists.")
                raise ValueError("LLM response 'join_on' and 'queries' must be lists.")

            # Validate 'join_on' entries and ensure db_id are string-convertible
            for join_entry in plan['join_on']:
                if not isinstance(join_entry, list):
                    logger.error("Each 'join_on' entry must be a list.")
                    raise ValueError("Each 'join_on' entry must be a list")

            # Validate 'queries' entries and ensure db_id are string-convertible
            for query_info in plan["queries"]:
                if not isinstance(query_info, dict) or 'db_id' not in query_info or 'query' not in query_info:
                    logger.error("Each 'query' entry must be a dictionary with 'db_id' and 'query'.")
                    raise ValueError("Each 'query' entry must be a dictionary with 'db_id' and 'query'.")
            return plan

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from multi-db plan response: {e}")
            raise RuntimeError(f"Failed to parse JSON from multi-db plan response: {e}") from e
        except Exception as e:
            logger.error(f"LLM query plan generation failed: {e}")
            raise RuntimeError("LLM query plan generation failed.") from e