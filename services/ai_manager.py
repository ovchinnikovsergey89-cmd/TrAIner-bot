import io
import os
import logging
import datetime
import re
from datetime import timedelta
import asyncio
from aiogram.enums import ChatAction
from openai import AsyncOpenAI
from config import Config
from utils.text_tools import clean_text

# --- НОВОЕ: ИМПОРТИРУЕМ ЛОКАЛЬНЫЙ WHISPER ---
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

# 🔥 ГЛОБАЛЬНАЯ ПЕРЕМЕННАЯ: Загружаем модель ОДИН РАЗ при старте.
# compute_type="int8" сильно снизит нагрузку на процессор и оперативку VDS!
try:
    whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
except Exception as e:
    logger.error(f"Не удалось загрузить Whisper: {e}")
    whisper_model = None

class AIManager:
    """
    Единый менеджер для работы с AI.
    Отвечает за генерацию тренировок, питания, анализ прогресса и распознавание голоса.
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
                logger.error(f"AI Generation Error: {e}")
                self.client = None

    # --- ТЕХНИЧЕСКИЙ МЕТОД: РАЗДЕЛЕНИЕ НА СТРАНИЦЫ ---
    def _smart_split(self, text: str) -> list[str]:
        text = clean_text(text)
        pages = text.split("===PAGE_BREAK===")
        final_pages = [p.strip() for p in pages if len(p.strip()) > 5]
        return final_pages if final_pages else [text]
    
    # --- 1. АНАЛИЗ ПРОГРЕССА ---
    async def analyze_progress(self, user_data: dict, current_weight: float, workouts_count: int = 0) -> str:
        if not self.client: return "Ошибка API: Ключ не настроен"
        
        old_weight = user_data.get('weight', current_weight)
        goal = user_data.get('goal', 'maintenance')
        name = user_data.get('name', 'Атлет')
        plan_days = user_data.get('workout_days', 3)
        diff = current_weight - old_weight
        
        prompt = f"""
        Ты — элитный фитнес-тренер бота TrAIner. Проанализируй прогресс клиента {name}.
        ДАННЫЕ: Вес: {old_weight} кг -> {current_weight} кг (Разница: {diff:.1f} кг). Цель: {goal}.
        План тренировок: {plan_days} раз в неделю. Выполнено тренировок: {workouts_count}.
        ТВОЯ ЗАДАЧА: Дай краткий анализ динамики. СТРОГО не используй слово "Вердикт".
        СТРОГИЙ ФОРМАТ ОТВЕТА (HTML):
        1. Первая строка: Эмодзи + краткая суть.
        2. Вторая строка: ОБЯЗАТЕЛЬНО ПУСТАЯ СТРОКА.
        3. Третья строка: <b>Анализ:</b> (Свяжи вес и активность).
        4. Четвертая строка: <b>Рекомендация:</b> (Один совет).
        """
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model, temperature=0.7, timeout=90.0
            )
            return clean_text(r.choices[0].message.content)
        except Exception: 
            return "📈 <b>Данные обновлены!</b>\n\nТренер зафиксировал новый вес и активность."

    # --- 1.5. МГНОВЕННЫЙ АНАЛИЗ КАТЕГОРИЙ (ТРЕНИРОВКИ / ПИТАНИЕ) ---
    async def analyze_category(self, user_data: dict, category: str, data_text: str) -> str:
        if not self.client: return "❌ Ошибка API: Ключ не настроен"
        
        goal = user_data.get('goal', 'фитнес')
        name = user_data.get('name', 'Атлет')
        weight = user_data.get('weight', 'неизвестен')

        if category == "workouts":
            prompt = (f"Ты элитный фитнес-тренер бота TrAIner. Оцени недавние тренировки клиента {name}.\n"
                      f"Цель: {goal}. Вес: {weight} кг.\n"
                      f"Данные из дневника:\n{data_text}\n\n"
                      f"Дай профессиональный, мотивирующий совет по рабочим весам и частоте. "
                      f"Пиши сразу по делу, структурированно, без общих фраз.")
        else:
            prompt = (f"Ты фитнес-нутрициолог бота TrAIner. Оцени рацион клиента {name} за последние 7 дней.\n"
                      f"Цель: {goal}. Текущий вес: {weight} кг.\n"
                      f"Сводка КБЖУ по дням:\n{data_text}\n\n"
                      f"Дай профессиональный анализ рациона. "
                      f"Пиши сразу по делу, структурированно, укажи на перекосы (если есть).")

        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model, temperature=0.6, timeout=60.0
            )
            return clean_text(r.choices[0].message.content)
        except Exception as e:
            logger.error(f"Category analysis error: {e}")
            return "❌ Тренер временно не может составить отчет из-за нагрузки на сервер. Попробуй позже."

    # --- 2. ГЕНЕРАЦИЯ ТРЕНИРОВКИ ---
    async def generate_workout_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API"]
        
        level = user_data.get('workout_level', 'beginner')
        days_per_week = user_data.get('workout_days', 3)
        goal = user_data.get('goal', 'maintenance')
        
        # --- НОВОЕ: ДОСТАЕМ ИСТОРИЮ ---
        past_programs = user_data.get('past_programs', '')
        
        now = datetime.datetime.now()
        weekdays_ru = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
        today_name = weekdays_ru[now.weekday()]
        today_date = now.strftime("%d.%m")
        wishes = user_data.get('wishes', 'Нет особых пожеланий.')

        # Базовая анкета
        user_prompt = f"""
        СОСТАВЬ ПЕРСОНАЛЬНЫЙ ПЛАН ТРЕНИРОВОК.
        АНКЕТА КЛИЕНТА: Имя: {user_data.get('name')}, Пол: {user_data.get('gender')}, Возраст: {user_data.get('age')} лет, Вес: {user_data.get('weight')} кг, Рост: {user_data.get('height')} см, Цель: {goal}, Уровень: {level}, График: {days_per_week} тр/нед, Пожелания: {wishes}
        """

        # --- НОВОЕ: БЛОК ПАМЯТИ (ПЕРИОДИЗАЦИЯ) ---
        if past_programs:
            user_prompt += f"""
        ⚠️ ИСТОРИЯ ПРОШЛЫХ ПРОГРАММ (архив за прошлые недели):
        {past_programs}
        
        ЗАДАЧА ПО ПЕРИОДИЗАЦИИ (КРИТИЧЕСКИ ВАЖНО):
        Выше представлен архив из нескольких прошлых программ клиента. 
        Твоя задача — составить АБСОЛЮТНО НОВУЮ программу.
        1. СТРОГО запрещено выдавать точно такую же структуру, как в последней программе!
        2. Проанализируй историю: если клиент несколько недель подряд делал одни и те же базовые движения (например, классический жим лежа или присед), ОБЯЗАТЕЛЬНО замени их на аналоги (жим гантелей, жим под углом, жим ногами, выпады).
        3. Измени сплит, диапазоны повторений или методы интенсификации (добавь суперсеты или дропсеты, если позволяет уровень), чтобы избежать плато.
        САМОЕ ГЛАВНОЕ! Учитывай пожелания на сегодня: {wishes}
        """

        # Правила оформления (остались без изменений)
        user_prompt += f"""
        ЛОГИКА ИНДИВИДУАЛЬНОСТИ:
        1. ЗАПРЕЩЕНО вычислять или упоминать ИМТ (индекс массы тела). При объективно большом весе минимизируй прыжки и ударную нагрузку.
        2. Новичок — акцент на нейромышечную связь.
        3. Набор массы — "Прогрессия весов".
        4. 40+ лет — разминка и контроль давления.
        5. Строго придерживайся локации из пожеланий.
          
        
        ЗАДАЧА: Создай программу на СЕМЬ ДНЕЙ. Ровно {days_per_week} тренировочных дней.
        Начиная с СЕГОДНЯ ({today_name} {today_date}).
        
        СТРОГИЕ ПРАВИЛА ОФОРМЛЕНИЯ:
        1. Всегда пиши названия упражнений, используя HTML-тег <code>название</code>, чтобы пользователь мог их скопировать.
        2. СРАЗУ начинай с программы по дням. Формат отдыха: 📅 <b>[Дата], День [Номер] ([День недели]) — ВОССТАНОВЛЕНИЕ</b>
        3. После каждого упражнения отступ строки.
        4. Формат упражнения (строго оберни название в тег code для копирования по клику):
        <b>[Номер].</b> <code>[Название]</code>
        <i>[Сеты] х [Повторы] (Отдых [сек])</i>
        Техника: [Короткий совет]
        5. В дни ВОССТАНОВЛЕНИЯ: 1-2 совета по активности.
        6. В САМОМ КОНЦЕ добавь "💡 Советы тренера" (3-4 пункта).
        Разделяй дни СТРОГО тегом: ===PAGE_BREAK===
        """
        
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": user_prompt}], 
                model=self.model, temperature=0.65, timeout=90.0
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
        АНКЕТА: Имя: {user_data.get('name')}, Вес: {user_data.get('weight')} кг, Цель: {goal}, Уровень: {level}.
        САМОЕ ГЛАВНЫЕ УСЛОВИЯ СЕГОДНЯ: {wishes}

        Формат (строго оберни название в тег code для копирования по клику):
        <b>[Номер].</b> <code>[Название]</code>
        <i>[Сеты] х [Повторы] (Отдых [сек])</i>
        Техника: [Короткий совет]
        """
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": user_prompt}], 
                model=self.model, temperature=0.5, timeout=60.0
            )
            return r.choices[0].message.content
        except Exception:
            return "❌ Ошибка при составлении тренировки."    

    # --- 3. ГЕНЕРАЦИЯ ПИТАНИЯ (С РЕЖИМОМ РЕДАКТИРОВАНИЯ И ПАМЯТЬЮ!) ---
    async def generate_nutrition_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API"]
        goal = user_data.get('goal', 'maintenance')
        wishes = user_data.get('wishes', 'Нет особых предпочтений')
        
        # Получаем старый план, если он есть (берем из БД)
        prev_plan = user_data.get('current_nutrition_program', user_data.get('previous_plan', ''))
        
        # --- НОВОЕ: ДОСТАЕМ ИСТОРИЮ ИЗ БД ---
        past_programs = user_data.get('past_programs', '')
        
        # Проверяем, это создание с нуля или запрос на изменение старого меню (длина пожелания > 3 символов)
        is_edit_mode = bool(prev_plan) and len(wishes) > 3 and not any(skip in wishes.lower() for skip in ['пропустить', 'нет особых', 'ем всё', 'ем все'])

        prompt = f"""
        Ты — профессиональный фитнес-диетолог. Твоя задача — составить или скорректировать рацион. 
        
        ДАННЫЕ КЛИЕНТА: 
        - Вес: {user_data.get('weight')} кг, Рост: {user_data.get('height')} см
        - Возраст: {user_data.get('age')} лет, Пол: {user_data.get('gender')}
        - Цель: {goal}
        """

        # Если меню уже было и клиент написал пожелания, заставляем ИИ работать в режиме редактора
        if is_edit_mode:
            prompt += f"""
        ⚠️ У КЛИЕНТА УЖЕ ЕСТЬ СОСТАВЛЕННЫЙ РАЦИОН:
        {prev_plan}
        
        🔥 КЛИЕНТ ПРОСИТ ВНЕСТИ ПРАВКИ В ЭТОТ РАЦИОН: 
        "{wishes}"
        
        ЗАДАЧА:
        Не создавай меню полностью с нуля! Возьми ТЕКУЩИЙ рацион (предоставлен выше) и внеси в него ТОЛЬКО те изменения, о которых просит клиент в своих правках. 
        Например: если клиент просит поменять только обеды — измени варианты обедов, а завтраки, ужины и перекусы оставь точно такими же, как в текущем рационе. Сохраняй структуру.
        """
        else:
            prompt += f"""
        ЗАДАЧА:
        1. Пожелания/Ограничения: {wishes} - Это самое главное что нужно учитывать!
        2. РАССЧИТАЙ суточную норму калорий и диапазоны БЖУ.
        3. Составь меню на день: Завтрак, Обед, Ужин, Перекусы. В каждом блоке по 3 варианта. 
        """
            # --- НОВОЕ: Включаем память только для новых генераций! ---
            if past_programs:
                prompt += f"""
        ⚠️ ИСТОРИЯ ПРОШЛЫХ МЕНЮ КЛИЕНТА (ТОЛЬКО ДЛЯ АНАЛИЗА БЛЮД):
        {past_programs}
        
        🚨 КРИТИЧЕСКОЕ ТРЕБОВАНИЕ ПО РАСЧЕТУ КБЖУ:
        Ты обязан ПОЛНОСТЬЮ ИГНОРИРОВАТЬ любые цифры калорий, белков, жиров и углеводов из истории выше. Они неактуальны.
        
        Сделай НОВЫЙ математический расчет, используя ТОЛЬКО актуальные параметры клиента:
        - Вес: {user_data.get('weight')} кг
        - Рост: {user_data.get('height')} см
        - Возраст: {user_data.get('age')} лет
        - Пол: {user_data.get('gender')}
        - Уровень активности: {user_data.get('activity_level')}
        - Текущая цель: {goal}
        - Пожелания/Ограничения: {wishes}

        Только после этого расчета применяй профицит или дефицит калорий согласно цели.
        Результат расчета должен быть уникальным и точным, а не шаблонным.
        """

        prompt += """
        СТРОГИЕ ПРАВИЛА ОФОРМЛЕНИЯ (ЧИТАЙ ВНИМАТЕЛЬНО!):
        1. Всегда пиши названия упражнений и названия блюд, используя HTML-тег <code>название</code>, чтобы пользователь мог их скопировать.
        2. СТРОГО, сразу начинай с заголовка.
        3. При составлении списка продуктов, заголовок: <b>Список покупок:</b>, заместо "*" используй "-", разделяй белки жиры углеводы (используй пример: <b>Белки</b>, <b>Жиры</b>, <b>Углеводы</b> ) делай отступ строки между ними.
        4. ЗАПРЕЩЕНО ставить ===PAGE_BREAK=== между вариантами одного и того же приема пищи! Варианты разделяй просто пустой строкой.
        5. Каждая новая страница (Завтрак, Обед, Ужин, Перекусы) ОБЯЗАТЕЛЬНО начинается с заголовка: 
        <b>Твой КБЖУ ~[Число] ккал (Б: [мин]-[макс], Ж: [мин]-[макс], У: [мин]-[макс])</b>
        6. Каждый ингридиент с новой строки
        ФОРМАТ ВАРИАНТА:
        Вариант X: <b>[Название]</b>
        - [Ингредиенты с весом]
        - <b>КБЖУ: ~[ккал] (Б:..г, Ж:..г, У:..г)</b>
        - Разделяй приемы пищи тегом ===PAGE_BREAK===. В конце добавь Shopping List.
        """
        
        # Добиваем ИИ последним правилом перед генерацией
        prompt += f"""
        🚨 ФИНАЛЬНОЕ ПРАВИЛО (ВЫПОЛНИТЬ БЕЗУКОРИЗНЕННО): 
        1. СТРОГО выполни пожелание пользователя: "{wishes}".
        2. ОФОРМЛЕНИЕ: Никаких отклонений от СТРОГИХ ПРАВИЛ выше! Используй теги <code>, жирный шрифт <b> и ===PAGE_BREAK=== ровно там, где указано.
        3. МАТЕМАТИКА: Запрещено выдавать шаблонные 2500 ккал! Сделай точный расчет по формуле под параметры:
        - Вес: {user_data.get('weight')} кг
        - Рост: {user_data.get('height')} см
        - Возраст: {user_data.get('age')} лет
        - Пол: {user_data.get('gender')}
        - Уровень активности: {user_data.get('activity_level')}
        - Текущая цель: {goal}
        - Пожелания/Ограничения: {wishes}  
        """

        try:
            # Чуть подняли температуру (до 0.6), чтобы ИИ перестал "лениться" и выдавать шаблон
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], 
                model=self.model, temperature=0.6, timeout=90.0
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

            if gender == 'male': bmr = 10 * w + 6.25 * h - 5 * a + 5
            else: bmr = 10 * w + 6.25 * h - 5 * a - 161
            
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
        
        system_prompt = (
            f"Ты — тренер TrAIner. Твой клиент: {name}, цель: {goal}. "
            "Отвечай на ВСЕ вопросы. Пиши простым текстом без звездочек."
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system_prompt}] + history[-6:],
                temperature=0.7, timeout=30.0
            )
            result = response.choices[0].message.content
            if not result: return "Я тут, готов к работе!"
            return result.replace("*", "").replace("#", "")
        except Exception as e:
            logger.error(f"DeepSeek Error: {e}")
            return f"❌ Ошибка связи с ИИ. Попробуй еще раз."
        
    # --- 6. БЕЗОПАСНОЕ РАСПОЗНАВАНИЕ ГОЛОСА (ЛОКАЛЬНО В ФОНЕ) ---
    async def transcribe_voice(self, file_data) -> str:
        if not whisper_model:
            return ""
            
        try:
            if isinstance(file_data, str):
                file_path = file_data
                
                def run_transcription():
                    segments, _ = whisper_model.transcribe(
                        file_path, 
                        beam_size=5, 
                        language="ru",
                        initial_prompt="Жим лежа, присед, становая тяга, гантели, штанга, КБЖУ, спагетти, углеводы, калории, повторения.",
                        vad_filter=True, # 🔥 Отрезаем тишину
                        vad_parameters=dict(min_silence_duration_ms=500)
                    )
                    return "".join([segment.text for segment in segments]).strip()

                transcription_text = await asyncio.to_thread(run_transcription)
                return transcription_text
                
            elif isinstance(file_data, io.BytesIO):
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp:
                    tmp.write(file_data.read())
                    tmp_path = tmp.name
                    
                def run_transcription_bytes():
                    segments, _ = whisper_model.transcribe(
                        tmp_path, # Исправлена старая опечатка
                        beam_size=5, 
                        language="ru",
                        initial_prompt="Жим лежа, присед, становая тяга, гантели, штанга, КБЖУ, спагетти, углеводы, калории, повторения.",
                        vad_filter=True, # 🔥 Отрезаем тишину
                        vad_parameters=dict(min_silence_duration_ms=500)
                    )
                    return "".join([segment.text for segment in segments]).strip()
                    
                transcription_text = await asyncio.to_thread(run_transcription_bytes)
                import re
                transcription_text = re.sub(r'(?i)\b\d*\s*подход[а-я]*\b', '', transcription_text)
                os.remove(tmp_path)
                return transcription_text
                
            else:
                return ""
                
        except Exception as e:
            logger.error(f"Ошибка распознавания голоса: {e}")
            return ""


    async def generate_marketing_post(self) -> str:
        """Генерирует уникальный пост от лица TrAIner Bot"""
        if not self.client: 
            return "🤖 Пора на тренировку! Заходи в @TrAInerFitnessBot"
        
        import random
        
        # 1. Темы стали более специфичными, чтобы избежать общих фраз про ошибки
        topics = [
            "Почему креатин — это не химия, а база",
            "Как сон влияет на твой бицепс больше, чем жим лежа",
            "Топ-3 упражнения, которые ты зря игнорируешь",
            "Что съесть перед тренировкой, чтобы энергия перла",
            "Как понять, что пора увеличивать рабочий вес",
            "Миф о том, что от пресса горят жиры на животе",
            "Почему твой пульс в покое — главный маркер перетренированности",
            "Как я (ИИ) вижу твой прогресс через цифры",
            "Сравнение: сколько калорий в твоем любимом бургере vs 2 часа в зале"
        ]
        
        # 2. Роли — это заставит его менять манеру речи
        roles = [
            "Суровый и прямолинейный тренер старой школы",
            "Лучший друг-качок, который дает совет по-братски",
            "Холодный и сверхточный искусственный интеллект, оперирующий только цифрами",
            "Мотивационный оратор, который заставляет встать с дивана",
            "Ученый-биохакер, объясняющий процессы в мышцах"
        ]
        
        current_topic = random.choice(topics)
        current_role = random.choice(roles)
        bot_username = "@TrAInerFitnessBot" 

        prompt = f"""
        Ты — {current_role}. Твое имя — TrAIner Bot.
        
        ЗАДАНИЕ: Напиши пост для Telegram-канала на тему: "{current_topic}".
        
        КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО:
        - Использовать фразы "Мои алгоритмы", "кричат от боли", "вижу 3 ошибки".
        - Использовать нумерованные списки (1, 2, 3).
        - Использовать заезженные клише про 'новичков' и 'технику'.
        
        ТРЕБОВАНИЯ:
        1. Текст от 300 до 500 символов.
        2. Пиши ЖИВО, как будто ты реально сейчас зашел в чат.
        3. Используй HTML: <b>жирный</b> для акцентов.
        4. В конце добавь ОДНУ СТРОКУ: "Жду тебя здесь: {bot_username}"
        """

        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model, 
                temperature=1.0, # Максимальный хаос для креатива
                timeout=60.0
            )
            return r.choices[0].message.content
        except Exception as e:
            return f"<b>Твое тело — твой проект.</b> Начни работу вместе со мной: {bot_username}"