import streamlit as st
import requests
import json
from urllib.parse import quote

st.set_page_config(page_title="Гибридный Поиск: Notion + Новости Нолана", layout="wide")

SERPER_API_KEY = st.secrets.get("SERPER_API_KEY", "")
OMDB_API_KEY = st.secrets.get("OMDB_API_KEY", "")
NOTION_API_KEY = st.secrets.get("NOTION_API_KEY", "")
NOTION_DATABASE_ID = st.secrets.get("NOTION_DATABASE_ID", "")

def check_relevance(query):
    if not query:
        return True 
        
    query_lower = query.lower()
    
    relevant_keywords = [
        "нолан", "nolan", "кристофер", "christopher", 
        "опенгеймер", "oppenheimer", "tenet", "интерстеллар", 
        "inception", "темный рыцарь", "dark knight", "престиж", "prestige", 
        "memento", "помни", "дюнкерк", "dunkirk", "бэтмен", "batman"
    ]
    
    general_keywords = ["актер", "фильм", "новость", "проект", "награда", "критик", "год", "бюджет"]
    
    if any(keyword in query_lower for keyword in relevant_keywords):
        return True
    
    if any(keyword in query_lower for keyword in general_keywords):
        return True

    return False

def search_notion_database(query):
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        return None, "❌ Добавьте NOTION_API_KEY и NOTION_DATABASE_ID в секреты для локального поиска"

    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    
    payload = {
        "filter": {
            "property": "Name", 
            "title": {
                "contains": query
            }
        }
    }
    
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28" 
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            results = response.json().get("results", [])
            
            notion_articles = []
            for item in results:
                try:
                    title = item['properties']['Name']['title'][0]['plain_text']
                    page_url = item['url']
                    
                    try:
                        snippet = ", ".join([tag['name'] for tag in item['properties']['Теги']['multi_select']])
                    except:
                        snippet = "Нажмите, чтобы открыть страницу в Notion"
                        
                    notion_articles.append({
                        'title': title,
                        'snippet': snippet,
                        'link': page_url,
                        'source': 'Notion Database'
                    })
                except Exception as e:
                    st.error(f"Ошибка парсинга записи Notion: {e}")
                    continue
            return notion_articles, None
        
        return None, f"Ошибка Notion API: {response.status_code}. Ответ: {response.text[:100]}..."
    except requests.exceptions.RequestException as e:
        return None, f"Ошибка подключения к Notion API: {e}"

def fetch_google_news(search_query):
    if not SERPER_API_KEY:
        return None, "❌ Добавьте SERPER_API_KEY в секреты"
    
    relevant_keywords = ["нолан", "nolan", "кристофер", "christopher"]
    if not any(keyword in search_query.lower() for keyword in relevant_keywords):
        final_query = f"Christopher Nolan {search_query}"
    else:
        final_query = search_query


    url = "https://google.serper.dev/news"
    payload = json.dumps({"q": final_query, "gl": "ru", "hl": "ru", "tbs": "qdr:w"})
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        if response.status_code == 200:
            google_articles = response.json().get("news", [])
            for article in google_articles:
                article['source'] = article.get('source', {}).get('title', 'Google News')
            return google_articles, None
        return None, f"Ошибка Serper API: {response.status_code}"
    except requests.exceptions.RequestException as e:
        return None, f"Ошибка подключения к Serper API: {e}"

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

st.title("🎬 Гибридный Поиск: Notion + Новости Нолана")
st.write("Сначала поиск в вашей базе данных Notion, затем в актуальных новостях Google. Блокирует запросы не по теме.")

st.sidebar.header("Статус API")
if SERPER_API_KEY:
    st.sidebar.success("Serper API (Google News): ✔️")
else:
    st.sidebar.error("Serper API: ❌")
if NOTION_API_KEY and NOTION_DATABASE_ID:
    st.sidebar.success("Notion API (Локальный поиск): ✔️")
else:
    st.sidebar.error("Notion API: ❌")
if OMDB_API_KEY:
    st.sidebar.success("OMDB API (Фильмы): ✔️")
