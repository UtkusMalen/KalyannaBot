import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import TypedDict, List, Tuple

from src.config import settings

logger = logging.getLogger(__name__)

DISCOUNT_TIERS: List[Tuple[Decimal, int]] = [
    (Decimal("0"), 1),
    (Decimal("5000"), 2),
    (Decimal("10000"), 3),
    (Decimal("15000"), 4),
    (Decimal("21000"), 5),
    (Decimal("27000"), 6),
    (Decimal("35000"), 7),
    (Decimal("45000"), 8),
    (Decimal("55000"), 9),
    (Decimal("70000"), 10),
]
DISCOUNT_TIERS.sort(key=lambda x: x[0])

class ProfileCalculations(TypedDict):
    discount_percent: int
    next_discount_percent: int | None
    progress_percent_to_next_discount: int
    amount_needed_for_next_discount: Decimal | None
    paid_hookahs_towards_next_free: int
    hookahs_needed_for_free: int
    hookah_progress_percent: int

def calculate_profile_metrics(total_spent: Decimal, hookah_count: int) -> ProfileCalculations:
    discount_percent = 0
    current_tier_threshold = Decimal("0")
    next_tier_threshold: Decimal | None = None
    next_discount_percent: int | None = None

    for i, (threshold, percent) in enumerate(DISCOUNT_TIERS):
        if total_spent >= threshold:
            discount_percent = percent
            current_tier_threshold = threshold
            if i + 1 < len(DISCOUNT_TIERS):
                next_tier_threshold = DISCOUNT_TIERS[i+1][0]
                next_discount_percent = DISCOUNT_TIERS[i+1][1]
            else:
                next_tier_threshold = None
                next_discount_percent = None
        else:
            break

    progress_percent_to_next_discount = 0
    amount_needed_for_next_discount: Decimal | None = None

    if next_tier_threshold is not None:
        if next_tier_threshold > current_tier_threshold:
            total_range = next_tier_threshold - current_tier_threshold
            spent_in_current_range = total_spent - current_tier_threshold
            progress_percent_to_next_discount = int(
                ((spent_in_current_range / total_range) * 100).to_integral_value(rounding=ROUND_HALF_UP)
            )
            progress_percent_to_next_discount = max(0, min(100, progress_percent_to_next_discount))
            amount_needed_for_next_discount = next_tier_threshold - total_spent
        else:
            progress_percent_to_next_discount = 100
            amount_needed_for_next_discount = Decimal("0")

    elif discount_percent == DISCOUNT_TIERS[-1][1] and total_spent >= DISCOUNT_TIERS[-1][0]:
        progress_percent_to_next_discount = 100
        amount_needed_for_next_discount = Decimal("0")

    paid_hookahs_towards_next = 0

    try:
        free_every = settings.free_hookah_every
        if free_every > 0:
            paid_hookahs_towards_next = hookah_count % free_every
            if paid_hookahs_towards_next == 0 and hookah_count > 0:
                 hookahs_needed_for_free = free_every
                 hookah_progress_percent = 0
            else:
                 hookahs_needed_for_free = free_every - paid_hookahs_towards_next
                 hookah_progress_percent = int((paid_hookahs_towards_next / free_every) * 100)

            if hookahs_needed_for_free == 0 and free_every != 1:
                 hookahs_needed_for_free = free_every
        else:
            logger.warning("Setting FREE_HOOKAH_EVERY is <= 0. Free hookah progress disabled.")
            hookahs_needed_for_free = 999
            hookah_progress_percent = 0
    except ZeroDivisionError:
        logger.error("Division by zero calculating hookah progress. FREE_HOOKAH_EVERY is likely 0.")
        hookahs_needed_for_free = 999
        hookah_progress_percent = 0
    except Exception as e:
        logger.error(f"Error calculating free hookah progress: {e}", exc_info=True)
        hookahs_needed_for_free = settings.free_hookah_every if settings.free_hookah_every > 0 else 999
        hookah_progress_percent = 0

    return ProfileCalculations(
        discount_percent=discount_percent,
        next_discount_percent=next_discount_percent,
        progress_percent_to_next_discount=progress_percent_to_next_discount,
        amount_needed_for_next_discount=amount_needed_for_next_discount,
        paid_hookahs_towards_next_free=paid_hookahs_towards_next,
        hookahs_needed_for_free=hookahs_needed_for_free,
        hookah_progress_percent=hookah_progress_percent
    )