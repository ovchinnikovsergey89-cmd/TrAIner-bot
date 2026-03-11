import pytest
from aiogram_tests import MockedBot
from aiogram_tests.handler import MessageHandler, CallbackQueryHandler
from aiogram_tests.types.dataset import MESSAGE, CALLBACK_QUERY

# Импортируем твои функции из start.py
from handlers.start import cmd_start, process_gender, process_age, process_weight, process_height
from states.user_states import Registration

@pytest.mark.asyncio
async def test_full_registration_flow():
    bot = MockedBot()

    # --- ТЕСТ 1: Команда /start ---
    # Проверяем, что новый пользователь получает приветствие
    handler = MessageHandler(cmd_start)
    # Имитируем, что юзера нет в базе (нужно подменить UserCRUD.get_user на None в реальном тесте)
    result = await bot.query(MESSAGE.as_object(text="/start"))
    assert "Я твой персональный AI-тренер" in result.send_message.fetchone().text
    print("✅ Шаг 0 (/start) — OK")

    # --- ТЕСТ 2: Выбор пола (Callback) ---
    handler = CallbackQueryHandler(process_gender)
    result = await bot.query(CALLBACK_QUERY.as_object(data="gender_male"))
    assert "Сколько тебе лет" in result.send_message.fetchone().text
    print("✅ Шаг 1 (Пол) — OK")

    # --- ТЕСТ 3: Ввод возраста (Text) ---
    handler = MessageHandler(process_age)
    result = await bot.query(MESSAGE.as_object(text="25"))
    assert "Введи свой вес" in result.send_message.fetchone().text
    print("✅ Шаг 2 (Возраст) — OK")

    # --- ТЕСТ 4: Ввод веса (Критическая точка!) ---
    handler = MessageHandler(process_weight)
    result = await bot.query(MESSAGE.as_object(text="85.5"))
    assert "Введи свой рост" in result.send_message.fetchone().text
    print("✅ Шаг 3 (Вес) — OK")

    # --- ТЕСТ 5: Ввод роста (Шаг 5) ---
    handler = MessageHandler(process_height)
    result = await bot.query(MESSAGE.as_object(text="180"))
    assert "Какая у тебя цель" in result.send_message.fetchone().text
    print("✅ Шаг 4 (Рост) — OK")

    print("\n🚀 ИТОГ: Регистрация работает стабильно!")