from typing import Annotated, Any
from typing_extensions import TypedDict
import sqlparse
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import AnyMessage, add_messages
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableLambda, RunnableWithFallbacks
from langgraph.prebuilt import ToolNode
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.messages import HumanMessage
from prompt.prompt_templates import query_gen_system
from langchain_core.prompts import ChatPromptTemplate


import re
from core.llm_config import get_llm

from prompt.prompt_templates import query_check_prompt, query_gen_prompt
from tools.sql_tools import (
    db_query_tool,
    get_schema_tool,
    list_tables_tool,
)
import logging

# Setup logging
logging.basicConfig(
    # level=logging.DEBUG,  # Captures everything from DEBUG and up
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler()  
    ]
)

logger = logging.getLogger(__name__)


llm = get_llm()

class SubmitFinalAnswer(BaseModel):
    """Submit the final answer to the user, based on the user query"""
    final_answer: str = Field(..., description="The final answer to submit to the user.")

# Bind prompts with tools
query_check = query_check_prompt | llm.bind_tools([db_query_tool])
# query_gen = query_gen_prompt | llm.bind_tools([SubmitFinalAnswer])
llm_to_get_schema = llm.bind_tools([get_schema_tool])

# State definition
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

# Nodes

def first_tool_call(state: State) -> dict[str, list[AIMessage]]:
    return {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "sql_db_list_tables",
                        "args": {},
                        "id": "tool_abcd123",
                    }
                ],
            )
        ]
    }

def handle_tool_error(state: State):
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}\n please fix your mistakes.",
                tool_call_id=tc["id"],
            )
            for tc in tool_calls
        ]
    }

def create_node_from_tool_with_fallback(tools: list) -> RunnableWithFallbacks[Any, dict]:
    return ToolNode(tools).with_fallbacks([RunnableLambda(handle_tool_error)], exception_key="error")

def check_the_given_query(state: State):
    return {"messages": [query_check.invoke({"messages": [state["messages"][-1]]})]}

def generation_query(state: State):
    
    logger.info("Running query generation...")

    # Extract the latest user message and context
    user_msg = next((m for m in reversed(state["messages"]) if m.type == "human"), None)
    table_msg = next((m for m in reversed(state["messages"])
                      if isinstance(m, ToolMessage) and m.name == "sql_db_list_tables"), None)
    schema_msg = next((m for m in reversed(state["messages"])
                       if isinstance(m, ToolMessage) and m.name == "sql_db_schema"), None)

    # Build prompt context
    full_context = []
    if table_msg:
        full_context.append(
            AIMessage(content=f"Here are the available tables in the database:\n\n{table_msg.content}")
        )
    if schema_msg:
        cleaned_schema = schema_msg.content.split("/*")[0].strip()
        schema_block = f"### SCHEMA:\n{cleaned_schema}"

        query_gen_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", query_gen_system + "\n\n" + schema_block),
            ("placeholder", "{messages}")
        ]
    )
        query_gen = query_gen_prompt | llm.bind_tools([SubmitFinalAnswer])
    if user_msg:
        full_context.append(user_msg)

    logger.debug("🧠 QUERY_GEN CONTEXT:")
    # for msg in full_context:
        # logger.debug(f"{msg.type.upper()}: {msg.content.strip()[:300]}...\n")

    # Generate output
    message = query_gen.invoke({"messages": full_context})

    # Case 1: LLM used correct SubmitFinalAnswer tool
    if message.tool_calls:
        for tc in message.tool_calls:
            if tc["name"] == "SubmitFinalAnswer":
                return {"messages": [message]}

    # Case 2: Raw SQL content returned — try to run it!
    sql_query = message.content.strip()
    
    def is_select_query(sql: str) -> bool:
        parsed = sqlparse.parse(sql.strip())
        return parsed and parsed[0].get_type() == "SELECT"
    
    sql_query = message.content.strip().rstrip(";")
    if is_select_query(sql_query):
        result = db_query_tool(sql_query)
        final_message = AIMessage(
            content="",
            tool_calls=[{
                "name": "SubmitFinalAnswer",
                "args": {"final_answer": result},
                "id": "tool_auto_generated"
            }]
        )
        return {"messages": [message, final_message]}

    

    # Case 3: LLM hallucinated wrong tool
    tool_messages = []
    if message.tool_calls:
        for tc in message.tool_calls:
            if tc["name"] != "SubmitFinalAnswer":
                tool_messages.append(
                    ToolMessage(
                        content=(
                            f"Error: The wrong tool was called: {tc['name']}. "
                            f"Please fix your mistakes. Remember to only call SubmitFinalAnswer."
                        ),
                        tool_call_id=tc["id"],
                    )
                )

    return {"messages": [message] + tool_messages}



def should_continue(state: State):
    messages = state["messages"]
    last_message = messages[-1]
    if getattr(last_message, "tool_calls", None):
        names = [tc["name"] for tc in last_message.tool_calls]
        if names == ["SubmitFinalAnswer"]:
            return END        # Only end when final answer is truly final
        else:
            return "query_gen"
    if last_message.content.startswith("Error:"):
        return "query_gen"
    else:
        return "correct_query"

def llm_get_schema(state: State):
    # print("this is my state", state)
    logger.debug("📥 Incoming state: %s", state)

    response = llm_to_get_schema.invoke(state["messages"])
    return {"messages": [response]}

# Graph Nodes
list_tables = create_node_from_tool_with_fallback([list_tables_tool])
get_schema = create_node_from_tool_with_fallback([get_schema_tool])
query_database = create_node_from_tool_with_fallback([db_query_tool])

# Graph Definition
workflow = StateGraph(State)
workflow.add_node("first_tool_call", first_tool_call)
workflow.add_node("list_tables_tool", list_tables)
workflow.add_node("get_schema_tool", get_schema)
workflow.add_node("model_get_schema", llm_get_schema)
workflow.add_node("query_gen", generation_query)
workflow.add_node("correct_query", check_the_given_query)
workflow.add_node("execute_query", query_database)

# Edges
workflow.add_edge(START, "first_tool_call")
workflow.add_edge("first_tool_call", "list_tables_tool")
workflow.add_edge("list_tables_tool", "model_get_schema")
workflow.add_edge("model_get_schema", "get_schema_tool")
workflow.add_edge("get_schema_tool", "query_gen")
workflow.add_conditional_edges(
    "query_gen",
    should_continue,
    {
        END: END,
        "correct_query": "correct_query",
    },
)
workflow.add_edge("correct_query", "execute_query")
workflow.add_edge("execute_query", "query_gen")

# Final App
app = workflow.compile()
