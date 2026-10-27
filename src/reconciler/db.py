import os  # for fetching .env vars from os.environ
from dotenv import load_dotenv  # for loading .env vars

# 1. load DB_USER and DB_PASSWORD from .env
load_dotenv()  # reads .env file
db_user = os.environ.get("DB_USER")
db_pass = os.environ.get("DB_PASSWORD")

if not db_user or not db_pass:  # give informative error message
    raise KeyError("Either DB_USER or DB_PASSWORD is not in your .env file.")


# 2. open a connection to source (port 5433) and one to target (port 5434)
def get_params(port, dbname):
    # Define connection parameters
    # read env vars, validate them, return the dict for psycopg.connect(**params)
    return {
        "dbname": dbname,
        "user": db_user,
        "password": db_pass,
        "host": "localhost",
        "port": port,
    }
