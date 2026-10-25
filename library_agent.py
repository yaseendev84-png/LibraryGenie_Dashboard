import json
import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from groq import Groq


load_dotenv()
st.set_page_config(page_title="LibraryGenie | AI Library Agent", page_icon="📚", layout="wide")

DB_PATH = Path(__file__).with_name("library.db")
MODEL_NAME = "openai/gpt-oss-20b"
MAX_RESULT_ROWS = 50
SOURCE_LABEL = "books table"


def get_connection():
    uri = f"{DB_PATH.resolve().as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def get_schema():
    with closing(get_connection()) as connection:
        names = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        schema = {}
        for item in names:
            name = item["name"]
            quoted_name = '"' + name.replace('"', '""') + '"'
            details = connection.execute(f"PRAGMA table_info({quoted_name})").fetchall()
            schema[name] = [f"{column['name']} ({column['type']})" for column in details]
    return schema


def create_sql_plan(client, question, schema_text, previous_sql="", error_text=""):
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "library_sql_plan",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string"},
                    "assumption": {"type": "string"},
                    "followups": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["sql", "assumption", "followups"],
                "additionalProperties": False,
            },
        },
    }
    system_prompt = f"""
You are LibraryGenie, a beginner-friendly SQLite assistant for a school library.
Translate the user question (English or Roman Urdu) into ONE SQLite SELECT statement using only this schema:
{schema_text}
The categories stored in the database are: Science, Fiction, History, Technology.
Rules:
- Return a single read-only SELECT or WITH...SELECT statement. Never produce write operations, PRAGMA, ATTACH, or multiple statements.
- Use only existing table and column names, never invent columns.
- For book listings add LIMIT 20 unless the user asks for a smaller number.
- For counts and totals, compute across ALL matching rows before applying any display limit.
- For "most borrowed" order by times_borrowed DESC, then book_id ASC.
- "Zero available copies" means available_copies = 0.
- Roman Urdu hints: "kitni" = how many, "mein" = in, "dikhao/batao" = show/tell, "sab se zyada" = the most.
- Match category names exactly as written above.
- If the question is not about this library database, use an empty sql string and explain briefly in assumption.
- Never pretend to have run a query. Python will execute your SQL separately.
- Give two short follow-up questions related to the available data.
"""
    correction = f"Previous SQL: {previous_sql}\nDatabase error: {error_text}\nFix the SQL using the schema." if error_text else ""
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question + "\n" + correction},
        ],
        temperature=0,
        max_completion_tokens=1600,
        reasoning_effort="low",
        reasoning_format="hidden",
        response_format=response_format,
    )
    return json.loads(response.choices[0].message.content or "{}")


def execute_read_only_sql(sql):
    statement = sql.strip()
    if not statement or not statement.lower().startswith(("select", "with")):
        raise ValueError("Only read-only SELECT statements are allowed.")
    if ";" in statement.rstrip(";"):
        raise ValueError("Only one SQL statement is allowed.")
    if len(statement) > 4500:
        raise ValueError("The query is too long for this classroom demo.")

    allowed_functions = {
        "count", "avg", "sum", "min", "max", "round", "lower", "upper", "length", "substr",
        "coalesce", "ifnull", "nullif", "abs", "total", "group_concat", "trim", "replace",
        "instr", "printf", "typeof", "like", "glob",
    }

    def only_reads(action, arg1, arg2, database, source):
        if database not in (None, "main"):
            return sqlite3.SQLITE_DENY
        if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ):
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_FUNCTION and str(arg2 or "").lower() in allowed_functions:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    connection = get_connection()
    connection.set_authorizer(only_reads)
    started = time.monotonic()
    connection.set_progress_handler(lambda: int(time.monotonic() - started > 3), 1000)
    try:
        cursor = connection.execute(statement)
        rows = cursor.fetchmany(MAX_RESULT_ROWS + 1)
        column_names = [column[0] for column in cursor.description]
        limited = len(rows) > MAX_RESULT_ROWS
        dataframe = pd.DataFrame([tuple(row) for row in rows[:MAX_RESULT_ROWS]], columns=column_names)
        return dataframe, limited
    except sqlite3.Error as error:
        raise ValueError(f"Database rejected the query: {error}") from error
    finally:
        connection.close()


def explain_results(client, question, sql, dataframe, limited):
    preview = dataframe.head(15).to_csv(index=False)
    extra = "More rows exist than the displayed preview." if limited else "All returned rows are displayed."
    prompt = f"""
You are a friendly school librarian explaining actual SQL results to students in very simple English.
Use only facts explicitly supported by the SQL output. Do not invent books, numbers or reasons.
If there are no results, say that no matching books were found.
If the result is truncated, state the limitation.
User question: {question}
Executed SQL: {sql}
Result preview (CSV):
{preview}
{extra}
Give a short answer of 2 to 4 sentences.
"""
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_completion_tokens=1200,
        reasoning_effort="low",
        reasoning_format="hidden",
    )
    return response.choices[0].message.content or "No explanation was generated."


st.title("📚 LibraryGenie")
st.caption("AI Library Agent | Ask in English or Roman Urdu, see the SQL, and check the real results")

if not DB_PATH.exists():
    st.error("library.db was not found. Run: python create_library_db.py")
    st.stop()

