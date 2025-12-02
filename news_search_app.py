import streamlit as st
import requests
import json
from urllib.parse import quote

st.set_page_config(page_title="Гибридный Поиск: Notion + Новости Нолана", layout="wide")

# Загрузка ключей из секретов
SERPER_API_KEY = st.secrets.get("SERPER_API_KEY", "")
OMDB_API_KEY = st.secrets.get("OMDB_API_KEY", "")
NOTION_API_KEY = st.secrets.get("NOTION_API_KEY", "")

def test_notion_connection():
    """Проверка подключения к Notion API"""
    if not NOTION_API_KEY:
        return False, "❌ Не хватает API ключа Notion"
    
    url = "https://api.notion.com/v1/users/me"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            user_data = response.json()
            user_name = user_data.get('name', 'Пользователь')
            return True, f"✅ Подключено как: {user_name}"
        elif response.status_code == 401:
            return False, "❌ Неверный API ключ Notion"
        else:
            return False, f"❌ Ошибка {response.status_code}"
    except Exception as e:
        return False, f"❌ Ошибка подключения: {e}"

def check_relevance(query):
    """Проверка релевантности запроса теме Кристофера Нолана"""
    if not query:
        return True 
        
    query_lower = query.lower()
    
    relevant_keywords = [
        "нолан", "nolan", "кристофер", "christopher", 
        "опенгеймер", "oppenheimer", "tenet", "интерстеллар", 
        "inception", "темный рыцарь", "dark knight", "престиж", "prestige", 
        "memento", "помни", "дюнкерк", "dunkirk", "бэтмен", "batman",
        "кинематограф", "режиссер", "фильм", "кино"
    ]
    
    general_keywords = ["актер", "фильм", "новость", "проект", "награда", "критик", "год", "бюджет"]
    
    if any(keyword in query_lower for keyword in relevant_keywords):
        return True
    
    if any(keyword in query_lower for keyword in general_keywords):
        return True

    return False

def search_notion_pages(query):
    """Поиск по всем страницам Notion"""
    if not NOTION_API_KEY:
        return None, "❌ Добавьте NOTION_API_KEY в секреты для поиска по Notion"
    
    url = "https://api.notion.com/v1/search"
    
    payload = {
        "query": query,
        "filter": {
            "value": "page",
            "property": "object"
        },
        "page_size": 20,
        "sort": {
            "direction": "descending",
            "timestamp": "last_edited_time"
        }
    }
    
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        
        if response.status_code == 200:
            results = response.json().get("results", [])
            
            notion_results = []
            for item in results:
                try:
                    # Получаем заголовок страницы
                    title = "Без названия"
                    page_id = item.get('id', '')
                    
                    # Пытаемся найти заголовок в разных местах
                    if 'properties' in item:
                        # Проверяем несколько возможных свойств с заголовком
                        for prop_name, prop_value in item['properties'].items():
                            if prop_value.get('type') == 'title':
                                title_items = prop_value.get('title', [])
                                if title_items and isinstance(title_items, list):
                                    for title_item in title_items:
                                        if title_item.get('type') == 'text' and title_item.get('plain_text'):
                                            title = title_item.get('plain_text')
                                            break
                                    if title != "Без названия":
                                        break
                    
                    # Пытаемся получить сниппет (первые 200 символов текста)
                    snippet = "Нажмите, чтобы открыть страницу"
                    last_edited = item.get('last_edited_time', '')
                    
                    # URL страницы
                    page_url = item.get('url', f"https://www.notion.so/{page_id.replace('-', '')}")
                    
                    notion_results.append({
                        'title': title,
                        'snippet': snippet,
                        'link': page_url,
                        'source': 'Notion Page',
                        'last_edited': last_edited,
                        'id': page_id
                    })
                    
                except Exception as e:
                    continue
            
            # Фильтруем результаты, чтобы показывать только релевантные
            filtered_results = []
            for result in notion_results:
                # Проверяем, содержит ли заголовок или сниппет ключевые слова о Нолане
                content_for_check = (result['title'] + " " + result['snippet']).lower()
                nolan_keywords = ["нолан", "nolan", "кристофер", "christopher", "опенгеймер", 
                                 "oppenheimer", "интерстеллар", "inception", "тенет", "tenet"]
                
                if any(keyword in content_for_check for keyword in nolan_keywords):
                    filtered_results.append(result)
            
            return filtered_results, None
        
        elif response.status_code == 401:
            return None, "❌ Неверный API ключ Notion"
        elif response.status_code == 429:
            return None, "❌ Слишком много запросов. Попробуйте позже."
        else:
            return None, f"❌ Ошибка Notion API: {response.status_code}"
    
    except requests.exceptions.Timeout:
        return None, "❌ Таймаут подключения к Notion"
    except requests.exceptions.RequestException as e:
        return None, f"❌ Ошибка подключения к Notion: {e}"

def fetch_google_news(search_query):
    """Поиск новостей в Google через Serper API"""
    if not SERPER_API_KEY:
        return None, "❌ Добавьте SERPER_API_KEY в секреты"
    
    # Добавляем "Christopher Nolan" если запрос не содержит ключевых слов
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
                        'title': title[:200],
                        'snippet': snippet[:300],
                        'link': link,
                        'source': source_text[:100]
                    })
                    
                except Exception as e:
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

def get_nolan_movies():
    """Получение информации о фильмах Нолана из OMDB"""
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
st.title("🔍 Гибридный поиск: Notion + Новости о Кристофере Нолане")
st.write("Ищет информацию по вашим страницам Notion и в актуальных новостях Google")

