from sqlalchemy import BigInteger, String, Float, Integer, Column, DateTime, func, ForeignKey
from sqlalchemy.orm import relationship
from database.database import Base 

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
    
    # 🔥 НОВОЕ: Час уведомления (по умолчанию 8:00)
    notification_time = Column(Integer, default=8)
    
    current_workout_program = Column(String, nullable=True)
    current_nutrition_program = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    weight_history = relationship("WeightHistory", back_populates="user", cascade="all, delete-orphan")

class WeightHistory(Base):
    __tablename__ = 'weight_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.telegram_id'))
    weight = Column(Float, nullable=False)
    date = Column(DateTime, default=func.now())
    
    user = relationship("User", back_populates="weight_history")