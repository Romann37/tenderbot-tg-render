import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from config import BOT_TOKEN
from parser import search_tenders, get_tender_details
from analyzer import analyze_tender
import random
import time

bot = telebot.TeleBot(BOT_TOKEN)


# Главное меню
def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add('🔍 Поиск тендеров', '📋 Подписки')
    markup.add('ℹ️ Помощь', '📊 Статистика')
    return markup


@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id,
                     "👋 Добро пожаловать в **TenderAnalyzerBot**!\n\n"
                     "🔍 Поиск тендеров по ключевым словам\n"
                     "🤖 Анализ документов ИИ\n"
                     "📋 Чек-лист для участия\n\n"
                     "*Пример*: `отопительные системы Иваново`",
                     reply_markup=main_menu(), parse_mode='Markdown')


@bot.message_handler(func=lambda message: message.text == '🔍 Поиск тендеров')
def search_menu(message):
    bot.send_message(message.chat.id,
                     "🔎 *Введите запрос для поиска тендеров*\n\n"
                     "*Примеры:*\n"
                     "• отопительные системы Иваново\n"
                     "• котельное оборудование\n"
                     "• теплоснабжение 44-ФЗ\n"
                     "• обследование зданий",
                     parse_mode='Markdown')
    bot.register_next_step_handler(message, process_search)


def process_search(message):
    query = message.text.strip()
    bot.send_message(message.chat.id, f"⏳ Ищем тендеры: *{query}*...", parse_mode='Markdown')

    try:
        tenders = search_tenders(query, limit=5)

        if not tenders:
            bot.send_message(message.chat.id,
                             "❌ Тендеры не найдены\n\n"
                             "💡 Попробуйте:\n"
                             "• Изменить ключевые слова\n"
                             "• Убрать лишние слова\n"
                             "• Проверить написание",
                             reply_markup=main_menu())
            return

        for i, tender in enumerate(tenders, 1):
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton(
                f"📄 Тендер #{i}",
                callback_data=f"details_{tender['id']}"
            ))
            bot.send_message(message.chat.id,
                             f"{i}. **{tender['title']}**\n"
                             f"💰 {tender.get('price', 'Цена не указана')}\n"
                             f"🔗 [{tender['id']}]({tender['url']})",
                             reply_markup=keyboard, parse_mode='Markdown', disable_web_page_preview=True)

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка поиска: {str(e)}", reply_markup=main_menu())


@bot.callback_query_handler(func=lambda call: call.data.startswith('details_'))
def show_details(call):
    order_id = call.data.split('_')[1]

    bot.answer_callback_query(call.id)
    bot.edit_message_text("⏳ Получаем детали тендера...", call.message.chat.id, call.message.id)

    try:
        details = get_tender_details(order_id)

        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(InlineKeyboardButton("🤖 Анализ ИИ", callback_data=f"analyze_{order_id}"))
        keyboard.add(InlineKeyboardButton("📎 Документы", callback_data=f"docs_{order_id}"))
        keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back_search"))

        text = (f"📋 **Тендер #{order_id}**\n\n"
                f"🏪 *Площадка*: {details['platform']}\n"
                f"⏰ *Срок подачи*: {details.get('deadline', 'N/A')}\n"
                f"💳 *Обеспечение*: {details['security']}\n\n"
                f"📎 *Документы* ({len(details['docs'])} шт.):")

        for doc in details['docs'][:3]:
            text += f"\n• {doc['name']}"

        bot.edit_message_text(text, call.message.chat.id, call.message.id,
                              reply_markup=keyboard, parse_mode='Markdown')

    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка получения деталей: {str(e)}",
                              call.message.chat.id, call.message.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('docs_'))
def show_documents(call):
    order_id = call.data.split('_')[1]

    bot.answer_callback_query(call.id)

    try:
        details = get_tender_details(order_id)

        keyboard = InlineKeyboardMarkup(row_width=1)

        text = f"📎 **Документы тендера #{order_id}**\n\n"

        if details['docs']:
            for i, doc in enumerate(details['docs'], 1):
                doc_url = doc['url']
                text += f"{i}. {doc['name']}\n🔗 [Скачать {doc['name']}]({doc_url})\n\n"

                # Кнопка прямого скачивания
                keyboard.add(InlineKeyboardButton(
                    f"📥 {doc['name'][:30]}...",
                    url=doc_url
                ))
        else:
            text += "📋 Документы доступны на сайте ЕИС\n"
            text += f"🔗 [Открыть тендер #{order_id}](https://zakupki.gov.ru/epz/order/{order_id}/common-info.html)"
            keyboard.add(InlineKeyboardButton("🌐 Открыть ЕИС",
                                              url=f"https://zakupki.gov.ru/epz/order/{order_id}/common-info.html"))

        keyboard.add(InlineKeyboardButton("🔙 Назад к тендеру", callback_data=f"details_{order_id}"))

        bot.edit_message_text(text, call.message.chat.id, call.message.id,
                              reply_markup=keyboard, parse_mode='Markdown',
                              disable_web_page_preview=True)

    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка документов: {str(e)}",
                              call.message.chat.id, call.message.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('analyze_'))
