import asyncio
import logging
import json
import time
from typing import TypedDict, Annotated, List, Dict, Any, Literal

from app.models.query import NLQueryRequest, FinalResponse
from app.services.db_inspector import DatabaseInspector
from app.services.query_generator import QueryGenerator
from app.services.query_executor import SafeQueryExecutor
from app.services.summary_generator import SummaryGenerator
from app.services.insight_generator import InsightGenerator
from app.services.data_joiner import DataJoiner
from app.services.classify_user_intent import classify_user_intent
from app.services.general_answer import generate_general_llm_response
from app.utils.exceptions import ConnectionError, SchemaError, IntentClassificationError, GeneralAnswerError, QueryGenerationError, QueryExecutionError, JoinError, AnalysisError, LLMNotConfiguredError
from app.utils.LLM_configuration import LLMConfig
from app.db.db_connector import get_db_connection
from app.core.config import settings

from langgraph.graph import StateGraph, END # type: ignore
from langgraph.graph.message import add_messages # type: ignore
import google.generativeai as genai # type: ignore

logger = logging.getLogger(__name__)



# 1. Define the new Graph State
class MultiDBQueryState(TypedDict):
    # Inputs
    request: NLQueryRequest
    
    # Global state
    db_connections: Dict[str, Any]
    db_schemas: Dict[str, Dict[str, Any]]
    llm: LLMConfig

    error: Annotated[List[str], add_messages]

    # Classification
    requires_db_context: bool
    question_type: Literal["query", "analysis", "general"]
    
    # Path for 'query'
    target_db_ids: List[str | None]  # The target databases ID for the query
    generated_query_plan: Dict[str, str] # db_id -> query string
    execution_results: List[Dict[str, Any]]
    final_data: List[Dict[str, Any]]
    
    # Final output
    final_response: FinalResponse




### 2. Define Nodes for the Graph




# This node establishes connections to all databases specified in the request.
async def get_all_db_connections_node(state: MultiDBQueryState) -> Dict[str, Any]:
    start_time = time.time()
    connections = {}
    for params in state["request"].connections:
        try:
            logger.info(f"Establishing connection to {params.id} ({params.db_type})...")
            conn = await get_db_connection(params)
            connections[params.id] = conn
        except Exception as e:
            logger.error(f"Failed to connect to DB {params.id}: {e}")
            raise ConnectionError(params.id, str(e))

    try:
        logger.info(f"Successfully established {len(connections)} DB connections.")
        return {"db_connections": connections}
    finally:
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"get_all_db_connections_node took {elapsed:.2f} ms")




# This node retrieves schema information from all connected databases.
async def get_all_schemas_node(state: MultiDBQueryState) -> Dict[str, Any]:
    start_time = time.time()
    schemas, connections = {}, state["db_connections"]
    all_params = {p.id: p for p in state["request"].connections}

    for db_id, conn in connections.items():
        try:
            params = all_params[db_id]
            logger.info(f"Inspecting schema for {db_id}...")
            inspector = DatabaseInspector(conn, params.db_type)
            schema_repr = await inspector.get_schema_representation()
            schemas[db_id] = {"db_type": params.db_type, **schema_repr}

        except Exception as e:
            logger.error(f'Error fetching schema for db_id: {db_id}')
            raise SchemaError(db_id, str(e))
    try:
        logger.info(f"Successfully inspected {len(schemas)} schemas.")
        return {"db_schemas": schemas}
    finally:
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"get_all_schemas_node took {elapsed:.2f} ms")




