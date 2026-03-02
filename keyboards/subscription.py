from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_subscription_keyboard():
    buttons = [
        [InlineKeyboardButton(text="🥉 Лайт — 149 ₽ / 28 дней", callback_data="sub_lite")],
        [InlineKeyboardButton(text="🥈 Стандарт — 299 ₽ / 28 дней", callback_data="sub_standard")],
        [InlineKeyboardButton(text="🥇 Ультра — 499 ₽ / 28 дней", callback_data="sub_ultra")],
        [InlineKeyboardButton(text="❌ Назад в меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)