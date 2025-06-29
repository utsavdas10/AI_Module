class Error(Exception):
    """Base exception for all query-related errors in the application."""
    pass

class ConnectionError(Error):
    """Raised when establishing a connection to a database fails."""
    def __init__(self, db_id: str, reason: str):
        super().__init__(f"Failed to connect to database '{db_id}': {reason}")
        self.db_id = db_id
        self.reason = reason

class SchemaError(Error):
    """Raised when schema extraction from a database fails."""
    def __init__(self, db_id: str, reason: str):
        super().__init__(f"Failed to fetch schema for database '{db_id}': {reason}")
        self.db_id = db_id
        self.reason = reason

class IntentClassificationError(Error):
    """Raised when the LLM fails to classify the user's intent."""
    def __init__(self, reason: str):
        super().__init__(f"Failed to classify question: {reason}")
        self.reason = reason

class GeneralAnswerError(Error):
    """Raised when the LLM fails to generate a general answer."""
    def __init__(self, reason: str):
        super().__init__(f"Failed to generate general answer: {reason}")
        self.reason = reason

class QueryGenerationError(Error):
    """Raised when the LLM fails to generate SQL/NoSQL queries."""
    def __init__(self, reason: str):
        super().__init__(f"Query generation failed: {reason}")
        self.reason = reason

class QueryExecutionError(Error):
    """Raised when a query execution fails on any DB."""
    def __init__(self, db_id: str, reason: str):
        super().__init__(f"Query execution failed on DB '{db_id}': {reason}")
        self.db_id = db_id
        self.reason = reason

class JoinError(Error):
    """Raised when joining data from multiple DBs fails."""
    def __init__(self, reason: str):
        super().__init__(f"Failed to join data: {reason}")
        self.reason = reason

class AnalysisError(Error):
    """Raised when result analysis or visualization generation fails."""
    def __init__(self, reason: str):
        super().__init__(f"Failed to analyze or summarize results: {reason}")
        self.reason = reason

class LLMNotConfiguredError(Error):
    """Raised when the LLM client is not available or improperly configured."""
    def __init__(self, context: str = ""):
        message = "LLM client is not configured or unavailable."
        if context:
            message += f" Context: {context}"
        super().__init__(message)
        self.context = context

class SecurityError(Error):
    """Raised when a security or authentication/authorization or Dangerous Query error occurs."""
    def __init__(self, reason: str):
        super().__init__(f"Security error: {reason}")
        self.reason = reason