# This node classifies the question into 'query' or 'analysis' intent and selects the target database.
async def classify_question_node(state: MultiDBQueryState) -> Dict[str, Any]:
    start_time = time.time()
    question = state["request"].question
    # Sanitize schema for the prompt to avoid overwhelming the LLM
    schemas_for_prompt = {
        db_id: {
            "db_type": sch["db_type"],
            "schema": sch["schema"] # Only include the core schema, not example data
        } for db_id, sch in state["db_schemas"].items()
    }

    try:
        schemas_str = json.dumps(schemas_for_prompt, indent=2)
    except Exception as e:
        logger.error(f"Failed to classify question: {e}")
        raise IntentClassificationError(str(e))

    logger.info(f"Classifying question intent (query vs analysis vs general...)")

    llm = state.get("llm")
    if not llm: raise LLMNotConfiguredError("LLM needs to be configured")
    try:
        classification = await classify_user_intent(llm, schemas_str, question, state)
        if "error" in classification:
            logger.error(f"Classification error: {classification['error']}")
            raise IntentClassificationError(str(classification["error"]))
        
        intent = classification["question_type"]
        target_db_ids = classification["target_db_ids"]
        logger.info(f"Classified intent: '{intent}', Target DBs: '{target_db_ids}'")


        if intent in ['query', 'analysis'] and not any(db_id in state["db_schemas"] for db_id in target_db_ids):
            error = f"Target databases '{target_db_ids}' not found in schemas for question type '{intent}'."
            raise IntentClassificationError(str(error))

        
        return {
            "question_type": intent,
            "target_db_ids": target_db_ids,
            "requires_db_context": True if intent in ['query', 'analysis'] else False,
        }
    except Exception as e:
        logger.error(f"Failed to classify question: {e}")
        raise IntentClassificationError(str(e))
    finally:
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"classify_question_node took {elapsed:.2f} ms")




# This node generates a general answer without needing database context.
async def general_answer_node(state: MultiDBQueryState) -> Dict[str, Any]:
    start_time = time.time()
    question = state["request"].question
    logger.info(f"Generating general answer.")
    
    llm = state.get("llm")
    if not llm: raise LLMNotConfiguredError("LLM needs to be configured")
    
    try:
        response = await generate_general_llm_response(llm, question)
        final_response = FinalResponse(success=True, response_type="general_answer", analysis=response)
        return {"final_response": final_response}
    except Exception as e:
        logger.error(f"Failed to generate general answer: {e}")
        raise GeneralAnswerError(str(e))
    finally:
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"general_answer_node took {elapsed:.2f} ms")


# This node generates a query based on the classified intent and the target database.
async def generate_query_node(state: MultiDBQueryState) -> Dict[str, Any]:
    start_time = time.time()
    question = state["request"].question
    intent = state["question_type"]
    db_ids = state["target_db_ids"]

    logger.info(f"Generating multi-db query plan for intent '{intent}' on DBs: {', '.join(db_ids)}")

    # 1. Consolidate schemas to pass to the planner
    schemas_to_plan = {}
    for db_id in db_ids:
        if db_id in state["db_schemas"]:
            schemas_to_plan[db_id] = state["db_schemas"][db_id]
        else:
            error = f"Database ID '{db_id}' not found in schemas."
            raise QueryGenerationError(str(error))

    # 2. Call the new planner method
    llm = state.get("llm")
    if not llm: raise LLMNotConfiguredError("LLM needs to be configured")
    try:
        query_gen = QueryGenerator()
        generated_plan = await query_gen.generate_query_plan(
            model=llm,
            intent=intent,
            schemas_for_planning=schemas_to_plan,
            question=question
        )
        logger.info(f"Query plan generation complete.")
        return {"generated_query_plan": generated_plan}
    except Exception as e:
        logger.error(f"Query plan generation failed: {e}")
        raise QueryGenerationError(str(e))
    finally:
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"generate_query_node took {elapsed:.2f} ms")




