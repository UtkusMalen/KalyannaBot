import configparser
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

SETTINGS_PATH = 'settings.ini'
ENV_FILE_PATH = '.env'

def get_setting(config, section, option, default=None):
    try:
        value = config.get(section, option)
        return value
    except Exception as e:
        logging.error(f"Error reading {section}/{option}: {e}")
        return default

def generate_env_file():
    config = configparser.ConfigParser(interpolation=None)
    try:
        config.read(SETTINGS_PATH)
    except configparser.Error as e:
        logging.error(f"Error parsing `{SETTINGS_PATH}`: {e}")
        return
    telegram_token = get_setting(config, 'Telegram', 'TOKEN')
    db_host = get_setting(config, 'Database', 'HOST')
    db_user = get_setting(config, 'Database', 'USER')
    db_password = get_setting(config, 'Database', 'PASSWORD')
    db_name = get_setting(config, 'Database', 'NAME')
    db_port = get_setting(config, 'Database', 'PORT')

    env_content = []
    if telegram_token:
        env_content.append(f"TELEGRAM_TOKEN={telegram_token}")
    else:
        env_content.append(f"TELEGRAM_TOKEN= # PLEASE SET YOUR TELEGRAM TOKEN IN settings.ini")
        logging.warning("Telegram token is not set")

    if db_user:
        env_content.append(f"DB_USER={db_user}")
    else:
        env_content.append(f"DB_USER= # PLEASE SET YOUR DATABASE USER IN settings.ini")
        logging.warning("Database user is not set")

    if db_password:
        env_content.append(f"DB_PASSWORD={db_password}")
    else:
        env_content.append(f"DB_PASSWORD= #PLEASE SET YOUR DATABASE PASSWORD IN settings.ini ")
        logging.warning("Database password is not set")
    if db_name:
        env_content.append(f"DB_NAME={db_name}")
    else:
        env_content.append(f"DB_NAME= # PLEASE SET YOUR DATABASE NAME IN settings.ini")
        logging.warning("Database user is not set")

    if db_port:
        env_content.append(f"DB_PORT={db_port}")
    else:
        env_content.append(f"DB_PORT= # PLEASE SET YOUR DATABASE PORT IN settings.ini")
        logging.warning("Database port is not set")

    if db_host:
        env_content.append(f"DB_HOST={db_host}")
    else:
        env_content.append(f"DB_HOST= # PLEASE SET YOUR DATABASE HOST IN settings.ini")
        logging.warning("Database host is not set")

    try:
        with open(ENV_FILE_PATH, 'w') as f:
            f.write("\n".join(env_content) + "\n")
        logging.info(f"`{ENV_FILE_PATH}` successfulle created/updated")
    except IOError as e:
        logging.error(f"Cannot create file `{ENV_FILE_PATH}`: {e}")

if __name__ == "__main__":
    generate_env_file()
