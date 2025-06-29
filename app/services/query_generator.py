import logging
import json
from app.prompts.plan_generation_prompt import get_multi_db_query_plan_prompt

logger = logging.getLogger(__name__)

class QueryGenerator:
    def __init__(self):
        pass

    async def generate_query_plan(self, model, intent: str, schemas_for_planning: dict, question: str) -> dict:
        if not model:
            raise RuntimeError("LLM for query generator is not configured.")

        # 1. Get the new multi-db prompt
        try:
            prompt = get_multi_db_query_plan_prompt(
                schemas=schemas_for_planning,
                user_question=question,
                intent=intent
            )
        except Exception as e:
            logger.error(f"Failed to build multi-db prompt: {e}")
            raise ValueError("Error building the multi-db prompt") from e

        # 2. Call the LLM
        try:
            generation_config = {
                "temperature": 0.0,
                "max_output_tokens": 32768, # Increase token limit for this complex task
            }
            response = await model.generate_content_async(prompt, generation_config=generation_config)
            response_text = response.text.strip()

            # 3. Clean and parse the JSON response
            if response_text.startswith("```json"):
                response_text = '\n'.join(response_text.split('\n')[1:-1])

            # The LLM should return a valid JSON object representing the plan
            plan = json.loads(response_text)

            
            if not isinstance(plan, dict):
                raise ValueError("LLM response is not a valid JSON object.")
            if 'join_on' not in plan or 'queries' not in plan:
                raise ValueError("LLM response does not contain required keys: 'join_on' and 'queries'.")
            if not isinstance(plan['join_on'], list) or not isinstance(plan['queries'], list):
                raise ValueError("LLM response 'join_on' and 'queries' must be lists.")

            # Validate 'join_on' entries and ensure db_id are string-convertible
            for join_entry in plan['join_on']:
                if not isinstance(join_entry, list):
                    raise ValueError("Each 'join_on' entry must be a list")


            # Validate 'queries' entries and ensure db_id are string-convertible
            for query_info in plan["queries"]:
                if not isinstance(query_info, dict) or 'db_id' not in query_info or 'query' not in query_info:
                    raise ValueError("Each 'query' entry must be a dictionary with 'db_id' and 'query'.")
            
            return plan

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from multi-db plan response: {e}\nResponse was:\n{response_text}")
            raise RuntimeError("LLM response was not valid JSON.") from e
        except Exception as e:
            logger.error(f"LLM multi-db query plan generation failed: {e}")
            raise RuntimeError("LLM query plan generation failed.") from e