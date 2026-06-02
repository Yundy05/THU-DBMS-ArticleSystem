# connections.py - Creates persistent connections to the databases.

from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

_mongo1_client = None
_mongo2_client = None

def _require_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def get_mongo1():
    global _mongo1_client
    if _mongo1_client is None:
        _mongo1_client = MongoClient(os.getenv("MONGO1_URI"))
    return _mongo1_client[os.getenv("DB_NAME")]

def get_mongo2():
    global _mongo2_client
    if _mongo2_client is None:
        _mongo2_client = MongoClient(os.getenv("MONGO2_URI"))
    return _mongo2_client[os.getenv("DB_NAME")]