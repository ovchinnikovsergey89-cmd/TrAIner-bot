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

    # --- 1. АНАЛИЗ ПРОГРЕССА (ОБНОВЛЕННЫЙ) ---
    async def analyze_progress(self, user_data: dict, current_weight: float) -> str:
        if not self.client: return "Ошибка API: Ключ не настроен"
        
        old_weight = user_data.get('weight', current_weight)
        goal = user_data.get('goal', 'Форма')
        diff = current_weight - old_weight
        
        # Новый, более дерзкий промпт
        prompt = f"""
        Ты — опытный фитнес-тренер (не врач, не робот). Твой стиль: краткий, по делу, с легким юмором или "мужской" поддержкой.
        
        СИТУАЦИЯ:
        Вес клиента изменился: {old_weight} кг -> {current_weight} кг.
        Разница: {diff:.1f} кг.
        Цель клиента: {goal}.

        ТВОЯ ЗАДАЧА:
        1. Оцени результат (хорошо/плохо/нормально).
        2. Дай ОДИН конкретный совет (про воду, углеводы, сон или тренировки).
        
        ЗАПРЕТЫ:
        - Не отправляй к врачу, если разница меньше 5 кг.
        - Не пиши "консультируйтесь со специалистом".
        - Не пиши банальщину "вы молодец".
        
        Напиши 2-3 предложения. Используй теги <b> и <i>.
        """
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model, temperature=0.8 # Температура повыше для креативности
            )
            return clean_text(r.choices[0].message.content)
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            return "Тренер кивнул и записал вес."

    # --- 2. ГЕНЕРАЦИЯ ТРЕНИРОВКИ ---
    async def generate_workout_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API: Ключ не настроен"]
        
        level = user_data.get('workout_level', 'Новичок')
        days = user_data.get('workout_days', 3)
        dates_str = ", ".join(self._get_dates_list(days))

        system_prompt = "Ты — профессиональный тренер. Пиши программу четко, используя HTML (b, i)."
        user_prompt = f"""
        СОСТАВЬ ПРОГРАММУ ({level}, {user_data.get('goal')}, {days} дн).
        ДАТЫ: {dates_str}
        
        ФОРМАТ ДНЯ:
        📅 <b>[Дата] — [Группа мышц]</b>
        1. <b>[Упражнение]</b>
        <i>[Подходы] x [Повторения]</i>
        Техника: [Кратко]
        (ПУСТАЯ СТРОКА)
        ...
        
        Раздели дни: ===PAGE_BREAK===. В конце блок "Советы".
        """
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], 
                model=self.model, temperature=0.3
            )
            return self._smart_split(r.choices[0].message.content)
        except Exception: return ["❌ Ошибка генерации."]

    # --- 3. ГЕНЕРАЦИЯ ПИТАНИЯ ---
    async def generate_nutrition_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API"]
        kcal = self._calculate_target_calories(user_data)
        
        prompt = f"""
        Рацион на ~{kcal} ккал. Без вступлений.
        ФОРМАТ:
        Вариант X: <b>[Блюдо]</b>
        * [Состав]
        * <b>КБЖУ: ~[ккал]</b>
        
        СТРУКТУРА:
        🍳 <b>ЗАВТРАК (3 варианта)</b> ... ===PAGE_BREAK===
        🍲 <b>ОБЕД (3 варианта)</b> ... ===PAGE_BREAK===
        🥗 <b>УЖИН (3 варианта)</b> ... ===PAGE_BREAK===
        🥪 <b>ПЕРЕКУСЫ</b> ... ===PAGE_BREAK===
        🛒 <b>СПИСОК ПРОДУКТОВ</b>
        """
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], model=self.model, temperature=0.4
            )
            return self._smart_split(r.choices[0].message.content)
        except Exception: return ["Ошибка генерации."]

    def _calculate_target_calories(self, user_data: dict) -> int:
        try:
            w = float(user_data.get('weight', 70))
            h = float(user_data.get('height', 170))
            a = int(user_data.get('age', 30))
            bmr = (10*w + 6.25*h - 5*a + 5) if user_data.get('gender')=='male' else (10*w + 6.25*h - 5*a - 161)
            return int(bmr * 1.375)
        except: return 2000

    # --- 4. ЧАТ ---
    async def get_chat_response(self, history: list, user_context: dict) -> str:
        if not self.client: return "Ошибка API"
        system = f"Ты — тренер TrAIner. Клиент: {user_context.get('name')}. Отвечай кратко, с юмором, как опытный наставник."
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "system", "content": system}] + history[-6:], model=self.model
            )
            return clean_text(r.choices[0].message.content)
        except: return "Связь прервалась."