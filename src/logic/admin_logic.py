import csv
import io
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import TypedDict, Optional, List, Dict, Any, Tuple

from src.database.manager import db_manager
from src.logic.admin_statistics import log_admin_action
from src.logic.profile_logic import calculate_profile_metrics
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


class ValidTokenInfo(TypedDict):
    user_id: int
    expires_at: datetime


class UserDataForUpdate(TypedDict):
    name: str
    phone_number: Optional[str]
    hookah_count: int
    free_hookahs_available: int
    total_spent: Decimal
    qr_message_id: Optional[int]


async def validate_token(token: str) -> Optional[ValidTokenInfo]:
    sql_find_token = """
    SELECT user_id, expires_at FROM temporary_codes
    WHERE secret_code = $1 AND expires_at > $2;
    """
    now_utc = datetime.now(timezone.utc)
    try:
        token_record = await db_manager.fetch_one(sql_find_token, token, now_utc)
        if token_record:
            logger.info(f"Token {token} is valid for user {token_record['user_id']}.")
            return ValidTokenInfo(user_id=token_record['user_id'], expires_at=token_record['expires_at'])
        else:
            logger.warning(f"Token {token} is invalid or expired.")
            return None
    except Exception as e:
        logger.error(f"Database error checking token {token}: {e}", exc_info=True)
        return None


async def get_user_initial_data(user_id: int) -> Optional[dict]:
    try:
        user_data = await db_manager.fetch_one(
            "SELECT name, phone_number, free_hookahs_available FROM users WHERE user_id = $1",
            user_id
        )
        if user_data:
            return dict(user_data)
        else:
            logger.warning(f"Could not find user data for user {user_id} during initial data fetch.")
            return None
    except Exception as e:
        logger.error(f"Failed to fetch initial data for user {user_id}: {e}", exc_info=True)
        return None


