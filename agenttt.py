# %%
import sqlite3

# %%
con = sqlite3.connect("mydb.db")


# %%
conn

# %%
table_creation_query="""
CREATE TABLE IF NOT EXISTS employees (
    emp_id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    hire_date TEXT NOT NULL,
    salary REAL NOT NULL
);
"""

# %%
table_creation_query2="""
CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT
);
"""

# %%
table_creation_query3="""
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    order_date TEXT NOT NULL,
    amount REAL NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
);

"""

# %%
cursor=con.cursor()


# %%
cursor.execute(table_creation_query)
cursor.execute(table_creation_query2)
cursor.execute(table_creation_query3)

# %%
insert_query = """
INSERT INTO employees (emp_id, first_name, last_name, email, hire_date, salary)
VALUES (?, ?, ?, ?, ?, ?);
"""

insert_query_customers = """
INSERT INTO customers (customer_id, first_name, last_name, email, phone)
VALUES (?, ?, ?, ?, ?);
"""

insert_query_orders = """
INSERT INTO orders (order_id, customer_id, order_date, amount)
VALUES (?, ?, ?, ?);
"""

# %%
employee_data = [
    (1, "Sunny", "Savita", "sunny.sv@abc.com", "2023-06-01", 50000.00),
    (2, "Arhun", "Meheta", "arhun.m@gmail.com", "2022-04-15", 60000.00),
    (3, "Alice", "Johnson", "alice.johnson@jpg.com", "2021-09-30", 55000.00),
    (4, "Bob", "Brown", "bob.brown@uio.com", "2020-01-20", 45000.00),
    ]

customers_data = [
    (1, "John", "Doe", "john.doe@example.com", "1234567890"),
    (2, "Jane", "Smith", "jane.smith@example.com", "9876543210"),
    (3, "Emily", "Davis", "emily.davis@example.com", "4567891230"),
    (4, "Michael", "Brown", "michael.brown@example.com", "7894561230"),
]

orders_data = [
    (1, 1, "2023-12-01", 250.75),
    (2, 2, "2023-11-20", 150.50),
    (3, 3, "2023-11-25", 300.00),
    (4, 4, "2023-12-02", 450.00),
]

# %%
cursor.executemany(insert_query,employee_data)
cursor.executemany(insert_query_customers,customers_data)
cursor.executemany(insert_query_orders,orders_data)

# %%
con.commit()


# %%
cursor = con.execute("SELECT * FROM employees;")
for row in cursor:
    print(row)

# %%
# Install the langchain-community package
%pip install langchain-community

# Import the SQLDatabase module
# from langchain_community.utilities import SQLDatabase

# %%
from langchain_community.utilities import SQLDatabase

# %%
db= SQLDatabase.from_uri("sqlite:///mydb.db")

# %%
db.get_usable_table_names()

# %%
db.get_table_info(['employees'])


# %%
from dotenv import load_dotenv
load_dotenv()

# %%
from langchain_groq import ChatGroq
llm= ChatGroq(model="llama-3.1-8b-instant")

# %%
messages = [
    ("system", "You are a Chatbot that can answer questions"),
    ("human", "who won IPL 2022?"),
]
llm.invoke(messages)

# %%
from langchain_community.agent_toolkits import SQLDatabaseToolkit

# %%
toolkit= SQLDatabaseToolkit(db=db, llm=llm)
tools=toolkit.get_tools()
for tool in tools:
    print(tool.name, tool.description)

# %%
list_table=next((tool for tool in tools if tool.name == "sql_db_list_tables"),None)
list_table.invoke('{customer}')

# %%
schema=next((tool for tool in tools if tool.name == "sql_db_schema"),None)
schema.invoke('customers')

# %%
from langchain_core.tools import tool
@tool
def db_query_tool(query : str)-> str:
    """Execute the SQL Query and return the result.
    If the query is not valid, return an error message.
    In case of an error, user is advised to rewrite the query.
    """
    try:
        result = db.run_no_throw(query)
        return result
    except Exception as e:
        return f"Error executing query: {str(e)}. Please rewrite the query."
    

# %%
from langchain.utilities import SQLDatabase

