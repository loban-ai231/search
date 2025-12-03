import streamlit as st
import requests
import json
from urllib.parse import quote
import datetime

# =================== НАСТРОЙКА СТРАНИЦЫ ===================
st.set_page_config(
    page_title="Поиск по страницам Notion",
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
            data = response.json()
            results = data.get("results", [])
            
            processed_pages = []
            pages_to_check = min(10, len(results))  # Проверяем только первые 10 страниц
            
            for i, page in enumerate(results[:pages_to_check]):
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
                    with st.spinner(f"Читаю страницу {i+1}/{pages_to_check}..."):
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
                    
                    # Создаем сниппет (первые 200 символов)
                    snippet = page_content[:200] + "..." if len(page_content) > 200 else page_content
                    
                    processed_pages.append({
                        'title': title,
                        'content': page_content,
                        'snippet': snippet if snippet else "Текст не найден",
                        'link': page_url,
                        'source': 'Notion',
                        'last_edited': last_edited,
                        'id': page_id,
                        'full_content': page_content  # Сохраняем полный текст для поиска
                    })
                    
                except Exception as e:
                    continue
            
            # Фильтрация по теме Нолана
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
            return None, "❌ Превышен лимит запросов"
        else:
            return None, f"❌ Ошибка API: {response.status_code}"
    
    except Exception as e:
        return None, f"❌ Ошибка подключения: {e}"

def search_specific_pages(query, page_ids, filter_by_nolan=True):
    """Ищет в конкретных страницах по их ID"""
    if not NOTION_API_KEY:
        return None, "❌ API ключ Notion не найден"
    
    results = []
    
    for page_id in page_ids[:5]:  # Ограничиваем 5 страницами для скорости
        try:
            # Получаем информацию о странице
            page_url = f"https://api.notion.com/v1/pages/{page_id}"
            headers = {
                "Authorization": f"Bearer {NOTION_API_KEY}",
                "Notion-Version": "2022-06-28"
            }
            
            page_response = requests.get(page_url, headers=headers, timeout=5)
            
            if page_response.status_code == 200:
                page_data = page_response.json()
                
                # Получаем заголовок
                title = "Без названия"
                properties = page_data.get('properties', {})
                for prop_name, prop_value in properties.items():
                    if prop_value.get('type') == 'title':
                        title_items = prop_value.get('title', [])
                        for title_item in title_items:
                            if 'plain_text' in title_item:
                                title = title_item['plain_text']
                                break
                
                # Получаем содержимое
                page_content, content_error = get_page_content(page_id)
                if content_error:
                    continue
                
                # Проверяем, содержит ли страница запрос
                search_text = (title + " " + page_content).lower()
                if query.lower() in search_text:
                    # Фильтрация по Нолану
                    if filter_by_nolan:
                        nolan_keywords = ["нолан", "nolan", "кристофер", "christopher"]
                        if not any(keyword in search_text for keyword in nolan_keywords):
                            continue
                    
                    snippet = page_content[:200] + "..." if len(page_content) > 200 else page_content
                    
                    results.append({
                        'title': title,
                        'content': page_content,
                        'snippet': snippet,
                        'link': f"https://www.notion.so/{page_id.replace('-', '')}",
                        'source': 'Notion',
                        'id': page_id
                    })
        
        except Exception:
            continue
    
    return results, None

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
    st.title("🔍 Поиск по вашим страницам Notion")
    st.write("Ищет текст внутри ваших страниц Notion")
    
    # ========== SIDEBAR ==========
    st.sidebar.title("⚙️ Настройки")
    
    # Режим поиска
    search_mode = st.sidebar.radio(
        "Режим поиска:",
        ["🔍 По всем страницам", "📄 По конкретным страницам"]
    )
    
    # Специфические страницы
    specific_pages = []
    if search_mode == "📄 По конкретным страницам":
        pages_input = st.sidebar.text_area(
            "ID страниц Notion:",
            placeholder="Введите ID страниц через запятую\nПример: abc123, def456, ghi789",
            help="ID можно найти в URL страницы Notion"
        )
        
        if pages_input:
            specific_pages = [pid.strip() for pid in pages_input.split(',') if pid.strip()]
            st.sidebar.info(f"Загружено {len(specific_pages)} страниц")
    
    # Настройки
    filter_nolan = st.sidebar.checkbox("Только про Нолана", value=True)
    
    # Инструкция
    with st.sidebar.expander("📖 Как найти ID страницы"):
        st.markdown("""
        1. Откройте страницу в Notion
        2. Посмотрите в адресной строке:
           ```
           https://www.notion.so/Ваше-название-abc123def456...
                                  ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
           Это ID страницы (32 символа)
           ```
        3. Скопируйте этот ID
        """)
    
    # ========== ПОИСКОВАЯ ФОРМА ==========
    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input(
            "Введите запрос:",
            placeholder="новости, интервью, проекты...",
            key="search_query"
        )
    
    with col2:
        st.write("")
        st.write("")
        search_clicked = st.button("🔍 Найти", type="primary", use_container_width=True)
    
    if search_clicked and query:
        with st.spinner("Ищем информацию..."):
            # Поиск в Notion
            if search_mode == "🔍 По всем страницам":
                notion_results, notion_error = search_in_notion_pages(query, filter_by_nolan=filter_nolan)
            else:
                notion_results, notion_error = search_specific_pages(query, specific_pages, filter_by_nolan=filter_nolan)
            
            # Поиск новостей
            news_results, news_error = fetch_google_news(query)
        
        # ========== РЕЗУЛЬТАТЫ ==========
        col_left, col_right = st.columns(2)
        
        # ЛЕВАЯ КОЛОНКА: Notion
        with col_left:
            st.markdown(f"### 📚 Ваши страницы Notion")
            
            if notion_error:
                st.error(f"Ошибка: {notion_error}")
            elif notion_results:
                st.success(f"Найдено {len(notion_results)} страниц")
                
                for i, page in enumerate(notion_results):
                    with st.expander(f"{i+1}. {page['title']}", expanded=i==0):
                        if page.get('last_edited'):
                            st.caption(f"📅 {page['last_edited']}")
                        
                        # Показываем сниппет с выделением запроса
                        snippet = page['snippet']
                        query_lower = query.lower()
                        
                        # Простой highlight
                        if query_lower in snippet.lower():
                            start_idx = snippet.lower().find(query_lower)
                            end_idx = start_idx + len(query_lower)
                            highlighted = (
                                snippet[:start_idx] + 
                                f"**{snippet[start_idx:end_idx]}**" + 
                                snippet[end_idx:]
                            )
                            st.markdown(highlighted)
                        else:
                            st.write(snippet)
                        
                        st.markdown(f"[🔗 Открыть в Notion]({page['link']})")
                        
                        # Кнопка для показа полного текста
                        if st.button("📄 Показать полный текст", key=f"full_{i}"):
                            st.text_area("Полный текст:", page['content'], height=200)
            else:
                st.info("В вашем Notion ничего не найдено")
        
        # ПРАВАЯ КОЛОНКА: Новости
        with col_right:
            st.markdown(f"### 🌐 Новости")
            
            if news_error:
                st.error(f"Ошибка: {news_error}")
            elif news_results:
                st.success(f"Найдено {len(news_results)} новостей")
                
                for i, article in enumerate(news_results):
                    with st.expander(f"{i+1}. {article['title']}", expanded=i==0):
                        st.markdown(f"**Источник:** {article['source']}")
                        st.write(article['snippet'])
                        st.markdown(f"[📖 Читать]({article['link']})")
            else:
                st.info("Новостей не найдено")
    
    # ========== БЫСТРЫЕ ЗАПРОСЫ ==========
    st.markdown("---")
    st.subheader("💡 Попробуйте также:")
    
    quick_queries = ["Интервью Нолана", "Новые проекты", "Награды", "Фильмы"]
    
    cols = st.columns(len(quick_queries))
    for idx, q in enumerate(quick_queries):
        with cols[idx]:
            if st.button(q, key=f"quick_{idx}"):
                st.session_state.search_query = q
                st.rerun()

# =================== ЗАПУСК ПРИЛОЖЕНИЯ ===================
if __name__ == "__main__":
    main()
