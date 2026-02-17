import re

def clean_text(text: str) -> str:
    if not text: return ""
    
    # Удаляем служебный мусор от DeepSeek
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # 🔥 ДОБАВЬТЕ ЭТУ СТРОКУ: заменяем <br> на обычный перенос строки
    text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = re.sub(r'```html', '', text, flags=re.IGNORECASE)
    text = re.sub(r'```', '', text)
    
    # Markdown -> HTML
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    
    # Форматирование заголовков
    text = re.sub(r'(^|\n)(День \d+:.*?)(?=\n|$)', r'\1<b>\2</b>', text)
    text = re.sub(r'(^|\n)(🍳|🍲|🥗|🛒|🥪)(.*?)(?=\n|$)', r'\1\2<b>\3</b>', text)
    
    # Чистим HTML теги, которые Telegram не любит
    for tag in ['div', 'p', 'span', 'html', 'body', 'header', 'footer']:
        text = re.sub(f'</?{tag}.*?>', '', text, flags=re.IGNORECASE)
            
    # Убираем разделители
    text = text.replace("###", "").replace("SPLIT", "").replace("Menu:", "")
    
    # 🔥 ВАЖНО: Оставляем пустые строки, но убираем слишком большие пробелы (3+ энтера)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()