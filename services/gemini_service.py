import logging
import google.generativeai as genai
from config import Config

class GeminiService:
    """Сервис для работы с Google Gemini (Бесплатно)"""

    def __init__(self):
        self.api_key = Config.GEMINI_API_KEY
        
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                # Используем gemini-1.5-flash (быстрая и креативная)
                self.model = genai.GenerativeModel('gemini-1.5-flash-latest')
                logging.info("✅ Google Gemini сервис инициализирован")
            except Exception as e:
                logging.error(f"❌ Ошибка настройки Gemini: {e}")
                self.model = None
        else:
            logging.warning("⚠️ GEMINI_API_KEY не найден")
            self.model = None

    async def generate_personalized_workout(self, user_data: dict) -> str:
        if not self.model:
            return "⚠️ API ключ Gemini не настроен."

        try:
            # Промпт без жестких рамок "ЗАПРЕЩЕНО", чтобы дать ИИ свободу
            prompt = self._create_friendly_prompt(user_data)
            
            # В библиотеке google вызов синхронный, но быстрый. 
            # Для идеального асинхрона можно обернуть в executor, но пока оставим так для простоты.
            response = self.model.generate_content(prompt)
            
            return response.text
        except Exception as e:
            logging.error(f"❌ Ошибка генерации Gemini: {e}")
            return "Ой, что-то пошло не так при генерации тренировки."

    async def generate_nutrition_advice(self, user_data: dict, calories: int, macros: dict) -> str:
        if not self.model:
            return "⚠️ API ключ не настроен."

        try:
            prompt = f"""
            Привет! Я {user_data.get('gender', 'атлет')}, вес {user_data.get('weight')} кг.
            Моя цель: {user_data.get('goal')}.
            Мои калории: {calories}. БЖУ: {macros}.
            
            Напиши мне классный план питания на день. Не нужно сухих списков.
            Расскажи, что мне съесть на завтрак, обед и ужин, чтобы было вкусно и я вписался в калории.
            Дай пару лайфхаков, как не сорваться. Общайся со мной как опытный друг-диетолог, на "ты".
            """
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logging.error(f"❌ Ошибка питания Gemini: {e}")
            return "Не удалось составить план питания."

    def _create_friendly_prompt(self, user_data: dict) -> str:
        gender_text = "Парень" if user_data.get('gender') == 'male' else "Девушка"
        
        return f"""
        Роль: Ты крутой персональный тренер. Твой стиль — мотивирующий, энергичный, без занудства.
        
        Клиент: {gender_text}, {user_data.get('age')} лет, вес {user_data.get('weight')} кг, рост {user_data.get('height')} см.
        Уровень: {user_data.get('workout_level', 'новичок')}.
        Цель: {user_data.get('goal', 'быть в форме')}.
        Дней для тренировок: {user_data.get('workout_days', 3)}.

        Задача:
        Составь программу тренировок на неделю.
        
        Как писать:
        1. Сначала напиши короткое, заряжающее вступление.
        2. Распиши тренировки по дням. Не просто "Приседания 3x10", а объясни нюансы (например: "Держи спину ровно, пятки не отрывай").
        3. Если вес клиента большой (>90 кг) — деликатно предложи упражнения без прыжков, береги его суставы.
        4. В конце дай совет по восстановлению.
        
        Используй эмодзи, списки и жирный шрифт для акцентов. Сделай так, чтобы мне захотелось пойти тренироваться прямо сейчас!
        """