from sqlalchemy import BigInteger, String, Float, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs

class Base(AsyncAttrs, DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    
    # Анкета
    first_name: Mapped[str] = mapped_column(String, nullable=True)
    gender: Mapped[str] = mapped_column(String, nullable=True)
    age: Mapped[int] = mapped_column(Integer, nullable=True)
    weight: Mapped[float] = mapped_column(Float, nullable=True)
    height: Mapped[int] = mapped_column(Integer, nullable=True)
    activity_level: Mapped[str] = mapped_column(String, nullable=True)
    goal: Mapped[str] = mapped_column(String, nullable=True)
    workout_level: Mapped[str] = mapped_column(String, nullable=True)
    workout_days: Mapped[int] = mapped_column(Integer, nullable=True)
    
    # Программа тренировок (JSON)
    current_workout_program: Mapped[str] = mapped_column(Text, nullable=True)

    # 🔥 НОВОЕ ПОЛЕ: Программа питания (JSON)
    current_nutrition_program: Mapped[str] = mapped_column(Text, nullable=True)