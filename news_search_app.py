import streamlit as st
import requests
import json
from urllib.parse import quote
import datetime

# =================== НАСТРОЙКА СТРАНИЦЫ ===================
st.set_page_config(
    page_title="🔍 Поиск по страницам Notion",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =================== ЗАГРУЗКА КЛЮЧЕЙ ===================
SERPER_API_KEY = st.secrets.get("SERPER_API_KEY", "")
OMDB_API_KEY = st.secrets.get("OMDB_API_KEY", "")
NOTION_API_KEY = st.secrets.get("NOTION_API_KEY", "")

# =================== ФУНКЦИИ ДЛЯ РАБОТЫ СО СТРАНИЦАМИ NOTION ===================
def extract_text_from_blocks(blocks):
    """Извлекает текст из блоков Notion"""
    text_parts = []
    
    for block in blocks:
        block_type = block.get('type')
        
        if block_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3', 'bulleted_list_item', 'numbered_list_item']:
            rich_text = block.get(block_type, {}).get('rich_text', [])
            for text_item in rich_text:
                if 'plain_text' in text_item:
                    text_parts.append(text_item['plain_text'])
        
        # Рекурсивно обрабатываем дочерние блоки
        if block.get('has_children', False):
            child_blocks = block.get('children', [])
            text_parts.extend(extract_text_from_blocks(child_blocks))
    
    return " ".join(text_parts)

def get_page_content(page_id):
    """Получает содержимое страницы Notion"""
    if not NOTION_API_KEY:
        return None, "❌ API ключ Notion не найден"
    
    # Получаем блоки страницы
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            blocks = data.get('results', [])
            text_content = extract_text_from_blocks(blocks)
            return text_content, None
        else:
            return None, f"❌ Ошибка API: {response.status_code}"
    
    except Exception as e:
        return None, f"❌ Ошибка подключения: {e}"

def search_in_notion_pages(query, filter_by_nolan=True):
    """Ищет по всем страницам Notion"""
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
            
            processed_pages = []
            
            for i, page in enumerate(results[:10]):  # Ограничиваем 10 страницами для скорости
                try:
                    # Получаем ID страницы
                    page_id = page.get('id', '')
                    
                    # Получаем заголовок страницы
                    title = "Без названия"
                    properties = page.get('properties', {})
                    
                    # Ищем заголовок в свойствах
                    for prop_name, prop_value in properties.items():
                        if prop_value.get('type') == 'title':
                            title_items = prop_value.get('title', [])
                            for title_item in title_items:
                                if 'plain_text' in title_item:
                                    title = title_item['plain_text']
                                    break
                        if title != "Без названия":
                            break
                    
                    # Получаем содержимое страницы
                    page_content, content_error = get_page_content(page_id)
                    
                    if content_error:
                        continue  # Пропускаем страницы с ошибками
                    
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
                    
                    # Создаем сниппет
                    snippet = page_content[:250] + "..." if len(page_content) > 250 else page_content
                    
                    processed_pages.append({
                        'title': title,
                        'content': page_content,
                        'snippet': snippet if snippet else "Текст не найден",
                        'link': page_url,
                        'source': 'Notion',
                        'last_edited': last_edited,
                        'id': page_id
                    })
                    
                except Exception as e:
                    continue
            
            # Фильтрация по теме Нолана (опционально)
            if filter_by_nolan and processed_pages:
                filtered_pages = []
                nolan_keywords = ["нолан", "nolan", "кристофер", "christopher", "опенгеймер", 
                                 "oppenheimer", "интерстеллар", "inception", "тенет", "tenet"]
                
                for page in processed_pages:
                    search_text = (page['title'] + " " + page['content']).lower()
                    if any(keyword in search_text for keyword in nolan_keywords):
                        filtered_pages.append(page)
                
                return filtered_pages, None
            
            return processed_pages, None
        
        elif response.status_code == 401:
            return None, "❌ Неверный API ключ Notion"
        elif response.status_code == 429:
            return None, "❌ Превышен лимит запросов. Подождите минуту."
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
    st.title("🔍 Умный поиск по страницам Notion")
    st.markdown("Ищет информацию в ваших страницах Notion и актуальные новости")
    
    # ========== SIDEBAR ==========
    st.sidebar.title("⚙️ Настройки")
    
    # Статус API
    st.sidebar.subheader("Статус API")
    
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        st.write("**Notion API:**")
        st.write("✅" if NOTION_API_KEY else "❌")
        
        st.write("**Google News:**")
        st.write("✅" if SERPER_API_KEY else "⚠️")
    
    with col2:
        st.write("**Фильмы:**")
        st.write("✅" if OMDB_API_KEY else "⚠️")
    
    # Настройки поиска
    st.sidebar.subheader("Настройки поиска")
    filter_nolan = st.sidebar.checkbox("Только про Нолана", value=True, 
                                      help="Показывать только страницы о Кристофере Нолане")
    
    # Инструкция
    with st.sidebar.expander("📖 Как пользоваться"):
        st.markdown("""
        ### 🔍 Как работает поиск:
        1. **Введите запрос** в поле поиска
        2. **Нажмите "Найти"** для поиска
        3. **Результаты** появятся ниже
        
        ### 📄 Что ищет:
        - **В Notion:** Заголовки и содержимое всех ваших страниц
        - **В новостях:** Актуальные статьи о Нолане
        
        ### ✨ Примеры запросов:
        - Новые проекты Нолана
        - Интервью Кристофера
        - Награды Опенгеймера
        - Фильмография
        - Tenet
        - Интерстеллар
        """)
    
    # ========== ПОИСКОВАЯ ФОРМА ==========
    col1, col2 = st.columns([4, 1])
    
    with col1:
        query = st.text_input(
            "Введите запрос:",
            placeholder="Что ищем? Например: новые проекты, интервью, награды...",
            key="search_query"
        )
    
    with col2:
        st.write("")
        st.write("")
        search_clicked = st.button("🔍 Найти", type="primary", use_container_width=True)
    
    if search_clicked and query:
        with st.spinner("🔍 Ищем информацию..."):
            # Поиск в Notion
            notion_results, notion_error = search_in_notion_pages(query, filter_by_nolan=filter_nolan)
            
            # Поиск новостей
            news_results, news_error = fetch_google_news(query)
        
        # ========== РЕЗУЛЬТАТЫ ==========
        if notion_error or news_error:
            if notion_error:
                st.error(f"**Ошибка Notion:** {notion_error}")
            if news_error:
                st.error(f"**Ошибка новостей:** {news_error}")
        
        # Показываем результаты в двух колонках
        col_left, col_right = st.columns(2)
        
        # ЛЕВАЯ КОЛОНКА: Notion
        with col_left:
            st.subheader("📚 Ваши страницы Notion")
            
            if notion_results:
                st.success(f"Найдено {len(notion_results)} страниц")
                
                for i, page in enumerate(notion_results):
                    with st.expander(f"**{i+1}. {page['title']}**", expanded=i==0):
                        # Метаинформация
                        if page.get('last_edited'):
                            st.caption(f"📅 Последнее изменение: {page['last_edited']}")
                        
                        # Сниппет с текстом
                        if page['snippet'] and page['snippet'] != "Текст не найден":
                            # Подсветка поискового запроса
                            query_lower = query.lower()
                            snippet_lower = page['snippet'].lower()
                            
                            if query_lower in snippet_lower:
                                start_idx = snippet_lower.find(query_lower)
                                end_idx = start_idx + len(query_lower)
                                highlighted = (
                                    page['snippet'][:start_idx] + 
                                    f"**{page['snippet'][start_idx:end_idx]}**" + 
                                    page['snippet'][end_idx:]
                                )
                                st.markdown(highlighted)
                            else:
                                st.write(page['snippet'])
                        
                        # Ссылка на страницу
                        st.markdown(f"[🔗 Открыть в Notion]({page['link']})")
                        
                        # Кнопка для показа полного текста
                        if st.button("📄 Показать больше текста", key=f"more_{i}"):
                            if len(page['content']) > 500:
                                st.text_area("Полный текст (сокращено):", page['content'][:500] + "...", height=150)
                            else:
                                st.text_area("Полный текст:", page['content'], height=150)
            else:
                if NOTION_API_KEY:
                    st.info("😔 В ваших страницах Notion ничего не найдено")
                else:
                    st.warning("🔑 Не настроен API ключ Notion")
        
        # ПРАВАЯ КОЛОНКА: Новости
        with col_right:
            st.subheader("🌐 Новости")
            
            if news_results:
                st.success(f"Найдено {len(news_results)} новостей")
                
                for i, article in enumerate(news_results):
                    with st.expander(f"**{i+1}. {article['title']}**", expanded=i==0):
                        st.markdown(f"**📰 Источник:** {article['source']}")
                        st.write(article['snippet'])
                        st.markdown(f"[📖 Читать статью →]({article['link']})")
            else:
                if SERPER_API_KEY:
                    st.info("📰 Новостей по запросу не найдено")
                else:
                    st.info("🔑 Не настроен API ключ для новостей")
        
        # Быстрые запросы
        st.markdown("---")
        st.subheader("💡 Попробуйте также:")
        
        quick_queries = ["Новые проекты", "Интервью", "Награды", "Фильмография", "Tenet", "Опенгеймер"]
        
        cols = st.columns(len(quick_queries))
        for idx, q in enumerate(quick_queries):
            with cols[idx]:
                if st.button(q, key=f"quick_{idx}"):
                    st.session_state.search_query = q
                    st.rerun()
    
    # ========== ПРИ ПУСТОМ ПОИСКЕ ==========
    else:
        # Показываем приветственный экран
        st.markdown("---")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("### 📄 **Ваши страницы**")
            st.markdown("""
            Ищет в:
            - Заголовках страниц
            - Текстовом содержимом
            - Списках и заметках
            """)
        
        with col2:
            st.markdown("### 🌐 **Новости**")
            st.markdown("""
            Показывает:
            - Актуальные статьи
            - Новости кино
            - Интервью и обзоры
            """)
        
        with col3:
            st.markdown("### 🎯 **Тематика**")
            st.markdown("""
            Фокус на:
            - Кристофер Нолан
            - Его фильмы
            - Проекты и награды
            """)
        
        # Примеры запросов
        st.markdown("---")
        st.subheader("✨ Примеры запросов для поиска:")
        
        example_cols = st.columns(4)
        
        examples = [
            ("🎬 Новые фильмы", "Что сейчас снимает Нолан"),
            ("🏆 Награды", "Оскар, Грэмми и другие"),
            ("📰 Интервью", "Последние интервью режиссера"),
            ("📚 Фильмография", "Все фильмы Нолана")
        ]
        
        for idx, (title, desc) in enumerate(examples):
            with example_cols[idx]:
                if st.button(title, key=f"example_{idx}"):
                    st.session_state.search_query = desc
                    st.rerun()
        
        # Пустое пространство для красоты
        st.markdown("")
        st.markdown("")
        
    # ========== ФУТЕР ==========
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; font-size: 0.9em; padding: 10px;">
        <p>🔍 Поиск по страницам Notion | Автоматически читает содержимое страниц | Ваши данные защищены</p>
    </div>
    """, unsafe_allow_html=True)

# =================== ЗАПУСК ПРИЛОЖЕНИЯ ===================
if __name__ == "__main__":
    main()
