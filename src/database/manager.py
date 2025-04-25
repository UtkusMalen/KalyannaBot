import asyncpg
from src.config import settings
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DatabaseManager:
    CREATE_USERS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        name VARCHAR(255),
        phone_number VARCHAR(30),
        registration_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
    );
    """
    CREATE_TEMP_CODES_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS temporary_codes (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        secret_code VARCHAR(10) NOT NULL,
        expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
    );
    """
    CREATE_TEMP_CODES_INDEX_SQL = """
    CREATE INDEX IF NOT EXISTS idx_temporary_codes_expires_at ON temporary_codes (expires_at);
    CREATE INDEX IF NOT EXISTS idx_temporary_codes_user_id_expires ON temporary_codes (user_id, expires_at);
    """
    def __init__(self):
        self.host = settings.db_host
        self.port = settings.db_port
        self.user = settings.db_user
        self.password = settings.db_password
        self.database = settings.db_name
        self._pool = None

    async def _initialize_schema(self, pool):
        if not pool:
            logging.error("Cannot initialize schema, connection pool is not available.")
            return
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    result_users = await conn.execute(self.CREATE_USERS_TABLE_SQL)
                    logging.info(f"Table 'users' checked/created successfully. Result: {result_users}")

                    result_codes = await conn.execute(self.CREATE_TEMP_CODES_TABLE_SQL)
                    logging.info(f"Table 'temporary_codes' checked/created successfully. Result: {result_codes}")

                    result_index = await conn.execute(self.CREATE_TEMP_CODES_INDEX_SQL)
                    logging.info(f"Indexes for 'temporary_codes' checked/created successfully. Result: {result_index}")
                    return True

        except Exception as e:
            logging.error(f"Error during database schema initialization (CREATE TABLE users): {e}")
            raise

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

                await self._initialize_schema(self._pool)
                logging.info("Database schema initialized successfully.")
            except Exception as e:
                logging.error(f"Error connecting to database: {e}")
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
            pool = await self.connect()
            if pool is None:
                logging.error("Failed to establish database connection after attempt. Cannot acquire connection.")
                return None
        return self._pool.acquire()

    async def execute(self, query, *args):
        conn_context = await self.get_connection()
        if conn_context is None:
            logging.error(f"Cannot execute query, failed to get connection.")
            return None
        async with conn_context as conn:
            if conn is None:
                return None
            try:
                result = await conn.execute(query, *args)
                return result
            except Exception as e:
                logging.error(f"Error executing query: {e}")
                return None

    async def fetch_one(self, query, *args):
        conn_context = await self.get_connection()
        if conn_context is None:
            logging.error(f"Cannot fetch_one, failed to get connection.")
            return None
        async with conn_context as conn:
            if conn is None:
                return None
            try:
                result = await conn.fetchrow(query, *args)
                return result
            except Exception as e:
                logging.error(f"Fetch one error for request `{query}` with args {args}: {e}")
                return None

    async def fetch_all(self, query, *args):
        conn_context = await self.get_connection()
        if conn_context is None:
            logging.error(f"Cannot fetch_all, failed to get connection.")
            return None
        async with conn_context as conn:
            if conn is None:
                return None
            try:
                result = await conn.fetch(query, *args)
                return result
            except Exception as e:
                logging.error(f"Fetch all error for request `{query}` with args {args}: {e}")
                return None

db_manager = DatabaseManager()
