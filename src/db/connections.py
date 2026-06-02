# connections.py - Creates persistent connections to the databases. 
# This is used by the rest of the code to get access to the databases.

from pymongo import MongoClient
from dotnev import load_dotenv
import os

load_dotenv()

_mongo1_clinet = None
_mongo2_client = None

def get_mongo1():
    global _mongol1_client 
    if _mongo1_clinet is None:
        _mongo1_clinet = MongoClient(os.getenv("MONGO1_URL"))
    return _mongo1_clinet[os.getenv("DB_NAME")]

def get_mongo2():
    global _mongol2_client 
    if _mongo2_client is None:
        _mongo2_client = MongoClient(os.getenv("MONGO2_URL"))
    return _mongo2_client[os.getenv("DB_NAME")]