# Sidebar с настройками
st.sidebar.header("Настройки API")

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

# Основные вкладки
tab1, tab2 = st.tabs(["🔎 Гибридный поиск", "🎬 Фильмография"])

with tab1:
    user_query = st.text_input("Введите запрос о Кристофере Нолане:", placeholder="например: новые проекты, интервью, награды")
    
    search_button = st.button("🔎 Найти информацию", type="primary")
    
    if search_button and user_query:
        
        # Проверка релевантности
        if not check_relevance(user_query):
            st.error("❌ Этот запрос не связан с Кристофером Ноланом")
            st.info("Попробуйте использовать ключевые слова: Нолан, фильмы, проекты, награды, интервью")
            st.stop()
        
        # Поиск в Notion
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📚 Поиск по вашим страницам Notion")
            with st.spinner("Ищем в ваших страницах Notion..."):
                notion_results, notion_error = search_notion_pages(user_query)
                
                if notion_error:
                    st.error(f"Ошибка поиска в Notion: {notion_error}")
                elif notion_results:
                    st.success(f"Найдено {len(notion_results)} страниц:")
                    
                    for article in notion_results:
                        with st.expander(f"📄 {article['title']}"):
                            st.markdown(f"**Последнее изменение:** {article['last_edited'][:10] if article['last_edited'] else 'Неизвестно'}")
                            st.markdown(f"**ID страницы:** `{article['id']}`")
                            st.markdown(f"[Открыть в Notion →]({article['link']})")
                else:
                    st.info("По вашему запросу в Notion ничего не найдено")
        
        with col2:
            st.subheader("🌐 Новости из интернета")
            if SERPER_API_KEY:
                with st.spinner("Ищем актуальные новости..."):
                    google_results, google_error = fetch_google_news(user_query)
                    
                    if google_error:
                        st.error(f"Ошибка поиска новостей: {google_error}")
                    elif google_results:
                        st.success(f"Найдено {len(google_results)} новостей:")
                        
                        for article in google_results[:5]:  # Показываем только 5
                            with st.expander(f"📰 {article['title']}"):
                                st.markdown(f"**Источник:** {article['source']}")
                                st.write(article['snippet'])
                                st.markdown(f"[Читать статью →]({article['link']})")
                    else:
                        st.info("По вашему запросу новостей не найдено")
            else:
                st.warning("Добавьте SERPER_API_KEY для поиска новостей")
        
        # Альтернативные запросы
        st.markdown("---")
        st.subheader("💡 Попробуйте также:")
        suggestions = ["интервью Нолана", "новые проекты", "награды", "фильмография", "критика"]
        
        cols = st.columns(len(suggestions))
        for idx, suggestion in enumerate(suggestions):
            with cols[idx]:
                if st.button(suggestion, key=f"sugg_{idx}"):
                    st.experimental_set_query_params(query=suggestion)
                    st.experimental_rerun()

with tab2:
    st.subheader("🎞 Фильмы Кристофера Нолана")
    
    if OMDB_API_KEY:
        with st.spinner("Загружаю информацию о фильмах..."):
            movies, error = get_nolan_movies()
            
            if error:
                st.error(error)
            elif movies:
                # Сортируем фильмы по году выхода
                movies.sort(key=lambda x: int(x.get('Year', '0')), reverse=True)
                
                for movie in movies:
                    with st.container():
                        col1, col2 = st.columns([1, 3])
                        
                        with col1:
                            if movie.get('Poster') != 'N/A':
                                st.image(movie['Poster'], use_column_width=True)
                            else:
                                st.write("🖼 Постер отсутствует")
                        
                        with col2:
                            st.subheader(movie.get('Title', 'Неизвестный фильм'))
                            
                            col_year, col_rating = st.columns(2)
                            with col_year:
                                st.metric("Год", movie.get('Year', '?'))
                            with col_rating:
                                rating = movie.get('imdbRating', '?')
                                if rating != 'N/A':
                                    st.metric("Рейтинг IMDb", rating)
                            
                            st.write(f"**Режиссер:** {movie.get('Director', 'Неизвестно')}")
                            st.write(f"**Жанр:** {movie.get('Genre', 'Неизвестно')}")
                            st.write(f"**Актеры:** {movie.get('Actors', 'Неизвестно')}")
                            st.write(f"**Описание:** {movie.get('Plot', 'Нет описания')}")
                        
                        st.markdown("---")
            else:
                st.info("Не удалось загрузить информацию о фильмах")
    else:
        st.info("Добавьте OMDB_API_KEY для загрузки фильмографии")

# Инструкции в sidebar
with st.sidebar.expander("ℹ️ Как это работает"):
    st.markdown("""
    ### 🔍 Поиск по Notion:
    - Ищет текст во всех ваших страницах Notion
    - Показывает страницы, содержащие запрос
    - Фильтрует только страницы о Кристофере Нолане
    
    ### 🌐 Поиск новостей:
    - Ищет актуальные новости через Google
    - Автоматически добавляет "Christopher Nolan" к запросу
    - Показывает самые свежие результаты
    
    ### 🎬 Фильмография:
    - Показывает информацию о фильмах Нолана
    - Использует OMDB API для данных
    - Включает постеры, рейтинги и описания
    
    ### 📌 Рекомендации:
    1. Убедитесь, что в вашем Notion есть страницы о Кристофере Нолане
    2. Используйте ключевые слова для поиска
    3. Проверьте подключение через кнопку в sidebar
    """)

# Футер
st.markdown("---")
st.caption("Приложение для поиска информации о Кристофере Нолане | Поиск по Notion + Google News")
