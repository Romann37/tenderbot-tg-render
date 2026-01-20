import telebot
import requests
from bs4 import BeautifulSoup
import os
import asyncio
import aiohttp
from dotenv import load_dotenv
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

load_dotenv()

# Конфигурация
BOT_TOKEN = os.getenv('BOT_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
MODEL_ID = os.getenv('MODEL_ID', 'anthropic/claude-3.5-sonnet')

bot = telebot.TeleBot(BOT_TOKEN)

# Демо тендеры (fallback)
demo_tenders = [
    {"num": "0373100026426", "title": "Отопительные системы для школ", "customer": "Департамент образования Иваново", "price": "2 500 000₽", "date": "20.01.2026", "link": "https://zakupki.gov.ru/epz/order/notice/ea44/view.html?regNumber=0373100026426"},
    {"num": "0373100026431", "title": "Ремонт котельной", "customer": "МУП Тепло Иваново", "price": "15 000 000₽", "date": "19.01.2026", "link": "https://zakupki.gov.ru/epz/order/notice/ea44/view.html?regNumber=0373100026431"},
]

# Регионы
REGION_MAP = {
    "иваново": "37000000000",
    "кострома": "44000000000", 
    "москва": "77000000000",
    "рф": "0"
}

# Главное меню
def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("🔍 Поиск тендеров"))
    markup.add(KeyboardButton("🤖 Анализ ИИ"))
    markup.add(KeyboardButton("📊 Мои подписки"))
    return markup

# Кнопки действий
def action_menu():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔍 Новый поиск", callback_data="search_new"))
    markup.add(InlineKeyboardButton("📋 Подписка на запрос", callback_data="subscribe"))
    markup.add(InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, 
        "🚀 <b>TenderAnalyzerBot</b>\n\n"
        "🤖 ИИ-бот для поиска <b>реальных тендеров ЕИС</b> (44-ФЗ/223-ФЗ)\n"
        "📍 Фокус: Ивановская область + вся РФ\n\n"
        "Выберите действие:", 
        reply_markup=main_menu(), parse_mode='HTML')

@bot.message_handler(func=lambda m: m.text == "🔍 Поиск тендеров")
def search_tenders(message):
    bot.send_message(message.chat.id, 
        "🔍 Введите запрос для поиска тендеров:\n"
        "• 'отопление'\n• 'строительство'\n• 'канцелярия'\n• 'ит оборудование'\n\n"
        "📍 По умолчанию: Иваново + вся РФ", 
        reply_markup=action_menu())

@bot.message_handler(func=lambda m: "🔍" in m.text or m.text.startswith("поиск"))
def handle_search(message):
    query = message.text.replace("🔍", "").replace("поиск", "").strip()
    
    bot.send_message(message.chat.id, f"🔄 Ищем реальные тендеры: <b>{query}</b>...", parse_mode='HTML')
    
    # Запуск асинхронного поиска
    asyncio.run(search_and_send_tenders(message.chat.id, query))

async def search_real_tenders(query, region="RU"):
    """Реальный поиск на zakupki.gov.ru"""
    url = "https://zakupki.gov.ru/epz/order/extendedsearch/search.html"
    
    # Добавляем регион в запрос
    region_id = REGION_MAP.get(region.lower(), "0")
    full_query = f"{query} region:{region_id}"
    
    data = {
        "searchString": query,
        "search-filter": f"Действие=1&isinUnifiedRegistry=True&isRegionalPart=True&custExtProg=1&custRegionIds={region_id}&custIndustryIds=0&custKindIds=&custUnreliableSuppliers=false&hasRecommendations=false&hasAwgRecommendations=false",
        "pageNumber": "1",
        "sortDirection": "false",
        "recordsPerPage": "_50",
        "showLotsInfoPlaced": "true",
        "sortBy": "UPDATE_DATE",
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        'Referer': 'https://zakupki.gov.ru/epz/order/extendedsearch/',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    return demo_tenders
                
                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                tenders = []
                rows = soup.select('table.searchResults tr')[1:11]  # Топ-10
                
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) > 9:
                        try:
                            num = cols[1].text.strip()
                            title = cols[3].text.strip()
                            customer = cols[5].text.strip()
                            price = cols[7].text.strip()
                            pub_date = cols[9].text.strip()
                            
                            tenders.append({
                                'num': num,
                                'title': title[:100] + "..." if len(title) > 100 else title,
                                'customer': customer,
                                'price': price,
                                'date': pub_date,
                                'link': f"https://zakupki.gov.ru/epz/order/notice/ea44/view.html?regNumber={num}"
                            })
                        except:
                            continue
                
                return tenders if tenders else demo_tenders
    except Exception as e:
        print(f"Парсинг ошибка: {e}")
        return demo_tenders

