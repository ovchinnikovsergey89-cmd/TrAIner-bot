from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_personality_keyboard():
    builder = InlineKeyboardBuilder()
    
    builder.row(InlineKeyboardButton(text="🔥 Тони (Мотиватор)", callback_data="set_style_supportive"))
    builder.row(InlineKeyboardButton(text="💀 Сержант (Жесткий)", callback_data="set_style_tough"))
    builder.row(InlineKeyboardButton(text="🧐 Доктор (Научный)", callback_data="set_style_scientific"))
    
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="cancel_edit"))
    return builder.as_markup()