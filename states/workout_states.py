from aiogram.fsm.state import State, StatesGroup

class WorkoutPagination(StatesGroup):
    active = State() # Пользователь смотрит тренировку