# This node executes the generated query on the target database.
async def execute_query_node(state: MultiDBQueryState) -> Dict[str, Any]:
    start_time = time.time()
    query_plan = state.get("generated_query_plan")
    if not query_plan or not query_plan.get("queries"):
        logger.info(f"No queries to execute in the plan.")
        return {"execution_results": {}}
    logger.info(f"Starting execution of {len(query_plan['queries'])} queries from the plan...")

    # A list to hold the results from all executions, keyed by db_id.
    all_results = []
    
    # Create a list of coroutine tasks to run in parallel
    tasks = []
    for query_info in query_plan["queries"]:
        query_id = query_info["query_id"]
        db_id = query_info["db_id"]
        query = query_info["query"]
        query_type = query_info["query_type"]
        

        db_conn = state["db_connections"].get(str(db_id), {})
        db_type = state["db_schemas"].get(str(db_id), {}).get("db_type")


        if db_conn is None or db_type not in ["mysql", "postgresql", "mongodb"]:
            error_msg = f"Connection or schema info not found for db_id: {db_id}"
            logger.error(f"{error_msg}")
            raise QueryExecutionError(db_id, str(error_msg))
        
        # Create a task for each query execution and add it to the list
        task = _execute_single_query(db_id, db_type, db_conn, query, query_id, query_type)
        tasks.append(task)
    
    try:
        # Run all query execution tasks concurrently
        execution_outputs = await asyncio.gather(*tasks)
        
        # Process the results
        for result in execution_outputs:
            if result.get("error"):
                # If any query fails, halte and return the error
                logger.error(f"A query execution failed: {result['error']}")
                return {"error": [f"A query execution failed: {result['error']}"]}
            
            # Store successful result in the dictionary
            all_results.append({
                "query_id": result['query_id'],
                'db_id': result['db_id'],
                'db_type': result['db_type'],
                'data': result['data']}
            )

        logger.info(f"All queries executed successfully.")
        return {"execution_results": all_results}
    except Exception as e:
        logger.error(f"Query execution failed on DB '{db_id}': {e}")
        raise QueryExecutionError(db_id, str(e))
    finally:
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"execute_query_node took {elapsed:.2f} ms")


# This helper coroutine executes a single query and returns a structured result.
async def _execute_single_query(db_id: str, db_type: str, db_conn: Any, query: Any, query_id: Any, query_type: str) -> Dict[str, Any]:
    """Helper coroutine to execute one query and return a structured result."""
    try:
        executor = SafeQueryExecutor(db_conn, db_type, db_id)
        result_data = await executor.execute(query, query_type)
        logger.info(f"Query for '{db_id}' executed, {result_data['row_count']} rows returned.")
        return {"db_id": db_id, "db_type": db_type, "data": result_data, "query_id" : query_id}
    except Exception as e:
        logger.error(f"Failed to execute query for '{db_id}': {e}")
        return {"db_id": db_id, "error": str(e)}




# Node to perform join operations
async def join_data_node(state: MultiDBQueryState) -> Dict[str, Any]:
    start_time = time.time()
    logger.info(f"Assembling final data tables from execution results...")

    execution_results = state.get("execution_results", [])
    query_plan = state.get("generated_query_plan", {})
    join_on_plan = query_plan.get("join_on", [])

    if not execution_results:
        logger.warning(f"No execution results found to join.")
        return {"final_data": []}
    
    try:
        joiner = DataJoiner()
        final_data = joiner.execute_join_plan(execution_results, join_on_plan)
        
        logger.info(f"Data assembly complete. {len(final_data)} Joined table(s) created.")
        return {"final_data": final_data}
    except Exception as e:
        logger.error(f"An error occurred during data joining: {e}", exc_info=True)
        raise JoinError(str(e))
    finally:
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"join_data_node took {elapsed:.2f} ms")


# This node processes the result for a 'query' intent, including data, summary, and visualization.
async def process_query_result_node(state: MultiDBQueryState) -> Dict[str, Any]:
    start_time = time.time()
    final_data = state["final_data"]
    question = state["request"].question
    logger.info(f"Generating summarya and final data for query type  question...")
    try:
        llm = state.get("llm")
        if not llm: raise LLMNotConfiguredError("LLM needs to be configured")
        summary_service = SummaryGenerator()
        summary = await summary_service.analyze(llm, question, final_data)
        summary_data_len = len(summary["detailed_analysis"]["data"])
        logger.info(f"{summary_data_len} Final Table(s) created")
        analysis = summary["detailed_analysis"]["analysis"]
        visualization = summary["detailed_analysis"]["visualization_hint"]
        table_desc = summary["detailed_analysis"]["table_desc"]
        for data in summary["detailed_analysis"]["data"]:
            final_data.append(data)
        state["final_data"] = final_data
        final_data_len = len(state["final_data"])
        logger.info(f"{final_data_len} Data Instances Ready")
        final_response = FinalResponse(
            success=True,
            response_type="query_result",
            analysis=analysis,
            visualization= visualization,
            generated_query=state["generated_query_plan"],
            data=state["final_data"],
            table_desc = table_desc
        )
        logger.info(f"Analysis generated successfully.")
        return {"final_response": final_response}
    except Exception as e:
        logger.error(f"Failed to generate analysis: {e}")
        raise AnalysisError(str(e))
    finally:
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"process_query_result_node took {elapsed:.2f} ms")