db = SQLDatabase.from_uri("sqlite:///mydb.db")

# Instead of db.run(), use:
result = db.run("SELECT * FROM employees;")
print(result)

# %%
from typing import Annotated, Literal
from langchain_core.messages import AIMessage
from langchain_core.pydantic_v1 import BaseModel, Field
from typing_extensions import TypedDict
from langgraph.graph import END, StateGraph, START
from langgraph.graph.message import AnyMessage, add_messages
from typing import Any
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableLambda, RunnableWithFallbacks
from langgraph.prebuilt import ToolNode


# %%
from langchain_core.prompts import ChatPromptTemplate

query_check_system = """You are a SQL expert with a strong attention to detail.
Double check the SQLite query for common mistakes, including:
 - Using NOT IN with NULL values
 - Using UNION when UNION ALL should have been used
 - Using BETWEEN for exclusive ranges
 - Data type mismatch in predicates
 - Properly quoting identifiers
 - Using the correct number of arguments for functions
 - Casting to the correct data type
 - Using the proper columns for joins
 - Always use single quotes for string literals in SQL queries.
 - Avoid ending the query with an unmatched quote.   

If there are any of the above mistakes, rewrite the query. If there are no mistakes, just reproduce the original query.

You will call the appropriate tool to execute the query after running this check."""

query_check_prompt = ChatPromptTemplate.from_messages(
    [("system", query_check_system), ("placeholder", "{messages}")]
)

query_check = query_check_prompt | llm.bind_tools([db_query_tool])

# %%
query_check.invoke({"messages": [("user", "SELECT * FROM customers LIMIT 5;")]})

# %%
class SubmitFinalAnswer(BaseModel):
    """Submit the final answer to the user, based on the user query"""
    final_answer: str = Field(..., description="The final answer to submit to the user.")

    
# Add a node for a model to generate a query based on the question and schema
query_gen_system = """You are a SQL expert with a strong attention to detail.

Given an input question, output a syntactically correct SQLite query to run, then look at the results of the query and return the answer.

DO NOT call any tool besides SubmitFinalAnswer to submit the final answer.

When generating the query:

Output the SQL query that answers the input question without a tool call.

Unless the user specifies a specific number of examples they wish to obtain, always limit your query to at most 5 results.
You can order the results by a relevant column to return the most interesting examples in the database.
Never query for all the columns from a specific table, only ask for the relevant columns given the question.

If you get an error while executing a query, rewrite the query and try again.

If you get an empty result set, you should try to rewrite the query to get a non-empty result set.
NEVER make stuff up if you don't have enough information to answer the query... just say you don't have enough information.

If you have enough information to answer the input question, simply invoke the appropriate tool to submit the final answer to the user.

DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the database. Do not return any sql query except answer.
Output the SQL query that answers the input question without a tool call.
"""

query_gen_prompt = ChatPromptTemplate.from_messages(
    [("system", query_gen_system), ("placeholder", "{messages}")]
)

query_gen = query_gen_prompt | llm.bind_tools([SubmitFinalAnswer])


# %%
list_tables_tool = next((tool for tool in tools if tool.name == "sql_db_list_tables"), None)
get_schema_tool = next((tool for tool in tools if tool.name == "sql_db_schema"), None)


# %%
llm_to_get_schema=llm.bind_tools([get_schema_tool])
list_tables_tool.invoke("")


# %%
class State(TypedDict):
    messages: Annotated[list[AnyMessage],add_messages]

# %%
def first_tool_call(state:State)->dict[str,list[AIMessage]]:
    return{"messages": [AIMessage(content="",tool_calls=[{"name":"sql_db_list_tables","args":{},"id":"tool_abcd123"}])]}

# %%
def handle_tool_error(state:State):
    error = state.get("error") 
    tool_calls = state["messages"][-1].tool_calls
    return { "messages": [ ToolMessage(content=f"Error: {repr(error)}\n please fix your mistakes.",tool_call_id=tc["id"],) for tc in tool_calls ] }

# %%
def create_node_from_tool_with_fallback(tools:list)-> RunnableWithFallbacks[Any, dict]:
    return ToolNode(tools).with_fallbacks([RunnableLambda(handle_tool_error)], exception_key="error")

