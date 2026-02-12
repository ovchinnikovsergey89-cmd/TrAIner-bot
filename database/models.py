from sqlalchemy import BigInteger, String, Float, Integer, Column, DateTime, func
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
    
    current_workout_program = Column(String, nullable=True)
    current_nutrition_program = Column(String, nullable=True)
    
    # trainer_style удален
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())