# This node synthesizes a final text answer for an 'analysis' intent using the fetched data.
async def process_analysis_result_node(state: MultiDBQueryState) -> Dict[str, Any]:
    start_time = time.time()
    final_data = state["final_data"]
    question = state["request"].question
    logger.info(f"Generating detailed analysis for high-level question...")
    try:
        llm = state.get("llm")
        if not llm: raise LLMNotConfiguredError("LLM needs to be configured")
        insight_service = InsightGenerator()
        insights = await insight_service.analyze(llm, question, final_data)
        insights_data_len = len(insights["detailed_analysis"]["data"])
        logger.info(f"{insights_data_len} Final Table(s) created")
        analysis = insights["detailed_analysis"]["analysis"]
        visualization = insights["detailed_analysis"]["visualization_hint"]
        table_desc = insights["detailed_analysis"]["table_desc"]
        for data in insights["detailed_analysis"]["data"]:
            final_data.append(data)
        state["final_data"] = final_data
        final_data_len = len(state["final_data"])
        logger.info(f"{final_data_len} Data Instances Ready")
        final_response = FinalResponse(
            success=True,
            response_type="analysis_result",
            analysis=analysis,
            visualization= visualization,
            generated_query=state["generated_query_plan"],
            data=state["final_data"],
            table_desc = table_desc
        )
        logger.info(f"Analysis generated successfully.")
        return {"final_response": final_response}
    except Exception as e:
        logger.error(f"Failed to generate analysis: {e}")
        raise AnalysisError(str(e))
    finally:
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"process_analysis_result_node took {elapsed:.2f} ms")

### 3. Define Conditional Edges

def should_get_db_context(state: MultiDBQueryState) -> str:
    if state.get("error"): return "error"
    return "get_context" if state.get("requires_db_context") else "general_question"


def check_execution_result(state: MultiDBQueryState) -> str:
    if state.get("error"):
        return "error"
    
    intent = state.get("question_type")
    if intent == "query":
        return "finalize_query"
    elif intent == "analysis":
        return "finalize_analysis"
    return "error"




### 4. Build the Graph
def create_multi_db_query_graph():
    workflow = StateGraph(MultiDBQueryState)
    
    # Core flow nodes
    workflow.add_node("get_all_db_connections", get_all_db_connections_node)
    workflow.add_node("get_all_schemas", get_all_schemas_node)
    workflow.add_node("classify_question", classify_question_node)
    workflow.add_node("generate_query", generate_query_node)
    workflow.add_node("execute_query", execute_query_node)
    workflow.add_node("join_data",  join_data_node)

    # Path-specific final processing nodes
    workflow.add_node("general_answer", general_answer_node)
    workflow.add_node("process_query_result", process_query_result_node)
    workflow.add_node("process_analysis_result", process_analysis_result_node)

    # Entry and edges
    workflow.set_entry_point("get_all_db_connections")
    workflow.add_edge("get_all_db_connections", "get_all_schemas")
    workflow.add_edge("get_all_schemas", "classify_question")

    # Conditional routing based on whether the question requires database context
    workflow.add_conditional_edges("classify_question", should_get_db_context, {
        "get_context": "generate_query",
        "general_question": "general_answer",
        "error": END
    })
    workflow.add_edge("general_answer", END)

    # Continue with the context-aware flow
    workflow.add_edge("generate_query", "execute_query")
    workflow.add_edge("execute_query", "join_data")

    # Routing based on question intent
    workflow.add_conditional_edges("join_data", check_execution_result, {
        "finalize_query": "process_query_result",
        "finalize_analysis": "process_analysis_result",
        "error": END
    })

    # Endpoints for each path
    workflow.add_edge("process_query_result", END)
    workflow.add_edge("process_analysis_result", END)

    return workflow.compile()


multi_db_query_app = create_multi_db_query_graph()



# 5. The Main Orchestrator Function
async def process_natural_language_query(
    request: NLQueryRequest
) -> FinalResponse:
    
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