import logging
from decimal import Decimal
from typing import TypedDict

from src.config import settings

logger = logging.getLogger(__name__)

class ProfileCalculations(TypedDict):
    discount_percent: int
    paid_hookahs_towards_next: int
    hookahs_needed_for_free: int

def calculate_profile_metrics(total_spent: Decimal, hookah_count: int) -> ProfileCalculations:
    discount_percent = 0
    try:
        if settings.discount_threshold_per_percent > 0:
            discount_percent = int(total_spent / settings.discount_threshold_per_percent)
        else:
            logger.warning("Setting DISCOUNT_THRESHOLD_PER_PERCENT is less than or equal to 0. Discount is not available.")
    except Exception as e:
        logger.error(f"Помилка при розрахунку знижки: {e}", exc_info=True)
        discount_percent = 0

    paid_hookahs_towards_next = 0
    hookahs_needed_for_free = settings.free_hookah_every if settings.free_hookah_every > 0 else 1

    try:
        if settings.free_hookah_every > 0:
            paid_hookahs_towards_next = hookah_count % settings.free_hookah_every
            hookahs_needed_for_free = settings.free_hookah_every - paid_hookahs_towards_next

            if hookahs_needed_for_free == settings.free_hookah_every and hookah_count > 0 and hookah_count % settings.free_hookah_every == 0:
                pass
            elif hookahs_needed_for_free == 0 and paid_hookahs_towards_next != 0:
                hookahs_needed_for_free = settings.free_hookah_every
        else:
            logger.warning("Setting FREE_HOOKAH_EVERY is less than or equal to 0. Free hookahs are not available.")
            hookahs_needed_for_free = 999

    except Exception as e:
        logger.error(f"Error calculating progress to free hookah: {e}", exc_info=True)
        hookahs_needed_for_free = settings.free_hookah_every

    return ProfileCalculations(
        discount_percent=discount_percent,
        paid_hookahs_towards_next=paid_hookahs_towards_next,
        hookahs_needed_for_free=hookahs_needed_for_free
    )
