import re

def clean_text(text: str) -> str:
    if not text:
        return ""

    # 1. Убираем "размышления" (для моделей R1)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)

    # 2. Заменяем структурные HTML теги на обычные переносы строк
    # Заменяем закрывающие </p>, </div> и <br> на переносы
    text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = text.replace("</p>", "\n").replace("</div>", "\n")
    
    # 3. Удаляем все остальные теги, кроме разрешенных (b, i, u, s, code)
    # Это защитит от <p>, <div>, <span> и прочего мусора
    text = re.sub(r'<(?!/?(b|i|u|s|code|a|pre)\b)[^>]+>', '', text)

    # 4. Убираем блоки кода Markdown (```html ... ```)
    text = re.sub(r'```[a-z]*', '', text, flags=re.IGNORECASE)
    text = text.replace('```', '')

    # 5. Приводим жирный шрифт из Markdown (**) в HTML (<b>)
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)

    # 6. Убираем лишние пустые строки (больше двух подряд)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()