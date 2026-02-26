from aiogram.fsm.state import State, StatesGroup

class WorkoutPagination(StatesGroup):
    active = State() 

class WorkoutRequest(StatesGroup):
    waiting_for_wishes = State() # Ожидание пожеланий для недельной
    waiting_for_quick_workout_wishes = State() # НОВОЕ: Ожидание пожеланий для разовой
    waiting_for_nutrition_wishes = State()
    waiting_for_adjustments = State() # Ожидание правок от пользователя
    waiting_for_weights = State() # <-- НОВОЕ: Ожидание ввода веса