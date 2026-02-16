import logging
import datetime
import re
from datetime import timedelta
from openai import AsyncOpenAI
from config import Config
from utils.text_tools import clean_text

logger = logging.getLogger(__name__)

class AIManager:
    """
    Единый менеджер для работы с AI (DeepSeek).
    """
    def __init__(self):
        self.api_key = Config.DEEPSEEK_API_KEY
        self.client = None
        self.model = "deepseek-chat"
        
        if self.api_key:
            try:
                self.client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url="https://api.deepseek.com"
                )
            except Exception as e:
                logger.error(f"AI Init Error: {e}")
        else:
            logger.warning("⚠️ DEEPSEEK_API_KEY не найден в конфиге")

    def _smart_split(self, text: str) -> list[str]:
        text = clean_text(text)
        pages = text.split("===PAGE_BREAK===")
        return [p.strip() for p in pages if len(p.strip()) > 20]

    def _get_dates_list(self, days_count: int) -> list[str]:
        today = datetime.date.today()
        dates = []
        months = ['янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек']
        weekdays = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']
        current_date = today 
        step = 1 if days_count > 3 else 2
        
        for _ in range(days_count):
            d_str = f"{current_date.day} {months[current_date.month-1]} ({weekdays[current_date.weekday()]})"
            dates.append(d_str)
            current_date += timedelta(days=step)
        return dates

    # --- 1. АНАЛИЗ ПРОГРЕССА ---
    async def analyze_progress(self, user_data: dict, current_weight: float) -> str:
        if not self.client: return "Ошибка API: Ключ не настроен"
        
        old_weight = user_data.get('weight', current_weight)
        goal = user_data.get('goal', 'Форма')
        diff = current_weight - old_weight

        # Описание цели для AI
        goal_desc = goal
        if goal == 'recomposition':
            goal_desc = "Рекомпозиция (сжигание жира при сохранении/росте мышц, вес может стоять)"

        prompt = f"""
        Ты — опытный фитнес-тренер (не врач, не робот). Твой стиль: краткий, по делу, с мужской поддержкой.
        
        СИТУАЦИЯ:
        Вес клиента изменился: {old_weight} кг -> {current_weight} кг.
        Разница: {diff:.1f} кг.
        Цель клиента: {goal_desc}.

        ТВОЯ ЗАДАЧА:
        1. Оцени результат (хорошо/плохо/нормально).
        2. Дай ОДИН конкретный совет.
        
        ЗАПРЕТЫ:
        - Не отправляй к врачу, если нет угрозы жизни.
        - Не пиши банальщину.
        
        Напиши 2-3 предложения. Используй теги <b> и <i>.
        """
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model, temperature=0.8
            )
            return clean_text(r.choices[0].message.content)
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            return "Тренер записал новый вес."

    # --- 2. ГЕНЕРАЦИЯ ТРЕНИРОВКИ ---
    async def generate_workout_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API: Ключ не настроен"]
        
        level = user_data.get('workout_level', 'Новичок')
        days = user_data.get('workout_days', 3)
        goal = user_data.get('goal', 'maintenance')
        dates_str = ", ".join(self._get_dates_list(days))

        system_prompt = "Ты — TrAIner. Пиши программу, используя HTML теги (b, i)."

        user_prompt = f"""
        СОСТАВЬ ПРОГРАММУ ({level}, Цель: {goal}, {days} дн).
        ДАТЫ ТРЕНИРОВОК: {dates_str}

        ФОРМАТ ДНЯ (Строго):
        📅 <b>[Дата] — [Группа мышц]</b>
        1. <b>[Упражнение]</b>
        <i>[Подходы] x [Повторения]</i>
        Техника: [Очень кратко]

        Раздели дни строкой ===PAGE_BREAK===.
        В конце добавь блок "Советы".
        """
        
        try:
            r = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ], model=self.model, temperature=0.3
            )
            return self._smart_split(r.choices[0].message.content)
        except Exception as e:
            logger.error(f"Workout gen error: {e}")
            return ["❌ Не удалось составить программу."]

    # --- 3. ГЕНЕРАЦИЯ ПИТАНИЯ ---
    async def generate_nutrition_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API: Ключ не настроен"]
        kcal = self._calculate_target_calories(user_data)
        goal = user_data.get('goal', 'maintenance')
        
        prompt = f"""
        Составь рацион на ~{kcal} ккал для цели: {goal}.
        ВАЖНО: НЕ ПИШИ ВСТУПЛЕНИЕ.
        
        ФОРМАТ ВЫВОДА ДЛЯ КАЖДОГО БЛЮДА:
        Вариант X: <b>[Блюдо]</b>
        * [Состав кратко]
        * <b>КБЖУ: ~[ккал] (Б:.., Ж:.., У:..)</b>
        
        СТРУКТУРА МЕНЮ:
        🍳 <b>ЗАВТРАК (3 варианта)</b>
        ===PAGE_BREAK===
        🍲 <b>ОБЕД (3 варианта)</b>
        ===PAGE_BREAK===
        🥗 <b>УЖИН (3 варианта)</b>
        ===PAGE_BREAK===
        🥪 <b>ПЕРЕКУСЫ (3 варианта)</b>
        ===PAGE_BREAK===
        🛒 <b>СПИСОК ПРОДУКТОВ</b>
        """
        
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], 
                model=self.model, temperature=0.4
            )
            return self._smart_split(r.choices[0].message.content)
        except Exception as e:
             logger.error(f"Nutrition gen error: {e}")
             return ["Ошибка генерации."]

    def _calculate_target_calories(self, user_data: dict) -> int:
        try:
            weight = float(user_data.get('weight', 70))
            height = float(user_data.get('height', 170))
            age = int(user_data.get('age', 30))
            goal = user_data.get('goal', 'maintenance')
            
            if user_data.get('gender') == 'male':
                bmr = 10 * weight + 6.25 * height - 5 * age + 5
            else:
                bmr = 10 * weight + 6.25 * height - 5 * age - 161
            
            # Средний коэффициент активности
            total_kcal = int(bmr * 1.375)
            
            # Коррекция под цель
            if goal == 'weight_loss': total_kcal -= 400
            elif goal == 'muscle_gain': total_kcal += 300
            elif goal == 'recomposition': total_kcal -= 150 # Небольшой дефицит для рекомпозиции
            
            return total_kcal
        except: return 2000

    # --- 4. ЧАТ С ТРЕНЕРОМ ---
    async def get_chat_response(self, history: list, user_context: dict) -> str:
        if not self.client: return "Ошибка конфигурации API"
        try:
            system_msg = f"Ты — фитнес-тренер TrAIner. Твой подопечный: {user_context.get('name', 'Атлет')}, цель: {user_context.get('goal', 'Здоровье')}."
            msgs = [{"role": "system", "content": system_msg}] + history[-6:]
            r = await self.client.chat.completions.create(messages=msgs, model=self.model)
            return clean_text(r.choices[0].message.content)
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return "Связь прервалась."