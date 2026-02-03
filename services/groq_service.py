import logging
import datetime
import re
from datetime import timedelta
from openai import AsyncOpenAI
from config import Config

class GroqService:
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
                logging.error(f"Err: {e}")

    # --- МАТЕМАТИКА ---
    def _calculate_target_calories(self, user_data: dict) -> int:
        try:
            weight = float(user_data.get('weight', 70))
            height = float(user_data.get('height', 170))
            age = int(user_data.get('age', 30))
            gender = user_data.get('gender', 'Мужской')
            activity = user_data.get('activity_level', 'Средняя')
            goal = user_data.get('goal', 'maintenance')

            if 'Муж' in gender or 'Male' in gender:
                bmr = 10 * weight + 6.25 * height - 5 * age + 5
            else:
                bmr = 10 * weight + 6.25 * height - 5 * age - 161

            activity_multipliers = {"Сидячий": 1.2, "Малая": 1.375, "Средняя": 1.55, "Высокая": 1.725}
            multiplier = 1.2
            for key, val in activity_multipliers.items():
                if key in str(activity): multiplier = val; break
            
            tdee = bmr * multiplier
            if goal == "weight_loss": target = tdee * 0.85
            elif goal == "muscle_gain": target = tdee * 1.15
            else: target = tdee
            return int(target)
        except: return 2000

    # --- ДАТЫ ---
    def _calculate_dates(self, days_per_week: int):
        today = datetime.date.today()
        start_date = today 
        schedule = []
        if days_per_week == 1: offsets = [0]
        elif days_per_week == 2: offsets = [0, 3]
        elif days_per_week == 3: offsets = [0, 2, 4]
        elif days_per_week == 4: offsets = [0, 1, 3, 4]
        elif days_per_week == 5: offsets = [0, 1, 2, 3, 4]
        else: offsets = list(range(days_per_week))
        
        months = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']
        weekdays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        for offset in offsets:
            date = start_date + timedelta(days=offset)
            schedule.append(f"{date.day} {months[date.month-1]} ({weekdays[date.weekday()]})")
        return schedule

    # --- ОЧИСТКА ---
    def _clean_response(self, text: str) -> str:
        if not text: return ""
        # 1. Удаляем мысли модели <think>
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        # 2. Удаляем блоки кода
        text = re.sub(r'^```html', '', text, flags=re.MULTILINE)
        text = re.sub(r'^```', '', text, flags=re.MULTILINE)
        # 3. HTML фиксы
        text = text.replace("<br>", "\n").replace("<p>", "").replace("</p>", "\n")
        # 4. Markdown жирный -> HTML
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        return text.strip()

    # --- ГЛАВНАЯ ФУНКЦИЯ РАЗРЕЗАНИЯ ---
    def _smart_split(self, text: str) -> list[str]:
        """
        Режет текст гарантированно.
        Использует смайлики как маркеры начала страницы.
        """
        text = self._clean_response(text)

        # 1. Если есть явный разделитель - используем его (если AI послушный)
        if "###SPLIT###" in text:
            pages = text.split("###SPLIT###")
        else:
            # 2. Если разделителя нет - режем по смайликам (📅 или 🍽)
            # Регулярка ищет позицию ПЕРЕД смайликом и режет там
            # (?=...) означает "смотреть вперед, но не удалять сам разделитель"
            pages = re.split(r'(?=\n(?:📅|🍽))', text)
            
            # Если регулярка не сработала (например, нет переноса строки перед смайлом)
            if len(pages) < 2:
                pages = re.split(r'(?=📅|🍽)', text)

        # 3. Фильтрация и очистка мусора
        valid_pages = []
        for p in pages:
            clean_p = p.strip()
            # Страница должна быть длиннее 20 символов и содержать контент
            if len(clean_p) > 20:
                # Дополнительная защита от вступлений:
                # Если страница не начинается с даты/тарелки и не содержит упражнений - выкидываем
                if not (("📅" in clean_p) or ("🍽" in clean_p)):
                    continue 
                valid_pages.append(clean_p)
                
        # Если вдруг фильтр удалил всё (такое бывает редко), возвращаем оригинал
        if not valid_pages:
            return [text]
            
        return valid_pages

    # --- ГЕНЕРАЦИЯ ---
    async def generate_workout_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API"]
        days = user_data.get('workout_days', 3)
        dates = ", ".join(self._calculate_dates(days))
        
        # Промпт упрощен, чтобы не путать AI сложными инструкциями
        prompt = f"""
        Роль: Тренер. Клиент: {user_data.get('gender')}, {user_data.get('weight')}кг. Цель: {user_data.get('goal')}.
        Даты: {dates}.
        Задача: Напиши программу.
        
        ФОРМАТ СТРОГО:
        Каждый день начинай с новой строки со смайла 📅.
        📅 <b>Дата: Название</b>
        1. Упражнение...
        """
        try:
            resp = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], model=self.model, temperature=0.6
            )
            return self._smart_split(resp.choices[0].message.content)
        except Exception as e: return [f"Ошибка: {e}"]

    async def generate_nutrition_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API"]
        target_calories = self._calculate_target_calories(user_data)
        goal_ru = "ПОХУДЕНИЯ" if user_data.get('goal') == "weight_loss" else "МАССЫ"
        
        prompt = f"""
        Роль: Диетолог. Клиент: {user_data.get('weight')}кг.
        Задача: 3 меню на {target_calories} ККАЛ.
        
        ФОРМАТ СТРОГО:
        Каждый вариант начинай с новой строки со смайла 🍽.
        🍽 <b>Меню (Вариант X)</b>
        Завтрак...
        """
        try:
            resp = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], model=self.model, temperature=0.7
            )
            return self._smart_split(resp.choices[0].message.content)
        except Exception as e: return [f"Ошибка: {e}"]

    # (Остальные методы analysis и chat оставляем, они работают нормально)
    async def analyze_progress(self, user_data: dict, cw: float) -> str:
        if not self.client: return "Err"
        prompt = f"Клиент {user_data.get('weight')}->{cw}. Цель {user_data.get('goal')}. Комментарий."
        try:
            r = await self.client.chat.completions.create(messages=[{"role":"user","content":prompt}], model=self.model)
            return self._clean_response(r.choices[0].message.content)
        except: return "Ошибка"

    async def get_chat_response(self, h: list, c: dict) -> str:
        if not self.client: return "Err"
        # ... (Код чата тот же, что и был, он работает) ...
        # Для краткости не дублирую огромный промпт, если он у тебя есть - оставь.
        # Главное - верни _clean_response в конце
        sys_p = {"role":"system", "content": f"Ты тренер. Ккал: {self._calculate_target_calories(c)}. Не используй <br>."}
        try:
            r = await self.client.chat.completions.create(messages=[sys_p]+h[-6:], model=self.model)
            return self._clean_response(r.choices[0].message.content)
        except: return "Ошибка"