async def finalize_user_update(client_user_id: int, used_token: str, entered_amount: Decimal,
                               hookah_count_added: int, used_free_hookahs: int,
                               admin_id: int, admin_name: Optional[str], admin_username: Optional[str]) -> Optional[
    UserDataForUpdate]:
    sql_get_current_user_data = """
    SELECT name, phone_number, hookah_count, free_hookahs_available, total_spent
    FROM users WHERE user_id = $1 FOR UPDATE;
    """
    sql_update_user_final = """
    UPDATE users
    SET total_spent = total_spent + $1,
        hookah_count = hookah_count + $2,
        free_hookahs_available = free_hookahs_available - $3 + $4
    WHERE user_id = $5 AND free_hookahs_available >= $3
    RETURNING name, phone_number, total_spent, hookah_count, free_hookahs_available;
    """
    sql_get_message_id = "SELECT message_id FROM temporary_codes WHERE secret_code = $1 AND user_id = $2;"
    sql_delete_token = "DELETE FROM temporary_codes WHERE secret_code = $1 AND user_id = $2;"

    conn_context_manager = await db_manager.get_connection()
    async with conn_context_manager as conn:
        if conn is None:
            logger.error(f"Failed to get connection from pool for transaction (admin logic finalize)")
            return None

        async with conn.transaction():
            try:
                current_user_data = await conn.fetchrow(sql_get_current_user_data, client_user_id)
                if not current_user_data:
                    logger.error(f"User {client_user_id} not found during final GET. Rolling back.")
                    raise Exception(f"User {client_user_id} not found")

                client_name_from_db = current_user_data.get('name')
                client_phone_number = current_user_data.get('phone_number')
                current_total_spent = current_user_data.get('total_spent', Decimal('0.00'))
                current_free_available = current_user_data.get('free_hookahs_available', 0)
                old_paid_count = current_user_data.get('hookah_count', 0)

                if current_total_spent == Decimal('0.00') and entered_amount > Decimal('0.00'):
                    try:
                        await log_admin_action(
                            admin_id=admin_id,
                            admin_name=admin_name,
                            admin_username=admin_username,
                            action_type='user_registered',
                            user_id=client_user_id,
                            client_name=client_name_from_db,
                            client_phone_number=client_phone_number
                        )
                        logger.info(
                            f"Logged new user registration for first-time spender: {client_user_id} by admin {admin_id} ({admin_name or admin_username})")
                    except Exception as e:
                        logger.error(f"Failed to log new user registration: {e}", exc_info=True)

                try:
                    await log_admin_action(
                        admin_id=admin_id,
                        admin_name=admin_name,
                        admin_username=admin_username,
                        action_type='transaction',
                        user_id=client_user_id,
                        client_name=client_name_from_db,
                        client_phone_number=client_phone_number,
                        amount=entered_amount,
                        hookah_count=hookah_count_added
                    )
                    logger.info(
                        f"Logged transaction for user {client_user_id} by admin {admin_id} ({admin_name or admin_username})")
                except Exception as e:
                    logger.error(f"Failed to log transaction for user {client_user_id}: {e}", exc_info=True)

                if current_free_available < used_free_hookahs:
                    logger.error(
                        f"Insufficient free hookahs for user {client_user_id}. Available: {current_free_available}, Tried to use: {used_free_hookahs}. Rolling back.")
                    raise ValueError("INSUFFICIENT_FREE_HOOKAHS")

                new_paid_count = old_paid_count + hookah_count_added

                newly_earned_free = 0
                if settings.free_hookah_every > 0:
                    newly_earned_free = (new_paid_count // settings.free_hookah_every) - \
                                        (old_paid_count // settings.free_hookah_every)
                else:
                    logger.warning("FREE_HOOKAH_EVERY setting is not positive, no free hookahs will be earned.")

                logger.info(
                    f"Finalizing update for {client_user_id}: Amount={entered_amount}, AddedPaid={hookah_count_added}, UsedFree={used_free_hookahs}, EarnedFree={newly_earned_free}")

                updated_user = await conn.fetchrow(
                    sql_update_user_final,
                    float(entered_amount),
                    hookah_count_added,
                    used_free_hookahs,
                    newly_earned_free,
                    client_user_id
                )

                if not updated_user:
                    logger.error(
                        f"Failed to update user {client_user_id}. Possible race condition or insufficient free hookahs.")
                    return None

                message_record = await conn.fetchrow(sql_get_message_id, used_token, client_user_id)
                qr_message_id = message_record[
                    'message_id'] if message_record and 'message_id' in message_record else None

                await conn.execute(sql_delete_token, used_token, client_user_id)
                logger.info(f"Successfully updated user {client_user_id} and deleted token {used_token}")

                return UserDataForUpdate(
                    name=updated_user['name'],
                    phone_number=updated_user['phone_number'],
                    hookah_count=updated_user['hookah_count'],
                    free_hookahs_available=updated_user['free_hookahs_available'],
                    total_spent=updated_user['total_spent'],
                    qr_message_id=qr_message_id
                )

            except ValueError as ve:
                logger.error(f"ValueError during finalize_user_update for user {client_user_id}: {ve}", exc_info=True)
                raise
            except Exception as e:
                logger.error(f"Error in finalize_user_update for user {client_user_id}: {e}", exc_info=True)
                raise


async def get_all_clients_data() -> List[Dict[str, Any]] | None:
    sql_get_all = """
    SELECT user_id, name, phone_number, total_spent, hookah_count, free_hookahs_available, registration_date FROM users
    ORDER BY registration_date ASC;
    """
    try:
        all_user_records = await db_manager.fetch_all(sql_get_all)
        if all_user_records:
            return [dict(record) for record in all_user_records]
        else:
            logger.warning("Failed to fetch all users data from DB. Returning None.")
            return None
    except Exception as e:
        logger.error(f"Failed to fetch all users data from DB: {e}", exc_info=True)
        return None


async def generate_clients_report_csv() -> str | None:
    clients_data = await get_all_clients_data()
    if clients_data is None:
        logger.error("Failed to fetch clients data for CSV generation.")
        return None

    report = io.StringIO()
    writer = csv.writer(report, dialect='excel', lineterminator='\n')
    header = [
        "Ім'я", "Телефон", "Сума витрат (грн)", "К-сть платних кальянів", "Доступно безкоштовних", "поточна знижка %",
        "Дата реєстрації"
    ]
    writer.writerow(header)

    for client in clients_data:
        try:
            name = client.get("name", "N/A")
            phone = client.get("phone_number", "N/A")
            phone_csv = f"'{phone}'" if phone != 'N/A' else 'N/A'
            total_spent = client.get("total_spent", Decimal(0.00))
            hookah_count = client.get("hookah_count", 0)
            free_hookahs_available = client.get("free_hookahs_available", 0)
            metrics = calculate_profile_metrics(total_spent, hookah_count)
            discount = metrics['discount_percent']
            total_spent_str = f"{total_spent:.2f}"
            registration_date_obj = client.get("registration_date")
            registration_date_str = registration_date_obj.strftime('%Y-%m-%d %H:%M:%S') if isinstance(
                registration_date_obj, datetime) else "N/A"

            writer.writerow([
                name,
                phone_csv,
                total_spent_str,
                hookah_count,
                free_hookahs_available,
                discount,
                registration_date_str
            ])
        except Exception as e:
            logger.error(f"Failed to generate row for client {client.get('user_id', 'UNKNOWN')}: {e}", exc_info=True)
            try:
                writer.writerow([client.get('name', 'ERROR'), 'ERROR', '0.00', 0, 0, 0, 'ERROR'])
            except:
                pass

    csv_content = report.getvalue()
    report.close()
    logger.info("CSV report generated successfully.")
    return csv_content


async def get_all_user_ids() -> List[int] | None:
    sql_get_ids = "SELECT user_id FROM users ORDER BY user_id;"
    try:
        user_records = await db_manager.fetch_all(sql_get_ids)
        if user_records:
            user_ids = [record['user_id'] for record in user_records]
            logger.info(f"Fetched {len(user_ids)} user IDs for broadcast.")
            return user_ids
        else:
            logger.warning("No user IDs found in the database.")
            return []
    except Exception as e:
        logger.error(f"Failed to fetch user IDs: {e}", exc_info=True)
        return None