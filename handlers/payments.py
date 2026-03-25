from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Router, F, types
from aiogram.types import LabeledPrice, PreCheckoutQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from config import Config
from database.crud import UserCRUD

# Токен ЮKassa
PAYMENTS_TOKEN = Config.PAYMENTS_TOKEN

# Состояние для ожидания ввода своей суммы
class TopupState(StatesGroup):
    waiting_for_amount = State()

router = Router()

PRICES = {
    "upgrade": 99,  # <--- Наш новый мини-пакет
    "lite": 149,      
    "standard": 299,  
    "ultra": 499,         
}

# 1. ВИТРИНА ТАРИФОВ (Покупка с внутреннего баланса)
@router.callback_query(F.data == "buy_premium")
async def show_subscription_plans(callback: types.CallbackQuery, session: AsyncSession):
    user = await UserCRUD.get_user(session, callback.from_user.id)
    
    text = f"""
💎 <b>Выберите уровень подписки или Апгрейд:</b>
💳 <i>Ваш баланс: {user.referral_balance or 0} руб.</i>

<b>🆓 Free (0₽)</b>
• 3 генерации / 5 вопросов

<b>🥉 Lite (149₽)</b>
• 10 генераций / 20 вопросов

<b>🥈 Standard (299₽)</b>
• 20 генераций / 50 вопросов + 🎙 Голосовые

<b>🥇 Ultra (499₽)</b>
• 40 генераций / 100 вопросов + 🎙 2 мин.

<b>🚀 Апгрейд (99₽)</b>
• +5 генераций и +10 вопросов к текущим лимитам.
• <i>Лимиты Апгрейда не сгорают!</i>
    """
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥇 Купить Ultra (499₽)", callback_data="buy_plan_ultra")],
        [InlineKeyboardButton(text="🥈 Купить Standard (299₽)", callback_data="buy_plan_standard")],
        [InlineKeyboardButton(text="🥉 Купить Lite (149₽)", callback_data="buy_plan_lite")],                
        [InlineKeyboardButton(text="🚀 Сделать Апгрейд (99₽)", callback_data="buy_plan_upgrade")], # <--- Новая кнопка
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="topup_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

# 2. МГНОВЕННАЯ ПОКУПКА ТАРИФА (Списание с баланса)
# 2. МГНОВЕННАЯ ПОКУПКА ТАРИФА (Списание с баланса)
@router.callback_query(F.data.startswith("buy_plan_"))
async def buy_plan_from_balance(callback: types.CallbackQuery, session: AsyncSession):
    try:
        parts = callback.data.split("_")
        plan = parts[2] 
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка данных кнопки", show_alert=True)
        return

    price = PRICES.get(plan)
    if not price:
        await callback.answer(f"❌ План {plan} не найден", show_alert=True)
        return

    user = await UserCRUD.get_user(session, callback.from_user.id)
    
    # ЗАЩИТА ОТ None: Если в базе None, считаем что баланс 0
    user_balance = user.referral_balance if user.referral_balance is not None else 0.0
    
    if user_balance >= price:
        # Списываем баланс
        user.referral_balance = user_balance - price
        await session.commit()
        
        if plan == "upgrade":
            await UserCRUD.add_upgrade_limits(session, user.telegram_id)
            await callback.message.edit_text(
                f"🚀 <b>Апгрейд выполнен!</b>\n\n"
                f"Добавлено: +5 генераций и +10 вопросов.\n"
                f"Списано: {price} руб. Остаток: {user.referral_balance} руб.",
                parse_mode="HTML"
            )
        else:
            success = await UserCRUD.update_user_subscription(session, user.telegram_id, plan)
            if success:
                await callback.message.edit_text(
                    f"✅ <b>Тариф повышен!</b>\n\n"
                    f"Ваш уровень теперь <b>{plan.upper()}</b> на 28 дней.\n"
                    f"Списано: {price} руб. Остаток: {user.referral_balance} руб.",
                    parse_mode="HTML"
                )
    else:
        need_more = price - user_balance
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="topup_menu")],
            [InlineKeyboardButton(text="🔙 Назад к тарифам", callback_data="buy_premium")]
        ])
        await callback.message.edit_text(
            f"❌ <b>Недостаточно средств.</b>\n\n"
            f"Стоимость: {price} руб.\n"
            f"На балансе: {user_balance} руб.\n"
            f"Вам не хватает: <b>{need_more} руб.</b>",
            reply_markup=kb,
            parse_mode="HTML"
        )
    
    await callback.answer()

