from aiogram.fsm.state import State, StatesGroup

class UserForm(StatesGroup):
    """Состояния для заполнения профиля"""
    age = State()
    gender = State()
    weight = State()
    height = State()
    activity_level = State()
    goal = State()
    workout_level = State()
    workout_days = State()
