from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_core.tools import tool
from core.db import db  # Import the shared database object
from core.llm_config import get_llm  # Import the shared LLM
llm=get_llm()  # Initialize the LLM

# Create toolkit and extract tools
toolkit = SQLDatabaseToolkit(db=db, llm=llm)
tools = toolkit.get_tools()

# Extract specific tools by name
list_tables_tool = next((tool for tool in tools if tool.name == "sql_db_list_tables"), None)
get_schema_tool = next((tool for tool in tools if tool.name == "sql_db_schema"), None)

# Custom tool for executing queries
@tool
def db_query_tool(query: str) -> str:
    """
    Execute the SQL Query and return the result.
    If the query is not valid, return an error message.
    In case of an error, user is advised to rewrite the query.
    """
    try:
        result = db.run_no_throw(query)
        return result
    except Exception as e:
        return f"Error executing query: {str(e)}. Please rewrite the query."

__all__ = ["list_tables_tool", "get_schema_tool", "db_query_tool"]
