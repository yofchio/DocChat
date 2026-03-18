import os
from pathlib import Path

from loguru import logger

from core.database.repository import db_connection, repo_query


class MigrationManager:
    def __init__(self, migrations_dir: str = None):
        if migrations_dir is None:
            migrations_dir = os.path.join(os.path.dirname(__file__), "..", "..", "migrations")
        self.migrations_dir = Path(migrations_dir).resolve()

    async def get_current_version(self) -> int:
        try:
            result = await repo_query(
                "SELECT math::max(version) as version FROM _sbl_migrations GROUP ALL"
            )
            if result and result[0].get("version") is not None:
                return int(result[0]["version"])
            return 0
        except Exception:
            return 0

    def _get_migration_files(self) -> list[Path]:
        if not self.migrations_dir.exists():
            return []
        files = sorted(self.migrations_dir.glob("*.surql"))
        return [f for f in files if not f.name.endswith("_down.surql")]

    async def needs_migration(self) -> bool:
        current = await self.get_current_version()
        available = len(self._get_migration_files())
        return current < available

    async def run_migrations(self):
        current = await self.get_current_version()
        migration_files = self._get_migration_files()

        if current >= len(migration_files):
            logger.info("Database is up to date")
            return

        for i, migration_file in enumerate(migration_files):
            version = i + 1
            if version <= current:
                continue

            logger.info(f"Running migration {version}: {migration_file.name}")
            sql = migration_file.read_text(encoding="utf-8")

            async with db_connection() as conn:
                try:
                    await conn.query(sql)
                except Exception as e:
                    logger.error(f"Migration {version} failed: {e}")
                    raise

            logger.success(f"Migration {version} completed")
