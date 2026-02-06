from aiogram.fsm.state import State, StatesGroup

class UserForm(StatesGroup):
    # Состояния для регистрации
    name = State()
    age = State()
    weight = State()
    height = State()
    gender = State()
    activity_level = State()
    goal = State()
    workout_level = State()
    workout_days = State()

class EditForm(StatesGroup):
    # Состояния для редактирования профиля
    age = State()
    weight = State()
    height = State()