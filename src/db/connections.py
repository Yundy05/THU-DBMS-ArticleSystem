# connections.py - Creates persistent connections to the databases.

from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

_mongo1_client = None
_mongo2_client = None
_mongo3_client = None


def _require_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

def _connect(uri: str, timeout_ms: int = 3000) -> MongoClient:
    client = MongoClient(uri, serverSelectionTimeoutMS=timeout_ms)
    client.admin.command("ping")   # raises if unreachable
    return client

def get_mongo1():
    """Returns DB1. Falls back to DB3 (hot standby) if DB1 is unreachable."""
    global _mongo1_client
    if _mongo1_client is not None:
        try:
            _mongo1_client.admin.command("ping")
            return _mongo1_client[os.getenv("DB_NAME")]
        except Exception:
            _mongo1_client = None   # reset so we retry below

    # Try DB1 first
    try:
        _mongo1_client = _connect(os.getenv("MONGO1_URI"))
        return _mongo1_client[os.getenv("DB_NAME")]
    except Exception:
        pass

    # Fallback to DB3 (hot standby)
    try:
        global _mongo3_client
        if _mongo3_client is None:
            _mongo3_client = _connect(os.getenv("MONGO3_URI"))
        return _mongo3_client[os.getenv("DB_NAME")]
    except Exception:
        raise ConnectionError(
            "DB1 (mongo1:27017) and standby DB3 (mongo3:27019) are both unreachable."
        )

def get_mongo2():
    global _mongo2_client
    if _mongo2_client is None:
        _mongo2_client = MongoClient(os.getenv("MONGO2_URI"))
    return _mongo2_client[os.getenv("DB_NAME")]

def get_mongo3():
    """Direct access to DB3 — used for syncing and monitor status checks."""
    global _mongo3_client
    if _mongo3_client is None:
        _mongo3_client = _connect(os.getenv("MONGO3_URI"))
    return _mongo3_client[os.getenv("DB_NAME")]

def node_status() -> dict:
    """Returns online/offline/standby status for all three nodes.
    Used by the monitor page."""
    statuses = {}
    for name, uri in [
        ("MongoDB1", os.getenv("MONGO1_URI")),
        ("MongoDB2", os.getenv("MONGO2_URI")),
        ("MongoDB3", os.getenv("MONGO3_URI")),
    ]:
        try:
            MongoClient(uri, serverSelectionTimeoutMS=1500).admin.command("ping")
            statuses[name] = "online"
        except Exception:
            statuses[name] = "offline"

    # DB3 is standby — relabel if online
    if statuses["MongoDB3"] == "online":
        statuses["MongoDB3"] = "standby"

    return statuses