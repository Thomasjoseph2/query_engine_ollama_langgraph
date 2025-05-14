import psycopg2
import json
import re
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Fetch database connection details from environment variables
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

# Ensure environment variables are set
if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
    raise ValueError("Missing one or more required environment variables for DB connection.")

# Connect to PostgreSQL Database
conn = psycopg2.connect(
    user=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME
)
conn.autocommit = False  # Use transactions for better safety
cursor = conn.cursor()

# Load data from JSON file
with open("data.json", "r") as file:
    data = json.load(file)

def format_value(value):
    if value is None:
        return "NULL"
    elif isinstance(value, str):
        # Check if the value is in the ISO 8601 date format (YYYY-MM-DD)
        if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
            return f"'{value}'::date"  # PostgreSQL date conversion
        elif re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?", value):
            # Handle timestamps
            value = value.split("+")[0].split("Z")[0]  # Remove timezone info
            return f"'{value}'::timestamp"  # PostgreSQL timestamp conversion
        else:
            return "'{}'".format(value.replace("'", "''"))  # Escape single quotes
    elif isinstance(value, (int, float)):
        return str(value)
    else:
        raise ValueError(f"Unsupported data type: {type(value)}")

# Iterate through tables and insert data
for table_name, rows in data.items():
    print(f"Inserting data into table: {table_name}")
    for row in rows:
        columns = ", ".join(row.keys())
        values = ", ".join(format_value(value) for value in row.values())
        insert_query = f"INSERT INTO {table_name} ({columns}) VALUES ({values})"
        try:
            cursor.execute(insert_query)
        except psycopg2.Error as e:
            print(f"Error inserting into table {table_name}: {e}")
            print(f"Query: {insert_query}")
            conn.rollback()  # Rollback in case of error
            break  # Exit the loop for this table
    else:  # This executes if no break occurred in the for loop
        print(f"Data inserted successfully for table: {table_name}")

# Commit the transaction
try:
    conn.commit()
    print("All transactions committed successfully")
except psycopg2.Error as e:
    print(f"Error committing transactions: {e}")
    conn.rollback()

# Close the connection
cursor.close()
conn.close()