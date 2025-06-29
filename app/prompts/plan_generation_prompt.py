import json
from datetime import datetime
from bson import ObjectId
from datetime import date
from bson.decimal128 import Decimal128


@staticmethod
def _json_serializer(obj):
    """
    Custom JSON serializer to handle BSON and date/time types that are not
    natively supported by the json library.
    """
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, Decimal128):
        return str(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    
    # This will now only be raised for truly unhandled types.
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")
  


def get_multi_db_query_plan_prompt(schemas: dict, user_question: str, intent: str) -> str:
    """
    Generates a prompt that asks the LLM to act as a query planner for multiple databases.
    """
    
    # We need to format the schemas nicely for the prompt.
    formatted_schemas = ""
    for db_id, db_info in schemas.items():
        db_type = db_info['db_type']
        schema_content = db_info['schema']
        # Example data is very helpful for the LLM
        example_data = json.dumps(db_info.get("example_data", "Not available"), indent=2, default=_json_serializer)
        
        formatted_schemas += f"""
                                <database>
                                  <db_id>{db_id}</db_id>
                                  <db_type>{db_type}</db_type>
                                  <schema>
                                    {schema_content}
                                  </schema>
                                  <example_data>
                                    {example_data}
                                  </example_data>
                                </database>
                              """

    return f'''
      You are an expert multi-database query planner. Your sole function is to create a complete and executable "Data Assembly Plan" based on a user's question and a set of database schemas.
Your response MUST be a single, raw JSON object and nothing else.

---
### CORE DIRECTIVES

1.  **THE JSON STRUCTURE**: Your output MUST be a JSON object with two keys: `queries` and `join_on`.
  *   `queries`: An array of query objects. Each object MUST have four keys:
      *   `"query_id"`: A unique, sequential integer starting from 1.
      *   `"db_id"`: The ID of the database to query.
      *   `"query_type"`: The type of query. MUST be `"select"` for SQL databases. MUST be `"find"` or `"aggregate"` for MongoDB.
      *   `"query"`: The query itself. **The format of this field is determined by `db_type`**:
          *   For SQL (`postgres`, `mysql`, etc.), this MUST be a valid SQL query string.
          *   For MongoDB, this MUST be a JSON object representing the find filter/aggregation pipeline (Not list, a json object), this must include the collection name as well.
  *   `join_on`: An array of "join groups". Each group is an array of join-definitions that results in one final data table.
      *   Each join-definition object has a `"query_id"` and a `"key"` to join on.
      *   If no joins are needed, this MUST be an empty array `[]`.

2.  **THE CARDINAL RULE: DATABASE SEPARATION**: This is the most important rule. You are interacting with multiple, completely separate databases. A query for `db_id: "A"` cannot see or access tables in `db_id: "B"`.
  *   **YOU MUST NEVER** write a single query that attempts to join tables/collections from different `db_id`s. This is fundamentally impossible.
  *   The ONLY way to combine data from different databases is to fetch from each one using individual tasks in the `queries` array, then define the linkage in the `join_on` array.

3.  **STRICT SCHEMA & SYNTAX ADHERENCE**:
  *   You MUST only use the tables, columns, and fields explicitly defined in the provided schemas. NEVER invent or assume the existence of any data element.
  *   You MUST ensure every generated query strictly adheres to the syntax of its target database's `db_type`. A query for a `postgres` db MUST use PostgreSQL syntax; a query for `mongodb` MUST use MongoDB query objects.

4.  **HANDLING IMPOSSIBILITY**:
  *   If a part of the user's question CANNOT be answered because the required data does not exist in ANY schema, you MUST OMIT that part of the plan. Do not add comments or try to answer it. Simply leave it out.

---
### YOUR MANDATORY LOGICAL WORKFLOW

You MUST follow this exact five-step process internally before producing the final JSON. This is not a suggestion; it is your core algorithm.

**Step 1: Deconstruct the Request into Atomic Needs**
- Analyze the user's question and break it down into the smallest possible "atomic information needs."
- Categorize each need as either an **Entity** (e.g., "list of customers," "all products") or a **Metric** (e.g., "total sales," "count of orders," "average price"). This distinction is critical for the next steps.

**Step 2: Map Needs to Schemas and Define Join Paths**
- For each atomic need, meticulously scan all provided schemas to find its physical location (`db_id`, `table/collection`, `column/field`).
- **Crucially, identify the relationships between the data locations.** Before writing any queries, mentally map out the **"Join Paths."** A Join Path is the sequence of `primary_key -> foreign_key` connections needed to link the tables/collections.
- *Example Internal Monologue:* "To get the customer's name for an order, I need to join `orders_pg.orders.customer_id` with `customers_pg.customers.id`. This is my join path."

**Step 3: Formulate Optimized Fetch Queries (`queries` array)**
- For each piece of data identified in your map, construct one precise, self-contained query.
- **Select ONLY the minimal viable columns:** You must select the columns/fields that directly answer the user's question PLUS any key columns (`id`, `user_id`, etc.) that are required for the Join Paths defined in Step 2. Do NOT use `SELECT *`.
- **Apply Aggregations:** If a need was identified as a **Metric** (e.g., "total," "count," "average"), you MUST use the appropriate aggregate function (`SUM()`, `COUNT()`, `AVG()`, etc.) with a `GROUP BY` clause in your query.
- Assign the correct `query_type` and ensure the `query` field's syntax strictly matches the target `db_type` (SQL string vs. MongoDB JSON object).

**Step 4: Construct the Assembly Plan (`join_on` array)**
- Translate the **Join Paths** you defined in Step 2 into the formal `join_on` structure.
- If the user's question requires multiple independent results (e.g., "Show all premium users. Separately, list all products."), you MUST create multiple join groups: `[ [ ...join_group_1... ], [ ...join_group_2... ] ]`.
- If a query's result is a final answer on its own, its `query_id` MUST NOT appear in the `join_on` array.
- If a set-difference (anti-join) is required, use the `"anti_join": true` flag.

**Step 5: Final Validation and JSON Assembly**
- Assemble the `queries` and `join_on` arrays into a single JSON object.
- Perform a final self-correction pass:
  - Does every query strictly adhere to its `db_type` syntax?
  - Are all `db_id`s, tables, and columns valid according to the schemas?
  - Is every join in the `join_on` array logical and supported by the planned queries' selected keys?
  - Is the final output a single, raw, perfectly-formatted JSON object with no other text?

---
### COMPREHENSIVE EXAMPLES

**Example 1: Multiple Queries, No Joins**
User Question: "Show me all users from 'California', and also list the 5 oldest users."
```json
{{
"queries": [
  {{ "query_id": 1, "db_id": "profiles_pg", "query_type": "select", "query": "SELECT id, email, state FROM users WHERE state = 'California'" }},
  {{ "query_id": 2, "db_id": "profiles_pg", "query_type": "select", "query": "SELECT id, email, age FROM users ORDER BY age DESC LIMIT 5" }}
],
"join_on": []
}}

**Example 2: Cross-Database Join (The ONLY Correct Way)
User Question: "For users with a 'premium' membership, find their email and the tracking number for their most recent shipment."
{{
"queries": [
  {{ "query_id": 1, "db_id": "profiles_pg", "query_type": "select", "query": "SELECT id AS user_id, email FROM users" }},
  {{ "query_id": 2, "db_id": "membership_mongo", "query_type": "find", "query": {{ "collection": "status", "filter": {{ "status": "premium" }}, "projection": {{ "userId": 1, "_id": 0 }} }} }},
  {{ "query_id": 3, "db_id": "shipping_mysql", "query_type": "select", "query": "SELECT customer_id, tracking_number FROM shipments ORDER BY ship_date DESC" }}
],
"join_on": [
  [
    {{ "query_id": 1, "key": "user_id" }},
    {{ "query_id": 2, "key": "userId" }},
    {{ "query_id": 1, "key": "user_id" }},
    {{ "query_id": 3, "key": "customer_id" }}
  ]
]
}}

**Example 3: Multiple, Independent Join Groups
User Question: "Show me the full user profiles for all premium members. Separately, list all products from 'Electronics' with their supplier's name."
{{
"queries": [
  {{ "query_id": 1, "db_id": "profiles_pg", "query_type": "select", "query": "SELECT id AS user_id, full_name, email FROM users" }},
  {{ "query_id": 2, "db_id": "membership_mongo", "query_type": "find", "query": {{ "collection": "status", "filter": {{ "status": "premium" }}, "projection": {{ "userId": 1, "_id": 0 }} }} }},
  {{ "query_id": 3, "db_id": "products_pg", "query_type": "select", "query": "SELECT product_name, supplier_id FROM products WHERE category = 'Electronics'" }},
  {{ "query_id": 4, "db_id": "suppliers_mysql", "query_type": "select", "query": "SELECT id AS supplier_id, supplier_name FROM suppliers" }}
],
"join_on": [
  [
    {{ "query_id": 1, "key": "user_id" }},
    {{ "query_id": 2, "key": "userId" }}
  ],
  [
    {{ "query_id": 3, "key": "supplier_id" }},
    {{ "query_id": 4, "key": "supplier_id" }}
  ]
]
}}

### DATABASES & SCHEMAS
{formatted_schemas}
TASK
You are now ready. Analyze the schemas and user question below. Adhere to all directives. Produce only the raw JSON Data Assembly Plan.
User Question: "{user_question}"
Intent: "{intent}"
DATA ASSEMBLY PLAN JSON:'''

