import asyncpg
from bot.config import settings
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DatabaseManager:
    def __init__(self):
        self.host = settings.db_host
        self.port = settings.db_port
        self.user = settings.db_user
        self.password = settings.db_password
        self.database = settings.db_name
        self._pool = None

    async def connect(self):
        if self._pool is None:
            try:
                self._pool = await asyncpg.create_pool(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    database=self.database
                )
                logging.info(f"Successfully created connection pool for {self.database} in {self.host}:{self.port}")
            except Exception as e:
                logging.ERROR(f"Error connecting to database: {e}")
                self._pool = None
        return self._pool

    async def close(self):
        if self._pool:
            try:
                await self._pool.close()
                logging.info("Database connection pool closed")
                self._pool = None
            except Exception as e:
                logging.error(f"Error closing database connection pool: {e}")

    async def get_connection(self):
        if self._pool is None:
            logging.info("Connection is not set. Trying to connect...")
            await self.connect()
        return self._pool.acquire()

    async def execute(self, query, *args):
        async with self.get_connection() as conn:
            if conn is None:
                return None
            try:
                result = await conn.execute(query, *args)
                return result
            except Exception as e:
                logging.error(f"Error executing query: {e}")
                return None

    async def fetch_one(self, query, *args):
        async with self.get_connection() as conn:
            if conn is None:
                return None
            try:
                result = await conn.fetchrow(query, *args)
                return result
            except Exception as e:
                logging.error(f"Fetch one error for request `{query}` with args {args}: {e}")
                return None

    async def fetch_all(self, query, *args):
        async with self.get_connection() as conn:
            if conn is None:
                return None
            try:
                result = await conn.fetch(query, *args)
                return result
            except Exception as e:
                logging.error(f"Fetch all error for request `{query}` with args {args}: {e}")
                return None

db_manager = DatabaseManager()
