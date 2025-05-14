from flask import Flask, request, jsonify
from langchain_community.utilities import SQLDatabase
from langchain.chains import create_sql_query_chain
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from dotenv import load_dotenv
import os
import re
import ast
import logging

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# PostgreSQL connection details from environment variables
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Ensure environment variables are set
if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME, OPENAI_API_KEY]):
    raise ValueError("Missing one or more required environment variables.")

# Establish connection to PostgreSQL database
try:
    db = SQLDatabase.from_uri(
        f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
except Exception as e:
    raise Exception(f"Failed to connect to database: {e}")

# Initialize LLM for natural language to SQL conversion and result analysis
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=OPENAI_API_KEY)

# Custom prompt template for SQL query generation
sql_query_prompt = ChatPromptTemplate.from_template(
    """You are an expert SQL query writer for a PostgreSQL database. Given the following user input and database schema, generate a precise SQL query to answer the question.

User Input: {input}

Database Schema:
{table_info}

Instructions:
- Write a SQL query that directly answers the user’s question.
- Use double quotes for column names (e.g., "cradlename") to respect PostgreSQL’s case sensitivity.
- Do NOT add a LIMIT clause unless the user explicitly requests it (e.g., "limit to 5 results", "show top {top_k}", "first 3 cradles"). If a limit is requested, use {top_k} as the limit value.
- Use exact column names from the schema (e.g., "cradlename", not "cradleName").
- If the question is ambiguous, target the most relevant table based on keywords (e.g., "cradles" for cradle-related questions).
- Return only the SQL query, without explanations or markdown.
"""
)

# Create a chain to generate SQL queries with the custom prompt
sql_query_chain = create_sql_query_chain(llm, db, prompt=sql_query_prompt)

# Prompt template for generating a dynamic description of query results
result_description_template = ChatPromptTemplate.from_template(
    """You are a database analyst. I ran the following SQL query:

SQL Query:
{sql_query}

And got these results:
{query_results}

The original question was: {original_question}

analyse the result and Provide a concise description (4,5 sentences) of what the results show, tailored to the original question. 
- Focus on the main data returned (e.g., entities or attributes shown).
- Mention if no results were found or if the results don't fully match the question.
- Use simple language for non-technical users."""
)

# Create a chain to generate the description
result_description_chain = result_description_template | llm

@app.route('/query', methods=['POST'])
def handle_query():
    try:
        # Get JSON data from the request
        data = request.get_json()
        if not data or 'prompt' not in data:
            return jsonify({
                "error": "Missing 'prompt' in JSON payload"
            }), 400

        nl_question = data['prompt']
        logger.debug(f"Received prompt: {nl_question}")

        # Determine if the prompt requests a limit and extract top_k
        limit_keywords = ['limit', 'top', 'first', 'show only']
        top_k = 10  # Default top_k if limit is requested but no number specified
        for keyword in limit_keywords:
            if keyword in nl_question.lower():
                # Extract number from prompt (e.g., "top 5" -> 5)
                match = re.search(r'(?:limit|top|first|show only)\s*(\d+)', nl_question.lower())
                if match:
                    top_k = int(match.group(1))
                break
        else:
            top_k = None  # No limit requested

        # Generate the SQL query
        try:
            generated_query = sql_query_chain.invoke({
                "input": nl_question,
                "top_k": top_k if top_k is not None else 1000,  # Large default to avoid limiting
                "table_info": db.get_table_info(),
                "question": nl_question  # Fallback for potential internal chain requirements
            })
        except KeyError as e:
            logger.error(f"KeyError in query generation: {str(e)}")
            return jsonify({
                "error": f"Error generating query: Missing key {str(e)}"
            }), 500

        logger.debug(f"Generated query: {generated_query}")

        # Extract SQL from markdown code blocks or raw query
        sql_pattern = r"```sql\s*(.*?)\s*```"
        sql_match = re.search(sql_pattern, generated_query, re.DOTALL)

        if sql_match:
            sql_query = sql_match.group(1).strip()
        else:
            # Handle queries with prefixes like "SQLQuery: " or raw SQL
            sql_query = generated_query.strip()
            if sql_query.startswith("SQLQuery:"):
                sql_query = sql_query[len("SQLQuery:"):].strip()
            # Remove any trailing semicolon for consistency
            sql_query = sql_query.rstrip(";").strip()

        logger.debug(f"Cleaned SQL query: {sql_query}")

        # Validate that the query is likely SQL
        if not any(sql_query.upper().startswith(keyword) for keyword in ["SELECT", "SHOW", "DESCRIBE"]):
            return jsonify({
                "error": "Generated query is not valid SQL",
                "generated_query": generated_query,
                "sql_query": sql_query
            }), 400

        # Remove LIMIT clause unless the prompt explicitly mentions limit-related terms
        if not any(keyword in nl_question.lower() for keyword in limit_keywords):
            sql_query = re.sub(r'\s*LIMIT\s+\d+', '', sql_query, flags=re.IGNORECASE)

        # Execute the SQL query
        try:
            query_results = db.run(sql_query)
        except Exception as e:
            logger.error(f"Query execution error: {str(e)}")
            return jsonify({
                "error": f"Error executing query: {str(e)}",
                "generated_query": generated_query,
                "sql_query": sql_query
            }), 500

        logger.debug(f"Query results: {query_results}")

        # Parse query results for description generation
        try:
            # Convert string representation of results to a list for analysis
            results_list = ast.literal_eval(query_results) if query_results else []
            results_summary = str(results_list[:5])  # Limit to first 5 rows for LLM input
        except (ValueError, SyntaxError):
            results_summary = query_results or "No results returned."

        # Generate a dynamic description of the results
        try:
            description_response = result_description_chain.invoke({
                "sql_query": sql_query,
                "query_results": results_summary,
                "original_question": nl_question
            })
            description = description_response.content
        except Exception as e:
            logger.error(f"Description generation error: {str(e)}")
            description = f"Unable to generate description: {str(e)}"

        # Return JSON response
        return jsonify({
            "status": "success",
            "original_question": nl_question,
            "generated_query": generated_query,
            "sql_query": sql_query,
            "query_results": query_results,
            "description": description
        }), 200

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({
            "error": f"Unexpected error: {str(e)}"
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)