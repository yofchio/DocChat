from datetime import datetime
from typing import Any, ClassVar, Dict, List, Optional, Type, TypeVar, Union, cast

from loguru import logger
from pydantic import BaseModel, ValidationError, field_validator

from core.database.repository import (
    ensure_record_id,
    repo_create,
    repo_delete,
    repo_query,
    repo_relate,
    repo_update,
)
from core.exceptions import DatabaseOperationError, InvalidInputError, NotFoundError

T = TypeVar("T", bound="ObjectModel")


class ObjectModel(BaseModel):
    """Base model with simple DB helper methods.

    These are small convenience wrappers so domain models can:
    - fetch records (`get_all`, `get`)
    - save/update themselves (`save`)
    - delete and create relationships

    """

    id: Optional[str] = None
    table_name: ClassVar[str] = ""
    nullable_fields: ClassVar[set[str]] = set()
    user_id: Optional[str] = None
    created: Optional[datetime] = None
    updated: Optional[datetime] = None

    @classmethod
    async def get_all(
        cls: Type[T], order_by: Optional[str] = None, user_id: Optional[str] = None
    ) -> List[T]:
        # Fetch all records from the model's table.
        # Optional: filter by user_id and sort via order_by.
        try:
            if not cls.table_name:
                raise InvalidInputError("get_all() must be called from a specific model class")

            where_clause = ""
            params: Dict[str, Any] = {}
            if user_id:
                where_clause = " WHERE user_id = $user_id"
                params["user_id"] = user_id

            order_clause = f" ORDER BY {order_by}" if order_by else ""
            query = f"SELECT * FROM {cls.table_name}{where_clause}{order_clause}"

            # Run the query and try to build model instances.
            result = await repo_query(query, params if params else None)
            objects = []
            for obj in result:
                try:
                    objects.append(cls(**obj))
                except Exception as e:
                    # If a DB row doesn't match the model, log and skip.
                    logger.warning(f"Error creating object from DB row: {e}")
            return objects
        except Exception as e:
            logger.error(f"Error fetching all {cls.table_name}: {e}")
            raise DatabaseOperationError(e)

    @classmethod
    async def get(cls: Type[T], id: str) -> T:
        # Fetch a single record by id. The id may include the table prefix.
        if not id:
            raise InvalidInputError("ID cannot be empty")
        try:
            table_name = id.split(":")[0] if ":" in id else id
            if cls.table_name and cls.table_name == table_name:
                target_class: Type[T] = cls
            else:
                # Find the class that maps to this table name.
                found_class = cls._get_class_by_table_name(table_name)
                if not found_class:
                    raise InvalidInputError(f"No class found for table {table_name}")
                target_class = cast(Type[T], found_class)

            result = await repo_query("SELECT * FROM $id", {"id": ensure_record_id(id)})
            if result:
                return target_class(**result[0])
            else:
                raise NotFoundError(f"{table_name} with id {id} not found")
        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error fetching object with id {id}: {e}")
            raise NotFoundError(f"Object with id {id} not found")

    @classmethod
    def _get_class_by_table_name(cls, table_name: str) -> Optional[Type["ObjectModel"]]:
        # Walk the ObjectModel subclass tree to find a class with matching table_name.
        def get_all_subclasses(c: Type["ObjectModel"]) -> List[Type["ObjectModel"]]:
            all_subclasses: List[Type["ObjectModel"]] = []
            for subclass in c.__subclasses__():
                all_subclasses.append(subclass)
                all_subclasses.extend(get_all_subclasses(subclass))
            return all_subclasses

        for subclass in get_all_subclasses(ObjectModel):
            if hasattr(subclass, "table_name") and subclass.table_name == table_name:
                return subclass
        return None

    async def save(self) -> None:
        # Validate this model and create or update it in the DB.
        try:
            self.model_validate(self.model_dump(), strict=True)
            data = self._prepare_save_data()
            data["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if self.id is None:
                # New object: set created timestamp and insert.
                data["created"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                repo_result = await repo_create(self.__class__.table_name, data)
            else:
                # Existing object: ensure created has the right format and update.
                data["created"] = (
                    self.created.strftime("%Y-%m-%d %H:%M:%S")
                    if isinstance(self.created, datetime)
                    else self.created
                )
                repo_result = await repo_update(self.__class__.table_name, self.id, data)

            # Update fields on this instance from the DB result.
            result_list = repo_result if isinstance(repo_result, list) else [repo_result]
            for key, value in result_list[0].items():
                if hasattr(self, key):
                    if isinstance(getattr(self, key), BaseModel):
                        setattr(self, key, type(getattr(self, key))(**value))
                    else:
                        setattr(self, key, value)
        except ValidationError as e:
            logger.error(f"Validation failed: {e}")
            raise
        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"Error saving record: {e}")
            raise DatabaseOperationError(e)

    def _prepare_save_data(self) -> Dict[str, Any]:
        # Prepare a dict for saving: remove None values unless field is nullable.
        data = self.model_dump()
        return {
            key: value
            for key, value in data.items()
            if value is not None or key in self.__class__.nullable_fields
        }

    async def delete(self) -> bool:
        # Delete this object from the DB. Requires `id`.
        if self.id is None:
            raise InvalidInputError("Cannot delete object without an ID")
        try:
            return await repo_delete(self.id)
        except Exception as e:
            logger.error(f"Error deleting {self.__class__.table_name} with id {self.id}: {e}")
            raise DatabaseOperationError(f"Failed to delete {self.__class__.table_name}")

    async def relate(
        self, relationship: str, target_id: str, data: Optional[Dict] = None
    ) -> Any:
        # Create a relation from this object to another record.
        if data is None:
            data = {}
        if not relationship or not target_id or not self.id:
            raise InvalidInputError("Relationship and target ID must be provided")
        try:
            return await repo_relate(
                source=self.id, relationship=relationship, target=target_id, data=data
            )
        except Exception as e:
            logger.error(f"Error creating relationship: {e}")
            raise DatabaseOperationError(e)

    @classmethod
    async def count(cls: Type[T], user_id: Optional[str] = None) -> int:
        # Count how many records exist in this model's table.
        # Optionally filter by user_id.
        if not cls.table_name:
            raise InvalidInputError("count() must be called from a specific model class")

        params: Dict[str, Any] = {}
        where = ""
        if user_id:
            where = " WHERE user_id = $user_id"
            params["user_id"] = user_id

        try:
            result = await repo_query(
                f"SELECT count() AS total FROM {cls.table_name}{where} GROUP ALL",
                params if params else None,
            )
            if result and result[0].get("total") is not None:
                return int(result[0]["total"])
            return 0
        except Exception as e:
            logger.error(f"Error counting {cls.table_name}: {e}")
            raise DatabaseOperationError(e)

    @classmethod
    async def exists(cls: Type[T], id: str) -> bool:
        # Check if a record with this id exists in the DB.
        # Returns True/False without loading the full object.
        if not id:
            return False
        try:
            result = await repo_query(
                "SELECT id FROM $id",
                {"id": ensure_record_id(id)},
            )
            return len(result) > 0
        except Exception:
            return False

    @classmethod
    async def get_by_field(
        cls: Type[T], field_name: str, field_value: Any, user_id: Optional[str] = None
    ) -> List[T]:
        # Look up records by any single field.
        # Example: Source.get_by_field("status", "completed")
        if not cls.table_name:
            raise InvalidInputError("get_by_field() must be called from a specific model class")

        params: Dict[str, Any] = {"val": field_value}
        where = f" WHERE {field_name} = $val"
        if user_id:
            where += " AND user_id = $user_id"
            params["user_id"] = user_id

        try:
            result = await repo_query(
                f"SELECT * FROM {cls.table_name}{where}",
                params,
            )
            return [cls(**row) for row in result] if result else []
        except Exception as e:
            logger.error(f"Error in get_by_field({field_name}): {e}")
            raise DatabaseOperationError(e)

    async def refresh(self: T) -> T:
        # Reload this object's data from the DB.
        # Useful after another part of the code may have changed it.
        if not self.id:
            raise InvalidInputError("Cannot refresh an object without an ID")
        fresh = await self.__class__.get(self.id)
        for key, value in fresh.model_dump().items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self

    def to_summary_dict(self) -> Dict[str, Any]:
        # Return a small dict with just id, table, and timestamps.
        # Handy for logs or lightweight API responses.
        return {
            "id": self.id,
            "table": self.__class__.table_name,
            "created": str(self.created) if self.created else None,
            "updated": str(self.updated) if self.updated else None,
        }

    @field_validator("created", "updated", mode="before")
    @classmethod
    def parse_datetime(cls, value):
        # Convert ISO string datetimes into `datetime` objects.
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value
