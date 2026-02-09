from aiogram.fsm.state import State, StatesGroup

class UserForm(StatesGroup):
    name = State()
    gender = State()
    age = State()
    weight = State()
    height = State()
    activity_level = State()
    goal = State()
    workout_level = State()
    workout_days = State()
    trainer_style = State() # 🔥 Добавили новый шаг
    
class EditForm(StatesGroup):
    weight = State()
    height = State()
    age = State()