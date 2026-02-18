from aiogram.fsm.state import State, StatesGroup

class WorkoutPagination(StatesGroup):
    active = State() 

class WorkoutRequest(StatesGroup):
    waiting_for_wishes = State() # Новое состояние для пожеланий
    waiting_for_nutrition_wishes = State()