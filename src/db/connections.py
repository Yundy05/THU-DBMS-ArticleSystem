# connections.py - Creates persistent connections to the databases.

from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

_mongo1_client = None
_mongo2_client = None
_mongo3_client = None
_mongo4_client = None
_db1_failed    = False


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

def _connect(uri: str, timeout_ms: int = 500) -> MongoClient:
    client = MongoClient(uri, serverSelectionTimeoutMS=timeout_ms)
    client.admin.command("ping")   # raises if unreachable
    return client

def get_mongo3():
    """
    Direct access to DB3 — used for syncing, monitor status checks,
    and as a hot standby for MongoDB1.
    """
    global _mongo3_client
    uri = os.getenv("MONGO3_URI")
    if not uri:
        raise RuntimeError("MONGO3_URI not configured (hot standby).")
    if _mongo3_client is None:
        _mongo3_client = _connect(uri)
    return _mongo3_client[_require_env("DB_NAME")]

def get_mongo1():
    """
    Returns DB1. Falls back to DB3 (hot standby) if DB1 is unreachable.
    """
    global _mongo1_client, _mongo3_client, _db1_failed

    # If we already know DB1 is down, skip straight to DB3
    if _db1_failed:
        return get_mongo3()

    # Reuse existing client if it's still healthy
    if _mongo1_client is not None:
        try:
            _mongo1_client.admin.command("ping")
            return _mongo1_client[_require_env("DB_NAME")]
        except Exception:
            _mongo1_client = None
            _db1_failed = True
            return get_mongo3()

    # First-time connection attempt
    try:
        _mongo1_client = _connect(_require_env("MONGO1_URI"))
        _db1_failed = False
        return _mongo1_client[_require_env("DB_NAME")]
    except Exception:
        _db1_failed = True
        # Fall back to hot standby (DB3)
        if _mongo3_client is None:
            _mongo3_client = _connect(_require_env("MONGO3_URI"))
        return _mongo3_client[_require_env("DB_NAME")]


def db1_or_standby():
    """Alias for code that conceptually wants 'DB1, but fail over to DB3'."""
    return get_mongo1()


def get_mongo2():
    """
    Direct access to DB2 (no special failover).
    """
    global _mongo2_client
    if _mongo2_client is None:
        _mongo2_client = MongoClient(
            _require_env("MONGO2_URI"),
            serverSelectionTimeoutMS=500,
        )
    return _mongo2_client[_require_env("DB_NAME")]

def get_mongo4():
    """
    Optional expansion node (MongoDB4).
    If MONGO4_URI is not set or the node is down, callers should handle errors.
    """
    global _mongo4_client
    uri = os.getenv("MONGO4_URI")
    if not uri:
        raise RuntimeError("MONGO4_URI not configured (expansion node).")
    if _mongo4_client is None:
        _mongo4_client = _connect(uri)
    return _mongo4_client[_require_env("DB_NAME")]

def node_status() -> dict:
    """
    Returns online/offline/standby status for all nodes, including MongoDB4.

    Rules:
      - DB1/DB2/DB4: 'online' if ping succeeds, otherwise 'offline'.
      - DB3:
          * DB1 online  + DB3 online → 'standby'
          * DB1 offline + DB3 online → 'online' (active)
          * DB3 offline              → 'offline'
    """
    global _db1_failed
    statuses: dict[str, str] = {}

    for name, uri in [
        ("MongoDB1", os.getenv("MONGO1_URI")),
        ("MongoDB2", os.getenv("MONGO2_URI")),
        ("MongoDB3", os.getenv("MONGO3_URI")),
        ("MongoDB4", os.getenv("MONGO4_URI")),
    ]:
        if not uri:
            # URI not configured → treat as offline / not present
            statuses[name] = "offline"
            continue

        try:
            MongoClient(uri, serverSelectionTimeoutMS=500).admin.command("ping")
            statuses[name] = "online"
        except Exception:
            statuses[name] = "offline"

    # If DB1 just came back online, clear the failover flag
    if statuses.get("MongoDB1") == "online":
        _db1_failed = False

    # DB3 role:
    # - DB1 online  + DB3 online  → DB3 is standby (yellow)
    # - DB1 offline + DB3 online  → DB3 is active (green / online)
    if statuses.get("MongoDB3") == "online" and statuses.get("MongoDB1") == "online":
        statuses["MongoDB3"] = "standby"
    # Otherwise:
    #  - if DB3 is online and DB1 is offline, leave DB3 as "online"
    #  - if DB3 is offline, it stays "offline"

    return statuses