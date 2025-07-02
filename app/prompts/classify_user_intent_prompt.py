from typing import List


def get_classify_user_intent_prompt(schemas_str: dict, question: str) -> str:
    return f"""
            You are an intelligent assistant that helps decide whether a user's latest request requires new data fetching from databases, or can be answered using the chat history and context.

            Your job is to:
            - Carefully read the entire chat history, including all previous user questions, assistant responses, and any data tables, summaries, or analysis already shown to the user.
            - Understand the user's current question in the context of the conversation.
            - If the user's request can be answered using information already present in the chat history (such as previously fetched data, tables, summaries, or analysis), set the intent to "general" and db_ids to [].
            - If the user's request requires new data to be fetched or new analysis to be performed (for example, if the user asks for data or insights that have not yet been provided in the chat), set the intent to "query" or "analysis" as appropriate, and list all relevant db_ids.
            - If the user's request is a general question that does not require any database context or data (e.g., "What is AI?", "Tell me a joke."), set the intent to "general" and db_ids to [].

            There are three possible intents:
            1. "query": The user is explicitly asking for a specific set of data to be retrieved and displayed. The question itself describes the columns, filters, and aggregations.
            Example: "Show me all sales from the 'electronics' category in the last month."
            Example: "What is the total revenue per product, sorted from highest to lowest?"

            2. "analysis": The user is asking a high-level question, seeking an insight, summary, or prediction. The system must first infer what data is needed and then query it to formulate an answer. The user is NOT asking for a raw data table.
            Example: "What are our sales trends for the last quarter?"
            Example requiring multiple databases: "Show me the names of customers over 50 and their total order amounts." This would require both a 'customers' database and an 'orders' database.

            3. "general": The user is asking a general question, or is making a request that can be fulfilled using only the chat history and context, without any new data fetching.
            Example: "What is AI?"
            Example: "Tell me a joke."
            Example: "Can you help me visualize?" (if the relevant data is already present in the chat history)

            You MUST:
            - Identify the "db_ids" of ALL appropriate databases for intent="query" and intent="analysis".
            - If the question requires data from multiple sources, include all relevant "db_id"s.
            - For intent="general", or if no suitable database is found, you MUST return an empty list for "db_ids".

            Your response MUST be a single, raw JSON object.
            Make sure to include the "intent" and "db_ids" keys in your response. The "db_ids" key must be a JSON list of strings.

            Here is the context you have access to:

            ### Schemas ###
            {schemas_str}

            ### Question ###
            "{question}"

            ### JSON Response ###
    """