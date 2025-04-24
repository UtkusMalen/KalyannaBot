import yaml
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_MESSAGES_PATH = PROJECT_ROOT / "messages.yaml"

MESSAGES = {}

def load_messages(path: Path = DEFAULT_MESSAGES_PATH):
    global MESSAGES
    try:
        with open(path, 'r', encoding='utf-8') as f:
            MESSAGES = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Unexpected error while loading messages file: {e}")
        raise

def get_message(key_path, **kwargs):
    keys = key_path.split('.')
    value = MESSAGES
    try:
        for key in keys:
            value = value[key]
        if isinstance(value, str):
            return value.format_map(kwargs)
        return value
    except Exception as e:
        logger.error(f"Unexpected error while getting message `{key_path}`: {e}")
        return f"<{key_path}_ERROR>"

load_messages()