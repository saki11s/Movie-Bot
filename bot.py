import config
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

import logic 

bot = telebot.TeleBot(config.API_TOKEN)

logic.setup_database()


def main_markup():
  markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
  markup.add(KeyboardButton('🎲 Случайный фильм'))
  markup.add(KeyboardButton('🔍 Поиск по названию'), KeyboardButton('🎭 Поиск по жанру'))
  markup.add(KeyboardButton('⭐ Мои избранные'))
  return markup

def add_to_favorite_markup(movie_id, user_id):
    is_favorite = logic.is_movie_in_favorites(user_id, movie_id) 
    markup = InlineKeyboardMarkup()
    if is_favorite:
        markup.add(InlineKeyboardButton("💔 Удалить из избранного", callback_data=f'unfavorite_{movie_id}'))
    else:
        markup.add(InlineKeyboardButton("🌟 Добавить фильм в избранное", callback_data=f'favorite_{movie_id}'))
    return markup

def create_movie_selection_markup(movies_data_list):
    markup = InlineKeyboardMarkup()
    for movie_data in movies_data_list[:5]: 
        movie_year = movie_data['release_date'][:4] if movie_data['release_date'] else 'Неизвестен'
        translated_title = logic.translate_text(movie_data['title']) 
        markup.add(InlineKeyboardButton(f"{translated_title.strip()} ({movie_year})", callback_data=f"show_movie_{movie_data['ID']}"))
    return markup

def create_genre_selection_markup(genres_data_list):
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = []
    for genre_data in genres_data_list:
        genre_id = genre_data['genre_ID']
        genre_name_english = genre_data['genre']
        translated_genre_name = logic.translate_text(genre_name_english) 
        buttons.append(InlineKeyboardButton(translated_genre_name, callback_data=f"genre_{genre_id}"))
    markup.add(*buttons)
    return markup

def send_movie_info_message(chat_id, movie_data, user_id=None, message_id_to_edit=None):
    if not movie_data:
        bot.send_message(chat_id, "Информация о фильме не найдена.")
        return

    translated_title = logic.translate_text(movie_data['title'])
    translated_genres_text = logic.translate_text(movie_data['genres'] or 'Не указаны')
    translated_overview = logic.translate_text(movie_data['overview'])
    movie_year = movie_data['release_date'][:4] if movie_data['release_date'] else 'Неизвестен'

    info = f"""
🎬 <b>Название фильма:</b> {translated_title.strip()}
🗓 <b>Год:</b> {movie_year}
🎭 <b>Жанры:</b> {translated_genres_text.strip()}
⭐ <b>Рейтинг IMDB:</b> {movie_data['vote_average']} / 10

📜 <b>Описание:</b>
{translated_overview.strip()}
"""
    markup = add_to_favorite_markup(movie_data['ID'], user_id)
    
    if message_id_to_edit:
        bot.edit_message_text(chat_id=chat_id, message_id=message_id_to_edit, text=info, reply_markup=markup, parse_mode="HTML")
    else:
        bot.send_message(chat_id=chat_id, text=info, reply_markup=markup, parse_mode="HTML")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, """
Привет! Добро пожаловать в Кино-Бот🎥!
Здесь ты найдешь тысячи фильмов 🔥

<b>Что я могу:</b>
- Нажми "🎲 Случайный фильм", чтобы получить случайный фильм.
- Нажми "🔍 Поиск по названию" чтобы найти фильм.
- Нажми "🎭 Поиск по жанру", чтобы выбрать жанр.
- Нажми "⭐ Мои избранные", чтобы посмотреть твои любимые фильмы.

Давай найдем отличные фильмы! 🎬
""", reply_markup=main_markup(), parse_mode="HTML")

@bot.message_handler(func=lambda message: message.text == '🎲 Случайный фильм' or message.text == '/random')
def random_movie_command(message):
    movie_data = logic.get_random_movie_data()
    if movie_data:
        send_movie_info_message(message.chat.id, movie_data, message.from_user.id)
    else:
        bot.send_message(message.chat.id, "К сожалению, не удалось найти случайный фильм.")

@bot.message_handler(func=lambda message: message.text == '🔍 Поиск по названию' or message.text == '/search_by_title')
def ask_for_title_command(message): 
    bot.send_message(message.chat.id, "Пожалуйста, введите название фильма, который вы ищете:")
    bot.register_next_step_handler(message, process_title_search_input) 

