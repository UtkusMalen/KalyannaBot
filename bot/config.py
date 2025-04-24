import configparser
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Settings:
    CONFIG_FILE = '../settings.ini'

    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read(self.CONFIG_FILE)
        self._load_settings()

    def _load_settings(self):
        self._load_telegram_settings()
        self._load_database_settings()

    def _load_telegram_settings(self):
        try:
            self.telegram_token = self.config.get('Telegram', 'TOKEN')
        except Exception as e:
            logging.error(f"Telegram bot token not found: {e}")
            self.telegram_token = None

    def _load_database_settings(self):
        try:
            self.db_host = self.config.get('Database', 'HOST')
            self.db_port = self.config.getint('Database', 'PORT', fallback=5432)
            self.db_user = self.config.get('Database', 'USER')
            self.db_password = self.config.get('Database', 'PASSWORD')
            self.db_name = self.config.get('Database', 'NAME')
        except Exception as e:
            logging.error("Database settings not found: {e}")
            self.db_host = None
            self.db_port = None
            self.db_user = None
            self.db_password = None
            self.db_name = None

settings = Settings()

