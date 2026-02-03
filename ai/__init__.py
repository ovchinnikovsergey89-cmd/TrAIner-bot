# ai/__init__.py
def get_ai_client():
    """Фабрика для получения AI клиента"""
    
    # --- ВАРИАНТ 1: Google Gemini (Бесплатно и креативно) ---
    # from services.gemini_service import GeminiService
    # return GeminiService()

    # --- ВАРИАНТ 2: Groq (Быстро и четко) ---
    from services.groq_service import GroqService
    return GroqService()