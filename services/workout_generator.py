from .workout_templates import WORKOUT_TEMPLATES, CARDIO_TEMPLATES, NUTRITION_TIPS
import random

class WorkoutGenerator:
    """Генератор тренировочных планов без ИИ"""
    
    @staticmethod
    def generate_weekly_plan(user_data: dict) -> dict:
        """
        Генерирует недельный план на основе данных пользователя
        """
        level = user_data.get("workout_level", "beginner")
        days = user_data.get("workout_days", 3)
        goal = user_data.get("goal", "maintenance")
        
        # Выбираем тип сплита в зависимости от дней
        if days <= 3:
            split_type = "full_body"
        elif days == 4:
            split_type = "upper_lower"
        else:
            split_type = "push_pull_legs" if level != "advanced" else "bro_split"
        
        # Генерируем дни тренировок
        plan = {
            "goal": goal,
            "level": level,
            "days_per_week": days,
            "split_type": split_type,
            "weekly_plan": [],
            "cardio": random.choice(CARDIO_TEMPLATES.get(goal, ["Ходьба 30 мин"])),
            "nutrition_tips": NUTRITION_TIPS.get(goal, [])
        }
        
        # Заполняем дни тренировок
        workout_days = WorkoutGenerator._get_workout_days(level, split_type, days)
        
        for i, day_info in enumerate(workout_days):
            plan["weekly_plan"].append({
                "day": i + 1,
                "focus": day_info["focus"],
                "exercises": day_info["exercises"],
                "duration": f"{len(day_info['exercises']) * 15 + 10} минут"
            })
        
        return plan
    
    @staticmethod
    def _get_workout_days(level: str, split_type: str, days: int) -> list:
        """Получает упражнения для каждого дня"""
        
        # Получаем шаблоны для уровня
        templates = WORKOUT_TEMPLATES.get(level, WORKOUT_TEMPLATES["beginner"])
        
        if split_type == "full_body":
            exercises = templates.get("full_body", templates.get("split", {}).get("upper", []))
            # Повторяем full_body для всех дней
            return [{"focus": "Все тело", "exercises": exercises}] * days
            
        elif split_type == "upper_lower":
            # Получаем верх/низ тела из split или используем full_body как запасной вариант
            if "split" in templates:
                upper = templates["split"].get("upper", [])
                lower = templates["split"].get("lower", [])
            else:
                # Если нет split, используем full_body для обоих
                full_body = templates.get("full_body", [])
                upper = full_body
                lower = full_body
            
            days_list = []
            for i in range(days):
                if i % 2 == 0:
                    days_list.append({"focus": "Верх тела", "exercises": upper})
                else:
                    days_list.append({"focus": "Низ тела", "exercises": lower})
            return days_list
            
        elif split_type == "push_pull_legs":
            ppl = templates.get("push_pull_legs", {})
            # Запасные варианты если нет PPL
            push = ppl.get("push", templates.get("full_body", []))
            pull = ppl.get("pull", templates.get("full_body", []))
            legs = ppl.get("legs", templates.get("full_body", []))
            
            cycles = [
                {"focus": "Толкающие", "exercises": push},
                {"focus": "Тянущие", "exercises": pull},
                {"focus": "Ноги", "exercises": legs}
            ]
            
            days_list = []
            for i in range(days):
                days_list.append(cycles[i % 3])
            return days_list
            
        else:  # bro_split
            bro = templates.get("bro_split", {})
            # Создаем список групп мышц
            muscle_groups = list(bro.keys())
            if not muscle_groups:
                # Если нет bro_split, используем полное тело
                full_body = templates.get("full_body", [])
                return [{"focus": "Полное тело", "exercises": full_body}] * days
            
            days_list = []
            for i in range(days):
                muscle = muscle_groups[i % len(muscle_groups)]
                days_list.append({
                    "focus": muscle.capitalize(),
                    "exercises": bro[muscle]
                })
            return days_list
    
    @staticmethod
    def format_plan_for_display(plan: dict) -> str:
        """Форматирует план для отображения в Telegram"""
        
        goal_text = {
            "weight_loss": "похудения",
            "muscle_gain": "набора массы", 
            "maintenance": "поддержания формы"
        }.get(plan["goal"], plan["goal"])
        
        level_text = {
            "beginner": "начинающего",
            "intermediate": "среднего уровня",
            "advanced": "продвинутого"
        }.get(plan["level"], plan["level"])
        
        text = f"🏋️‍♂️ *ПЛАН ТРЕНИРОВОК НА НЕДЕЛЮ*\n\n"
        text += f"🎯 Цель: {goal_text}\n"
        text += f"📊 Уровень: {level_text}\n"
        text += f"📅 Дней в неделю: {plan['days_per_week']}\n"
        text += f"📝 Тип сплита: {plan['split_type'].replace('_', ' ').title()}\n\n"
        
        text += "---\n"
        text += "📋 *РАСПИСАНИЕ ТРЕНИРОВОК:*\n\n"
        
        for day in plan["weekly_plan"]:
            text += f"*День {day['day']}: {day['focus']}* ({day['duration']})\n"
            
            for ex in day["exercises"]:
                text += f"  • {ex['exercise']}: {ex['sets']}x{ex['reps']} (отдых {ex.get('rest', '60 сек')})\n"
            
            text += "\n"
        
        text += "---\n"
        text += "🏃 *КАРДИО (2-3 раза в неделю):*\n"
        text += f"{plan['cardio']}\n\n"
        
        text += "🍎 *СОВЕТЫ ПО ПИТАНИЮ:*\n"
        for tip in plan.get("nutrition_tips", []):
            text += f"• {tip}\n"
        
        text += "\n---\n"
        text += "💡 *РЕКОМЕНДАЦИИ:*\n"
        text += "• Разминка 5-10 мин перед тренировкой\n"
        text += "• Заминка и растяжка после тренировки\n"
        text += "• Слушайте свое тело, не работайте через боль\n"
        text += "• Пейте воду во время тренировки\n"
        
        return text
    # В конце workout_templates.py убедитесь есть:
CARDIO_TEMPLATES = {
    "weight_loss": [
        "Интервальный бег: 30 сек спринт / 60 сек ходьба (15-20 мин)",
        "Велотренажер: 30 мин умеренного темпа",
        "Прыжки на скакалке: 10 раундов по 1 мин / 30 сек отдых"
    ],
    "muscle_gain": [
        "Ходьба на беговой дорожке: 20 мин легкого темпа",
        "Велотренажер: 15 мин для разминки"
    ],
    "maintenance": [
        "Бег: 25-30 мин в комфортном темпе",
        "Плавание: 20-30 мин"
    ]
}

NUTRITION_TIPS = {
    "weight_loss": [
        "🍎 Ешьте больше овощей (50% тарелки)",
        "💧 Пейте 2-3 литра воды в день",
        "⏰ Не пропускайте завтрак",
        "🚫 Избегайте сладких напитков"
    ],
    "muscle_gain": [
        "🍗 Белок каждый прием пищи",
        "⏱️ Ешьте каждые 3-4 часа",
        "🥑 Добавьте полезные жиры",
        "🍚 Сложные углеводы после тренировки"
    ],
    "maintenance": [
        "⚖️ Следите за баланс БЖУ",
        "📊 Взвешивайтесь раз в неделю",
        "🔄 Меняйте тренировки каждые 6-8 недель"
    ]
}
