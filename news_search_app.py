import streamlit as st
import requests
import os
from datetime import datetime
from urllib.parse import quote
import json

# --- Настройки страницы ---
st.set_page_config(page_title="Новости Кристофера Нолана", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #f0f2f6; }
    body, p, .st-emotion-cache-16txtl3, .st-emotion-cache-1629p8f p, .st-emotion-cache-1xarl3l, h1, h2, h3, h4, h5, h6 {
        color: #111111 !important;
    }
    .st-emotion-cache-16txtl3 { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)

# --- Функция для поиска новостей через Google (Serper.dev) ---
@st.cache_data(ttl=1800) # Кэшируем результат на 30 минут
def fetch_google_news(search_query):
    """Ищет новости через Google News API от Serper.dev."""
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return None, "Ключ SERPER_API_KEY не найден в секретах."

    url = "https://google.serper.dev/news"
    # Добавляем в запрос требование искать только за последнюю неделю для свежести
    payload = json.dumps({"q": search_query, "gl": "ru", "hl": "ru", "tbs": "qdr:w"})
    headers = {'X-API-KEY': api_key, 'Content-Type': 'application/json'}

    try:
        response = requests.post(url, headers=headers, data=payload)
        if response.status_code == 200:
            results = response.json().get("news", [])
            return results, None
        else:
            return None, f"Ошибка API Serper. Статус: {response.status_code}, Ответ: {response.text}"
    except Exception as e:
        return None, f"Ошибка сети: {e}"

# === ИНТЕРФЕЙС ПРИЛОЖЕНИЯ ===
st.title("🎬 Дайджест новостей о Кристофере Нолане")
st.write("Автоматический поиск самых актуальных новостей о фильмах, проектах и деятельности режиссера Кристофера Нолана.")
st.divider()

# --- Раздел "Последние актуальные новости" ---
st.header("🔥 Последние релевантные новости")

# Каждая фраза в кавычках ищется как единое целое. Оператор OR ищет хотя бы одно совпадение.
relevant_keywords = (
    # Режиссер и основные проекты
    '"Christopher Nolan" OR "Кристофер Нолан" OR "Nolan" OR '
    # Фильмы
    '"Inception" OR "Начало" OR "Начало (фильм)" OR '
    '"Interstellar" OR "Интерстеллар" OR "Межзвездный" OR '
    '"The Dark Knight" OR "Темный рыцарь" OR "Бэтмен: Темный рыцарь" OR '
    '"Dunkirk" OR "Дюнкерк" OR '
    '"Tenet" OR "Довод" OR "Тенет" OR '
    '"Oppenheimer" OR "Оппенгеймер" OR '
    '"Memento" OR "Помни" OR "Мементо" OR '
    '"The Prestige" OR "Престиж" OR '
    '"Insomnia" OR "Бессонница" OR '
    # Проекты и сотрудничества
    '"Syncopy" OR "Warner Bros" OR "Universal Pictures" OR '
    '"IMAX" OR "70mm film" OR "пленка 70мм" OR '
    # Награды и премии
    '"Oscar" OR "Оскар" OR "Academy Award" OR "BAFTA" OR "БАФТА"'
)

with st.spinner("Загружаю самые релевантные новости из Google за последнюю неделю..."):
    latest_articles, error = fetch_google_news(relevant_keywords)

    if error:
        st.error(error)
    elif latest_articles:
        st.success(f"Найдено свежих новостей: {len(latest_articles)}")
        for article in latest_articles[:10]: # Показываем до 10 новостей
            st.subheader(article['title'])
            date_published_str = article.get('date', 'Дата неизвестна')
            st.caption(f"Источник: {article['source']} | Опубликовано: {date_published_str}")
            st.write(article.get('snippet', 'Описание отсутствует.'))
            st.markdown(f"[*Читать далее...*]({article['link']})")
            st.divider()
    else:
        st.info("Не удалось найти свежих новостей за последнюю неделю.")

# --- Раздел "Индивидуальный поиск" ---
st.header("🔍 Индивидуальный поиск")
st.write("Ищите новости по конкретным фильмам, актерам или темам, связанным с Кристофером Ноланом.")

# Примеры для пользователя
st.info('Примеры запросов: `Cillian Murphy Nolan`, `Hans Zimmer`, `Tenet box office`, `Oppenheimer Oscar`')

search_term = st.text_input("Введите ваш точный запрос для поиска:", "")

if st.button("Найти"):
    if not search_term:
        st.warning("Пожалуйста, введите запрос для поиска.")
    else:
        with st.spinner(f"Ищу в Google News по запросу '{search_term}'..."):
            articles, error = fetch_google_news(search_term)

            if error:
                st.error(error)
            elif not articles:
                st.info(f"Новостей по запросу '{search_term}' не найдено.")
            else:
                st.success(f"Найдено результатов: {len(articles)}")
                for article in articles[:15]:
                    st.subheader(article['title'])
                    date_published_str = article.get('date', 'Дата неизвестна')
                    st.caption(f"Источник: {article['source']} | Опубликовано: {date_published_str}")
                    st.write(article.get('snippet', 'Описание отсутствует.'))
                    st.markdown(f"[*Читать далее...*]({article['link']})")
                    st.divider()

# --- Раздел "Популярные фильмы Нолана" ---
st.header("🎞️ Поиск по фильмам")
st.write("Быстрый поиск новостей по конкретным фильмам Нолана")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Oppenheimer"):
        st.session_state['search'] = "Oppenheimer Christopher Nolan"

with col2:
    if st.button("Interstellar"):
        st.session_state['search'] = "Interstellar Nolan"

with col3:
    if st.button("Inception"):
        st.session_state['search'] = "Inception Nolan"

col4, col5, col6 = st.columns(3)

with col4:
    if st.button("The Dark Knight"):
        st.session_state['search'] = '"The Dark Knight" Nolan'

with col5:
    if st.button("Tenet"):
        st.session_state['search'] = "Tenet Nolan"

with col6:
    if st.button("Dunkirk"):
        st.session_state['search'] = "Dunkirk Nolan"

# Обработка поиска из кнопок
if 'search' in st.session_state:
    search_term = st.session_state['search']
    del st.session_state['search']
    
    with st.spinner(f"Ищу новости по запросу '{search_term}'..."):
        articles, error = fetch_google_news(search_term)
        
        if error:
            st.error(error)
        elif not articles:
            st.info(f"Новостей по запросу '{search_term}' не найдено.")
        else:
            st.success(f"Найдено результатов: {len(articles)}")
            for article in articles[:10]:
                st.subheader(article['title'])
                date_published_str = article.get('date', 'Дата неизвестна')
                st.caption(f"Источник: {article['source']} | Опубликовано: {date_published_str}")
                st.write(article.get('snippet', 'Описание отсутствует.'))
                st.markdown(f"[*Читать далее...*]({article['link']})")
                st.divider()
