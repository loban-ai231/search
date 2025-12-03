import streamlit as st
import requests
import json
import datetime
import re

# =================== НАСТРОЙКА СТРАНИЦЫ ===================
st.set_page_config(
    page_title="🔍 Умный поиск по содержимому Notion",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =================== ЗАГРУЗКА КЛЮЧЕЙ ===================
SERPER_API_KEY = st.secrets.get("SERPER_API_KEY", "")
OMDB_API_KEY = st.secrets.get("OMDB_API_KEY", "")
NOTION_API_KEY = st.secrets.get("NOTION_API_KEY", "")

# =================== ФУНКЦИИ ДЛЯ РАБОТЫ С NOTION ===================
def get_all_notion_pages():
    """Получает ВСЕ страницы из Notion"""
    if not NOTION_API_KEY:
        return None, "❌ API ключ Notion не найден"
    
    all_pages = []
    has_more = True
    next_cursor = None
    
    url = "https://api.notion.com/v1/search"
    
    while has_more:
        payload = {
            "filter": {
                "value": "page",
                "property": "object"
            },
            "page_size": 100,  # Максимальный размер страницы
            "sort": {
                "direction": "descending",
                "timestamp": "last_edited_time"
            }
        }
        
        if next_cursor:
            payload["start_cursor"] = next_cursor
        
        headers = {
            "Authorization": f"Bearer {NOTION_API_KEY}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                all_pages.extend(results)
                
                has_more = data.get("has_more", False)
                next_cursor = data.get("next_cursor")
                
                # Если у нас уже много страниц, можно ограничить
                if len(all_pages) >= 200:  # Ограничим 200 страницами
                    has_more = False
                    
            elif response.status_code == 401:
                return None, "❌ Неверный API ключ Notion"
            elif response.status_code == 429:
                return None, "❌ Превышен лимит запросов"
            else:
                return None, f"❌ Ошибка API: {response.status_code}"
                
        except Exception as e:
            return None, f"❌ Ошибка подключения: {e}"
    
    return all_pages, None

def extract_text_from_block(block):
    """Извлекает текст из одного блока Notion"""
    block_type = block.get('type')
    text_content = ""
    
    # Проверяем, есть ли текст в блоке
    if block_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3', 
                     'heading_4', 'heading_5', 'heading_6', 'bulleted_list_item', 
                     'numbered_list_item', 'to_do', 'toggle', 'quote', 'callout']:
        
        rich_text = block.get(block_type, {}).get('rich_text', [])
        for text_item in rich_text:
            if 'plain_text' in text_item:
                text_content += text_item['plain_text'] + " "
    
    # Для таблиц, кодовых блоков и других специальных типов
    elif block_type == 'code':
        rich_text = block.get('code', {}).get('rich_text', [])
        for text_item in rich_text:
            if 'plain_text' in text_item:
                text_content += text_item['plain_text'] + " "
    
    return text_content.strip()

def get_page_content_with_cache(page_id):
    """Получает содержимое страницы с кэшированием"""
    # Используем кэширование Streamlit
    @st.cache_data(ttl=600)  # Кэш на 10 минут
    def _get_page_content(page_id):
        return get_page_content_impl(page_id)
    
    return _get_page_content(page_id)

def get_page_content_impl(page_id):
    """Получает содержимое страницы Notion (реализация)"""
    if not NOTION_API_KEY:
        return "", "❌ API ключ Notion не найден"
    
    all_text = ""
    
    # Получаем блоки страницы с пагинацией
    has_more = True
    next_cursor = None
    
    while has_more:
        url = f"https://api.notion.com/v1/blocks/{page_id}/children"
        params = {"page_size": 100}
        
        if next_cursor:
            params["start_cursor"] = next_cursor
        
        headers = {
            "Authorization": f"Bearer {NOTION_API_KEY}",
            "Notion-Version": "2022-06-28"
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                blocks = data.get('results', [])
                
                for block in blocks:
                    # Извлекаем текст из блока
                    block_text = extract_text_from_block(block)
                    if block_text:
                        all_text += block_text + "\n"
                    
                    # Рекурсивно проверяем дочерние блоки
                    if block.get('has_children'):
                        child_text, _ = get_page_content_impl(block['id'])
                        if child_text:
                            all_text += child_text + "\n"
                
                has_more = data.get('has_more', False)
                next_cursor = data.get('next_cursor')
                
            elif response.status_code == 404:
                return "", "❌ Страница не найдена"
            else:
                return "", f"❌ Ошибка при получении содержимого: {response.status_code}"
                
        except Exception as e:
            return "", f"❌ Ошибка подключения: {e}"
    
    return all_text, None

def search_in_content(pages, query, filter_by_nolan=True, max_pages=20):
    """Ищет запрос в содержимом страниц"""
    if not pages:
        return [], "Нет страниц для поиска"
    
    results = []
    search_query = query.lower()
    query_words = search_query.split()
    
    # Ключевые слова для фильтрации по Нолану
    nolan_keywords = ["нолан", "nolan", "кристофер", "christopher", "опенгеймер", 
                     "oppenheimer", "интерстеллар", "interstellar", "инсепшн", 
                     "inception", "тенет", "tenet", "дюнкерк", "dunkirk", 
                     "мементо", "memento", "престиж", "prestige"]
    
    # Ограничиваем количество проверяемых страниц для скорости
    pages_to_check = min(max_pages, len(pages))
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, page in enumerate(pages[:pages_to_check]):
        status_text.text(f"🔍 Проверяю страницу {i+1}/{pages_to_check}")
        progress_bar.progress((i + 1) / pages_to_check)
        
        try:
            # Получаем заголовок страницы
            title = "Без названия"
            properties = page.get('properties', {})
            
            for prop_name, prop_value in properties.items():
                if prop_value.get('type') == 'title':
                    title_items = prop_value.get('title', [])
                    for title_item in title_items:
                        if 'plain_text' in title_item:
                            title = title_item['plain_text']
                            break
                if title != "Без названия":
                    break
            
            # Получаем ID страницы
            page_id = page.get('id', '')
            
            # Получаем содержимое страницы
            page_content, content_error = get_page_content_with_cache(page_id)
            
            if content_error:
                continue
            
            # Объединяем заголовок и содержимое для поиска
            search_text = (title + " " + page_content).lower()
            
            # Проверяем, содержит ли страница запрос
            matches_query = False
            
            # Ищем все слова запроса
            if all(word in search_text for word in query_words if len(word) > 2):
                matches_query = True
            elif search_query in search_text:
                matches_query = True
            
            # Проверяем фильтр по Нолану
            matches_nolan = True
            if filter_by_nolan:
                matches_nolan = any(keyword in search_text for keyword in nolan_keywords)
            
            # Если страница соответствует критериям
            if matches_query and matches_nolan:
                # URL страницы
                page_url = page.get('url', f"https://www.notion.so/{page_id.replace('-', '')}")
                
                # Дата последнего редактирования
                last_edited = page.get('last_edited_time', '')
                if last_edited:
                    try:
                        dt = datetime.datetime.fromisoformat(last_edited.replace('Z', '+00:00'))
                        last_edited = dt.strftime("%d.%m.%Y %H:%M")
                    except:
                        pass
                
                # Создаем сниппет с подсветкой
                snippet = create_snippet(page_content, query)
                
                results.append({
                    'title': title,
                    'content': page_content,
                    'snippet': snippet if snippet else "Текст не найден",
                    'link': page_url,
                    'source': 'Notion',
                    'last_edited': last_edited,
                    'id': page_id,
                    'relevance': calculate_relevance(search_text, query)  # Для сортировки
                })
                
        except Exception as e:
            continue
    
    progress_bar.empty()
    status_text.empty()
    
    # Сортируем по релевантности
    results.sort(key=lambda x: x.get('relevance', 0), reverse=True)
    
    return results, None

def create_snippet(text, query, max_length=300):
    """Создает сниппет с найденным текстом"""
    if not text:
        return ""
    
    text_lower = text.lower()
    query_lower = query.lower()
    
    # Ищем первое вхождение запроса
    position = text_lower.find(query_lower)
    
    if position == -1:
        # Если точного вхождения нет, ищем отдельные слова
        for word in query_lower.split():
            if len(word) > 3:
                word_pos = text_lower.find(word)
                if word_pos != -1:
                    position = word_pos
                    query_lower = word
                    break
    
    if position == -1:
        # Если ничего не нашли, берем начало текста
        return text[:max_length] + ("..." if len(text) > max_length else "")
    
    # Берем текст вокруг найденного места
    start = max(0, position - 100)
    end = min(len(text), position + len(query_lower) + 100)
    
    snippet = text[start:end]
    
    # Добавляем многоточия если нужно
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    
    # Подсветка найденного текста
    snippet = highlight_text(snippet, query_lower)
    
    return snippet

def highlight_text(text, query):
    """Подсвечивает найденный текст в сниппете"""
    text_lower = text.lower()
    query_lower = query.lower()
    
    position = text_lower.find(query_lower)
    
    if position == -1:
        return text
    
    # Заменяем найденный текст на версию с подсветкой
    original_found = text[position:position + len(query_lower)]
    highlighted = f"**{original_found}**"
    
    return text[:position] + highlighted + text[position + len(query_lower):]

def calculate_relevance(text, query):
    """Вычисляет релевантность страницы запросу"""
    if not text or not query:
        return 0
    
    text_lower = text.lower()
    query_lower = query.lower()
    query_words = query_lower.split()
    
    score = 0
    
    # Бонус за точное совпадение
    if query_lower in text_lower:
        score += 100
    
    # Бонус за каждое слово запроса
    for word in query_words:
        if len(word) > 2 and word in text_lower:
            score += 20
    
    # Бонус за частоту встречаемости
    for word in query_words:
        if len(word) > 2:
            count = text_lower.count(word)
            score += min(count, 10) * 5
    
    return score

# =================== ПОИСК НОВОСТЕЙ ===================
def fetch_google_news(search_query):
    """Поиск новостей через Serper API"""
    if not SERPER_API_KEY:
        return None, "❌ API ключ Serper не найден"
    
    url = "https://google.serper.dev/news"
    payload = json.dumps({
        "q": search_query + " Christopher Nolan",
        "gl": "ru",
        "hl": "ru",
        "tbs": "qdr:w",
        "num": 8
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

# =================== ОСНОВНОЙ ИНТЕРФЕЙС ===================
def main():
    # Заголовок приложения
    st.title("🔍 Глубокий поиск по содержимому Notion")
    st.markdown("Ищет текст ВНУТРИ ваших страниц Notion, а не только по названиям")
    
    # ========== SIDEBAR ==========
    st.sidebar.title("⚙️ Настройки")
    
    # Настройки поиска
    st.sidebar.subheader("Настройки поиска")
    
    filter_nolan = st.sidebar.checkbox("Только про Нолана", value=True,
                                      help="Показывать только страницы, связанные с Кристофером Ноланом")
    
    search_depth = st.sidebar.slider("Глубина поиска", 1, 50, 20,
                                    help="Сколько страниц проверять (чем больше, тем медленнее)")
    
    # Кэш страниц
    if 'all_notion_pages' not in st.session_state:
        st.session_state.all_notion_pages = None
    
    # Кнопка загрузки всех страниц
    if st.sidebar.button("🔄 Загрузить все страницы Notion"):
        with st.spinner("Загружаю ваши страницы..."):
            all_pages, error = get_all_notion_pages()
            if error:
                st.sidebar.error(error)
            else:
                st.session_state.all_notion_pages = all_pages
                st.sidebar.success(f"✅ Загружено {len(all_pages)} страниц")
    
    if st.session_state.all_notion_pages:
        st.sidebar.info(f"📄 Загружено страниц: {len(st.session_state.all_notion_pages)}")
    
    # Инструкция
    with st.sidebar.expander("📖 Как работает поиск"):
        st.markdown("""
        ### 🔍 **Поиск по содержимому:**
        1. **Загружает ВСЕ ваши страницы** из Notion
        2. **Читает текст внутри** каждой страницы
        3. **Ищет слова запроса** в тексте
        4. **Сортирует по релевантности**
        
        ### ⚡ **Особенности:**
        - Ищет **внутри текста**, а не только в заголовках
        - **Подсвечивает** найденные слова
        - **Кэширует** содержимое страниц (ускоряет повторный поиск)
        - **Показывает сниппеты** с контекстом
        
        ### ⏱️ **Скорость:**
        - Первый поиск: **медленнее** (нужно загрузить страницы)
        - Повторный поиск: **быстрее** (используется кэш)
        """)
    
    # ========== ПОИСКОВАЯ ФОРМА ==========
    col1, col2 = st.columns([4, 1])
    
    with col1:
        query = st.text_input(
            "Введите запрос:",
            placeholder="Ищите внутри текста страниц... Например: 'новый проект', 'интервью', 'съемки'...",
            key="search_query"
        )
    
    with col2:
        st.write("")
        st.write("")
        search_clicked = st.button("🔍 Искать в содержимом", type="primary", use_container_width=True)
    
    if search_clicked and query:
        if not st.session_state.all_notion_pages:
            st.warning("⚠️ Сначала загрузите страницы Notion (кнопка в сайдбаре)")
            st.stop()
        
        with st.spinner(f"🔍 Ищу '{query}' в содержимом {len(st.session_state.all_notion_pages)} страниц..."):
            # Поиск по содержимому
            notion_results, notion_error = search_in_content(
                st.session_state.all_notion_pages,
                query,
                filter_by_nolan=filter_nolan,
                max_pages=search_depth
            )
            
            # Поиск новостей
            news_results, news_error = fetch_google_news(query)
        
        # ========== РЕЗУЛЬТАТЫ ==========
        if notion_error:
            st.error(f"**Ошибка Notion:** {notion_error}")
        
        # Показываем результаты
        st.subheader(f"📄 Найдено в содержимом страниц: {len(notion_results)}")
        
        if notion_results:
            for i, page in enumerate(notion_results):
                with st.expander(f"**{i+1}. {page['title']}**", expanded=i < 2):
                    # Метаинформация
                    if page.get('last_edited'):
                        st.caption(f"📅 Изменено: {page['last_edited']}")
                    
                    # Сниппет с подсветкой
                    st.markdown("**Найдено в тексте:**")
                    st.markdown(page['snippet'])
                    
                    # Ссылка на страницу
                    st.markdown(f"[🔗 Открыть в Notion]({page['link']})")
                    
                    # Кнопка для показа полного текста
                    if st.button("📄 Показать больше текста", key=f"more_{i}"):
                        # Показываем первые 1000 символов
                        preview = page['content'][:1000]
                        if len(page['content']) > 1000:
                            preview += "..."
                        st.text_area("Содержимое страницы:", preview, height=200)
        else:
            st.info("😔 В содержимом ваших страниц ничего не найдено")
        
        # Новости
        st.markdown("---")
        st.subheader("🌐 Новости")
        
        if news_results:
            for i, article in enumerate(news_results):
                with st.expander(f"**{i+1}. {article['title']}**"):
                    st.markdown(f"**📰 Источник:** {article['source']}")
                    st.write(article['snippet'])
                    st.markdown(f"[📖 Читать статью →]({article['link']})")
        else:
            st.info("📰 Новостей по запросу не найдено")
    
    # ========== ПРИ ПУСТОМ ПОИСКЕ ==========
    else:
        st.markdown("---")
        
        # Инструкция
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📋 **Как начать:**")
            st.markdown("""
            1. **Нажмите кнопку в сайдбаре:**  
               `🔄 Загрузить все страницы Notion`
            2. **Дождитесь загрузки** (может занять минуту)
            3. **Введите запрос** в поле поиска
            4. **Нажмите** `🔍 Искать в содержимом`
            """)
        
        with col2:
            st.markdown("### 🎯 **Что искать:**")
            st.markdown("""
            - **Любые слова** из текста ваших страниц
            - **Фразы** и **предложения**
            - **Имена**, **даты**, **события**
            - **Ключевые слова** из заметок
            """)
        
        st.markdown("---")
        
        # Примеры запросов
        st.subheader("✨ Примеры для поиска в содержимом:")
        
        examples = [
            ("🎬 Кинопроекты", "Что сейчас снимает, планы на будущее"),
            ("📅 График съемок", "Даты, расписание, сроки"),
            ("🏆 Награды", "Оскар, номинации, премии"),
            ("🤝 Коллаборации", "Актеры, композиторы, операторы"),
        ]
        
        for title, desc in examples:
            if st.button(f"{title}: {desc}"):
                st.session_state.search_query = desc
                st.rerun()

# =================== ЗАПУСК ПРИЛОЖЕНИЯ ===================
if __name__ == "__main__":
    main()