# 3. МЕНЮ ПОПОЛНЕНИЯ БАЛАНСА
@router.callback_query(F.data == "topup_menu")
async def show_topup_menu(call: types.CallbackQuery, state: FSMContext):
    await state.clear() 
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="100 ₽", callback_data="topup_100"), InlineKeyboardButton(text="200 ₽", callback_data="topup_200")],
        [InlineKeyboardButton(text="300 ₽", callback_data="topup_300"), InlineKeyboardButton(text="500 ₽", callback_data="topup_500")],
        [InlineKeyboardButton(text="✍️ Ввести свою сумму", callback_data="topup_custom")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="show_balance")]
    ])
    await call.message.edit_text(
        "💰 <b>Выберите сумму пополнения:</b>\n\n"
        "<i>Деньги будут зачислены на ваш счет, и вы сможете в любой момент купить подписку в 1 клик.</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

# 4. ВВОД СВОЕЙ СУММЫ
@router.callback_query(F.data == "topup_custom")
async def enter_custom_amount(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "✍️ <b>Введите сумму пополнения (в рублях):</b>\n\n"
        "<i>Минимальная сумма — 99 руб.</i>\n\n"
        "Просто отправьте число ответным сообщением.",
        parse_mode="HTML"
    )
    # Включаем режим ожидания
    await state.set_state(TopupState.waiting_for_amount)
    await call.answer()

@router.message(TopupState.waiting_for_amount)
async def process_custom_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
        if amount < 99:
            await message.answer("⚠️ Минимальная сумма пополнения — 99 руб. Пожалуйста, введите сумму больше:")
            return
        
        # Если всё ок, выключаем режим ожидания и генерируем счет
        await state.clear()
        
        await message.answer_invoice(
            title="Пополнение баланса",
            description=f"Зачисление {amount} руб. на счет TrAIner Bot.",
            payload=f"topup_{amount}",
            provider_token=PAYMENTS_TOKEN,
            currency="RUB",
            prices=[LabeledPrice(label="Пополнение счета", amount=amount * 100)],
            start_parameter="trainer-bot-topup"
        )
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введите только число (например, 150):")

# 5. ВЫСТАВЛЕНИЕ СЧЕТА ИЗ ГОТОВЫХ КНОПОК
@router.callback_query(F.data.startswith("topup_"))
async def send_topup_invoice(callback: types.CallbackQuery):
    data_part = callback.data.split("_")[1]
    
    # Защита: пропускаем, если это не число (защищает от срабатывания на "menu" или "custom")
    if not data_part.isdigit():
        return
        
    amount = int(data_part)
    
    await callback.message.answer_invoice(
        title="Пополнение баланса",
        description=f"Зачисление {amount} руб. на счет TrAIner Bot.",
        payload=f"topup_{amount}",
        provider_token=PAYMENTS_TOKEN,
        currency="RUB",
        prices=[LabeledPrice(label="Пополнение счета", amount=amount * 100)],
        start_parameter="trainer-bot-topup"
    )
    await callback.answer()

# Обязательное подтверждение для Telegram
@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

# 6. УСПЕШНОЕ ПОПОЛНЕНИЕ БАЛАНСА
# 6. УСПЕШНОЕ ПОПОЛНЕНИЕ БАЛАНСА
@router.message(F.successful_payment)
async def success_payment(message: Message, session: AsyncSession):
    payment_info = message.successful_payment
    payload = payment_info.invoice_payload
    
    if payload.startswith("topup_"):
        amount_rub = payment_info.total_amount / 100 
        
        # Получаем юзера
        user = await UserCRUD.get_user(session, message.from_user.id)
        
        # ИСПРАВЛЕНИЕ 1: Проверяем на None, чтобы не было ошибки при сложении
        if user.referral_balance is None:
            user.referral_balance = 0.0
            
        # ИСПРАВЛЕНИЕ 2: Зачисляем именно на тот баланс, который ты используешь
        # Если ты хочешь, чтобы это был общий баланс для покупок:
        user.referral_balance += amount_rub 
        
        await session.commit()
        
        # 2. Начисляем кэшбэк рефереру
        await UserCRUD.add_referral_reward(session, message.from_user.id, amount_rub)
        
        await message.answer(
            f"✅ Оплата прошла успешно!\n"
            f"На ваш счет зачислено: {amount_rub} руб.\n"
            f"Текущий баланс: {user.referral_balance} руб."
        )