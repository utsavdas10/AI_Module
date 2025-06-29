# AI Agent

This project is a FastAPI-based AI agent that translates natural language questions into executable queries across multiple databases, including PostgreSQL, MySQL, and MongoDB. It uses a Large Language Model (LLM) to understand user intent, generate complex query plans, and synthesize the results into actionable insights.

## Key Features

-   **Natural Language to Multi-DB Query:** Ask questions in plain English and get answers from one or more databases simultaneously.
-   **Stateful Orchestration:** Powered by `langgraph` to manage the complex workflow from connection to final analysis.
-   **Extensible Architecture:** Easily add support for new database types.
-   **Comprehensive Analysis:** Generates not just data, but also textual analysis, summaries, and visualization hints.

## Documentation

-   **API Documentation:** For users of the API.
-   **Maintenance & Contribution Guide:** For developers working on the codebase.



## API Documentation

The API is built with FastAPI and provides a single main endpoint for natural language queries.

### Base URL




### Endpoints

#### `POST /api/v1/query`

- **Description:**  
  Submit a natural language question and database connection details. The system will generate a query plan, execute it, and return results, analysis, and visualization hints.

- **Request Body Example:**
    ```json
    {
      "question": "Show me the top 5 selling books and their authors.",
      "connections": [
        {
          "id": "1",
          "db_type": "postgresql",
          "host": "your-db-host",
          "port": 5432,
          "username": "user",
          "password": "pass",
          "database": "dbname",
          "ssl_mode": "prefer"
        }
      ]
    }
    ```

- **Response Example:**
    ```json
    {
      "success": true,
      "response_type": "query_result",
      "analysis": "Top 5 selling books and their authors are ...",
      "generated_query": { ... },
      "execution_time_ms": 1234,
      "data": [ ... ],
      "visualization": { ... },
      "table_desc": { ... }
    }
    ```

- **Error Handling:**  
  If an error occurs, the response will have `success: false`, an `error_type`, and an `error_message` describing the issue.

- **Interactive Documentation:**  
  Visit `/docs` or `/redoc` on your running server for interactive OpenAPI documentation and to try out the API.

---

## Maintenance & Contribution Guide

### Project Structure

- `app/` - Main application code
    - `api/` - API endpoints (FastAPI routers)
    - `services/` - Core business logic, orchestration, and LLM integration
    - `models/` - Pydantic models and schemas
    - `core/` - Configuration and settings
    - `utils/` - Utility functions and custom exceptions
- `tests/` - (Optional) Automated tests

### Setup

1. **Install dependencies:**
    ```
    pip install -r [requirements.txt](http://_vscodecontentref_/0)
    ```

2. **Run the server:**
    ```
    uvicorn app.main:app --reload
    ```

3. **Environment variables:**  
   Configure your environment variables in a `.env` file or via `app/core/config.py`.  
   Required variables may include database credentials, LLM API keys, and other settings.

### Contributing

- Fork the repository and create a feature branch.
- Write clear, well-documented code and add tests where appropriate.
- Use `black` or `ruff` for code formatting and linting.
- Submit a pull request with a clear description of your changes and reference any related issues.

### Testing

- Add tests in the `tests/` directory.
- Use `pytest` to run tests:

    **Example**
    ```
    pytest tests/test_api.py
    pytest tests/test_api_mock.py
    ```

### Troubleshooting

- Check logs for errors (`uvicorn` logs).
- Ensure your database credentials and network access are correct.
- For LLM-related issues, verify your API keys and model configuration.
- If you encounter schema or query errors, check that your database schemas match the expected format.

### Support

- For questions, open an issue on GitHub or contact the maintainers.
- Contributions, bug reports, and feature