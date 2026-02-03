import logging
from config import Config

class GroqAITrainerService:
    """ИИ-сервис на базе Groq API"""
    
    def __init__(self):
        self.api_key = Config.GROQ_API_KEY
        self.client = None
        self.model = "llama-3.3-70b-versatile"
        self.use_mock = False
        
        print(f"🔑 Ключ Groq: {self.api_key[:10]}..." if self.api_key else "❌ Ключ не найден")
        
        if self.api_key and self.api_key.startswith("gsk_"):
            try:
                from groq import Groq
                print("✅ Библиотека groq импортирована")
                
                self.client = Groq(api_key=self.api_key)
                print("✅ Клиент Groq создан")
                
                # Тест подключения
                try:
                    test = self.client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": "test"}],
                        max_tokens=1
                    )
                    print(f"✅ Модель {self.model} работает")
                    self.use_mock = False
                except Exception as e:
                    print(f"❌ Модель не работает: {e}")
                    self.use_mock = True
                    
            except ImportError:
                print("❌ Библиотека groq не установлена")
                self.use_mock = True
            except Exception as e:
                print(f"❌ Ошибка подключения: {e}")
                self.use_mock = True
        else:
            print("❌ Ключ невалидный")
            self.use_mock = True
    
    async def generate_personalized_workout(self, user_data: dict) -> str:
        """Генерация персонализированной тренировки"""
        if self.use_mock or not self.client:
            return self._get_mock_workout(user_data)
        
        try:
            prompt = self._create_workout_prompt(user_data)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.9,
                max_tokens=1800
            )
            
            workout_text = response.choices[0].message.content
            return f"🤖 ИИ-ТРЕНИРОВКА\n\n{workout_text}"
            
        except Exception as e:
            print(f"❌ Ошибка генерации: {e}")
            return self._get_mock_workout(user_data)
    
    def _create_workout_prompt(self, user_data: dict) -> str:
        """Создание детального промпта"""
        gender = "мужчина" if user_data.get('gender') == 'male' else "женщина"
        weight = user_data.get('weight', 70)
        goal = user_data.get('goal', 'maintenance')
        
        return f"""
        ВАЖНО: Создай УНИКАЛЬНУЮ программу для КОНКРЕТНЫХ параметров.
        НЕ используй шаблоны. УЧТИ ВСЕ параметры.

        ПАРАМЕТРЫ КЛИЕНТА:
        • Пол: {gender}
        • Вес: {weight} кг ({'ОЧЕНЬ БОЛЬШОЙ ВЕС' if weight > 100 else 'большой вес' if weight > 80 else 'средний вес' if weight > 60 else 'малый вес'})
        • Цель: {goal}
        • Уровень: {user_data.get('workout_level', 'beginner')}
        • Дней: {user_data.get('workout_days', 3)}

        ОБЯЗАТЕЛЬНО:
        1. Для ВЕСА {weight} кг:
           - Упражнения: {'ТОЛЬКО сидя/лежа, НЕТ прыжкам' if weight > 90 else 'минимум ударной нагрузки' if weight > 70 else 'можно больше интенсивных упражнений'}
           - Отдых: {'90-120 сек между подходами' if weight > 90 else '60-90 сек' if weight > 70 else '45-60 сек'}
        
        2. Для ПОЛА {gender}:
           - {'70% верх тела, 30% низ тела' if gender == 'мужчина' else '30% верх тела, 70% низ тела'}
           - {'8-12 повторений для силы' if gender == 'мужчина' else '12-15 повторений для тонуса'}

        3. Для ЦЕЛИ {goal}:
           - Похудение: 60% кардио, 40% силовые
           - Набор массы: 80% силовые, 20% кардио
           - Поддержание: 50/50

        Дай КОНКРЕТНУЮ программу на {user_data.get('workout_days', 3)} дня.
        Для КАЖДОГО упражнения укажи подходы, повторения, отдых.
        Будь максимально конкретным.
        """
    
    async def generate_nutrition_advice(self, user_data: dict, calories: int, macros: dict) -> str:
        """Генерация советов по питанию"""
        if self.use_mock or not self.client:
            return self._get_mock_nutrition_advice(user_data)
        
        try:
            gender = "мужчина" if user_data.get('gender') == 'male' else "женщина"
            weight = user_data.get('weight', 70)
            
            prompt = f"""
            Дай ПЕРСОНАЛИЗИРОВАННЫЕ рекомендации по питанию для:

            • Пол: {gender}
            • Вес: {weight} кг
            • Калории: {calories} ккал/день
            • Белки: {macros.get('protein', 100)}г
            • Жиры: {macros.get('fat', 70)}г
            • Углеводы: {macros.get('carbs', 250)}г

            Учти вес {weight} кг и пол {gender}.
            Дай конкретные примеры блюд и порций.
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=1500
            )
            
            return f"🍎 ИИ-ПИТАНИЕ\n\n{response.choices[0].message.content}"
            
        except Exception as e:
            print(f"❌ Ошибка питания: {e}")
            return self._get_mock_nutrition_advice(user_data)
    
    def _get_mock_workout(self, user_data: dict) -> str:
        """Демо-тренировка"""
        return f"🤖 ДЕМО: Вес={user_data.get('weight', 70)}кг, Пол={user_data.get('gender')}"
    
    def _get_mock_nutrition_advice(self, user_data: dict) -> str:
        """Демо-питание"""
        return f"🍎 ДЕМО: Вес={user_data.get('weight', 70)}кг"