with st.sidebar:
    st.header("Agent Control Center")
    api_key = st.text_input("Groq API Key", value=os.getenv("GROQ_API_KEY", ""), type="password")
    st.caption(f"Model: {MODEL_NAME}")
    st.success("Database access: Read-only (SELECT only)")
    if st.button("Clear conversation", use_container_width=True):
        st.session_state.history = []
        st.session_state.pending_question = ""
        st.rerun()

with closing(get_connection()) as connection:
    metrics = pd.read_sql_query(
        "SELECT COUNT(*) AS books, COUNT(DISTINCT category) AS categories, "
        "SUM(available_copies) AS copies, SUM(times_borrowed) AS borrowings FROM books",
        connection,
    ).iloc[0]

m1, m2, m3, m4 = st.columns(4)
m1.metric("Books", int(metrics["books"]), border=True)
m2.metric("Categories", int(metrics["categories"]), border=True)
m3.metric("Available copies", int(metrics["copies"]), border=True)
m4.metric("Total borrowings", int(metrics["borrowings"]), border=True)

if "history" not in st.session_state:
    st.session_state.history = []
if "pending_question" not in st.session_state:
    st.session_state.pending_question = ""

ask_tab, data_tab = st.tabs(["🧠 Ask LibraryGenie", "📊 Explore Library"])

with ask_tab:
    st.subheader("Ask a question in English or Roman Urdu")
    st.caption("Try: How many books are in the library? | Science category mein kitni books hain?")
    b1, b2, b3 = st.columns(3)
    if b1.button("🔥 Most borrowed", use_container_width=True):
        st.session_state.pending_question = "Show the 5 most borrowed books."
    if b2.button("🚫 Zero copies", use_container_width=True):
        st.session_state.pending_question = "Which books have zero available copies?"
    if b3.button("🏆 Top category", use_container_width=True):
        st.session_state.pending_question = "Which category has the highest total borrowings?"

    for message in st.session_state.history:
        with st.chat_message("user"):
            st.markdown(message["question"])
        with st.chat_message("assistant"):
            st.markdown(message["answer"])
            with st.expander("See generated SQL and database result"):
                st.code(message["sql"], language="sql")
                st.dataframe(pd.DataFrame(message["rows"]), hide_index=True, width="stretch")
                st.caption(f"Source: {SOURCE_LABEL}")

    typed_question = st.chat_input("Ask a question about the library books...")
    question = st.session_state.pending_question or typed_question
    st.session_state.pending_question = ""

    if question:
        if not api_key:
            st.warning("Add your Groq API Key in the sidebar first.")
        else:
            try:
                client = Groq(api_key=api_key)
                schema = get_schema()
                schema_text = "\n".join(f"{table}: {', '.join(columns)}" for table, columns in schema.items())
                with st.status("LibraryGenie is working", expanded=True) as status:
                    st.write("1. Reading the database schema")
                    plan = create_sql_plan(client, question, schema_text)
                    sql = plan.get("sql", "").strip()
                    if not sql:
                        raise ValueError(plan.get("assumption", "Please ask about the library books."))
                    st.write("2. SQL proposed by the model")
                    st.code(sql, language="sql")
                    st.write("3. Checking that the query is SELECT only, then running it")
                    try:
                        dataframe, limited = execute_read_only_sql(sql)
                    except ValueError as first_error:
                        if not str(first_error).startswith("Database rejected the query:"):
                            raise
                        st.write("4. Database returned a SQL error. Asking the agent to fix it once")
                        corrected = create_sql_plan(client, question, schema_text, sql, str(first_error))
                        sql = corrected.get("sql", "").strip()
                        st.code(sql, language="sql")
                        dataframe, limited = execute_read_only_sql(sql)
                        plan = corrected
                    st.write(f"4. Database returned {len(dataframe)} rows")
                    st.write("5. Explaining the real result")
                    explanation = explain_results(client, question, sql, dataframe, limited)
                    status.update(label="Done", state="complete", expanded=False)

                with st.chat_message("user"):
                    st.markdown(question)
                with st.chat_message("assistant"):
                    st.markdown(explanation)

                st.subheader("Database result")
                st.dataframe(dataframe, hide_index=True, width="stretch")
                if limited:
                    st.warning(f"Preview limited to {MAX_RESULT_ROWS} rows.")
                with st.expander("Generated SQL", expanded=True):
                    st.code(sql, language="sql")
                    if plan.get("assumption"):
                        st.caption(f"Assumption: {plan['assumption']}")
                st.caption(f"Source: {SOURCE_LABEL}")
                if plan.get("followups"):
                    st.caption("Try next: " + " | ".join(plan["followups"][:2]))
                st.session_state.history.append({
                    "question": question,
                    "answer": explanation,
                    "sql": sql,
                    "rows": dataframe.to_dict(orient="records"),
                })
            except Exception as error:
                st.error(f"Could not complete the question: {error}")
                st.caption("Try a shorter question. Check the database and your Groq API key.")

with data_tab:
    with closing(get_connection()) as connection:
        books = pd.read_sql_query("SELECT * FROM books ORDER BY book_id", connection)
        by_category = pd.read_sql_query(
            "SELECT category, SUM(times_borrowed) AS total_borrowings FROM books "
            "GROUP BY category ORDER BY total_borrowings DESC",
            connection,
        )
    left, right = st.columns([1.4, 1])
    with left:
        st.subheader("All books")
        st.dataframe(books, hide_index=True, width="stretch", height=380)
    with right:
        st.subheader("Total borrowings by category")
        st.bar_chart(by_category, x="category", y="total_borrowings", height=300)
        st.caption("Synthetic school library records for practice.")