from sqlalchemy.ext.asyncio import AsyncSession  # Добавь это в начало файла, если нет
from aiogram import Router, F, types
from aiogram.types import LabeledPrice, PreCheckoutQuery, Message
from config import Config
from database.crud import UserCRUD  # Импортируем только класс

PAYMENTS_TOKEN = Config.PAYMENTS_TOKEN

router = Router()

PRICES = {
    "lite": 14900,      # 149.00 RUB
    "standard": 29900,  # 299.00 RUB
    "ultra": 49900      # 499.00 RUB
}

@router.callback_query(F.data.startswith("sub_"))
async def send_invoice(callback: types.CallbackQuery):
    plan = callback.data.split("_")[1]
    
    titles = {
        "lite": "Тариф Лайт",
        "standard": "Тариф Стандарт",
        "ultra": "Тариф Ультра"
    }

    await callback.message.answer_invoice(
        title=titles[plan],
        description=f"Подписка на 28 дней. Доступ к функциям уровня {plan.capitalize()}.",
        payload=f"plan_{plan}",
        provider_token=PAYMENTS_TOKEN,
        currency="RUB",
        prices=[LabeledPrice(label="Оплата подписки", amount=PRICES[plan])],
        start_parameter="trainer-bot-subscription"
    )
    await callback.answer()

# Обязательный ответ на запрос перед окончательной оплатой
@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

# Обработка успешного платежа
@router.message(F.successful_payment)
async def success_payment(message: Message, session: AsyncSession):
    payment_info = message.successful_payment
    # Получаем план из payload (например, "plan_ultra" -> "ultra")
    plan = payment_info.invoice_payload.split("_")[1]
    
    # Обновляем
    success = await UserCRUD.update_user_subscription(session, message.from_user.id, plan)
    
    if success:
        # Принудительно очищаем состояние, чтобы профиль не брал старые данные
        await message.answer(
            f"✅ **Оплата прошла успешно!**\n\n"
            f"Тариф **{plan.upper()}** активирован.\n"
            f"Введите /profile для проверки.",
            parse_mode="Markdown"
        )
    else:
        await message.answer("Ошибка обновления БД.")