# %%
def check_the_given_query(state:State):
    return {"messages": [query_check.invoke({"messages": [state["messages"][-1]]})]}

# %%
def generation_query(state:State):
    message = query_gen.invoke(state)

    # Sometimes, the LLM will hallucinate and call the wrong tool. We need to catch this and return an error message.
    tool_messages = []
    if message.tool_calls:
        for tc in message.tool_calls:
            if tc["name"] != "SubmitFinalAnswer":
                tool_messages.append(
                    ToolMessage(
                        content=f"Error: The wrong tool was called: {tc['name']}. Please fix your mistakes. Remember to only call SubmitFinalAnswer to submit the final answer. Generated queries should be outputted WITHOUT a tool call.",
                        tool_call_id=tc["id"],
                    )
                )
    else:
        tool_messages = []
    return {"messages": [message] + tool_messages}

# %%
def should_continue(state:State):
    messages = state["messages"]
    last_message = messages[-1]
    if getattr(last_message, "tool_calls", None):
        return END
    if last_message.content.startswith("Error:"):
        return "query_gen"
    else:
        return "correct_query"

# %%
def llm_get_schema(state:State):
    print("this is my state", state)
    response = llm_to_get_schema.invoke(state["messages"])
    return {"messages": [response]}

# %%
list_tables=create_node_from_tool_with_fallback([list_tables_tool])


# %%
get_schema=create_node_from_tool_with_fallback([get_schema_tool])


# %%
query_database=create_node_from_tool_with_fallback([db_query_tool])


# %%
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


# %%
workflow = StateGraph(State)
workflow.add_node("first_tool_call",first_tool_call)
workflow.add_node("list_tables_tool", list_tables)
workflow.add_node("get_schema_tool", get_schema)
workflow.add_node("model_get_schema", llm_get_schema)
workflow.add_node("query_gen", generation_query)
workflow.add_node("correct_query", check_the_given_query)
workflow.add_node("execute_query", query_database)

# %%
workflow.add_edge(START, "first_tool_call")
workflow.add_edge("first_tool_call", "list_tables_tool")
workflow.add_edge("list_tables_tool", "model_get_schema")
workflow.add_edge("model_get_schema", "get_schema_tool")
workflow.add_edge("get_schema_tool", "query_gen")
workflow.add_conditional_edges("query_gen",should_continue,
                            {END:END,
                            "correct_query":"correct_query"})
workflow.add_edge("correct_query", "execute_query")
workflow.add_edge("execute_query", "query_gen")

# %%
app=workflow.compile()


# %%
from IPython.display import Image, display
from langchain_core.runnables.graph import MermaidDrawMethod

display(
    Image(
        app.get_graph().draw_mermaid_png(
            draw_method=MermaidDrawMethod.API,
        )
    )
)

# %%
query={"messages": [("user", "List all the users")]}
for step in app.stream(query):
    print("🔄 Step:", step)
# response=app.invoke(query)

# %%
from langchain_core.messages import BaseMessage, HumanMessage


# %%
llm_to_get_schema.invoke([HumanMessage(content='List all customer with their email', additional_kwargs={}, response_metadata={}, id='0571873a-df8f-4673-942c-ea73a052f7d6'), AIMessage(content='', additional_kwargs={}, response_metadata={}, id='bcaf622f-b11e-4502-b5ef-0b784bc5bdf1', tool_calls=[{'name': 'sql_db_list_tables', 'args': {}, 'id': 'tool_abcd123', 'type': 'tool_call'}]), ToolMessage(content='customers, employees, orders', name='sql_db_list_tables', id='a48f6154-23de-47f0-887c-2888405ced08', tool_call_id='tool_abcd123')])


# %%
query={"messages": [("user", "List all the users")]}
for step in app.stream(query):
    print("🔄 Step:", step)
    if "query_gen" in step:
        msg = step["query_gen"]["messages"][-1]
        print("🧠 QUERY_GEN output:", msg.content or msg.tool_calls)


# %%
msg = step["query_gen"]["messages"][-1]
print(msg.content)

# %%


# %%