def process_title_search_input(message):
    user_original_query = message.text.strip() 

    found_movies = logic.search_movies_by_title_in_db(user_original_query)

    if not found_movies:
        bot.send_message(message.chat.id, "Хм, дай мне пару секунд...")
        english_query = logic.translate_text(user_original_query, target_lang='en', source_lang='ru')
        if english_query and english_query.lower() != user_original_query.lower():
            found_movies = logic.search_movies_by_title_in_db(english_query)
        else:
            bot.send_message(message.chat.id, "Не удалось перевести ваш запрос для поиска на английском.")

    if found_movies:
        if len(found_movies) == 1:
            bot.send_message(message.chat.id, "Конечно! Я нашел этот фильм😌")
            send_movie_info_message(message.chat.id, found_movies[0], message.from_user.id)
        else:
            bot.send_message(message.chat.id, "Найдено несколько фильмов. Выберите один из списка:",
                             reply_markup=create_movie_selection_markup(found_movies))
    else:
        bot.send_message(message.chat.id, "К сожалению, я не смог найти фильм с таким названием😞")

@bot.message_handler(func=lambda message: message.text == '🎭 Поиск по жанру' or message.text == '/search_by_genre')
def list_genres_command(message):
    genres_data = logic.get_all_genres_from_db()
    if genres_data:
        bot.send_message(message.chat.id, "Выберите жанр:", reply_markup=create_genre_selection_markup(genres_data))
    else:
        bot.send_message(message.chat.id, "Жанры не найдены.")

@bot.message_handler(func=lambda message: message.text == '⭐ Мои избранные' or message.text == '/my_favorites')
def list_my_favorites_command(message):
    user_id = message.from_user.id
    favorite_movies = logic.get_favorite_movies_from_db(user_id)

    if favorite_movies:
        response = "🌟 <b>Ваши избранные фильмы:</b>\n\n"
        for i, movie in enumerate(favorite_movies):
            movie_year = movie['release_date'][:4] if movie['release_date'] else 'Неизвестен'
            translated_title = logic.translate_text(movie['title']) 
            response += f"{i+1}. {translated_title.strip()} ({movie_year})\n"
        bot.send_message(message.chat.id, response, parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, "У вас пока нет избранных фильмов. Добавьте что-нибудь! ✨")


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    message_id = call.message.message_id
    chat_id = call.message.chat.id

    if call.data.startswith("favorite_"):
        movie_id = int(call.data.split('_')[1])
        if logic.add_movie_to_favorites(user_id, movie_id):
            bot.answer_callback_query(call.id, "Фильм добавлен в избранное! ✨")
        else:
            bot.answer_callback_query(call.id, "Этот фильм уже в избранном.", show_alert=True)
        
        movie_data_for_update = logic.get_movie_data_by_id(movie_id)
        if movie_data_for_update:
            send_movie_info_message(chat_id, movie_data_for_update, user_id, message_id)

    elif call.data.startswith("unfavorite_"):
        movie_id = int(call.data.split('_')[1])
        logic.remove_movie_from_favorites(user_id, movie_id)
        bot.answer_callback_query(call.id, "Фильм удален из избранного! 💔")

        movie_data_for_update = logic.get_movie_data_by_id(movie_id)
        if movie_data_for_update:
            send_movie_info_message(chat_id, movie_data_for_update, user_id, message_id)

    elif call.data.startswith("show_movie_"):
        movie_id = int(call.data.split('_')[2]) 
        movie_data = logic.get_movie_data_by_id(movie_id)
        if movie_data:
            bot.delete_message(chat_id, message_id)
            send_movie_info_message(chat_id, movie_data, user_id)
        else:
            bot.answer_callback_query(call.id, "Ошибка: фильм не найден.")

    elif call.data.startswith("genre_"):
        genre_id = int(call.data.split('_')[1])
        genre_name_english = logic.get_genre_name_by_id(genre_id)
        genre_name_russian = logic.translate_text(genre_name_english) if genre_name_english else "Неизвестный жанр"
        
        movies_by_genre = logic.get_movies_by_genre_id_from_db(genre_id)

        if movies_by_genre:
            response_text = f"Вот несколько фильмов в жанре <b>{genre_name_russian}</b>:\n\n"
            for i, movie in enumerate(movies_by_genre):
                movie_year = movie['release_date'][:4] if movie['release_date'] else 'Неизвестен'
                translated_title = logic.translate_text(movie['title']) 
                response_text += f"{i+1}. {translated_title.strip()} ({movie_year})\n"
            selection_markup = create_movie_selection_markup(movies_by_genre)
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=response_text + "\nВыберите фильм для подробной информации:", reply_markup=selection_markup, parse_mode="HTML")
        else:
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"К сожалению, фильмы в жанре '{genre_name_russian}' не найдены.")
        bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: True)
def echo_message(message):
    process_title_search_input(message)

bot.infinity_polling()
