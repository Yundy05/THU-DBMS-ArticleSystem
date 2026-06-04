# connections.py - Creates persistent connections to the databases.

from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

_mongo1_client = None
_mongo2_client = None
_mongo3_client = None
_db1_failed    = False


def _connect(uri: str, timeout_ms: int = 500) -> MongoClient:
    client = MongoClient(uri, serverSelectionTimeoutMS=timeout_ms)
    client.admin.command("ping")   # raises if unreachable
    return client


def get_mongo1():
    """Returns DB1. Falls back to DB3 (hot standby) if DB1 is unreachable."""
    global _mongo1_client, _mongo3_client, _db1_failed

    # If we already know DB1 is down, skip straight to DB3
    if _db1_failed:
        return get_mongo3()

    if _mongo1_client is not None:
        try:
            _mongo1_client.admin.command("ping")
            return _mongo1_client[os.getenv("DB_NAME")]
        except Exception:
            _mongo1_client = None
            _db1_failed = True
            return get_mongo3()

    try:
        _mongo1_client = _connect(os.getenv("MONGO1_URI"))
        _db1_failed = False
        return _mongo1_client[os.getenv("DB_NAME")]
    except Exception:
        _db1_failed = True
        if _mongo3_client is None:
            _mongo3_client = _connect(os.getenv("MONGO3_URI"))
        return _mongo3_client[os.getenv("DB_NAME")]


def db1_or_standby():
    """Alias for code that conceptually wants 'DB1, but fail over to DB3'."""
    return get_mongo1()


def get_mongo2():
    global _mongo2_client
    if _mongo2_client is None:
        _mongo2_client = MongoClient(os.getenv("MONGO2_URI"),
                                     serverSelectionTimeoutMS=500)
    return _mongo2_client[os.getenv("DB_NAME")]


def get_mongo3():
    """Direct access to DB3 — used for syncing and monitor status checks."""
    global _mongo3_client
    if _mongo3_client is None:
        _mongo3_client = _connect(os.getenv("MONGO3_URI"))
    return _mongo3_client[os.getenv("DB_NAME")]


def node_status() -> dict:
    """Returns online/offline/standby status for all three nodes."""
    global _db1_failed
    statuses = {}
    for name, uri in [
        ("MongoDB1", os.getenv("MONGO1_URI")),
        ("MongoDB2", os.getenv("MONGO2_URI")),
        ("MongoDB3", os.getenv("MONGO3_URI")),
    ]:
        try:
            MongoClient(uri, serverSelectionTimeoutMS=500).admin.command("ping")
            statuses[name] = "online"
        except Exception:
            statuses[name] = "offline"

    # If DB1 just came back online, clear the failover flag
    if statuses["MongoDB1"] == "online":
        _db1_failed = False

    # DB3 is standby when online
    if statuses["MongoDB3"] == "online":
        statuses["MongoDB3"] = "standby"

    return statuses