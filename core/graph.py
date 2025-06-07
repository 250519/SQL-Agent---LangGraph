from typing import Annotated, Any
from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import AnyMessage, add_messages
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableLambda, RunnableWithFallbacks
from langgraph.prebuilt import ToolNode

from core.llm_config import llm
from prompt.prompt_templates import query_check_prompt, query_gen_prompt
from tools.sql_tools import (
    db_query_tool,
    SubmitFinalAnswer,
    get_schema_tool,
    list_tables_tool,
)

# Bind prompts with tools
query_check = query_check_prompt | llm.bind_tools([db_query_tool])
query_gen = query_gen_prompt | llm.bind_tools([SubmitFinalAnswer])
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
    # Extract latest human message
    user_msg = next((m for m in reversed(state["messages"]) if m.type == "human"), None)

    # Extract tool messages from earlier nodes
    table_msg = next((m for m in reversed(state["messages"])
                      if isinstance(m, ToolMessage) and m.name == "sql_db_list_tables"), None)
    schema_msg = next((m for m in reversed(state["messages"])
                       if isinstance(m, ToolMessage) and m.name == "sql_db_schema"), None)

    # Construct enriched prompt
    full_context = []

    if table_msg:
        full_context.append(
            AIMessage(content=f"Here are the available tables in the database:\n\n{table_msg.content}")
        )

    if schema_msg:
        # ✅ Clean schema content by removing sample rows
        cleaned_schema = schema_msg.content.split("/*")[0].strip()
        full_context.append(
            AIMessage(content=f"Here is the schema of the relevant tables:\n\n{cleaned_schema}")
        )

    if user_msg:
        full_context.append(user_msg)

    

    print("\n🧠 QUERY_GEN CONTEXT:")
    for msg in full_context:
        print(f"{msg.type.upper()}: {msg.content.strip()[:300]}...\n")

    message = query_gen.invoke({"messages": full_context})

    # Check if LLM incorrectly called a non-approved tool
    tool_messages = []
    if message.tool_calls:
        for tc in message.tool_calls:
            if tc["name"] != "SubmitFinalAnswer":
                tool_messages.append(
                    ToolMessage(
                        content=(
                            f"Error: The wrong tool was called: {tc['name']}. "
                            f"Please fix your mistakes. Remember to only call SubmitFinalAnswer "
                            f"to submit the final answer. Generated queries should be outputted "
                            f"WITHOUT a tool call."
                        ),
                        tool_call_id=tc["id"],
                    )
                )

    return {"messages": [message] + tool_messages}


def should_continue(state: State):
    messages = state["messages"]
    last_message = messages[-1]
    if getattr(last_message, "tool_calls", None):
        return END
    if last_message.content.startswith("Error:"):
        return "query_gen"
    else:
        return "correct_query"

def llm_get_schema(state: State):
    print("this is my state", state)
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
