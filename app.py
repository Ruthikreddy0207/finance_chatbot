import streamlit as st
import pandas as pd
import io
from datetime import date
from backend.persistence import db
from backend.insights import summarize_budget, plan_emergency_fund, quick_goals_tip
from backend.tax import estimate_tax_india
from backend import nlp

st.set_page_config(page_title="Finance Chatbot", page_icon="💸", layout="wide")

st.sidebar.title("🔧 Setup")
st.sidebar.caption("Make sure .streamlit/secrets.toml has your Snowflake connection.")
user_id = st.sidebar.text_input("User ID", value="demo_user")
kind = st.sidebar.selectbox("I am a", ["student", "professional"])
age = st.sidebar.number_input("Age", min_value=10, max_value=100, value=22)
monthly_income = st.sidebar.number_input("Monthly income (₹)", min_value=0, value=30000, step=1000)
fixed_expenses = st.sidebar.number_input("Fixed monthly expenses (₹)", min_value=0, value=15000, step=500)
goals = st.sidebar.text_area("Goals (comma separated)", value="build emergency fund, pay education loan")

if st.sidebar.button("Save profile"):
    try:
        db.upsert_profile(user_id, kind, int(age), float(monthly_income), float(fixed_expenses), goals)
        st.sidebar.success("Profile saved to Snowflake.")
    except Exception as e:
        st.sidebar.error(f"Profile save failed: {e}")

st.title("💬 Personal Finance Chatbot — Streamlit + Snowflake")
st.caption("Offline-ready insights. Plug IBM watsonx (Granite) in backend/nlp.py when keys are ready.")

try:
    db.init_db()
except Exception as e:
    st.error(f"Snowflake connection failed. Check secrets.toml.\n{e}")
    st.stop()

# Load history from Snowflake
history_rows = db.fetch_history(user_id, limit=50)
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": r, "content": c} for r, c in history_rows]

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message("assistant" if msg["role"]=="assistant" else "user"):
        st.write(msg["content"])

# Quick insight cards
c1, c2, c3 = st.columns(3)
with c1:
    st.subheader("Budget Suggestion")
    st.write(summarize_budget(monthly_income, fixed_expenses))
with c2:
    st.subheader("Emergency Fund")
    st.write(plan_emergency_fund(fixed_expenses if fixed_expenses>0 else monthly_income*0.5))
with c3:
    st.subheader("Tax (Rough Demo)")
    tax = estimate_tax_india(annual_income=monthly_income*12)
    st.write(f"Est. annual tax: ₹{tax['estimated_tax']:,.0f} (eff. ~{tax['effective_rate']*100:.1f}%)")

st.divider()
st.subheader("📥 Upload Transactions (CSV)")
st.caption("Columns: date, description, amount, category  |  amount > 0 treated as expense.")
file = st.file_uploader("Upload a CSV", type=["csv"])
if file:
    try:
        df = pd.read_csv(file)
        # expected columns
        req = {"date","description","amount","category"}
        if not req.issubset(set(map(str.lower, df.columns))):
            st.error("CSV must have columns: date, description, amount, category")
        else:
            # normalize column names
            df.columns = [c.lower() for c in df.columns]
            df["date"] = pd.to_datetime(df["date"]).dt.date
            rows = list(df[["date","description","amount","category"]].itertuples(index=False, name=None))
            db.add_transactions(user_id, rows)
            st.success(f"Uploaded {len(rows)} transactions to Snowflake.")
    except Exception as e:
        st.error(f"Upload failed: {e}")

st.subheader("📊 Recent Transactions (last 6 months)")
try:
    tx = db.fetch_transactions(user_id, months=6)
    if tx:
        tx_df = pd.DataFrame(tx, columns=["date","description","amount","category"])
        st.dataframe(tx_df, use_container_width=True, hide_index=True)

        st.subheader("📈 Spend by Category (last 6 months)")
        by_cat = db.category_summary(user_id, months=6)
        if by_cat:
            cat_df = pd.DataFrame(by_cat, columns=["category","total"])
            st.bar_chart(cat_df.set_index("category"))
    else:
        st.info("No transactions yet.")
except Exception as e:
    st.error(f"Query failed: {e}")

# Chat input -> reply -> store in Snowflake
if prompt := st.chat_input("Ask about savings, budgets, taxes, or goals…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    try:
        db.save_message(user_id, "user", prompt)
    except Exception as e:
        st.warning(f"Could not save user message: {e}")

    # Profile for context (optional)
    prof = db.get_profile(user_id)
    profile = None
    if prof:
        profile = {
            "user_id": prof[0],
            "kind": prof[1],
            "age": prof[2],
            "monthly_income": prof[3],
            "fixed_expenses": prof[4],
            "goals": prof[5],
        }

    # Build short history for LLM
    short_hist = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-10:]]
    reply = nlp.generate_reply(short_hist, profile)

    # Add deterministic finance tips
    tips = []
    tips.append(quick_goals_tip(profile["kind"] if profile else "user", profile["goals"] if profile else None))
    if profile and profile.get("monthly_income") is not None:
        tips.append(summarize_budget(profile["monthly_income"], profile.get("fixed_expenses")))

    final = reply + "\n\n" + "• " + "\n• ".join(tips)
    st.session_state.messages.append({"role": "assistant", "content": final})
    try:
        db.save_message(user_id, "assistant", final)
    except Exception as e:
        st.warning(f"Could not save assistant message: {e}")

    with st.chat_message("assistant"):
        st.write(final)
