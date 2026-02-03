class NutritionCalculator:
    """Калькулятор калорий и БЖУ"""
    
    @staticmethod
    def calculate_bmr(weight: float, height: float, age: int, gender: str) -> float:
        """
        Расчет базового метаболизма (BMR)
        Формула Миффлина-Сан Жеора
        """
        if gender == "male":
            return (10 * weight) + (6.25 * height) - (5 * age) + 5
        else:  # female
            return (10 * weight) + (6.25 * height) - (5 * age) - 161
    
    @staticmethod
    def calculate_tdee(bmr: float, activity_level: str) -> float:
        """
        Расчет общего расхода калорий (TDEE)
        """
        activity_multipliers = {
            "low": 1.2,          # Минимальная активность
            "medium": 1.375,     # Легкая активность 1-3 дня/неделю
            "high": 1.55,        # Умеренная активность 3-5 дней/неделю
            "very_high": 1.725   # Высокая активность 6-7 дней/неделю
        }
        
        multiplier = activity_multipliers.get(activity_level, 1.2)
        return bmr * multiplier
    
    @staticmethod
    def calculate_daily_calories(tdee: float, goal: str) -> float:
        """
        Расчет рекомендуемых калорий в день
        """
        goal_adjustments = {
            "weight_loss": -500,      # Дефицит для похудения
            "maintenance": 0,         # Поддержание веса
            "muscle_gain": +300       # Профицит для набора массы
        }
        
        adjustment = goal_adjustments.get(goal, 0)
        return tdee + adjustment
    
    @staticmethod
    def calculate_macros(calories: float, goal: str) -> dict:
        """
        Расчет БЖУ (белки, жиры, углеводы)
        """
        # Базовые проценты в зависимости от цели
        if goal == "weight_loss":
            protein_percent = 0.40  # 40% белка
            fat_percent = 0.30      # 30% жиров
            carb_percent = 0.30     # 30% углеводов
        elif goal == "muscle_gain":
            protein_percent = 0.35  # 35% белка
            fat_percent = 0.25      # 25% жиров
            carb_percent = 0.40     # 40% углеводов
        else:  # maintenance
            protein_percent = 0.30  # 30% белка
            fat_percent = 0.30      # 30% жиров
            carb_percent = 0.40     # 40% углеводов
        
        # Расчет в граммах (1г белка/углеводов = 4 ккал, 1г жиров = 9 ккал)
        protein_grams = (calories * protein_percent) / 4
        fat_grams = (calories * fat_percent) / 9
        carb_grams = (calories * carb_percent) / 4
        
        return {
            "protein": round(protein_grams),
            "fat": round(fat_grams),
            "carbs": round(carb_grams),
            "calories": round(calories)
        }
