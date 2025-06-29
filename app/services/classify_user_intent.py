import json
import logging
import re

logger = logging.getLogger(__name__)

async def classify_user_intent(llm, schemas_str, question, state):
    # --- PROMPT MODIFICATION ---
    # The prompt now asks for a list of db_ids and provides a multi-DB example.
    prompt = f"""Given a user's question and available database schemas, classify the user's INTENT and identify ALL relevant databases.

                There are three intents:
                1. 'query': The user is explicitly asking for a specific set of data to be retrieved and displayed. The question itself describes the columns, filters, and aggregations.
                Example: "Show me all sales from the 'electronics' category in the last month."
                Example: "What is the total revenue per product, sorted from highest to lowest?"

                2. 'analysis': The user is asking a high-level question, seeking an insight, summary, or prediction. The system must first INFER what data is needed and then query it to formulate an answer. The user is NOT asking for a raw data table.
                Example: "What are our sales trends for the last quarter?"
                Example requiring multiple databases: "Show me the names of customers over 50 and their total order amounts." This would require both a 'customers' database and an 'orders' database.

                3. 'general': The user is asking a general question that does not require any database context. You should make this decision based on the question's content and the schemas provided.
                Example: "What is AI?"
                Example: "Tell me a joke."

                You MUST identify the 'db_ids' of ALL appropriate databases for intent='query' and intent='analysis'.
                If the question requires data from multiple sources, include all relevant 'db_id's.
                For intent='general', or if no suitable database is found, you MUST return an empty list for 'db_ids'.

                Your response MUST be a single, raw JSON object.
                Make sure to include the 'intent' and 'db_ids' keys in your response. The 'db_ids' key must be a JSON list of strings.

                ```
                ### Schemas ###
                {schemas_str}

                ### Question ###
                "{question}"

                ### JSON Response ###
            """
    response = await llm.generate_content_async(
        prompt,
        generation_config={"temperature": 0.0, "max_output_tokens": 1024}
    )
    try:
        # Try to extract JSON from the response text, even if it's not a pure JSON string
        response_text = response.text.strip()
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            # Attempt to extract JSON object from within the response text
            match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if match:
                result = json.loads(match.group(0))
            else:
                raise json.JSONDecodeError("No valid JSON found in response text")

        intent = result.get("intent")
        db_ids = result.get("db_ids") 

        if intent not in ["query", "analysis", "general"]:
            return {"error": [f"Classifier returned an unknown intent: {intent}"]}

        # --- VALIDATION LOGIC MODIFICATION ---
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