# Personal Finance Chatbot — Streamlit + Snowflake

This is a from-scratch starter you can run locally and extend for your hackathon.
- Frontend: Streamlit chat UI
- Database: Snowflake (profiles, conversations, transactions)
- Offline insights: 50/30/20, emergency fund, simple India tax demo
- LLM Hook: placeholder to plug IBM watsonx Granite later

## Quickstart
1) Create Snowflake objects (see sql/bootstrap.sql)
2) Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill values.
3) Install deps and run:
   ```bash
   python -m venv .venv
   # Windows: .venv\Scripts\activate
   # macOS/Linux:
   source .venv/bin/activate
   pip install -r requirements.txt
   streamlit run app.py
   ```
