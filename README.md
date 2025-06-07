# SQL-Agent---LangGraph

## In progresss

sql_agent/
│
├── 📁 app/                        # Streamlit frontend interface
│   └── main.py                   # Streamlit app for uploading CSVs and querying DB
│
├── 📁 api/                        # FastAPI server
│   ├── main.py                   # FastAPI entrypoint
│   ├── routes.py                 # API routes for uploading CSVs, querying
│   └── schemas.py                # Pydantic models for requests/responses
│
├── 📁 core/                       # Core logic
│   ├── db.py                     # SQLite connection and setup
│   ├── ingest.py                 # CSV ingestion into SQLite
│   ├── llm_config.py             # LLM and tool configuration
│   └── graph.py                  # LangGraph workflow and logic
│
├── 📁 utils/                      # Utilities
│   └── logger.py                 # Logging setup
│
├── 📁 data/                       # Uploaded CSVs
│   └── sample.csv                # (Example)
│
├── requirements.txt              # Required packages
└── README.md                     # Project overview

