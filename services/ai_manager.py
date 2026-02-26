from groq import AsyncGroq
from config import Config
import io
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
    Отвечает за генерацию тренировок, питания и анализ прогресса.
    """
    def __init__(self):
        self.api_key = Config.DEEPSEEK_API_KEY
        self.client = None
        self.model = "deepseek-chat"
        
        if self.api_key:
            try:
                from openai import AsyncOpenAI
                self.client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url="https://api.deepseek.com"
                )
            except Exception as e:
                import logging
                logging.error(f"AI Generation Error: {e}")
                # Возвращаем понятную ошибку вместо падения
                return ["❌ <b>Сервер тренера перегружен.</b>\n\nПожалуйста, попробуй еще раз через минуту."]
    # --- ТЕХНИЧЕСКИЙ МЕТОД: РАЗДЕЛЕНИЕ НА СТРАНИЦЫ ---
    def _smart_split(self, text: str) -> list[str]:
        # Очищаем текст общим чистильщиком
        text = clean_text(text)
        
        # Разрезаем текст по нашему тегу
        pages = text.split("===PAGE_BREAK===")
        
        # Убираем пустые куски и лишние пробелы
        final_pages = [p.strip() for p in pages if len(p.strip()) > 5]
        
        # Если вдруг ИИ не прислал тег, возвращаем весь текст одной страницей
        return final_pages if final_pages else [text]
    
    # --- 1. АНАЛИЗ ПРОГРЕССА ---
    # ВАЖНО: Добавлен аргумент workouts_count=0
    async def analyze_progress(self, user_data: dict, current_weight: float, workouts_count: int = 0) -> str:
        if not self.client: return "Ошибка API: Ключ не настроен"
        
        old_weight = user_data.get('weight', current_weight)
        goal = user_data.get('goal', 'maintenance')
        name = user_data.get('name', 'Атлет')
        plan_days = user_data.get('workout_days', 3)
        diff = current_weight - old_weight
        
        prompt = f"""
        Ты — элитный фитнес-коуч. Проанализируй прогресс клиента {name}.
        
        ДАННЫЕ:
        - Вес: {old_weight} кг -> {current_weight} кг (Разница: {diff:.1f} кг). 
        - Цель: {goal}.
        - План тренировок: {plan_days} раз в неделю.
        - Выполнено тренировок: {workouts_count}.

        ТВОЯ ЗАДАЧА: Дай краткий анализ динамики.
        
        СТРОГИЙ ФОРМАТ ОТВЕТА (HTML):
        1. Первая строка: Эмодзи + вердикт.
        2. Вторая строка: ОБЯЗАТЕЛЬНО ПУСТАЯ СТРОКА.
        3. Третья строка: <b>Анализ:</b> (Свяжи вес и активность).
        4. Четвертая строка: <b>Рекомендация:</b> (Один совет).
        """
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model, temperature=0.7,
                timeout=90.0
            )
            from utils.text_tools import clean_text
            return clean_text(r.choices[0].message.content)
        except Exception: 
            return "📈 <b>Данные обновлены!</b>\n\nТренер зафиксировал новый вес и активность."

    # ... (остальные методы: generate_workout_pages и т.д.)

    # --- 2. ГЕНЕРАЦИЯ ТРЕНИРОВКИ ---
    async def generate_workout_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API"]
        
        level = user_data.get('workout_level', 'beginner')
        days_per_week = user_data.get('workout_days', 3)
        goal = user_data.get('goal', 'maintenance')
        
        now = datetime.datetime.now()
        weekdays_ru = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
        today_name = weekdays_ru[now.weekday()]
        today_date = now.strftime("%d.%m")
        wishes = user_data.get('wishes', 'Нет особых пожеланий.')

        user_prompt = f"""
        СОСТАВЬ ПЕРСОНАЛЬНЫЙ ПЛАН ТРЕНИРОВОК.
        
        АНКЕТА КЛИЕНТА:
        - Имя: {user_data.get('name')}
        - Пол: {user_data.get('gender')}
        - Возраст: {user_data.get('age')} лет
        - Вес: {user_data.get('weight')} кг
        - Рост: {user_data.get('height')} см
        - Цель: {goal}
        - Уровень подготовки: {level}
        - График: {days_per_week} тренировок в неделю
        - Пожелания: {user_data.get('wishes')}

        ТВОЯ РОЛЬ: Ты — топовый эксперт-тренер. Твоя задача — составить программу, которая учитывает ИМТ и возраст клиента без лишних слов.

        ЛОГИКА ИНДИВИДУАЛЬНОСТИ:
        1. Если вес большой (ИМТ > 28) — ЗАПРЕЩЕНЫ прыжки и осевые нагрузки. Пиши: "Бережем суставы: выполняй плавно".
        2. Если клиент — новичок — акцент на нейромышечную связь. В технике пиши: "Почувствуй, как работает целевая мышца".
        3. Если цель — набор массы — в каждом упражнении пиши про "Прогрессию весов".
        4. Если возраст 40+ — добавь больше внимания разминке и контролю давления.
        5. Всегда строго придерживайся локации и условий, указанных в истории пожеланий. Если первая тренировка была на улице, все последующие изменения тоже должны быть для улицы, если не указано иное.
        
        МЕТОДОЛОГИЯ РАСПРЕДЕЛЕНИЯ (Выбери подходящую под {days_per_week} дн.):
        - 1 день: Full Body (база на всё тело).
        - 2 дня: Upper/Lower (Верх / Низ).
        - 3 дня: Classic Push/Pull/Legs (Жим / Тяга / Ноги).
        - 4 дня: Upper/Lower Split (2 раза Верх + 2 раза Низ).
        - 5 дней: Bro-Split (одна группа мышц в день).
        - 6 дней: Push/Pull/Legs (2 полных круга).
        - 7 дней: 5-6 силовых + активное восстановление (LISS/растяжка).

        ЗАДАЧА: Создай программу на СЕМЬ ДНЕЙ (недельный цикл), которая строго учитывает физические данные. 
        Из них должно быть ровно {days_per_week} тренировочных дней и {7 - days_per_week} дня отдыха.
        Распредели их логично (например, не ставь 4 тяжелых дня подряд).
        Распредели тренировки, начиная с СЕГОДНЯ ({today_name} {today_date}) 
        
        СТРОГИЕ ПРАВИЛА ОФОРМЛЕНИЯ:
        1. СРАЗУ начинай с программы тренировок по дням.
        2. Формат заголовка для отдыха: 📅 <b>[Дата], День [Номер] ([День недели]) — ВОССТАНОВЛЕНИЕ</b>
        3. Между упражнениями ОБЯЗАТЕЛЬНО ПУСТАЯ СТРОКА.
        4. ЗАПРЕЩЕНО писать вступление, анализ ИМТ, расчеты калорий или принципы плана в самом начале.
        5. СРАЗУ начинай с программы тренировок по дням.
        6. Формат упражнения:
        <b>[Номер]. [Название]</b>
        <i>[Сеты] х [Повторы] (Отдых [сек])</i>
        Техника: [Короткий совет]
        7. 4. В дни ВОССТАНОВЛЕНИЯ: вместо упражнений дай 1-2 конкретных совета по активности (например: находить 10 000 шагов, сделать легкое кардио, растяжку, МФР или поплавать в бассейне).
        8. В САМОМ КОНЦЕ (на последней странице после всех дней) добавь блок "💡 Советы тренера".
        9. В советах ОЧЕНЬ КРАТКО (3-4 пункта) укажи рекомендации по питанию и технике, основываясь на данных клиента. заместо "*" ставь "-"
        
        Разделяй дни СТРОГО тегом: ===PAGE_BREAK===
        """
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": user_prompt}], 
                model=self.model, temperature=0.3,
                timeout=90.0
            )
            return self._smart_split(r.choices[0].message.content)
        except Exception:
            return ["❌ Ошибка при составлении программы."]
        
    # --- НОВОЕ: ГЕНЕРАЦИЯ РАЗОВОЙ ТРЕНИРОВКИ ---
    async def generate_single_workout(self, user_data: dict) -> str:
        if not self.client: return "❌ Ошибка API"
        
        level = user_data.get('workout_level', 'beginner')
        goal = user_data.get('goal', 'maintenance')
        wishes = user_data.get('wishes', 'Стандартная тренировка')

        user_prompt = f"""
        СОСТАВЬ ОДНУ РАЗОВУЮ ТРЕНИРОВКУ.
        
        АНКЕТА: Имя: {user_data.get('name')}, Пол: {user_data.get('gender')}, Возраст: {user_data.get('age')}, Вес: {user_data.get('weight')} кг, Цель: {goal}, Уровень: {level}.
        УСЛОВИЯ/ПОЖЕЛАНИЯ СЕГОДНЯ: {wishes}

        ЗАДАЧА: Напиши одну конкретную тренировку, строго подстроенную под пожелания клиента (инвентарь, время, ограничения).
        
        СТРОГИЕ ПРАВИЛА:
        1. Сразу начинай с программы. Никаких "Привет, вот твоя тренировка".
        2. Формат:
        <b>[Номер]. [Название]</b>
        <i>[Сеты] х [Повторы] (Отдых [сек])</i>
        Техника: [Короткий совет]
        3. В конце дай один мотивирующий совет.
        """
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": user_prompt}], 
                model=self.model, temperature=0.5,
                timeout=60.0
            )
            return r.choices[0].message.content
        except Exception:
            return "❌ Ошибка при составлении тренировки."    

    # --- 3. ГЕНЕРАЦИЯ ПИТАНИЯ (3 ВАРИАНТА + ПЕРЕКУСЫ + СПИСОК) ---
    async def generate_nutrition_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API"]
        goal = user_data.get('goal', 'maintenance')
        # Достаем пожелания (если их нет, будет 'Нет')
        wishes = user_data.get('wishes', 'Нет особых предпочтений')
        
        prompt = f"""
        Ты — профессиональный фитнес-диетолог. Твоя задача — рассчитать КБЖУ и составить рацион. 
        
        ДАННЫЕ КЛИЕНТА: 
        - Вес: {user_data.get('weight')} кг, Рост: {user_data.get('height')} см
        - Возраст: {user_data.get('age')} лет, Пол: {user_data.get('gender')}
        - Цель: {goal}
        - Пожелания/Ограничения: {wishes}

        ЗАДАЧА:
        1. На основе веса и пожеланий (например, если просят 2.2г белка на кг веса — рассчитай строго так) РАССЧИТАЙ суточную норму калорий и диапазоны БЖУ.
        2. Составь меню на день: Завтрак, Обед, Ужин, Перекусы. В каждом блоке предложи по 3 варианта.

        СТРОЖАЙШЕЕ ПРАВИЛО ОФОРМЛЕНИЯ КАЖДОЙ СТРАНИЦЫ:
        Каждая страница (каждый блок приема пищи) ОБЯЗАТЕЛЬНО должна начинаться с этого заголовка:
        <b>Твой КБЖУ ~[Число] ккал (Б: [мин]-[макс], Ж: [мин]-[макс], У: [мин]-[макс])</b>
        
        ИНДИВИДУАЛЬНАЯ СТРАТЕГИЯ:
        1. Если вес выше нормы — делай упор на продукты с низким гликемическим индексом.
        
        ТРЕБОВАНИЯ К КОНТЕНТУ:
        1. Для КАЖДОГО блока (Завтрак, Обед, Ужин, Перекусы) предоставь ровно 3 РАЗНЫХ варианта на выбор.
        2. Указывай точные ингредиенты в граммах и КБЖУ для каждого варианта.
        3. В конце добавь расширенный список продуктов на неделю (Shopping List).
        
        СТРОГИЕ ПРАВИЛА ОФОРМЛЕНИЯ:
        1. Между вариантами блюд (включая ПЕРЕКУСЫ) ОБЯЗАТЕЛЬНО делай ПУСТУЮ СТРОКУ для читабельности.
        2. Используй HTML (<b>, <i>). Без вступлений.
        3. Разделяй блоки (Завтрак, Обед, Ужин, Перекусы, Список покупок) СТРОГО тегом: ===PAGE_BREAK===
        4. Пишешь: (<i> Твой КБЖУ 
        5. - После заголовка КБЖУ на каждой странице идет (отспуп строки) далее, название приема пищи (например, 🍳 ЗАВТРАК) и далее 3 варианта.

        ФОРМАТ ВАРИАНТА:
        Вариант X: <b>[Название]</b>
        - [Ингредиенты с весом]
        - <b>КБЖУ: ~[ккал] (Б:..г, Ж:..г, У:..г)</b>
        - Разделяй приемы пищи тегом ===PAGE_BREAK===.
        """
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], 
                model=self.model, temperature=0.4,
                timeout=90.0
            )
            return self._smart_split(r.choices[0].message.content)
        except Exception:
            return ["❌ Ошибка генерации рациона."]

    # --- 4. РАСЧЕТ КАЛОРИЙ ---
    def _calculate_target_calories(self, user_data: dict) -> int:
        try:
            w = float(user_data.get('weight', 70))
            h = float(user_data.get('height', 170))
            a = int(user_data.get('age', 30))
            gender = user_data.get('gender', 'male')
            goal = user_data.get('goal', 'maintenance')

            if gender == 'male':
                bmr = 10 * w + 6.25 * h - 5 * a + 5
            else:
                bmr = 10 * w + 6.25 * h - 5 * a - 161
            
            target = int(bmr * 1.375)

            if goal == 'weight_loss': target -= 400
            elif goal == 'muscle_gain': target += 300
            elif goal == 'recomposition': target -= 150
            
            return max(target, 1200) 
        except Exception: 
            return 2000

    # --- 5. ЧАТ С ТРЕНЕРОМ ---
    async def get_chat_response(self, history: list, user_context: dict) -> str:
        if not self.client: return "Ошибка: API не настроен"
        
        name = user_context.get('name', 'атлет')
        goal = user_context.get('goal', 'фитнес')
        
        # Упрощаем промпт до предела, чтобы ИИ не боялся отвечать
        system_prompt = (
            f"Ты — тренер TrAIner. Твой клиент: {name}, цель: {goal}. "
            "Отвечай на ВСЕ вопросы. Если спрашивают про боль — дай совет по отдыху. "
            "Если спрашивают 'работаем?' — предлагай тренировку. "
            "НЕ используй символы #, *, _ и сложные теги. Пиши простым текстом."
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system_prompt}] + history[-6:],
                temperature=0.7,
                timeout=60.0 # Ждем до минуты
            )
            
            result = response.choices[0].message.content
            if not result:
                return "Я тут, готов к работе! О чем хочешь поговорить?"
            
            # Очищаем текст от Markdown-звездочек, которые ломают Telegram
            result = result.replace("*", "").replace("#", "")
            return result
        except Exception as e:
            logger.error(f"DeepSeek Error: {e}")
            return f"Ошибка связи с ИИ: {str(e)}"
        
    # --- НОВОЕ: РАСПОЗНАВАНИЕ ГОЛОСА (STT) ---
    async def transcribe_voice(self, voice_bytes: io.BytesIO) -> str:
        try:
            # Используем Groq для сверхбыстрого распознавания речи
            groq_client = AsyncGroq(api_key=Config.GROQ_API_KEY)
            
            # Whisper требует, чтобы у файла было имя с расширением
            voice_bytes.name = "voice.ogg" 
            
            transcription = await groq_client.audio.transcriptions.create(
                file=voice_bytes,
                model="whisper-large-v3",
                language="ru", # Подсказываем, что язык русский
                response_format="json"
            )
            return transcription.text
        except Exception as e:
            print(f"Ошибка распознавания голоса: {e}")
            return ""    