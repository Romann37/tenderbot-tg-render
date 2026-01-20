import requests
import json
from config import OPENROUTER_KEY, MODEL_ID


def analyze_tender(details):
    """Анализ через прямые HTTP запросы к OpenRouter"""
    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/ii_agent37_Bot",  # Опционально
        "X-Title": "TenderAnalyzerBot"
    }

    prompt = f"""Тендер {details['id']}. Документы: {details['docs']}

Составь чек-лист для участия по 44-ФЗ:
| Раздел | Документы | Срок | Примечание |

Учти теплоэнергетику Иваново, СМП, обеспечение 1-5%."""

    data = {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1000,
        "temperature": 0.1
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            return f"❌ Ошибка API: {response.status_code}\nПроверьте OPENROUTER_API_KEY"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"
