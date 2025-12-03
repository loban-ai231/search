import streamlit as st
import requests
import json
from urllib.parse import quote
import datetime

# =================== НАСТРОЙКА СТРАНИЦЫ ===================
st.set_page_config(
    page_title="Умный поиск по Notion",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =================== ЗАГРУЗКА КЛЮЧЕЙ ИЗ СЕКРЕТОВ ===================
# ВАЖНО: Никогда не храните ключи прямо в коде!
SERPER_API_KEY = st.secrets.get("SERPER_API_KEY", "")
OMDB_API_KEY = st.secrets.get("OMDB_API_KEY", "")
NOTION_API_KEY = st.secrets.get("NOTION_API_KEY", "")

# =================== ФУНКЦИЯ ПРОВЕРКИ ПОДКЛЮЧЕНИЯ ===================
def test_notion_connection():
    """Проверка подключения к Notion API"""
    if not NOTION_API_KEY:
        return False, "❌ API ключ Notion не найден в секретах"
    
    url = "https://api.notion.com/v1/users/me"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            user_data = response.json()
            user_name = user_data.get('name', 'Неизвестный пользователь')
            return True, f"✅ Подключено как: {user_name}"
        elif response.status_code == 401:
            return False, "❌ Неверный API ключ Notion"
        elif response.status_code == 429:
            return False, "❌ Слишком много запросов. Подождите минуту."
        else:
            return False, f"❌ Ошибка {response.status_code}"
    except Exception as e:
        return False, f"❌ Ошибка подключения: {e}"

# =================== ФУНКЦИЯ ПРОВЕРКИ РЕЛЕВАНТНОСТИ ===================
def check_relevance(query):
    """Проверка, связан ли запрос с Кристофером Ноланом"""
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

# =================== ПОИСК В NOTION ===================
def search_notion_pages(query, filter_by_nolan=True):
    """Поиск по всем страницам Notion"""
    if not NOTION_API_KEY:
        return None, "❌ API ключ Notion не найден"
    
    url = "https://api.notion.com/v1/search"
    
    payload = {
        "query": query,
        "filter": {
            "value": "page",
            "property": "object"
        },
        "page_size": 15,
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
            data = response.json()
            results = data.get("results", [])
            
            notion_results = []
            for item in results:
                try:
                    # Получаем ID страницы
                    page_id = item.get('id', '')
                    
                    # Получаем заголовок страницы
                    title = "Без названия"
                    if 'properties' in item:
                        for prop_name, prop_value in item['properties'].items():
                            if prop_value.get('type') == 'title':
                                title_items = prop_value.get('title', [])
                                if title_items:
                                    for title_item in title_items:
                                        if 'plain_text' in title_item:
                                            title = title_item['plain_text']
                                            break
                                    if title != "Без названия":
                                        break
                    
                    # URL страницы
                    page_url = item.get('url', f"https://www.notion.so/{page_id.replace('-', '')}")
                    
                    # Дата последнего редактирования
                    last_edited = item.get('last_edited_time', '')
                    if last_edited:
                        try:
                            dt = datetime.datetime.fromisoformat(last_edited.replace('Z', '+00:00'))
                            last_edited = dt.strftime("%d.%m.%Y %H:%M")
                        except:
                            pass
                    
                    # Сниппет
                    snippet = "Страница в Notion"
                    
                    notion_results.append({
                        'title': title,
                        'snippet': snippet,
                        'link': page_url,
                        'source': 'Notion',
                        'last_edited': last_edited,
                        'id': page_id
                    })
                    
                except Exception:
                    continue
            
            # Фильтрация по теме Нолана
            if filter_by_nolan and notion_results:
                filtered_results = []
                nolan_keywords = ["нолан", "nolan", "кристофер", "christopher", "опенгеймер", 
                                 "oppenheimer", "интерстеллар", "inception", "тенет", "tenet"]
                
                for result in notion_results:
                    content = (result['title'] + " " + result['snippet']).lower()
                    if any(keyword in content for keyword in nolan_keywords):
                        filtered_results.append(result)
                
                return filtered_results, None
            
            return notion_results, None
        
        elif response.status_code == 401:
            return None, "❌ Неверный API ключ Notion"
        elif response.status_code == 429:
            return None, "❌ Превышен лимит запросов"
        else:
            return None, f"❌ Ошибка API: {response.status_code}"
    
    except Exception as e:
        return None, f"❌ Ошибка подключения: {e}"

# =================== ПОИСК НОВОСТЕЙ ===================
def fetch_google_news(search_query):
    """Поиск новостей через Serper API"""
    if not SERPER_API_KEY:
        return None, "❌ API ключ Serper не найден"
    
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
            articles = data.get("news", [])
            
            processed_articles = []
            for article in articles:
                try:
                    # Обработка источника
                    source_val = article.get('source', 'Google News')
                    if isinstance(source_val, dict):
                        source_text = source_val.get('title', 'Google News')
                    elif isinstance(source_val, str):
                        source_text = source_val
                    else:
                        source_text = 'Google News'
                    
                    processed_articles.append({
                        'title': article.get('title', 'Без заголовка')[:200],
                        'snippet': article.get('snippet', 'Нет описания')[:300],
                        'link': article.get('link', '#'),
                        'source': source_text[:100]
                    })
                    
                except Exception:
                    continue
            
            return processed_articles, None
        
        return None, f"❌ Ошибка Serper API: {response.status_code}"
    
    except Exception as e:
        return None, f"❌ Ошибка подключения: {e}"

# =================== ФИЛЬМОГРАФИЯ ===================
def get_nolan_movies():
    """Получение информации о фильмах Нолана"""
    if not OMDB_API_KEY:
        return None, "❌ API ключ OMDB не найден"
    
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

# =================== ОСНОВНОЙ ИНТЕРФЕЙС ===================
def main():
    # Заголовок приложения
    st.title("🔍 Умный поиск: Notion + Новости")
    st.write("Ищет информацию в вашем Notion и актуальные новости")
    
    # ========== SIDEBAR ==========
    st.sidebar.title("⚙️ Настройки")
    
    # Проверка подключения
    st.sidebar.subheader("Подключение к Notion")
    if NOTION_API_KEY:
        if st.sidebar.button("🔍 Проверить подключение", type="primary"):
            with st.spinner("Проверяем..."):
                success, message = test_notion_connection()
                if success:
                    st.sidebar.success(message)
                else:
                    st.sidebar.error(message)
    else:
        st.sidebar.error("❌ NOTION_API_KEY не найден")
    
    # Статус API
    st.sidebar.subheader("Статус API")
    
    status_col1, status_col2 = st.sidebar.columns(2)
    
    with status_col1:
        st.write("**Notion API:**")
        st.write("✅" if NOTION_API_KEY else "❌")
        
        st.write("**Google News:**")
        st.write("✅" if SERPER_API_KEY else "⚠️")
    
    with status_col2:
        st.write("**Фильмы:**")
        st.write("✅" if OMDB_API_KEY else "⚠️")
    
    # Настройки поиска
    st.sidebar.subheader("Настройки поиска")
    filter_nolan = st.sidebar.checkbox("Только про Нолана", value=True, 
                                      help="Показывать только страницы о Кристофере Нолане")
    
    # Инструкция
    with st.sidebar.expander("📖 Как пользоваться"):
        st.markdown("""
        1. **Введите запрос** в поле поиска
        2. **Нажмите "Найти"** для поиска
        3. **Результаты** появятся ниже
        
        **Примеры запросов:**
        - Новые проекты Нолана
        - Интервью Кристофера
        - Награды Опенгеймера
        - Фильмография
        """)
    
    # ========== ОСНОВНОЕ ОКНО ==========
    # Вкладки
    tab1, tab2, tab3 = st.tabs(["🔎 Поиск", "📚 Все страницы", "🎬 Фильмы"])
    
    # ВКЛАДКА 1: ПОИСК
    with tab1:
        st.subheader("Поиск информации")
        
        # Поле поиска
        col1, col2 = st.columns([3, 1])
        with col1:
            query = st.text_input("Введите запрос:", 
                                 placeholder="новости, интервью, проекты...",
                                 key="search_query")
        
        with col2:
            st.write("")
            st.write("")
            search_clicked = st.button("🔍 Найти", type="primary", use_container_width=True)
        
        if search_clicked and query:
            # Проверка релевантности
            if not check_relevance(query):
                st.warning("⚠️ Этот запрос может быть не связан с Кристофером Ноланом")
                st.info("Попробуйте: новые проекты, интервью Нолана, награды, фильмы")
            
            # Колонки для результатов
            col_left, col_right = st.columns(2)
            
            # ЛЕВАЯ КОЛОНКА: Notion
            with col_left:
                st.markdown("### 📚 Ваш Notion")
                
                if NOTION_API_KEY:
                    with st.spinner("Ищем в ваших страницах..."):
                        notion_results, notion_error = search_notion_pages(query, filter_by_nolan=filter_nolan)
                        
                        if notion_error:
                            st.error(f"Ошибка: {notion_error}")
                        elif notion_results:
                            st.success(f"Найдено {len(notion_results)} страниц")
                            
                            for i, article in enumerate(notion_results[:5], 1):
                                with st.expander(f"{i}. {article['title']}", expanded=i==1):
                                    if article['last_edited']:
                                        st.caption(f"📅 {article['last_edited']}")
                                    st.write(article['snippet'])
                                    st.markdown(f"[🔗 Открыть в Notion]({article['link']})")
                        else:
                            st.info("В вашем Notion ничего не найдено")
                else:
                    st.warning("Добавьте NOTION_API_KEY для поиска")
            
            # ПРАВАЯ КОЛОНКА: Новости
            with col_right:
                st.markdown("### 🌐 Новости")
                
                if SERPER_API_KEY:
                    with st.spinner("Ищем новости..."):
                        news_results, news_error = fetch_google_news(query)
                        
                        if news_error:
                            st.error(f"Ошибка: {news_error}")
                        elif news_results:
                            st.success(f"Найдено {len(news_results)} новостей")
                            
                            for i, article in enumerate(news_results[:5], 1):
                                with st.expander(f"{i}. {article['title']}", expanded=i==1):
                                    st.markdown(f"**Источник:** {article['source']}")
                                    st.write(article['snippet'])
                                    st.markdown(f"[📖 Читать]({article['link']})")
                        else:
                            st.info("Новостей не найдено")
                else:
                    st.info("Добавьте SERPER_API_KEY для поиска новостей")
            
            # Быстрые запросы
            st.markdown("---")
            st.subheader("💡 Попробуйте также:")
            
            quick_queries = ["Интервью Нолана", "Новые проекты", 
                            "Награды Опенгеймера", "Фильмография"]
            
            cols = st.columns(len(quick_queries))
            for idx, q in enumerate(quick_queries):
                with cols[idx]:
                    if st.button(q, key=f"quick_{idx}"):
                        st.session_state.search_query = q
                        st.experimental_rerun()
    
    # ВКЛАДКА 2: ВСЕ СТРАНИЦЫ
    with tab2:
        st.subheader("Все ваши страницы Notion")
        
        if NOTION_API_KEY:
            if st.button("🔄 Загрузить все страницы", type="secondary"):
                with st.spinner("Загружаю..."):
                    all_pages, error = search_notion_pages("", filter_by_nolan=False)
                    
                    if error:
                        st.error(f"Ошибка: {error}")
                    elif all_pages:
                        st.success(f"Всего страниц: {len(all_pages)}")
                        
                        # Поиск по названию
                        search_filter = st.text_input("Фильтр по названию:", 
                                                     placeholder="Введите часть названия...")
                        
                        # Показываем страницы
                        for page in all_pages:
                            if not search_filter or search_filter.lower() in page['title'].lower():
                                with st.expander(f"{page['title']}"):
                                    if page['last_edited']:
                                        st.caption(f"Изменено: {page['last_edited']}")
                                    st.markdown(f"**ID:** `{page['id']}`")
                                    st.markdown(f"[Открыть в Notion →]({page['link']})")
                    else:
                        st.info("Не удалось загрузить страницы")
        else:
            st.error("❌ NOTION_API_KEY не найден")
    
    # ВКЛАДКА 3: ФИЛЬМЫ
    with tab3:
        st.subheader("🎬 Фильмы Кристофера Нолана")
        
        if OMDB_API_KEY:
            with st.spinner("Загружаю фильмы..."):
                movies, error = get_nolan_movies()
                
                if error:
                    st.error(error)
                elif movies:
                    # Сортируем по году
                    movies.sort(key=lambda x: int(x.get('Year', '0')), reverse=True)
                    
                    for movie in movies:
                        with st.container():
                            col_img, col_info = st.columns([1, 3])
                            
                            with col_img:
                                poster = movie.get('Poster', 'N/A')
                                if poster != 'N/A':
                                    st.image(poster, use_column_width=True)
                                else:
                                    st.markdown("""
                                    <div style="height: 300px; display: flex; align-items: center; 
                                                justify-content: center; background: #f0f0f0; 
                                                border-radius: 10px;">
                                        <span style="color: #666;">Постер отсутствует</span>
                                    </div>
                                    """, unsafe_allow_html=True)
                            
                            with col_info:
                                title = movie.get('Title', 'Неизвестный фильм')
                                st.subheader(title)
                                
                                # Информация в колонках
                                info_col1, info_col2, info_col3 = st.columns(3)
                                
                                with info_col1:
                                    year = movie.get('Year', '?')
                                    st.metric("Год", year)
                                
                                with info_col2:
                                    rating = movie.get('imdbRating', '?')
                                    if rating != 'N/A':
                                        st.metric("IMDb", rating)
                                    else:
                                        st.metric("IMDb", "—")
                                
                                with info_col3:
                                    runtime = movie.get('Runtime', '?')
                                    st.metric("Длительность", runtime)
                                
                                # Дополнительная информация
                                st.write(f"**Режиссер:** {movie.get('Director', 'Неизвестно')}")
                                st.write(f"**Жанр:** {movie.get('Genre', 'Неизвестно')}")
                                st.write(f"**Актеры:** {movie.get('Actors', 'Неизвестно')}")
                                
                                plot = movie.get('Plot', 'Нет описания')
                                if plot != 'N/A':
                                    st.write(f"**Описание:** {plot}")
                            
                            st.markdown("---")
                else:
                    st.info("Не удалось загрузить фильмы")
        else:
            st.info("Добавьте OMDB_API_KEY для показа фильмов")
    
    # Футер
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; font-size: 0.9em;">
        <p>🔍 Поиск по Notion API | Ваши ключи хранятся в защищенных секретах</p>
    </div>
    """, unsafe_allow_html=True)

# =================== ЗАПУСК ПРИЛОЖЕНИЯ ===================
if __name__ == "__main__":
    main()
