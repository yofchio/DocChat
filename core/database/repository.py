import asyncio
import os
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from loguru import logger
from surrealdb import AsyncSurreal, RecordID


"""Database helpers.

These helpers manage connections and provide simple CRUD helpers
used by the backend
"""


def get_database_url():
    # Build the SurrealDB WebSocket URL from environment variables.
    # Prefer `SURREAL_URL` if present (e.g. ws://surrealdb:8000/rpc or Railway private DNS).
    surreal_url = os.getenv("SURREAL_URL")
    if surreal_url:
        return surreal_url.rstrip("/")
    address = os.getenv("SURREAL_ADDRESS", "localhost")
    port = os.getenv("SURREAL_PORT", "8000")
    # Standard form matches Docker / Surreal docs (not ws://host/rpc:port).
    return f"ws://{address}:{port}/rpc"


def get_database_password():
    # Read DB password from either of two env vars.
    return os.getenv("SURREAL_PASSWORD") or os.getenv("SURREAL_PASS")


def parse_record_ids(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: parse_record_ids(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [parse_record_ids(item) for item in obj]
    elif isinstance(obj, RecordID):
        return str(obj)
    return obj

# Convert any SurrealDB-specific RecordID objects into plain strings.
# Works recursively for dicts and lists so returned data is simple to use.


def ensure_record_id(value: Union[str, RecordID]) -> RecordID:
    if isinstance(value, RecordID):
        return value
    return RecordID.parse(value)

# Ensure we have a RecordID object. Accept either a string or RecordID.


class _ConnectionPool:
    def __init__(self, max_idle: int = 10):
        self._idle: deque = deque()
        self._max_idle = max_idle

    async def _create_connection(self):
        # Make a new SurrealDB connection and authenticate.
        db = AsyncSurreal(get_database_url())
        await db.signin(
            {
                "username": os.environ.get("SURREAL_USER"),
                "password": get_database_password(),
            }
        )
        # Select namespace and database
        await db.use(
            os.environ.get("SURREAL_NAMESPACE"), os.environ.get("SURREAL_DATABASE")
        )
        return db

    async def acquire(self):
        # Try to reuse an idle connection that belongs to the current event loop.
        current_loop = asyncio.get_running_loop()
        requeue: deque = deque()
        conn = None
        while self._idle:
            candidate = self._idle.popleft()
            # If the connection was created on the same loop, reuse it.
            candidate_loop = getattr(candidate, "loop", None)
            if candidate_loop is current_loop:
                conn = candidate
                break
            # Otherwise keep it for later checks.
            requeue.append(candidate)
        requeue.extend(self._idle)
        self._idle = requeue
        if conn is not None:
            return conn
        # No available connection on this loop, create a new one.
        return await self._create_connection()

    async def release(self, conn, *, discard: bool = False):
        # Close connection if requested.
        if discard:
            try:
                await conn.close()
            except Exception:
                pass
            return

        # Only keep connections that belong to the current loop.
        current_loop = asyncio.get_running_loop()
        conn_loop = getattr(conn, "loop", None)
        if conn_loop is not None and conn_loop is not current_loop:
            return

        # Add back to pool if under max idle, otherwise close it.
        if len(self._idle) < self._max_idle:
            self._idle.append(conn)
        else:
            try:
                await conn.close()
            except Exception:
                pass


_pool = _ConnectionPool()


@asynccontextmanager
async def db_connection():
    # Provide a simple async context manager for DB connections.
    # Always acquires from the pool and releases it afterwards.
    conn = await _pool.acquire()
    try:
        yield conn
    except Exception:
        # On error, discard the connection to avoid reusing a bad connection.
        await _pool.release(conn, discard=True)
        raise
    else:
        await _pool.release(conn)


async def repo_query(
    query_str: str, vars: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    # Central query helper:
    # - retry once for transient failures
    # - convert RecordID objects to strings
    for attempt in range(2):
        async with db_connection() as connection:
            try:
                result = parse_record_ids(await connection.query(query_str, vars))
                # Surreal may return an error string; treat that as an exception.
                if isinstance(result, str):
                    raise RuntimeError(result)
                return result
            except RuntimeError:
                # Let explicit runtime errors bubble up unchanged.
                raise
            except Exception as e:
                # Log first failure and retry once.
                if attempt == 0:
                    logger.debug(f"Query failed (attempt 1), retrying: {e}")
                    continue
                raise
    raise RuntimeError("Query failed after retries")


async def repo_create(table: str, data: Dict[str, Any]) -> Dict[str, Any]:
    # Insert a single record with created/updated timestamps.
    data.pop("id", None)
    data["created"] = datetime.now(timezone.utc)
    data["updated"] = datetime.now(timezone.utc)
    try:
        async with db_connection() as connection:
            result = parse_record_ids(await connection.insert(table, data))
            if isinstance(result, str):
                raise RuntimeError(result)
            return result
    except RuntimeError:
        raise
    except Exception as e:
        logger.exception(e)
        raise RuntimeError("Failed to create record")


async def repo_relate(
    source: str, relationship: str, target: str, data: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    if data is None:
        data = {}
    # Create a relation between two records.
    query = f"RELATE {source}->{relationship}->{target} CONTENT $data;"
    return await repo_query(query, {"data": data})


async def repo_upsert(
    table: str, id: Optional[str], data: Dict[str, Any], add_timestamp: bool = False
) -> List[Dict[str, Any]]:
    data.pop("id", None)
    if add_timestamp:
        data["updated"] = datetime.now(timezone.utc)
    query = f"UPSERT {id if id else table} MERGE $data;"
    return await repo_query(query, {"data": data})


async def repo_update(
    table: str, id: str, data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    try:
        # Normalize id to a full record identifier if needed.
        if isinstance(id, RecordID) or (":" in id and id.startswith(f"{table}:")):
            record_id = id
        else:
            record_id = f"{table}:{id}"
        data.pop("id", None)
        # Convert created string back to datetime if needed.
        if "created" in data and isinstance(data["created"], str):
            data["created"] = datetime.fromisoformat(data["created"])
        # Always update the updated timestamp.
        data["updated"] = datetime.now(timezone.utc)
        query = f"UPDATE {record_id} MERGE $data;"
        result = await repo_query(query, {"data": data})
        return parse_record_ids(result)
    except Exception as e:
        raise RuntimeError(f"Failed to update record: {str(e)}")


async def repo_delete(record_id: Union[str, RecordID]):
    try:
        # Delete a record by id. Accept string or RecordID.
        async with db_connection() as connection:
            return await connection.delete(ensure_record_id(record_id))
    except Exception as e:
        logger.exception(e)
        raise RuntimeError(f"Failed to delete record: {str(e)}")


async def repo_insert(
    table: str, data: List[Dict[str, Any]], ignore_duplicates: bool = False
) -> List[Dict[str, Any]]:
    try:
        # Insert multiple records. Optionally ignore duplicate errors.
        async with db_connection() as connection:
            result = parse_record_ids(await connection.insert(table, data))
            if isinstance(result, str):
                raise RuntimeError(result)
            return result
    except RuntimeError as e:
        # If caller asked to ignore duplicates and the DB reports duplicates,
        # return empty list instead of raising.
        if ignore_duplicates and "already contains" in str(e):
            return []
        raise
    except Exception as e:
        if ignore_duplicates and "already contains" in str(e):
            return []
        logger.exception(e)
        raise RuntimeError("Failed to create record")