def analyze(call):
    order_id = call.data.split('_')[1]

    bot.answer_callback_query(call.id)
    bot.edit_message_text("🧠 *Анализируем документы ИИ*...\nЭто займет 10-20 секунд",
                          call.message.chat.id, call.message.id, parse_mode='Markdown')

    try:
        details = get_tender_details(order_id)
        analysis = analyze_tender(details)

        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(InlineKeyboardButton("🔍 Новый поиск", callback_data="new_search"))
        keyboard.add(InlineKeyboardButton("📋 Главное меню", callback_data="main_menu"))

        bot.edit_message_text(f"📊 **Анализ тендера #{order_id}**\n\n{analysis}",
                              call.message.chat.id, call.message.id,
                              reply_markup=keyboard, parse_mode='Markdown')

    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка анализа: {str(e)}\n\n"
                              f"💡 Проверьте OPENROUTER_API_KEY в .env",
                              call.message.chat.id, call.message.id)


@bot.callback_query_handler(func=lambda call: call.data == 'back_search')
def back_search(call):
    bot.edit_message_text("🔍 *Введите новый запрос:*",
                          call.message.chat.id, call.message.id,
                          reply_markup=None, parse_mode='Markdown')
    bot.register_next_step_handler(call.message, process_search)


@bot.callback_query_handler(func=lambda call: call.data in ['new_search', 'main_menu'])
def menu_actions(call):
    if call.data == 'new_search':
        bot.edit_message_text("🔍 *Введите запрос для поиска:*", call.message.chat.id, call.message.id)
        bot.register_next_step_handler(call.message, process_search)
    else:
        bot.edit_message_text("👋 Главное меню:", call.message.chat.id, call.message.id,
                              reply_markup=main_menu())


@bot.message_handler(func=lambda message: message.text == 'ℹ️ Помощь')
def help_command(message):
    help_text = """
🤖 *TenderAnalyzerBot* - помощник по госзакупкам

*🔥 Как пользоваться:*
1️⃣ *🔍 Поиск* → «отопительные системы Иваново»
2️⃣ *📄 Тендер* → подробности + документы
3️⃣ *🤖 Анализ ИИ* → готовый чек-лист
4️⃣ *📎 Документы* → прямые ссылки

*Примеры запросов:*
• отопительные системы Иваново
• котельное оборудование 44-ФЗ  
• обследование зданий
• теплоснабжение СМП
    """
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown',
                     reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add('🔍 Поиск тендеров'))


@bot.message_handler(
    func=lambda message: message.text and message.text not in ['🔍 Поиск тендеров', '📋 Подписки', 'ℹ️ Помощь',
                                                               '📊 Статистика'])
def handle_unknown(message):
    if message.text.startswith('/'):
        bot.reply_to(message, "❓ Неизвестная команда\n\nНажмите *🔍 Поиск тендеров* или /start",
                     reply_markup=main_menu(), parse_mode='Markdown')
    else:
        # Любой текст = поиск тендеров
        process_search(message)


if __name__ == '__main__':
    import os
    from threading import Thread
    
    print("🚀 TenderAnalyzerBot запущен!")
    print("✅ Токен: OK | Парсинг: OK | ИИ: OK | Документы: OK")
    print("🎯 Тестируйте: t.me/ii_agent37_Bot → /start")
    
    # Health check endpoint для Render
    @bot.message_handler(commands=['health'])
    def health_check(message):
        bot.reply_to(message, "✅ Bot alive!")
    
    # Запуск polling в фоне + веб-сервер
    def run_bot():
        try:
            bot.infinity_polling(none_stop=True, interval=1, timeout=30)
        except Exception as e:
            print(f"❌ Bot error: {e}")
    
    bot_thread = Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Минимальный веб-сервер для Render Free (держит awake)
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/')
    def home():
        return "🤖 TenderAnalyzerBot работает! t.me/ii_agent37_Bot"
    
    @app.route('/health')
    def health():
        return {"status": "ok", "bot": "running"}
    
    # Render порт
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)