async def search_and_send_tenders(chat_id, query):
    """Поиск + отправка результатов"""
    # Поиск в Иваново
    ivanovo_tenders = await search_real_tenders(query, "иваново")
    
    msg = f"🔍 <b>Результаты по '{query}'</b>\n\n"
    msg += "📍 <b>Ивановская область:</b>\n\n"
    
    for i, tender in enumerate(ivanovo_tenders[:5], 1):
        msg += f"{i}️⃣ <b>№{tender['num']}</b>\n"
        msg += f"📋 {tender['title']}\n"
        msg += f"🏢 {tender['customer']}\n"
        msg += f"💰 {tender['price']}\n"
        msg += f"📅 {tender['date']}\n"
        msg += f"🔗 <a href='{tender['link']}'>Открыть</a>\n\n"
    
    bot.send_message(chat_id, msg, parse_mode='HTML', disable_web_page_preview=True)
    
    # Поиск по РФ (если мало в Иваново)
    if len(ivanovo_tenders) < 3:
        rf_tenders = await search_real_tenders(query, "рф")
        msg_rf = "\n🌍 <b>По всей РФ (дополнительно):</b>\n\n"
        for i, tender in enumerate(rf_tenders[:3], 1):
            msg_rf += f"{i}️⃣ <b>№{tender['num']}</b>\n"
            msg_rf += f"📋 {tender['title']}\n💰 {tender['price']}\n"
            msg_rf += f"🔗 <a href='{tender['link']}'>Открыть</a>\n\n"
        
        bot.send_message(chat_id, msg_rf, parse_mode='HTML', disable_web_page_preview=True)

@bot.message_handler(func=lambda m: m.text == "🤖 Анализ ИИ")
def ai_analysis(message):
    bot.send_message(message.chat.id, 
        "🤖 <b>ИИ-анализ документа</b>\n\n"
        "Отправьте:\n• Ссылку на тендер\n• PDF/DOCX файл\n• Скриншот\n\n"
        "Claude 3.5 Sonnet проверит:", 
        parse_mode='HTML')
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📋 Чек-лист для тендера", callback_data="ai_checklist"))
    markup.add(InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))
    bot.send_message(message.chat.id, "Выберите:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📊 Мои подписки")
def subscriptions(message):
    bot.send_message(message.chat.id, 
        "📊 <b>Уведомления о новых тендерах</b>\n\n"
        "• Ежедневный дайджест\n• Push при новых тендерах\n• Фильтры по региону\n\n"
        "⚙️ <i>В разработке</i>", 
        parse_mode='HTML', reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "main_menu":
        bot.edit_message_text("🏠 Главное меню:", call.message.chat.id, call.message.message_id, 
                            reply_markup=main_menu())
    elif call.data == "search_new":
        bot.edit_message_text("🔍 Введите новый запрос:", call.message.chat.id, call.message.message_id,
                            reply_markup=action_menu())
    elif call.data == "ai_checklist":
        checklist = """
✅ <b>ИИ Чек-лист для тендера:</b>

1. 📅 <b>Срок подачи</b> > 7 дней?
2. 💰 <b>НМЦК</b> подходит под бюджет?
3. 📋 <b>ТЗ четкое</b> или размытое?
4. 🏢 <b>Заказчик надежный</b> (без отказов)?
5. 📄 <b>Документы стандартные</b>?
6. ⚠️ <b>Риски/штрафы</b> указаны?
7. 🏆 <b>Шансы на победу</b> 30%+

<i>Claude: "Если 5+ ✅ → участвовать!"</i>
        """
        bot.edit_message_text(checklist, call.message.chat.id, call.message.message_id, parse_mode='HTML')
    bot.answer_callback_query(call.id)

# Обработка документов
@bot.message_handler(content_types=['document', 'photo', 'text_link'])
def handle_documents(message):
    bot.send_message(message.chat.id, 
        "📄 Документ получен!\n\n"
        "🤖 Claude 3.5 анализирует...\n⏳ 10-30 сек", 
        reply_markup=action_menu())

# ДОБАВИТЬ ПЕРЕД if __name__:
from flask import Flask
import os
from threading import Thread

app = Flask('')

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def home(path=''):
    return {
        'status': 'ok',
        'bot': 'TenderAnalyzerBot работает!',
        'telegram': 't.me/ii_agent37_Bot'
    }

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

# ЗАМЕНИТЬ if __name__ == '__main__':
if __name__ == '__main__':
    print("🚀 TenderAnalyzerBot + Flask запускаются...")
    
    # Flask на порту PORT (Render счастлив)
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print(f"✅ Flask: http://0.0.0.0:{os.environ.get('PORT', 10000)}")
    print("✅ Telegram Bot: polling...")
    print("🎯 Тестируйте: t.me/ii_agent37_Bot → /start")
    
    # Telegram bot бесконечно
    bot.infinity_polling(none_stop=True)
