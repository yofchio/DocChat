import asyncio
import os
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from loguru import logger
from surrealdb import AsyncSurreal, RecordID


def get_database_url():
    surreal_url = os.getenv("SURREAL_URL")
    if surreal_url:
        return surreal_url
    address = os.getenv("SURREAL_ADDRESS", "localhost")
    port = os.getenv("SURREAL_PORT", "8000")
    return f"ws://{address}/rpc:{port}"


def get_database_password():
    return os.getenv("SURREAL_PASSWORD") or os.getenv("SURREAL_PASS")


def parse_record_ids(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: parse_record_ids(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [parse_record_ids(item) for item in obj]
    elif isinstance(obj, RecordID):
        return str(obj)
    return obj


def ensure_record_id(value: Union[str, RecordID]) -> RecordID:
    if isinstance(value, RecordID):
        return value
    return RecordID.parse(value)


class _ConnectionPool:
    def __init__(self, max_idle: int = 10):
        self._idle: deque = deque()
        self._max_idle = max_idle

    async def _create_connection(self):
        db = AsyncSurreal(get_database_url())
        await db.signin(
            {
                "username": os.environ.get("SURREAL_USER"),
                "password": get_database_password(),
            }
        )
        await db.use(
            os.environ.get("SURREAL_NAMESPACE"), os.environ.get("SURREAL_DATABASE")
        )
        return db

    async def acquire(self):
        current_loop = asyncio.get_running_loop()
        requeue: deque = deque()
        conn = None
        while self._idle:
            candidate = self._idle.popleft()
            candidate_loop = getattr(candidate, "loop", None)
            if candidate_loop is current_loop:
                conn = candidate
                break
            requeue.append(candidate)
        requeue.extend(self._idle)
        self._idle = requeue
        if conn is not None:
            return conn
        return await self._create_connection()

    async def release(self, conn, *, discard: bool = False):
        if discard:
            try:
                await conn.close()
            except Exception:
                pass
            return
        current_loop = asyncio.get_running_loop()
        conn_loop = getattr(conn, "loop", None)
        if conn_loop is not None and conn_loop is not current_loop:
            return
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
    conn = await _pool.acquire()
    try:
        yield conn
    except Exception:
        await _pool.release(conn, discard=True)
        raise
    else:
        await _pool.release(conn)


async def repo_query(
    query_str: str, vars: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    for attempt in range(2):
        async with db_connection() as connection:
            try:
                result = parse_record_ids(await connection.query(query_str, vars))
                if isinstance(result, str):
                    raise RuntimeError(result)
                return result
            except RuntimeError:
                raise
            except Exception as e:
                if attempt == 0:
                    logger.debug(f"Query failed (attempt 1), retrying: {e}")
                    continue
                raise
    raise RuntimeError("Query failed after retries")


async def repo_create(table: str, data: Dict[str, Any]) -> Dict[str, Any]:
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
        if isinstance(id, RecordID) or (":" in id and id.startswith(f"{table}:")):
            record_id = id
        else:
            record_id = f"{table}:{id}"
        data.pop("id", None)
        if "created" in data and isinstance(data["created"], str):
            data["created"] = datetime.fromisoformat(data["created"])
        data["updated"] = datetime.now(timezone.utc)
        query = f"UPDATE {record_id} MERGE $data;"
        result = await repo_query(query, {"data": data})
        return parse_record_ids(result)
    except Exception as e:
        raise RuntimeError(f"Failed to update record: {str(e)}")


async def repo_delete(record_id: Union[str, RecordID]):
    try:
        async with db_connection() as connection:
            return await connection.delete(ensure_record_id(record_id))
    except Exception as e:
        logger.exception(e)
        raise RuntimeError(f"Failed to delete record: {str(e)}")


async def repo_insert(
    table: str, data: List[Dict[str, Any]], ignore_duplicates: bool = False
) -> List[Dict[str, Any]]:
    try:
        async with db_connection() as connection:
            result = parse_record_ids(await connection.insert(table, data))
            if isinstance(result, str):
                raise RuntimeError(result)
            return result
    except RuntimeError as e:
        if ignore_duplicates and "already contains" in str(e):
            return []
        raise
    except Exception as e:
        if ignore_duplicates and "already contains" in str(e):
            return []
        logger.exception(e)
        raise RuntimeError("Failed to create record")
