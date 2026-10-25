import os  # for fetching .env vars from os.environ
import psycopg  # for connecting to PostgreSQL
from dotenv import load_dotenv  # for loading .env vars

SOURCE_DB = "source"
SOURCE_PORT = 5433
TARGET_DB = "target"
TARGET_PORT = 5434

# 1. load DB_USER and DB_PASSWORD from .env
load_dotenv()  # reads .env file
db_user = os.environ.get("DB_USER")
db_pass = os.environ.get("DB_PASSWORD")

if not db_user or not db_pass:  # give informative error message
    raise KeyError("Either DB_USER or DB_PASSWORD is not in your .env file.")

# 2. open a connection to source (port 5433) and one to target (port 5434)
# A connection string formatted as a standard URI

# Define connection parameters
db_src_params = {
    "dbname": SOURCE_DB,
    "user": db_user,
    "password": db_pass,
    "host": "localhost",
    "port": SOURCE_PORT,
}

db_tar_params = {
    "dbname": TARGET_DB,
    "user": db_user,
    "password": db_pass,
    "host": "localhost",
    "port": TARGET_PORT,
}


try:
    with psycopg.connect(**db_src_params) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            db_version = cur.fetchone()
            print(f"Connected to PostgreSQL! Version: {db_version}")
            # automatically close the cursor object
        # commit changes to the database, if something goes haywire rollback recent change

    # automatically close the connection object

except psycopg.OperationalError as e:
    print(f"Database connection failed: {e}")


# 3. empty the target tables (ratings first, then movies. Why that order?)
# 4. for each table, in the right order:
#       - read a batch of rows from source
#       - write that batch to target
#       - repeat until no rows are left
# 5. commit, and print how many rows were copied per table
