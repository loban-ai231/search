import streamlit as st
import requests
import json
from urllib.parse import quote

st.set_page_config(page_title="Поиск: Notion + Новости Нолана", layout="wide")

# Загрузка ключей из секретов
SERPER_API_KEY = st.secrets.get("SERPER_API_KEY", "")
OMDB_API_KEY = st.secrets.get("OMDB_API_KEY", "")
NOTION_API_KEY = st.secrets.get("NOTION_API_KEY", "")
# NOTION_DATABASE_ID больше не нужен для поиска по страницам
NOTION_DATABASE_ID = st.secrets.get("NOTION_DATABASE_ID", "")

def test_notion_connection():
    """Проверка подключения к Notion API"""
    if not NOTION_API_KEY:
        return False, "❌ Не хватает API ключа"
    
    # Проверяем, работает ли API
    url = "https://api.notion.com/v1/users/me"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return True, "✅ API ключ работает"
        elif response.status_code == 401:
            return False, "❌ Неверный API ключ"
        else:
            return False, f"❌ Ошибка {response.status_code}: {response.text[:200]}"
    except Exception as e:
        return False, f"❌ Ошибка подключения: {e}"

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

def search_notion_pages(query):
    """Поиск по тексту в страницах Notion"""
    if not NOTION_API_KEY:
        return None, "❌ Добавьте NOTION_API_KEY в секреты"
    
    url = "https://api.notion.com/v1/search"
    
    payload = {
        "query": query,
        "filter": {
            "value": "page",
            "property": "object"
        },
        "page_size": 10
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
                    # Получаем заголовок страницы
                    title = "Без названия"
                    if 'properties' in item:
                        # Ищем свойство с заголовком (обычно это 'title')
                        for prop_name, prop_value in item['properties'].items():
                            prop_type = prop_value.get('type')
                            if prop_type == 'title':
                                title_data = prop_value.get('title', [])
                                if title_data and isinstance(title_data, list):
                                    for title_item in title_data:
                                        if 'plain_text' in title_item:
                                            title = title_item['plain_text']
                                            break
                    
                    # Пытаемся получить сниппет из rich_text
                    snippet = "Нажмите, чтобы открыть страницу в Notion"
                    if 'properties' in item:
                        for prop_name, prop_value in item['properties'].items():
                            if prop_value.get('type') == 'rich_text':
                                rich_text = prop_value.get('rich_text', [])
                                if rich_text and isinstance(rich_text, list):
                                    text_parts = []
                                    for text_item in rich_text[:2]:
                                        if 'plain_text' in text_item:
                                            text_parts.append(text_item['plain_text'])
                                    if text_parts:
                                        snippet = " ".join(text_parts)[:150] + "..."
                                        break
                    
                    page_url = item.get('url', '#')
                    
                    # Фильтруем только релевантные страницы (по ключевым словам)
                    content_to_check = (title + " " + snippet).lower()
                    nolan_keywords = ["нолан", "nolan", "кристофер", "christopher", "опенгеймер", "oppenheimer"]
                    
                    if any(keyword in content_to_check for keyword in nolan_keywords):
                        notion_articles.append({
                            'title': title,
                            'snippet': snippet,
                            'link': page_url,
                            'source': 'Notion Page'
                        })
                        
                except Exception as e:
                    continue
            
            return notion_articles, None
        
        return None, f"Ошибка Notion API: {response.status_code}. Ответ: {response.text[:200]}"
    
    except requests.exceptions.RequestException as e:
        return None, f"Ошибка подключения к Notion API: {e}"

def fetch_google_news(search_query):
    if not SERPER_API_KEY:
        return None, "❌ Добавьте SERPER_API_KEY в секреты"
    
    # Проверка на релевантность для добавления имени Нолана
    relevant_keywords = ["нолан", "nolan", "кристофер", "christopher"]
    if not any(keyword in search_query.lower() for keyword in relevant_keywords):
        final_query = f"Christopher Nolan {search_query}"
    else:
        final_query = search_query

    url = "https://google.serper.dev/news"
    payload = json.dumps({
        "q": final_query, 
        "gl": "ru", 
        "hl": "ru", 
        "tbs": "qdr:w",
        "num": 10
    })
    
    headers = {
        'X-API-KEY': SERPER_API_KEY, 
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            google_articles = data.get("news", [])
            
            processed_articles = []
            for article in google_articles:
                try:
                    # Безопасная обработка источника
                    source_val = article.get('source', 'Google News')
                    
                    if isinstance(source_val, dict):
                        source_text = source_val.get('title', 'Google News')
                    elif isinstance(source_val, str):
                        source_text = source_val
                    else:
                        source_text = 'Google News'
                    
                    # Безопасная обработка сниппета
                    snippet = article.get('snippet', 'Нет описания')
                    if not snippet or snippet == '':
                        snippet = 'Нет описания'
                    
                    # Безопасная обработка заголовка
                    title = article.get('title', 'Без заголовка')
                    if not title or title == '':
                        title = 'Без заголовка'
                    
                    # Безопасная обработка ссылки
                    link = article.get('link', '#')
                    
                    processed_articles.append({
                        'title': title[:200],  # Ограничиваем длину
                        'snippet': snippet[:300],  # Ограничиваем длину
                        'link': link,
                        'source': source_text[:100]  # Ограничиваем длину
                    })
                    
                except Exception as e:
                    # Пропускаем проблемные статьи
                    continue
            
            return processed_articles, None
        
        elif response.status_code == 401:
            return None, "❌ Неверный API ключ Serper"
        elif response.status_code == 429:
            return None, "❌ Превышен лимит запросов Serper API"
        else:
            return None, f"❌ Ошибка Serper API: {response.status_code}"
    
    except requests.exceptions.Timeout:
        return None, "❌ Таймаут подключения к Serper API"
    except requests.exceptions.RequestException as e:
        return None, f"❌ Ошибка подключения к Serper API: {e}"
    except json.JSONDecodeError as e:
        return None, f"❌ Ошибка парсинга ответа Serper API: {e}"
    except Exception as e:
        return None, f"❌ Неизвестная ошибка: {e}"

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

# Интерфейс Streamlit
st.title("🎬Поиск: Notion + Новости Нолана")
st.write("Поиск по вашим страницам Notion и актуальным новостям Google.")

# Sidebar
st.sidebar.header("Статус API")
if SERPER_API_KEY:
    st.sidebar.success("Serper API (Google News): ✔️")
else:
    st.sidebar.error("Serper API: ❌")

if NOTION_API_KEY:
    st.sidebar.success("Notion API (Поиск по страницам): ✔️")
else:
    st.sidebar.error("Notion API: ❌")

if OMDB_API_KEY:
    st.sidebar.success("OMDB API (Фильмы): ✔️")
else:
    st.sidebar.error("OMDB API: ❌")

# Диагностика Notion
st.sidebar.markdown("---")
st.sidebar.subheader("Диагностика Notion")

if st.sidebar.button("🔍 Проверить подключение к Notion"):
    with st.sidebar:
        with st.spinner("Проверяем подключение..."):
            success, message = test_notion_connection()
            if success:
                st.success(message)
            else:
                st.error(message)

# Вкладки
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

        # Поиск в Notion (по страницам)
        notion_results = []
        notion_error = None
        
        with st.spinner("Шаг 1: Ищу в ваших страницах Notion..."):
            query_for_notion = user_query if user_query else "Christopher Nolan"
            notion_results, notion_error = search_notion_pages(query_for_notion)
        
        st.markdown("---")
        
        if notion_error:
            st.error(f"Ошибка поиска в Notion: {notion_error}")
            notion_results = []
        
        if notion_results:
            st.success(f"✅ Найдено **{len(notion_results)}** страниц в Notion:")
            for article in notion_results:
                with st.expander(article['title']):
                    st.markdown(f"**Источник:** {article['source']}")
                    st.write(article['snippet'])
                    st.markdown(f"[Открыть в Notion →]({article['link']})")
        else:
            st.info("❌ В ваших страницах Notion ничего не найдено.")
            
        # Поиск в Google News
        google_results = []
        google_error = None
        
        # После поиска в Notion и перед отображением Google News
st.markdown("---")

if SERPER_API_KEY:
    with st.spinner("Шаг 2: Ищу актуальные новости в Google..."):
        google_results, google_error = fetch_google_news(user_query)
else:
    st.warning("Google News API не настроен, пропуск Шага 2.")
    google_results = []
    google_error = None

# Отображение результатов Google News
if google_error:
    st.error(f"Ошибка поиска Google: {google_error}")
elif google_results:
    st.success(f"🌐 Найдено **{len(google_results)}** актуальных новостей в Google News:")
    
    for i, article in enumerate(google_results[:10], 1):
        with st.expander(f"{i}. {article['title']}"):
            st.markdown(f"**Источник:** {article.get('source', 'Google News')}")
            st.write(article.get('snippet', 'Нет описания'))
            st.markdown(f"[Читать полную статью →]({article['link']})")
    
    # Показать, сколько результатов скрыто
    if len(google_results) > 10:
        st.info(f"Показано 10 из {len(google_results)} найденных новостей.")
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
                        else:
                            st.write("Постер отсутствует")
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

# Инструкция
with st.sidebar.expander("ℹ️ Как это работает"):
    st.markdown("""
    ### Поиск по страницам Notion
    
    1. **Приложение ищет текст** во всех ваших страницах Notion
    2. **Фильтрует результаты** по ключевым словам Нолана
    3. **Показывает найденные страницы** с кратким описанием
    
    ### Что нужно сделать:
    
    1. Убедитесь, что интеграция имеет доступ к страницам
    2. Добавьте информацию о Нолане в ваши страницы
    3. Используйте ключевые слова для лучшего поиска
    
    ### Примеры запросов:
    - "Нолан новые фильмы"
    - "Опенгеймер"
    - "Интерстеллар"
    - "Награды Кристофера Нолана"
    """)
