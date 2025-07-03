# AI Module Codebase Maintenance & Developer Guide

Welcome to the AI Module! This documentation is designed to help new developers and interns quickly understand the architecture, flow, and maintenance practices of this codebase. It covers the purpose and usage of each major module, function, and how they interact, as well as best practices for extending and maintaining the system.

---

## Table of Contents
- [Project Overview](#project-overview)
- [Architecture Diagram](#architecture-diagram)
- [Core Modules & Their Roles](#core-modules--their-roles)
- [Main Workflow: Orchestration](#main-workflow-orchestration)
- [LLM Configuration & Usage](#llm-configuration--usage)
- [Prompt Engineering](#prompt-engineering)
- [Logging & Error Handling](#logging--error-handling)
- [Adding New Features or Models](#adding-new-features-or-models)
- [Testing & Debugging](#testing--debugging)
- [Maintenance Best Practices](#maintenance-best-practices)
- [FAQ](#faq)

---

## Project Overview
This project is a modular, context-aware AI orchestration system that leverages LLMs (Gemini, OpenAI, Claude) to answer user questions, generate queries, analyze data, and provide recommendations. It supports multi-database querying, robust prompt engineering, and structured, JSON-based outputs.

---

## Architecture Diagram

```mermaid
graph TD
    A[User Request] --> B[ai_compute.py (Entry Point)]
    B --> C[orchestrator.py (Main Workflow)]
    C --> D1[DB Inspector]
    C --> D2[Query Generator]
    C --> D3[General Answer]
    D1 --> E1[Query Executor]
    D2 --> E2[Summary/Insight Generator]
    E1 --> F[Data Joiner]
    E2 --> F
    F --> G[Final Response]
```

---

## Core Modules & Their Roles

### 1. `ai_compute.py` (Entry Point)
- **Purpose:** Accepts user requests, sets up logging, and calls the orchestrator.
- **Key Function:** `process_query(request)`
    - Times the request, calls the orchestrator, and returns a structured response.
    - **Docstring Example:**
    ```python
    async def process_query(request: FullQueryRequest):
        """
        Main entry point for processing a user query.
        - Times the request
        - Calls the orchestrator
        - Returns a FinalResponse object
        """
        # ...existing code...
    ```
- **Maintenance:** Update logging or request/response structure as needed.

### 2. `app/services/orchestrator.py` (Main Orchestration)
- **Purpose:** Central workflow manager. Handles the full lifecycle: DB connection, schema inspection, intent classification, query generation, execution, joining, and final response.
- **Key Functions/Nodes:**
    - `process_natural_language_query(request)` — Main async entry point.
    - Node functions: `get_all_db_connections_node`, `get_all_schemas_node`, `classify_question_node`, `generate_query_node`, `execute_query_node`, `join_data_node`, `process_query_result_node`, `process_analysis_result_node`, `general_answer_node`.
    - **State Management:** Uses a state dict to pass data between nodes.
    - **Node Example:**
    ```python
    async def classify_question_node(state: MultiDBQueryState) -> Dict[str, Any]:
        """
        Classifies the user's question as 'query', 'analysis', or 'general'.
        Uses LLM to determine intent and target DBs.
        """
        # ...existing code...
    ```
- **Maintenance:** Add new nodes for new features, update state structure, or modify workflow edges as needed.

### 3. `app/utils/LLM_configuration.py` (LLMConfig)
- **Purpose:** Unified interface for all LLM providers. Handles chat history, model selection, and robust JSON response parsing.
- **Key Functions:**
    - `generate_response(prompt)` — Synchronous, always returns a dict or string.
    - `parse_json_response(response_text)` — Robustly extracts JSON from LLM output.
    - **Docstring Example:**
    ```python
    def generate_response(self, prompt: str) -> dict:
        """
        Sends a prompt to the configured LLM and returns the parsed response.
        Handles chat history and provider-specific logic.
        """
        # ...existing code...
    ```
- **Maintenance:** Add new providers, update parsing logic, or extend chat history handling.

### 4. `app/services/classify_user_intent.py`
- **Purpose:** Classifies user questions as `query`, `analysis`, or `general` using LLM.
- **Key Function:** `classify_user_intent(model, schemas_str, question, state)`
    - **Docstring Example:**
    ```python
    async def classify_user_intent(model: LLMConfig, schemas_str, question, state):
        """
        Uses LLM to classify the user's question intent and select target DBs.
        Returns a dict with 'question_type' and 'target_db_ids'.
        """
        # ...existing code...
    ```
- **Maintenance:** Update prompt logic or validation as needed.

### 5. `app/services/general_answer.py`
- **Purpose:** Handles general, context-aware LLM answers (not requiring DB context).
- **Key Function:** `generate_general_llm_response(model, question)`
    - **Docstring Example:**
    ```python
    async def generate_general_llm_response(model: LLMConfig, question: str) -> dict:
        """
        Generates a general answer using the LLM, returning a structured dict.
        """
        # ...existing code...
    ```
- **Maintenance:** Update prompt or output structure as needed.

### 6. `app/services/query_generator.py`
- **Purpose:** Generates multi-DB query plans using LLM.
- **Key Class:** `QueryGenerator`
    - `generate_query_plan(model, intent, schemas_for_planning, question)`
    - **Docstring Example:**
    ```python
    class QueryGenerator:
        async def generate_query_plan(self, model: LLMConfig, intent: str, schemas_for_planning: dict, question: str) -> dict:
            """
            Generates a query plan for multiple DBs using the LLM.
            Returns a dict with 'queries' and 'join_on'.
            """
            # ...existing code...
    ```
- **Maintenance:** Update prompt, validation, or add new query types.

### 7. `app/services/summary_generator.py` & `app/services/insight_generator.py`
- **Purpose:** Generate summaries, insights, and visualizations from query results using LLM.
- **Key Classes:** `SummaryGenerator`, `InsightGenerator`
    - `analyze(model, question, query_result)`
    - **Docstring Example:**
    ```python
    class SummaryGenerator:
        async def analyze(self, model: LLMConfig, original_question: str, query_result: List[Dict[str, Any]]) -> Dict[str, Any]:
            """
            Generates a detailed summary and visualization hints from query results using the LLM.
            Returns a dict with 'analysis', 'data', 'visualization_hint', and 'table_desc'.
            """
            # ...existing code...
    ```
- **Maintenance:** Update analysis prompt, output parsing, or add new insight types.

### 8. `app/services/data_joiner.py`
- **Purpose:** Joins data from multiple DBs as per the query plan.
- **Key Class:** `DataJoiner`
    - `execute_join_plan(execution_results, join_on_plan)`
    - **Docstring Example:**
    ```python
    class DataJoiner:
        def execute_join_plan(self, execution_results, join_on_plan):
            """
            Joins data from multiple DBs according to the join plan.
            Returns a list of joined tables.
            """
            # ...existing code...
    ```
- **Maintenance:** Update join logic for new DB types or join strategies.

### 9. `app/services/db_inspector.py`
- **Purpose:** Inspects DB schemas for use in query planning and validation.
- **Key Class:** `DatabaseInspector`
    - `get_schema_representation()`
    - **Docstring Example:**
    ```python
    class DatabaseInspector:
        async def get_schema_representation(self):
            """
            Returns a structured representation of the DB schema for planning.
            """
            # ...existing code...
    ```
- **Maintenance:** Add support for new DB types or schema features.

### 10. `app/services/query_executor.py`
- **Purpose:** Executes generated queries safely on the target DBs.
- **Key Class:** `SafeQueryExecutor`
    - `execute(query, query_type)`
    - **Docstring Example:**
    ```python
    class SafeQueryExecutor:
        async def execute(self, query, query_type):
            """
            Executes a query on the DB and returns the result as a dict.
            """
            # ...existing code...
    ```
- **Maintenance:** Add support for new DBs or query types.

### 11. `app/prompts/` (Prompt Engineering)
- **Purpose:** Contains all prompt templates for LLMs, including general answers, query plans, analysis, and classification.
- **Maintenance:** Update or add new prompt templates as LLM capabilities or requirements evolve.
- **Prompt Example:**
    ```python
    def get_general_answer_prompt(question: str) -> str:
        """
        Returns a robust, context-aware prompt for general LLM answers.
        """
        # ...existing code...
    ```

---

## Main Workflow: Orchestration (with Code Snippet)
```python
async def process_natural_language_query(request: NLQueryRequest) -> FinalResponse:
    """
    Main orchestrator function. Runs the workflow graph for a user request.
    """
    model_provider = request["model_provider"] if "model_provider" in request else settings.DEFAULT_MODEL_PROVIDER
    chat_history = request["chat_history"] if "chat_history" in request else []
    llm = LLMConfig(model_provider, chat_history)
    initial_state = MultiDBQueryState(
        request=request,
        db_connections={}, 
        db_schemas={}, 
        error=[],
        llm=llm
    )
    final_state = await multi_db_query_app.ainvoke(initial_state)
    if final_state.get("error") and not final_state.get("final_response"):
        error_message = ', '.join(final_state['error'])
        return FinalResponse(success=False, response_type="general_answer", summary=f"An error occurred: {error_message}", error_message=error_message)
    return final_state["final_response"]
```

---

## LLM Configuration & Usage
- All LLM calls go through `LLMConfig` for consistency.
- Chat history is maintained for context-aware responses.
- All LLM outputs are parsed to JSON (if possible) for structured downstream use.
- To add a new LLM provider, extend `LLMConfig` and update the provider list.
- **Code Snippet:**
    ```python
    llm = LLMConfig(model_provider="gemini", initial_history=[])
    response = llm.generate_response("What is AI?")
    print(response["analysis"])
    ```

---

## Prompt Engineering
- Prompts are modular and live in `app/prompts/`.
- Each prompt is designed to elicit structured, context-aware, and robust responses from the LLM.
- Update prompt examples and instructions as LLM capabilities improve.
- **Prompt Example:**
    ```python
    prompt = get_general_answer_prompt("What is AI?")
    print(prompt)
    ```

---

## Logging & Error Handling
- Uses `colorlog` for colored, timestamped logs.
- All errors are caught and logged at the appropriate node.
- Custom exceptions are defined in `app/utils/exceptions.py` for clarity.
- Always check logs for warnings/errors when debugging.
- **Logging Example:**
    ```python
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
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    ```

---

## Adding New Features or Models
- Add new nodes or services as needed (e.g., new analysis types, DBs, or LLMs).
- Update the state structure in the orchestrator if new data needs to be passed between nodes.
- Add new prompt templates for new LLM tasks.
- **Adding a New Node Example:**
    ```python
    async def new_feature_node(state: MultiDBQueryState) -> Dict[str, Any]:
        """
        Example node for a new feature.
        """
        # ...feature logic...
        return {"new_feature_result": result}
    ```

---

## Testing & Debugging
- Use the provided test request in `ai_compute.py` as a template.
- Check logs for errors and warnings.
- Add unit tests for new modules and integration tests for new workflows.
- Use mock DBs or LLMs for safe testing.
- **Test Example:**
    ```python
    request = FullQueryRequest(
        question = "Show me sales by genre.",
        connections = [ ... ]
    )
    response = asyncio.run(process_query(request=request))
    print(response)
    ```

---

## Maintenance Best Practices
- **Keep prompts up to date** as LLMs evolve.
- **Document all new functions/classes** in code and update this README.
- **Refactor regularly** for clarity and modularity.
- **Review logs** after any major change.
- **Validate all LLM outputs** for structure before downstream use.
- **Onboard new team members** with this document and a walkthrough of the main workflow.

---

## FAQ
**Q: How do I add a new LLM provider?**
A: Extend `LLMConfig` with the new provider logic and add it to the `SUPPORTED_PROVIDERS` list.

**Q: How do I add a new prompt or task?**
A: Add a new prompt template in `app/prompts/` and a new node/service in `app/services/` as needed.

**Q: What if the LLM returns unstructured output?**
A: All LLM outputs are parsed via `parse_json_response`. If parsing fails, log the error and handle gracefully in the orchestrator/service.

**Q: How do I debug a failing node?**
A: Check the logs for errors/warnings. Each node logs timing and errors. Use the stack trace and error message to locate the issue.

---

For further questions, contact the project maintainer or check the code comments for inline documentation.
