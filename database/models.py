from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import BigInteger, String, Float, Integer

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    
    # Анкета
    name: Mapped[str] = mapped_column(String, nullable=True)
    age: Mapped[int] = mapped_column(Integer, nullable=True)
    weight: Mapped[float] = mapped_column(Float, nullable=True)
    height: Mapped[float] = mapped_column(Float, nullable=True)
    gender: Mapped[str] = mapped_column(String, nullable=True)
    activity_level: Mapped[str] = mapped_column(String, nullable=True)
    goal: Mapped[str] = mapped_column(String, nullable=True)
    
    # Настройки тренировок
    workout_level: Mapped[str] = mapped_column(String, nullable=True)
    workout_days: Mapped[int] = mapped_column(Integer, nullable=True)
    
    # Программы (JSON строки)
    current_workout_program: Mapped[str] = mapped_column(String, nullable=True)
    current_nutrition_program: Mapped[str] = mapped_column(String, nullable=True)
    
    # 🔥 НОВОЕ ПОЛЕ: Стиль общения тренера (по умолчанию "supportive")
    trainer_style: Mapped[str] = mapped_column(String, default="supportive", nullable=True)