else:
    st.sidebar.error("OMDB API: ❌")


tab1, tab2 = st.tabs(["🔎 Гибридный Поиск", "🎞 Фильмы (OMDB)"])

with tab1:
    user_query = st.text_input("Введите запрос, связанный с Кристофером Ноланом:", "новые проекты")
    
    if st.button("🔎 Найти информацию"):
        
        if not check_relevance(user_query):
            st.markdown("---")
            st.markdown(
                f"""
                <div style="background-color: #381212; padding: 15px; border-radius: 10px; border-left: 5px solid #E63946;">
                    <h4><span style="color: #E63946;">🛑 Этот запрос не связан с Кристофером Ноланом</span></h4>
                    <p>Вы искали: <b>{user_query}</b></p>
                    <p>Эта система ищет только информацию, связанную с Кристофером Ноланом, его фильмами, актерами и проектами.</p>
                </div>
                """, unsafe_allow_html=True
            )
            st.markdown("---")
            
            st.subheader("💡 Попробуйте найти в Google:")
            google_search_link = f"https://www.google.com/search?q={quote(user_query)}"
            st.markdown(f"**[Поиск \"{user_query}\" в Google →]({google_search_link})**", unsafe_allow_html=True)
            st.stop()

        notion_results = []
        notion_error = None
        
        with st.spinner("Шаг 1: Ищу в базе данных Notion..."):
            query_for_notion = user_query if user_query else "Christopher Nolan"
            notion_results, notion_error = search_notion_database(query_for_notion)
        
        st.markdown("---")


        if notion_error and NOTION_API_KEY:
             st.error(f"Ошибка локального поиска Notion: {notion_error}")
             notion_results = []
        
        if notion_results:
            st.success(f"✅ Найдено **{len(notion_results)}** локальных записей в Notion:")
            for article in notion_results:
                with st.expander(article['title']):
                    st.markdown(f"**Источник:** {article['source']}")
                    st.write(article['snippet'])
                    st.markdown(f"[Открыть в Notion →]({article['link']})")
        else:
            st.info("❌ В базе данных Notion ничего не найдено.")
            
        
        google_results = []
        google_error = None
        
        st.markdown("---")
        
        if SERPER_API_KEY:
            with st.spinner("Шаг 2: Ищу актуальные новости в Google..."):
                google_results, google_error = fetch_google_news(user_query)
        else:
            st.warning("Google News API не настроен, пропуск Шага 2.")

        if google_error:
            st.error(f"Ошибка поиска Google: {google_error}")
        elif google_results:
            st.success(f"🌐 Найдено **{len(google_results)}** актуальных новостей в Google News:")
            for article in google_results[:10]:
                with st.expander(article['title']):
                    st.markdown(f"**Источник:** {article.get('source', 'Google News')}")
                    st.write(article.get('snippet', 'Нет описания'))
                    st.markdown(f"[Читать полную статью →]({article['link']})")
        elif SERPER_API_KEY:
            st.info("❌ Актуальных новостей в Google News не найдено.")


with tab2:
    st.subheader("Основные фильмы Кристофера Нолана")
    st.markdown("---")
    if OMDB_API_KEY:
        with st.spinner("Загружаю фильмы..."):
            movies, error = get_nolan_movies()
            if error:
                st.error(error)
            elif movies:
                for movie in movies:
                    st.markdown("---")
                    st.subheader(movie.get('Title'))
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        if movie.get('Poster') != 'N/A':
                            st.image(movie['Poster'], use_column_width=True)
                    with col2:
                        st.write(f"**Год:** {movie.get('Year')}")
                        st.write(f"**Рейтинг IMDb:** {movie.get('imdbRating')}")
                        st.write(f"**Режиссер:** {movie.get('Director')}")
                        st.write(f"**Жанр:** {movie.get('Genre')}")
                        st.write(f"**Краткое содержание:** {movie.get('Plot')}")
            else:
                st.info("Не удалось загрузить информацию о фильмах.")
    else:
        st.info("Добавьте OMDB_API_KEY для загрузки фильмов")
