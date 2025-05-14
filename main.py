from flask import Flask, request, jsonify
from langchain_community.utilities import SQLDatabase
from langchain.chains import create_sql_query_chain
from langchain_ollama import ChatOllama
from langchain.prompts import ChatPromptTemplate
from dotenv import load_dotenv
import os, re, ast, logging

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME, OPENAI_API_KEY]):
    raise ValueError("Missing required environment variables.")

# Connect to PostgreSQL database
db = SQLDatabase.from_uri(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# Initialize LLM
llm = ChatOllama(model="qwen3:4b", temperature=0)

# Custom SQL generation prompt including top_k
sql_query_prompt = ChatPromptTemplate.from_template(
    """You are a PostgreSQL expert. Generate ONLY the SQL query to answer this question:
{input}

Database Schema:
{table_info}

Return at most {top_k} rows.

Rules:
- Use double-quoted identifiers (e.g., \"columnName\")
- No explanations, markdown, or formatting
- Never include text besides the SQL query
- Directly output the query ready for execution

Example Response:
SELECT \"id\" FROM \"trolleys\" WHERE \"status\" = 'active';"""
)

# Build the SQL query chain
sql_query_chain = create_sql_query_chain(llm, db, prompt=sql_query_prompt)

# Helper to extract raw SQL from LLM output
def extract_sql(text):
    # Try code block first
    m = re.search(r"```(?:sql)?\s*(SELECT.*?)\s*```", text, re.I | re.S)
    if m:
        return m.group(1).strip()
    # Fallback to first SELECT...;
    m2 = re.search(r"(SELECT.*?;)", text, re.I | re.S)
    if m2:
        return m2.group(1).strip()
    # Last fallback: raw text up to semicolon
    return text.split(";")[0].strip()

# Result description chain
result_description_template = ChatPromptTemplate.from_template(
    """You are a database analyst. I ran the following SQL query:

SQL Query:
{sql_query}

And got these results:
{query_results}

The original question was: {original_question}

Provide a concise description (4-5 sentences) of what the results show, tailored to the original question:
- Focus on the main data returned (e.g., entities or attributes).
- Mention if no results were found or if the results don't match.
- Use simple language for non-technical users."""
)
result_description_chain = result_description_template | llm

@app.route('/query', methods=['POST'])
def handle_query():
    try:
        data = request.get_json()
        if not data or 'prompt' not in data:
            return jsonify(error="Missing 'prompt' in JSON"), 400

        nl_question = data['prompt']
        logger.debug(f"Received NL prompt: {nl_question}")

        # Detect a limit in the question
        top_k = 1000
        match = re.search(r"(?:limit|top|first|show only)\s*(\d+)", nl_question, re.I)
        if match:
            top_k = int(match.group(1))

                # Generate SQL query
        generated = sql_query_chain.invoke({
            "input": nl_question,
            "table_info": db.get_table_info(),
            "top_k": top_k,
            "question": nl_question  # include for chain compatibility
        })
        sql_query = extract_sql(generated)(generated)
        logger.debug(f"Generated SQL: {sql_query}")

        # Validate
        if not sql_query.upper().startswith(('SELECT', 'SHOW', 'DESCRIBE')):
            return jsonify(error="Invalid SQL generated", generated=generated), 400

        # Execute the query
        try:
            results = db.run(sql_query)
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return jsonify(error=f"Error executing query: {e}"), 500

        # Summarize the first few rows for description
        try:
            rows = ast.literal_eval(results)
            summary = str(rows[:5])
        except Exception:
            summary = results or '[]'

        # Generate human‑friendly description
        description_resp = result_description_chain.invoke({
            "sql_query": sql_query,
            "query_results": summary,
            "original_question": nl_question
        })
        description = description_resp.content

        # Return everything
        return jsonify(
            status="success",
            original_question=nl_question,
            generated_query=generated,
            sql_query=sql_query,
            query_results=results,
            description=description
        ), 200

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify(error=f"Unexpected error: {e}"), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
