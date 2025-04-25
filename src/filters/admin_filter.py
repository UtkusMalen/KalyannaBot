from aiogram.filters import Filter
from aiogram.types import Message, CallbackQuery
from src.config import settings

class AdminFilter(Filter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        if not event.from_user or not event.from_user.id:
            return False
        user_id = event.from_user.id
        return user_id in settings.admin_ids