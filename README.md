# 📚 LibraryGenie: AI Library Agent

Ask a question about a school library in **English or Roman Urdu**. The agent writes the SQL, runs it on a real SQLite database, and explains the result in simple words.

![LibraryGenie screenshot](screenshots/question1.png)

## What it does
- Turns a normal question into a SQL `SELECT` query (Groq LLM)
- Runs the SQL on `library.db` and shows the **real result table**
- Shows the generated SQL and a simple explanation
- Labels the data source: *books table*
- Includes quick-question buttons and a chart of borrowings by category

## Example questions
- How many books are in the library?
- Show the 5 most borrowed books.
- Science category mein kitni books hain?
- Which books have zero available copies?
- Which category has the highest total borrowings?

## Safety (read-only)
- Only `SELECT` / `WITH ... SELECT` queries are allowed
- Only one statement at a time
- The database is opened in read-only mode, so the data cannot be changed
- Dangerous commands (DELETE, DROP, UPDATE, PRAGMA) are blocked

## Limitations
- The AI can sometimes write wrong or unexpected SQL, so the app always shows the SQL so you can check it
- The data is **synthetic** (32 practice books in 4 categories), not a real library
- Questions that are not about the books table are not answered

## Project files
| File | Purpose |
|---|---|
| `create_library_db.py` | Creates `library.db` with 32 books |
| `library_agent.py` | The Streamlit AI agent |
| `library.db` | SQLite database |
| `requirements.txt` | Python packages |

## How to run
1. Install packages: `pip install -r requirements.txt`
2. Create the database: `python create_library_db.py`
3. Make a file named `.env` and add your own key: `GROQ_API_KEY=your_key_here`
4. Start the app: `streamlit run library_agent.py`

## Tech used
Python, Streamlit, Groq API, SQLite, pandas

## Author
Muhammad Yaseen Botaj 