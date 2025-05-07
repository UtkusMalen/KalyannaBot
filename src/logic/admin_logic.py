import logging
import csv
import io
from datetime import datetime, timezone
from decimal import Decimal
from typing import TypedDict, Optional, List, Dict, Any

from aiogram import Bot

from src.database.manager import db_manager
from src.logic.profile_logic import calculate_profile_metrics

logger = logging.getLogger(__name__)

class ValidTokenInfo(TypedDict):
    user_id: int
    expires_at: datetime

class UserDataForUpdate(TypedDict):
    name: str
    hookah_count: int
    free_hookahs_available: int
    total_spent: Decimal

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
            "SELECT name, free_hookahs_available FROM users WHERE user_id = $1",
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

async def finalize_user_update(client_user_id: int,used_token: str,entered_amount: Decimal,hookah_count_added: int,used_free_hookahs: int, bot: Bot) -> Optional[UserDataForUpdate]:
    sql_get_current_counts = """
    SELECT name, hookah_count, free_hookahs_available, total_spent
    FROM users WHERE user_id = $1 FOR UPDATE;
    """
    sql_update_user_final = """
    UPDATE users
    SET total_spent = total_spent + $1,
        hookah_count = hookah_count + $2,
        free_hookahs_available = free_hookahs_available - $3 + $4
    WHERE user_id = $5 AND free_hookahs_available >= $3
    RETURNING name, total_spent, hookah_count, free_hookahs_available;
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
                message_record = await conn.fetchrow(sql_get_message_id, used_token, client_user_id)
                if message_record and message_record['message_id']:
                    message_to_delete = message_record['message_id']
                    logger.info(f"Found message_id {message_to_delete} associated with token {used_token} for user {client_user_id}.")
                current_data = await conn.fetchrow(sql_get_current_counts, client_user_id)
                if not current_data:
                    logger.error(f"User {client_user_id} not found during final GET. Rolling back.")
                    raise Exception(f"User {client_user_id} not found")

                current_free_available = current_data.get('free_hookahs_available', 0)

                if current_free_available < used_free_hookahs:
                    logger.error(f"Insufficient free hookahs for user {client_user_id}. Available: {current_free_available}, Tried to use: {used_free_hookahs}. Rolling back.")
                    raise ValueError("INSUFFICIENT_FREE_HOOKAHS")

                old_paid_count = current_data.get('hookah_count', 0)
                new_paid_count = old_paid_count + hookah_count_added
                newly_earned_free = (new_paid_count // 6) - (old_paid_count // 6)

                logger.info(f"Finalizing update for {client_user_id}: Amount={entered_amount}, AddedPaid={hookah_count_added}, UsedFree={used_free_hookahs}, EarnedFree={newly_earned_free}")

                updated_user_data = await conn.fetchrow(
                    sql_update_user_final,
                    entered_amount,
                    hookah_count_added,
                    used_free_hookahs,
                    newly_earned_free,
                    client_user_id
                )

                if not updated_user_data:
                    logger.error(f"User {client_user_id} UPDATE failed or returned no data within transaction. Possibly due to concurrency or insufficient free hookahs check failed at DB level. Rolling back.")
                    raise Exception(f"User {client_user_id} update failed during UPDATE.")

                delete_result = await conn.execute(sql_delete_token, used_token, client_user_id)
                if not delete_result or 'DELETE 0' in delete_result:
                     logger.warning(f"Token {used_token} for user {client_user_id} might not have been deleted (Result: {delete_result}). Transaction continues but investigate.")


                logger.info(f"Transaction successful for user {client_user_id}. Final data: {updated_user_data}")
                final_data = UserDataForUpdate(
                    name=updated_user_data['name'],
                    total_spent=updated_user_data['total_spent'],
                    hookah_count=updated_user_data['hookah_count'],
                    free_hookahs_available=updated_user_data['free_hookahs_available']
                )

            except ValueError as ve:
                if str(ve) == "INSUFFICIENT_FREE_HOOKAHS":
                    logger.warning(f"Transaction rolled back for user {client_user_id} due to insufficient free hookahs.")
                    return None
                else:
                    logger.error(f"Transaction failed for user {client_user_id} with ValueError: {ve}", exc_info=True)
                    return None
            except Exception as e:
                logger.error(f"Transaction failed for user {client_user_id}: {e}", exc_info=True)
                return None

    if message_to_delete:
        try:
            await bot.delete_message(chat_id=client_user_id, message_id=message_to_delete)
            logger.info(f"Successfully deleted QR message {message_to_delete} for user {client_user_id} after admin use.")
        except Exception as e:
            logger.error(f"Unexpected error deleting QR message {message_to_delete} for user {client_user_id}: {e}",exc_info=True)

    return final_data


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
        "Ім'я", "Телефон", "Сума витрат (грн)", "К-сть платних кальянів", "Доступно безкоштовних", "поточна знижка %", "Дата реєстрації"
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
            registration_date = client.get("registration_date", "N/A")

            writer.writerow([
                name,
                phone_csv,
                total_spent_str,
                hookah_count,
                free_hookahs_available,
                discount,
                registration_date
            ])
        except Exception as e:
            logger.error(f"Failed to generate row for client {client}: {e}", exc_info=True)
            try:
                writer.writerow([client.get('name', 'ERROR'), 'ERROR', '0.00', 0, 0, 0])
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