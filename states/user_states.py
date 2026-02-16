from aiogram.fsm.state import State, StatesGroup

# Бывший UserForm, теперь Registration, чтобы совпадать с handlers/start.py
class Registration(StatesGroup):
    name = State()
    gender = State()
    age = State()
    weight = State()
    height = State()
    activity_level = State()
    goal = State()
    workout_level = State()
    workout_days = State()
    
class EditForm(StatesGroup):
    weight = State()
    height = State()
    age = State()