import streamlit as st
import requests
from urllib.parse import quote
import json

# --- Настройки страницы ---
st.set_page_config(page_title="Новости Кристофера Нолана", layout="wide")

# Получаем ключи из секретов Streamlit
SERPER_API_KEY = st.secrets.get("SERPER_API_KEY", "")
OMDB_API_KEY = st.secrets.get("OMDB_API_KEY", "")

# --- Функции API ---
def fetch_google_news(search_query):
    if not SERPER_API_KEY:
        return None, "❌ Добавьте SERPER_API_KEY в секреты"
    
    url = "https://google.serper.dev/news"
    payload = json.dumps({"q": search_query, "gl": "ru", "hl": "ru", "tbs": "qdr:w"})
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        if response.status_code == 200:
            return response.json().get("news", []), None
        return None, f"Ошибка API: {response.status_code}"
    except:
        return None, "Ошибка подключения"

def get_nolan_movies():
    if not OMDB_API_KEY:
        return None, "❌ Добавьте OMDB_API_KEY в секреты"
    
    movies = []
    titles = ["Inception", "Interstellar", "The Dark Knight", "Oppenheimer", 
              "Tenet", "Dunkirk", "Memento", "The Prestige"]
    
    for title in titles:
        try:
            url = f"http://www.omdbapi.com/?t={quote(title)}&apikey={OMDB_API_KEY}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("Response") == "True":
                    movies.append(data)
        except:
            continue
    
    return movies, None

# --- Интерфейс ---
st.title("🎬 Новости о Кристофере Нолане")
st.write("Поиск актуальных новостей и информации о фильмах")

# Проверка ключей
if not SERPER_API_KEY:
    st.error("Добавьте SERPER_API_KEY в секреты Streamlit Cloud")
if not OMDB_API_KEY:
    st.warning("Добавьте OMDB_API_KEY для загрузки информации о фильмах")

tab1, tab2 = st.tabs(["📰 Новости", "🎞️ Фильмы"])

with tab1:
    if SERPER_API_KEY:
        search = st.text_input("Поиск новостей:", "Christopher Nolan")
        if st.button("Искать"):
            with st.spinner("Загружаю новости..."):
                articles, error = fetch_google_news(search)
                if error:
                    st.error(error)
                elif articles:
                    for article in articles[:10]:
                        with st.expander(article['title']):
                            st.write(article.get('snippet', 'Нет описания'))
                            st.markdown(f"[Читать →]({article['link']})")
                else:
                    st.info("Новостей не найдено")

with tab2:
    if OMDB_API_KEY:
        with st.spinner("Загружаю фильмы..."):
            movies, error = get_nolan_movies()
            if error:
                st.error(error)
            elif movies:
                for movie in movies:
                    st.subheader(movie.get('Title'))
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        if movie.get('Poster') != 'N/A':
                            st.image(movie['Poster'])
                    with col2:
                        st.write(f"**Год:** {movie.get('Year')}")
                        st.write(f"**Рейтинг IMDb:** {movie.get('imdbRating')}")
                        st.write(f"**Режиссер:** {movie.get('Director')}")
    else:
        st.info("Добавьте OMDB_API_KEY для загрузки фильмов")
