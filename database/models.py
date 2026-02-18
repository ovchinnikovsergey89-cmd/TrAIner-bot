from sqlalchemy import BigInteger, String, Float, Integer, Column, DateTime, func, ForeignKey, Boolean  # <-- Добавь Boolean сюда
from sqlalchemy.orm import relationship
from database.database import Base
import datetime 

class User(Base):
    __tablename__ = 'users'

    telegram_id = Column(BigInteger, primary_key=True)
    name = Column(String, nullable=True)
    age = Column(Integer, nullable=True)
    weight = Column(Float, nullable=True)
    height = Column(Float, nullable=True)
    gender = Column(String, nullable=True)
    activity_level = Column(String, nullable=True)
    goal = Column(String, nullable=True)
    workout_level = Column(String, nullable=True)
    workout_days = Column(Integer, default=3)
    
    # --- СИСТЕМА МОНЕТИЗАЦИИ ---
    is_premium = Column(Boolean, default=False) # Статус подписки
    workout_limit = Column(Integer, default=3)   # Бесплатные генерации (базово 3)
    chat_limit = Column(Integer, default=5)      # Бесплатные вопросы (базово 5)
    # ---------------------------

    notification_time = Column(Integer, default=8)
    current_workout_program = Column(String, nullable=True)
    current_nutrition_program = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    weight_history = relationship("WeightHistory", back_populates="user", cascade="all, delete-orphan")

class WorkoutLog(Base):
    __tablename__ = "workout_logs"

    id = Column(Integer, primary_key=True)
    # Ссылаемся на telegram_id, так как в таблице User нет колонки id
    user_id = Column(BigInteger, ForeignKey("users.telegram_id")) 
    date = Column(DateTime, default=datetime.datetime.now)
    workout_type = Column(String)  # Например: "День 1", "День 2"

class WeightHistory(Base):
    __tablename__ = 'weight_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.telegram_id'))
    weight = Column(Float, nullable=False)
    date = Column(DateTime, default=func.now())
    
    user = relationship("User", back_populates="weight_history")