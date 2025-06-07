import streamlit as st
import pandas as pd
import sqlite3
import os

from langchain_core.messages import HumanMessage
from core.graph import app  # compiled LangGraph workflow
from core.db import db  # shared SQLDatabase
from sqlite3 import OperationalError
import sys
import os
from core.db import initialize_db
initialize_db()
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ---------- UI Setup ----------
st.set_page_config(page_title="Natural Language to SQL", layout="centered")
st.title("🧠 Ask Your Database in Natural Language")

# ---------- Upload CSV ----------
st.header("📤 Upload CSV to Insert into SQLite")

uploaded_file = st.file_uploader("Upload a CSV file", type=["csv"])
table_name = st.text_input("Enter table name for this CSV")

if uploaded_file and table_name:
    df = pd.read_csv(uploaded_file)
    st.write("📄 Preview of uploaded CSV:")
    st.dataframe(df.head())

    if st.button("📥 Insert into Database"):
        try:
            conn = sqlite3.connect("mydb.db")
            df.to_sql(table_name, conn, if_exists="replace", index=False)
            st.success(f"✅ Data inserted into table `{table_name}` successfully.")
        except OperationalError as e:
            st.error(f"❌ Failed to insert data: {str(e)}")

# ---------- Natural Query Section ----------
st.header("💬 Ask a Question in Natural Language")

query = st.text_input("What do you want to know?", placeholder="e.g., List all customer emails")

if st.button("🔎 Submit Query") and query:
    with st.spinner("Thinking..."):
        messages = [("user", query)]
        try:
            final_answer = None
            for step in app.stream({"messages": messages}):
                if "query_gen" in step:
                    msg = step["query_gen"]["messages"][-1]
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        # Tool called SubmitFinalAnswer
                        final_answer = msg.tool_calls[0]["args"].get("final_answer")
                    else:
                        final_answer = msg.content
            if final_answer:
                st.success("✅ Answer:")
                st.markdown(f"**{final_answer}**")
            else:
                st.warning("⚠️ No answer was generated.")
        except Exception as e:
            st.error(f"❌ Something went wrong: {str(e)}")
