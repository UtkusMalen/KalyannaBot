import logging

logger = logging.getLogger(__name__)

def generate_progress_bar(percentage: int, length: int = 10, fill_char: str = '🟩', empty_char: str = '⬜️') -> str:
    if not 0 <= percentage <= 100:
        logger.warning(f"Progress bar percentage {percentage} out of bounds (0-100). Clamping.")
        percentage = max(0, min(100, percentage))
    if length <= 0:
        logger.warning(f"Progress bar length {length} is not positive. Returning empty string.")
        return ""

    try:
        filled_length = int(length * percentage / 100)
        empty_length = length - filled_length
        bar = fill_char * filled_length + empty_char * empty_length
        return bar
    except Exception as e:
        logger.error(f"Error generating progress bar for percentage {percentage}: {e}", exc_info=True)
        return f"[{percentage}%]"
