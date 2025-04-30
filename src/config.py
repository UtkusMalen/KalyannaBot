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
        self.super_admin_ids: set[int] = set()
        self.menu_url: str | None = None
        self.booking_phone_number: str | None = None
        self.instagram_url: str | None = None
        self.tiktok_url: str | None = None
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
            admin_ids_str = self.config.get('Admin', 'ADMIN_IDS', fallback='')
            if admin_ids_str:
                self.admin_ids = {int(id.strip()) for id in admin_ids_str.split(',') if id.strip().isdigit()}
                logging.info(f"Loaded admin IDs: {self.admin_ids}")
            else:
                logging.warning("ADMIN_IDS not found or empty in settings.ini. No regular admins configured.")
                self.admin_ids = set()

            super_admin_ids_str = self.config.get('Admin', 'SUPER_ADMIN_IDS', fallback='')
            if super_admin_ids_str:
                self.super_admin_ids = {int(id.strip()) for id in super_admin_ids_str.split(',') if id.strip().isdigit()}
                logging.info(f"Loaded super admin IDs: {self.super_admin_ids}")
                missing_admins = self.super_admin_ids - self.admin_ids
                if missing_admins:
                    logging.warning(
                        f"Super admin IDs {missing_admins} are not listed in ADMIN_IDS. Adding them to admin_ids.")
                    self.admin_ids.update(missing_admins)
            else:
                logging.warning("SUPER_ADMIN_IDS not found or empty in settings.ini. No super admins configured.")
                self.super_admin_ids = set()
        except Exception as e:
            logging.error(f"Error loading admin settings: {e}", exc_info=True)
            self.admin_ids = set()
            self.super_admin_ids = set()

    def _load_business_logic_settings(self):
        try:
            self.free_hookah_every = self.config.getint('BusinessLogic', 'FREE_HOOKAH_EVERY',fallback=6)
            self.qr_code_ttl_seconds = self.config.getint('BusinessLogic', 'QR_CODE_TTL_SECONDS',fallback=600)
            self.cleanup_interval_seconds = self.config.getint('BusinessLogic', 'CLEANUP_INTERVAL_SECONDS',fallback=610)
            self.menu_url = self.config.get("BusinessLogic", "MENU_URL", fallback=None)
            self.booking_phone_number = self.config.get("BusinessLogic", "BOOKING_PHONE_NUMBER", fallback=None)
            self.instagram_url = self.config.get("BusinessLogic", "INSTAGRAM_URL", fallback=None)
            self.tiktok_url = self.config.get("BusinessLogic", "TIKTOK_URL", fallback=None)
        except Exception as e:
            logging.error(f"Error loading buisness logic settings: {e}", exc_info=True)

settings = Settings()

