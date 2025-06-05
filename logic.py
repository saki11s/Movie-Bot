import sqlite3
import requests

DB_PATH = 'movie.db' 
TRANSLATION_API_URL = "http://localhost:5001/translate" # Или твой актуальный URL

def get_db_connection():
    """Устанавливает соединение с базой данных."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def setup_database():
    """Создает таблицы для избранных фильмов и для кеша переводов, если они еще не существуют."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_favorites (
            user_id INTEGER NOT NULL,
            movie_id INTEGER NOT NULL,
            PRIMARY KEY (user_id, movie_id),
            FOREIGN KEY (movie_id) REFERENCES movies(ID)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS translations_cache (
            original_text TEXT PRIMARY KEY,
            translated_text TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def translate_text(text, target_lang='ru', source_lang='auto'):
    if not text:
        return ""
    text = str(text)
    cache_key = f"{source_lang}_{target_lang}_{text}"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT translated_text FROM translations_cache WHERE original_text = ?", (cache_key,))
    cached_translation = cursor.fetchone()
    if cached_translation:
        conn.close()
        return cached_translation['translated_text']

    try:
        data = {
            "q": text,
            "source": source_lang,
            "target": target_lang,
            "format": "text"
        }
        
        response = requests.post(TRANSLATION_API_URL, json=data, timeout=15)
        response.raise_for_status()
        translated_data = response.json()
        translated_text = translated_data.get('translatedText', text)

        cursor.execute("INSERT OR REPLACE INTO translations_cache (original_text, translated_text) VALUES (?, ?)", 
                       (cache_key, translated_text))
        conn.commit()
        return translated_text
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к API перевода ('{cache_key}'): {e}")
        cursor.execute("INSERT OR REPLACE INTO translations_cache (original_text, translated_text) VALUES (?, ?)", (cache_key, text))
        conn.commit()
        return text 
    except KeyError:
        print(f"Неожиданный формат ответа от API для '{cache_key}': {response.text}")
        cursor.execute("INSERT OR REPLACE INTO translations_cache (original_text, translated_text) VALUES (?, ?)", (cache_key, text))
        conn.commit()
        return text 
    finally:
        if conn: 
            conn.close()

def get_random_movie_data():
    """Извлекает данные для случайного фильма."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            m.ID, m.title, m.release_date, m.vote_average, m.overview,
            GROUP_CONCAT(g.genre, ', ') AS genres
        FROM
            movies AS m
        LEFT JOIN
            movies_genres AS mg ON m.ID = mg.movie_id
        LEFT JOIN
            genres AS g ON mg.genre_id = g.genre_ID
        GROUP BY
            m.ID
        ORDER BY RANDOM() LIMIT 1
    """)
    movie_data = cursor.fetchone()
    conn.close()
    return movie_data

def search_movies_by_title_in_db(title_query):
    """Ищет фильмы по названию в БД."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            m.ID, m.title, m.release_date, m.vote_average, m.overview,
            GROUP_CONCAT(g.genre, ', ') AS genres
        FROM
            movies AS m
        LEFT JOIN
            movies_genres AS mg ON m.ID = mg.movie_id
        LEFT JOIN
            genres AS g ON mg.genre_id = g.genre_ID
        WHERE
            LOWER(m.title) LIKE ? 
        GROUP BY
            m.ID
        LIMIT 10 
    """, (f'%{title_query.lower()}%',))
    found_movies = cursor.fetchall()
    conn.close()
    return found_movies

def get_all_genres_from_db():
    """Получает все жанры из БД."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT genre_ID, genre FROM genres ORDER BY genre")
    genres = cursor.fetchall()
    conn.close()
    return genres

def get_favorite_movies_from_db(user_id):
    """Получает избранные фильмы пользователя из БД."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            m.ID, m.title, m.release_date, m.vote_average, m.overview,
            GROUP_CONCAT(g.genre, ', ') AS genres
        FROM
            user_favorites AS uf
        JOIN
            movies AS m ON uf.movie_id = m.ID
        LEFT JOIN
            movies_genres AS mg ON m.ID = mg.movie_id
        LEFT JOIN
            genres AS g ON mg.genre_id = g.genre_ID
        WHERE
            uf.user_id = ?
        GROUP BY
            m.ID
        ORDER BY
            m.title
    """, (user_id,))
    favorite_movies = cursor.fetchall()
    conn.close()
    return favorite_movies

def add_movie_to_favorites(user_id, movie_id):
    """Добавляет фильм в избранное."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO user_favorites (user_id, movie_id) VALUES (?, ?)", (user_id, movie_id))
        conn.commit()
        return True 
    except sqlite3.IntegrityError:
        return False 
    finally:
        conn.close()

def remove_movie_from_favorites(user_id, movie_id):
    """Удаляет фильм из избранного."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_favorites WHERE user_id = ? AND movie_id = ?", (user_id, movie_id))
    conn.commit()
    success = cursor.rowcount > 0 
    conn.close()
    return success

def is_movie_in_favorites(user_id, movie_id):
    """Проверяет, находится ли фильм в избранном у пользователя."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM user_favorites WHERE user_id = ? AND movie_id = ?", (user_id, movie_id))
    is_favorite = cursor.fetchone() is not None
    conn.close()
    return is_favorite

def get_movie_data_by_id(movie_id):
    """Получает данные о фильме по его ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            m.ID, m.title, m.release_date, m.vote_average, m.overview,
            GROUP_CONCAT(g.genre, ', ') AS genres
        FROM
            movies AS m
        LEFT JOIN
            movies_genres AS mg ON m.ID = mg.movie_id
        LEFT JOIN
            genres AS g ON mg.genre_id = g.genre_ID
        WHERE m.ID = ?
        GROUP BY m.ID
    """, (movie_id,))
    movie_data = cursor.fetchone()
    conn.close()
    return movie_data

def get_genre_name_by_id(genre_id):
    """Получает название жанра по ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT genre FROM genres WHERE genre_ID = ?", (genre_id,))
    genre_row = cursor.fetchone()
    conn.close()
    return genre_row['genre'] if genre_row else None

def get_movies_by_genre_id_from_db(genre_id):
    """Получает фильмы по ID жанра."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            m.ID, m.title, m.release_date, m.vote_average, m.overview,
            GROUP_CONCAT(g.genre, ', ') AS genres
        FROM
            movies AS m
        JOIN
            movies_genres AS mg ON m.ID = mg.movie_id
        JOIN
            genres AS g ON mg.genre_id = g.genre_ID
        WHERE
            g.genre_ID = ?
        GROUP BY
            m.ID
        ORDER BY RANDOM() LIMIT 5
    """, (genre_id,))
    movies = cursor.fetchall()
    conn.close()
    return movies
