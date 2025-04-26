import configparser
import logging
import os.path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Settings:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    CONFIG_FILE = os.path.join(BASE_DIR, '..', 'settings.ini')

    def __init__(self):
        self.config = configparser.ConfigParser()
        self.admin_ids: set[int] = set()
        self.config.read(self.CONFIG_FILE, encoding='utf-8')
        self._load_settings()

    def _load_settings(self):
        self._load_telegram_settings()
        self._load_database_settings()
        self._load_admin_settings()
        self._load_business_logic_settings()

    def _load_telegram_settings(self):
        try:
            self.telegram_token = self.config.get('Telegram', 'TOKEN')
        except Exception as e:
            logging.error(f"Telegram bot token not found: {e}")
            self.telegram_token = None

    def _load_database_settings(self):
        try:
            self.db_host = self.config.get('Database', 'HOST', fallback=None)
            self.db_port = self.config.getint('Database', 'PORT', fallback=5432)
            self.db_user = self.config.get('Database', 'USER')
            self.db_password = self.config.get('Database', 'PASSWORD')
            self.db_name = self.config.get('Database', 'NAME')
        except Exception as e:
            logging.error(f"Database settings not found: {e}")
            self.db_host = None
            self.db_port = None
            self.db_user = None
            self.db_password = None
            self.db_name = None

    def _load_admin_settings(self):
        try:
            admin_ids_str = self.config.get('Admin', 'ADMIN_IDS', fallback=None)
            if admin_ids_str:
                raw_ids = admin_ids_str.split(',')
                processed_ids = set()
                for raw_id in raw_ids:
                    try:
                        processed_ids.add(int(raw_id))
                    except ValueError:
                        logging.warning(f"Invalid admin ID: {raw_id}")
                self.admin_ids = processed_ids
                logging.info(f"Loaded admin IDs: {self.admin_ids}")
            else:
                logging.warning("ADMIN_IDS not found or empty in settings.ini. No admins configured.")
                self.admin_ids = set()

        except configparser.NoSectionError:
             logging.warning("Section [Admin] not found in settings.ini. No admins configured.")
             self.admin_ids = set()
        except Exception as e:
            logging.error(f"Error loading admin settings: {e}", exc_info=True)
            self.admin_ids = set()

    def _load_business_logic_settings(self):
        try:
            self.discount_threshold_per_percent = self.config.getint(
                'BusinessLogic', 'DISCOUNT_THRESHOLD_PER_PERCENT',
                fallback=5000
            )
            self.free_hookah_every = self.config.getint(
                'BusinessLogic', 'FREE_HOOKAH_EVERY',
                fallback=6
            )
            self.qr_code_ttl_seconds = self.config.getint(
                'BusinessLogic', 'QR_CODE_TTL_SECONDS',
                fallback=600
            )
            self.cleanup_interval_seconds = self.config.getint(
                'BusinessLogic', 'CLEANUP_INTERVAL_SECONDS',
                fallback=610
            )
        except Exception as e:
            logging.error(f"Error loading buisness logic settings: {e}", exc_info=True)

settings = Settings()

