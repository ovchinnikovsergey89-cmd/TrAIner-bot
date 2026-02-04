import logging
import json
import datetime
from datetime import timedelta
from openai import AsyncOpenAI
from config import Config

class GroqService:
    def __init__(self):
        self.api_key = Config.DEEPSEEK_API_KEY
        self.client = None
        # DeepSeek V3 отлично работает с JSON, если попросить
        self.model = "deepseek-chat"
        
        if self.api_key:
            try:
                self.client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url="https://api.deepseek.com"
                )
            except Exception as e:
                logging.error(f"Err init OpenAI: {e}")

    # --- ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ (Вынеси их потом в calculators.py) ---
    def _calculate_target_calories(self, user_data: dict) -> int:
        try:
            weight = float(user_data.get('weight', 70))
            height = float(user_data.get('height', 170))
            age = int(user_data.get('age', 30))
            gender = user_data.get('gender', 'Мужской')
            activity = user_data.get('activity_level', 'Средняя')
            goal = user_data.get('goal', 'maintenance')

            # Миффлин-Сан Жеор
            if 'Муж' in str(gender) or 'Male' in str(gender):
                bmr = 10 * weight + 6.25 * height - 5 * age + 5
            else:
                bmr = 10 * weight + 6.25 * height - 5 * age - 161

            activity_multipliers = {"Сидячий": 1.2, "Малая": 1.375, "Средняя": 1.55, "Высокая": 1.725}
            multiplier = activity_multipliers.get(activity, 1.2)
            
            tdee = bmr * multiplier
            if goal == "weight_loss": target = tdee * 0.85
            elif goal == "muscle_gain": target = tdee * 1.15
            else: target = tdee
            return int(target)
        except: return 2000

    def _calculate_dates(self, days_per_week: int):
        today = datetime.date.today()
        # Если дней 0 или None, ставим 3
        days_per_week = days_per_week if days_per_week else 3
        
        # Простая логика распределения дней пн-ср-пт и т.д.
        offsets = []
        if days_per_week == 1: offsets = [0]
        elif days_per_week == 2: offsets = [0, 2] 
        elif days_per_week == 3: offsets = [0, 2, 4]
        elif days_per_week >= 4: offsets = list(range(days_per_week)) # Подряд
        
        schedule = []
        months = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']
        weekdays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        
        for offset in offsets:
            date = today + timedelta(days=offset)
            schedule.append(f"{date.day} {months[date.month-1]} ({weekdays[date.weekday()]})")
        return schedule

    # --- НОВЫЙ МЕТОД ПАРСИНГА JSON ---
    def _parse_json_response(self, text: str) -> list[str]:
        """Пытается найти JSON в ответе и превратить его в список страниц."""
        try:
            # 1. Очистка от markdown блоков кода ```json ... ```
            text = text.replace("```json", "").replace("```", "").strip()
            
            # 2. Пытаемся найти начало списка '[' и конец ']'
            start = text.find('[')
            end = text.rfind(']')
            if start != -1 and end != -1:
                json_str = text[start:end+1]
                data = json.loads(json_str)
                
                # Если это список строк - отлично
                if isinstance(data, list):
                    # Превращаем каждый элемент в строку (на случай если там объекты)
                    return [str(item) for item in data]
            
            # Если JSON не нашелся, возвращаем текст как есть (fallback)
            logging.warning("JSON не найден, возвращаю сырой текст")
            return [text]
        except Exception as e:
            logging.error(f"Ошибка парсинга JSON: {e}")
            return [text]

    # --- ГЕНЕРАЦИЯ ПИТАНИЯ (АПГРЕЙД) ---
    async def generate_nutrition_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API Key"]
        
        target_calories = self._calculate_target_calories(user_data)
        
        # ПРОМПТ JSON
        # Мы просим вернуть массив строк ["Меню 1...", "Меню 2..."]
        prompt = f"""
        Роль: Профессиональный диетолог.
        Клиент: вес {user_data.get('weight')}кг, цель: {user_data.get('goal')}.
        Задача: Составь 3 разных варианта дневного рациона на {target_calories} ккал.

        ФОРМАТ ОТВЕТА СТРОГО JSON LIST OF STRINGS:
        [
          "🍽 <b>Вариант 1: Белковый</b>\\n\\n<b>Завтрак:</b>...\\n<b>Обед:</b>...",
          "🍽 <b>Вариант 2: Сбалансированный</b>\\n\\n<b>Завтрак:</b>...\\n<b>Обед:</b>...",
          "🍽 <b>Вариант 3: Легкий</b>\\n\\n<b>Завтрак:</b>...\\n<b>Обед:</b>..."
        ]
        
        Используй HTML теги <b> для жирного текста. Не используй Markdown (**).
        """
        
        try:
            resp = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], 
                model=self.model,
                temperature=0.7
            )
            content = resp.choices[0].message.content
            return self._parse_json_response(content)
        except Exception as e:
            logging.error(f"AI Error: {e}")
            return ["❌ Ошибка генерации питания. Попробуйте позже."]

    # --- ГЕНЕРАЦИЯ ТРЕНИРОВОК (АПГРЕЙД) ---
    async def generate_workout_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API Key"]
        
        days_count = user_data.get('workout_days', 3)
        dates = self._calculate_dates(days_count)
        dates_str = ", ".join(dates)
        
        prompt = f"""
        Роль: Фитнес-тренер.
        Клиент: {user_data.get('gender')}, уровень: {user_data.get('workout_level')}.
        Дни тренировок: {dates_str}.
        
        Задача: Составь программу тренировок для каждого из перечисленных дней.
        
        ФОРМАТ ОТВЕТА СТРОГО JSON LIST OF STRINGS. В списке должно быть ровно {len(dates)} элемента(ов).
        Пример:
        [
          "📅 <b>{dates[0] if dates else 'День 1'}</b>\\n\\n1. <b>Разминка:</b> 5 мин...\\n2. <b>Приседания:</b> 3х15...",
          "📅 <b>{dates[1] if len(dates)>1 else 'День 2'}</b>\\n\\n..."
        ]
        
        Используй HTML теги <b> для жирного текста.
        """

        try:
            resp = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], 
                model=self.model,
                temperature=0.6
            )
            content = resp.choices[0].message.content
            return self._parse_json_response(content)
        except Exception as e:
            logging.error(f"AI Error: {e}")
            return ["❌ Ошибка генерации тренировок."]

    # Чат оставляем пока как есть, там JSON не нужен, но clean_response пригодится
    async def get_chat_response(self, history: list, context: dict) -> str:
        if not self.client: return "Ошибка API"
        sys_prompt = {"role":"system", "content": "Ты тренер. Отвечай кратко, используй HTML теги <b> для выделения."}
        try:
            # Берем последние 6 сообщений для контекста
            messages = [sys_prompt] + history[-6:]
            r = await self.client.chat.completions.create(messages=messages, model=self.model)
            return r.choices[0].message.content.strip()
        except: return "Ошибка соединения с мозгом 🧠"