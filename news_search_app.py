import streamlit as st
import requests
import json
import datetime
import re

# =================== НАСТРОЙКА СТРАНИЦЫ ===================
st.set_page_config(
    page_title="🔍 Умный поиск по Notion",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =================== ЗАГРУЗКА КЛЮЧЕЙ ===================
SERPER_API_KEY = st.secrets.get("SERPER_API_KEY", "")
OMDB_API_KEY = st.secrets.get("OMDB_API_KEY", "")
NOTION_API_KEY = st.secrets.get("NOTION_API_KEY", "")

# =================== ФУНКЦИИ ДЛЯ РАБОТЫ С NOTION ===================
def extract_text_from_blocks(blocks):
    """Извлекает текст из блоков Notion"""
    text_parts = []
    
    for block in blocks:
        block_type = block.get('type')
        
        # Текстовые блоки
        if block_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3', 
                         'bulleted_list_item', 'numbered_list_item', 'to_do', 
                         'toggle', 'quote', 'callout']:
            rich_text = block.get(block_type, {}).get('rich_text', [])
            for text_item in rich_text:
                if 'plain_text' in text_item:
                    text_parts.append(text_item['plain_text'])
        
        # Код и формулы
        elif block_type in ['code', 'equation']:
            rich_text = block.get(block_type, {}).get('rich_text', [])
            for text_item in rich_text:
                if 'plain_text' in text_item:
                    text_parts.append(text_item['plain_text'])
        
        # Таблицы
        elif block_type == 'table':
            table_rows = block.get('table', {}).get('children', [])
            for row in table_rows:
                cells = row.get('table_row', {}).get('cells', [])
                for cell in cells:
                    for text_item in cell:
                        if 'plain_text' in text_item:
                            text_parts.append(text_item['plain_text'])
        
        # Рекурсивно обрабатываем дочерние блоки
        if block.get('has_children', False):
            child_blocks = block.get('children', [])
            child_text = extract_text_from_blocks(child_blocks)
            text_parts.extend(child_text)
    
    return " ".join(text_parts)

def get_page_title(page_data):
    """Извлекает заголовок страницы"""
    try:
        properties = page_data.get('properties', {})
        
        # Ищем свойство с заголовком
        for prop_name, prop_value in properties.items():
            if prop_value.get('type') == 'title':
                title_items = prop_value.get('title', [])
                for title_item in title_items:
                    if 'plain_text' in title_item:
                        return title_item['plain_text']
        
        # Если нет title, ищем в других свойствах
        for prop_name, prop_value in properties.items():
            if prop_value.get('type') == 'rich_text':
                rich_text = prop_value.get('rich_text', [])
                for text_item in rich_text:
                    if 'plain_text' in text_item and text_item['plain_text'].strip():
                        return text_item['plain_text']
        
        return "Без названия"
    except:
        return "Без названия"

def smart_search_notion(query, search_mode="all"):
    """Умный поиск в Notion"""
    if not NOTION_API_KEY:
        return None, "❌ API ключ Notion не найден"
    
    results = []
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    
    # Разбиваем запрос на слова, убираем стоп-слова
    query_lower = query.lower()
    query_words = [word for word in query_lower.split() if len(word) > 2]
    
    # Если запрос короткий, не фильтруем слова
    if len(query.split()) <= 2:
        query_words = query_lower.split()
    
    # Поиск через Notion Search API
    url = "https://api.notion.com/v1/search"
    
    # Сначала ищем по заголовкам
    title_payload = {
        "query": query,
        "filter": {
            "value": "page",
            "property": "object"
        },
        "page_size": 50,
        "sort": {
            "direction": "descending",
            "timestamp": "last_edited_time"
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=title_payload, timeout=20)
        
        if response.status_code == 200:
            data = response.json()
            pages = data.get("results", [])
            
            # Процессим каждую страницу
            for page in pages:
                try:
                    # Получаем заголовок
                    title = get_page_title(page)
                    
                    # Получаем ID и URL
                    page_id = page.get('id', '')
                    
                    # ПРАВИЛЬНЫЙ URL - используем URL из API или строим по ID
                    page_url = page.get('url')
                    if not page_url or 'notion.so' not in page_url:
                        page_url = f"https://www.notion.so/{page_id.replace('-', '')}"
                    
                    # Получаем содержимое страницы
                    content_text, content_error = get_page_content(page_id)
                    full_text = title + " " + (content_text if not content_error else "")
                    
                    # Проверяем релевантность
                    relevance = calculate_relevance(full_text, query)
                    
                    # Если релевантность выше порога или ищем по всем
                    if relevance > 0 or search_mode == "all":
                        # Дата последнего редактирования
                        last_edited = page.get('last_edited_time', '')
                        if last_edited:
                            try:
                                dt = datetime.datetime.fromisoformat(last_edited.replace('Z', '+00:00'))
                                last_edited = dt.strftime("%d.%m.%Y %H:%M")
                            except:
                                pass
                        
                        # Создаем сниппет
                        snippet = create_smart_snippet(title, content_text if not content_error else "", query)
                        
                        results.append({
                            'title': title,
                            'content': content_text if not content_error else "",
                            'snippet': snippet,
                            'link': page_url,
                            'source': 'Notion',
                            'last_edited': last_edited,
                            'id': page_id,
                            'relevance': relevance,
                            'found_in': "заголовок" if relevance > 0 and query.lower() in title.lower() else "содержимое"
                        })
                        
                except Exception as e:
                    continue
            
            # Сортируем по релевантности
            results.sort(key=lambda x: x['relevance'], reverse=True)
            
            # Если не нашли по заголовкам, пробуем более глубокий поиск
            if not results and len(query_words) > 0:
                return deep_content_search(query_words, headers)
            
            return results[:50], None
        
        elif response.status_code == 401:
            return None, "❌ Неверный API ключ Notion"
        elif response.status_code == 429:
            return None, "❌ Превышен лимит запросов. Подождите минуту."
        else:
            return None, f"❌ Ошибка API: {response.status_code}"
    
    except Exception as e:
        return None, f"❌ Ошибка подключения: {e}"

def deep_content_search(query_words, headers):
    """Глубокий поиск по содержимому всех страниц"""
    results = []
    
    try:
        # Получаем все страницы
        url = "https://api.notion.com/v1/search"
        payload = {
            "filter": {"value": "page", "property": "object"},
            "page_size": 100,
            "sort": {"direction": "descending", "timestamp": "last_edited_time"}
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            all_pages = data.get("results", [])
            
            # Проверяем первые 30 страниц
            for page in all_pages[:30]:
                try:
                    title = get_page_title(page)
                    page_id = page.get('id', '')
                    page_url = page.get('url', f"https://www.notion.so/{page_id.replace('-', '')}")
                    
                    # Получаем содержимое
                    content, error = get_page_content(page_id)
                    if error:
                        continue
                    
                    full_text = (title + " " + content).lower()
                    
                    # Ищем каждое слово запроса
                    found_words = 0
                    for word in query_words:
                        if word in full_text:
                            found_words += 1
                    
                    # Если нашли хотя бы одно слово
                    if found_words > 0:
                        relevance = found_words * 10
                        
                        # Создаем сниппет
                        snippet = create_smart_snippet(title, content, " ".join(query_words))
                        
                        results.append({
                            'title': title,
                            'content': content,
                            'snippet': snippet,
                            'link': page_url,
                            'source': 'Notion',
                            'id': page_id,
                            'relevance': relevance,
                            'found_in': "содержимое"
                        })
                        
                except Exception:
                    continue
            
            results.sort(key=lambda x: x['relevance'], reverse=True)
            return results[:30], None
    
    except Exception:
        pass
    
    return [], None

def get_page_content(page_id):
    """Получает содержимое страницы Notion"""
    if not NOTION_API_KEY:
        return "", "❌ API ключ Notion не найден"
    
    try:
        url = f"https://api.notion.com/v1/blocks/{page_id}/children"
        headers = {
            "Authorization": f"Bearer {NOTION_API_KEY}",
            "Notion-Version": "2022-06-28"
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            blocks = data.get('results', [])
            text_content = extract_text_from_blocks(blocks)
            return text_content, None
        else:
            return "", ""
    
    except Exception as e:
        return "", ""

def calculate_relevance(text, query):
    """Вычисляет релевантность текста запросу"""
    if not text or not query:
        return 0
    
    text_lower = text.lower()
    query_lower = query.lower()
    
    # Разбиваем запрос на слова
    query_words = query_lower.split()
    
    # Если запрос одно слово
    if len(query_words) == 1:
        word = query_words[0]
        if len(word) <= 2:
            # Для коротких слов ищем точное вхождение
            pattern = r'\b' + re.escape(word) + r'\b'
            if re.search(pattern, text_lower):
                return 100
            elif word in text_lower:
                return 50
        else:
            # Для длинных слов
            if word in text_lower:
                return 100
    
    # Для нескольких слов
    score = 0
    words_found = 0
    
    for word in query_words:
        if len(word) > 0:
            # Ищем слово с границами (целое слово)
            pattern = r'\b' + re.escape(word) + r'\b'
            if re.search(pattern, text_lower):
                score += 30
                words_found += 1
            elif word in text_lower:
                score += 15
                words_found += 1
    
    # Бонус за нахождение всех слов
    if words_found == len(query_words):
        score += 50
    
    # Бонус за точную фразу
    if query_lower in text_lower:
        score += 100
    
    return score

def create_smart_snippet(title, content, query, max_length=250):
    """Создает умный сниппет с найденными словами"""
    if not content:
        return title[:150] + ("..." if len(title) > 150 else "")
    
    # Объединяем заголовок и содержимое
    full_text = title + " " + content
    full_text_lower = full_text.lower()
    query_lower = query.lower()
    query_words = [word for word in query_lower.split() if len(word) > 0]
    
    # Ищем лучшее место для сниппета
    best_position = -1
    best_score = 0
    
    for i in range(0, len(full_text_lower) - 100, 50):
        segment = full_text_lower[i:i+200]
        score = 0
        
        for word in query_words:
            if word in segment:
                score += 10
                # Бонус за точное совпадение с границами слова
                if re.search(r'\b' + re.escape(word) + r'\b', segment):
                    score += 5
        
        if score > best_score:
            best_score = score
            best_position = i
    
    # Если не нашли хорошее место, берем начало
    if best_position == -1 or best_score == 0:
        snippet = content[:max_length]
        if len(content) > max_length:
            snippet += "..."
        return snippet
    
    # Вырезаем сниппет вокруг лучшей позиции
    start = max(0, best_position - 50)
    end = min(len(full_text), best_position + 200)
    
    snippet = full_text[start:end]
    
    # Добавляем многоточия
    if start > 0:
        snippet = "..." + snippet
    if end < len(full_text):
        snippet = snippet + "..."
    
    # Подсвечиваем найденные слова
    for word in query_words:
        if len(word) > 0:
            # Используем regex для поиска слова с любыми границами
            pattern = r'(\b' + re.escape(word) + r'\b)'
            snippet = re.sub(pattern, r'**\1**', snippet, flags=re.IGNORECASE)
    
    return snippet

def fetch_google_news(search_query):
    """Поиск новостей через Serper API"""
    if not SERPER_API_KEY:
        return None, "❌ API ключ Serper не найден"
    
    url = "https://google.serper.dev/news"
    payload = json.dumps({
        "q": search_query,
        "gl": "ru",
        "hl": "ru",
        "tbs": "qdr:w",
        "num": 6
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
                        'title': article.get('title', 'Без заголовка')[:150],
                        'snippet': article.get('snippet', 'Нет описания')[:200],
                        'link': article.get('link', '#'),
                        'source': source_text[:80]
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
    st.title("🔍 Умный поиск по Notion")
    st.markdown("Ищет по **названиям и содержимому** ваших страниц")
    
    # ========== SIDEBAR ==========
    st.sidebar.title("⚙️ Настройки")
    
    # Статус API
    st.sidebar.subheader("🔑 Статус API")
    
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        st.write("**Notion:**")
        st.write("✅" if NOTION_API_KEY else "❌")
    
    with col2:
        st.write("**Google News:**")
        st.write("✅" if SERPER_API_KEY else "⚠️")
    
    # Режим поиска
    st.sidebar.subheader("🔍 Режим поиска")
    search_mode = st.sidebar.radio(
        "Тип поиска:",
        ["📝 Быстрый (только заголовки)", "🔍 Глубокий (заголовки + содержимое)"],
        index=1
    )
    
    # Лимит отображения
    st.sidebar.subheader("📊 Лимиты")
    limit_high = st.sidebar.slider("Высокая релевантность", 0, 50, 50, help="Макс. страниц для показа")
    limit_medium = st.sidebar.slider("Средняя релевантность", 0, 50, 50, help="Макс. страниц для показа")
    limit_low = st.sidebar.slider("Низкая релевантность", 0, 50, 50, help="Макс. страниц для показа")
    
    # Инструкция
    with st.sidebar.expander("📖 Как пользоваться"):
        st.markdown("""
        ### 🔍 **Что ищет:**
        1. **В заголовках** всех страниц
        2. **В тексте** внутри страниц
        3. **Отдельные слова** и **фразы**
        4. **Короткие слова** (2+ буквы)
        
        ### ⚡ **Советы:**
        - Используйте **конкретные слова**
        - **Не используйте** стоп-слова (и, в, на)
        - Для точной фразы - **вводите полностью**
        """)
    
    # ========== ПОИСКОВАЯ ФОРМА ==========
    st.markdown("---")
    
    col1, col2 = st.columns([4, 1])
    
    with col1:
        query = st.text_input(
            "Введите запрос:",
            placeholder="Например: звезда, один из, новый проект...",
            key="search_query",
            help="Ищет отдельные слова и фразы"
        )
    
    with col2:
        st.write("")
        st.write("")
        search_clicked = st.button("🔍 Найти", type="primary", use_container_width=True)
    
    if search_clicked and query:
        with st.spinner(f"🔍 Ищу '{query}'..."):
            # Определяем режим поиска
            mode = "deep" if "Глубокий" in search_mode else "title"
            
            # Поиск в Notion
            notion_results, notion_error = smart_search_notion(query, mode)
            
            # Поиск новостей
            news_results, news_error = fetch_google_news(query)
        
        # ========== РЕЗУЛЬТАТЫ ==========
        if notion_error:
            st.error(f"**Ошибка Notion:** {notion_error}")
        
        # Notion результаты
        if notion_results:
            total_found = len(notion_results)
            st.subheader(f"📚 Найдено в Notion: {total_found} страниц")
            
            # Статистика по релевантности
            high_relevance = [r for r in notion_results if r['relevance'] >= 50]
            medium_relevance = [r for r in notion_results if 20 <= r['relevance'] < 50]
            low_relevance = [r for r in notion_results if r['relevance'] < 20]
            
            # Отображаем статистику
            col_stats1, col_stats2, col_stats3 = st.columns(3)
            with col_stats1:
                st.metric("🔥 Высокая", len(high_relevance))
            with col_stats2:
                st.metric("⭐ Средняя", len(medium_relevance))
            with col_stats3:
                st.metric("💡 Низкая", len(low_relevance))
            
            # Показываем высокорелевантные
            if high_relevance:
                st.markdown("##### 🔥 Высокая релевантность:")
                shown_high = 0
                for i, page in enumerate(high_relevance):
                    if shown_high < limit_high:
                        with st.expander(f"**{i+1}. {page['title']}** - Релевантность: {page['relevance']}%", expanded=(i == 0)):
                            show_page_result(page, query)
                        shown_high += 1
            
            # Показываем среднюю релевантность
            if medium_relevance:
                st.markdown("##### ⭐ Средняя релевантность:")
                shown_medium = 0
                for i, page in enumerate(medium_relevance):
                    if shown_medium < limit_medium:
                        with st.expander(f"**{i+1}. {page['title']}** - Релевантность: {page['relevance']}%", expanded=False):
                            show_page_result(page, query)
                        shown_medium += 1
            
            # Показываем низкую релевантность
            if low_relevance:
                st.markdown("##### 💡 Низкая релевантность:")
                shown_low = 0
                for i, page in enumerate(low_relevance):
                    if shown_low < limit_low:
                        with st.expander(f"**{i+1}. {page['title']}** - Релевантность: {page['relevance']}%", expanded=False):
                            show_page_result(page, query)
                        shown_low += 1
        
        elif NOTION_API_KEY:
            st.info("😔 По вашему запросу ничего не найдено")
            st.markdown("""
            **Возможные причины:**
            - Слова запроса нет в ваших страницах
            - Страницы не содержат текст
            - API не имеет доступа к страницам
            
            **Попробуйте:**
            - Другие слова или синонимы
            - Более общие запросы
            - Проверить доступ интеграции к страницам
            """)
        
        # Новости
        st.markdown("---")
        st.subheader(f"🌐 Новости ({len(news_results) if news_results else 0})")
        
        if news_results:
            for i, article in enumerate(news_results):
                with st.expander(f"**{i+1}. {article['title']}**"):
                    st.markdown(f"**📰 Источник:** {article['source']}")
                    st.write(article['snippet'])
                    st.markdown(f"[📖 Читать →]({article['link']})")
        else:
            st.info("📰 Новостей не найдено")
        
    # ========== ПРИ ПУСТОМ ПОИСКЕ ==========
    else:
        show_welcome_screen()

# =================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===================
def show_page_result(page, query):
    """Показывает результат поиска по странице"""
    # Метаинформация
    col1, col2 = st.columns(2)
    
    with col1:
        if page.get('last_edited'):
            st.caption(f"📅 {page['last_edited']}")
    
    with col2:
        if page.get('found_in'):
            st.caption(f"📍 Найдено в: {page['found_in']}")
    
    # Сниппет
    if page['snippet']:
        st.markdown("**Найдено:**")
        
        # Показываем сниппет с подсветкой
        snippet_html = page['snippet']
        
        # Добавляем больше контекста если нужно
        if len(page['snippet']) < 100 and page['content']:
            # Находим больше текста вокруг
            content_lower = page['content'].lower()
            query_lower = query.lower()
            
            # Ищем первое вхождение
            pos = content_lower.find(query_lower)
            if pos != -1:
                start = max(0, pos - 100)
                end = min(len(page['content']), pos + 200)
                extra_snippet = page['content'][start:end]
                
                if start > 0:
                    extra_snippet = "..." + extra_snippet
                if end < len(page['content']):
                    extra_snippet = extra_snippet + "..."
                
                # Подсвечиваем запрос
                for word in query_lower.split():
                    if len(word) > 2:
                        extra_snippet = re.sub(
                            r'(\b' + re.escape(word) + r'\b)',
                            r'**\1**',
                            extra_snippet,
                            flags=re.IGNORECASE
                        )
                
                snippet_html = extra_snippet
        
        st.markdown(snippet_html)
    
    # Ссылка на страницу
    st.markdown("")
    
    link_col1, link_col2 = st.columns(2)
    
    with link_col1:
        # ПРЯМАЯ ССЫЛКА НА КОНКРЕТНУЮ СТРАНИЦУ
        if page['link']:
            st.markdown(f"[🔗 Открыть страницу в Notion]({page['link']})")
        else:
            st.markdown(f"[🔗 Открыть страницу в Notion](https://www.notion.so/{page['id'].replace('-', '')})")
    
    with link_col2:
        if page['content'] and len(page['content']) > 50:
            if st.button("📄 Показать больше текста", key=f"more_{page['id']}"):
                # Показываем первые 500 символов
                preview = page['content'][:500]
                if len(page['content']) > 500:
                    preview += "..."
                
                # Подсвечиваем запрос
                for word in query.lower().split():
                    if len(word) > 2:
                        preview = re.sub(
                            r'(\b' + re.escape(word) + r'\b)',
                            r'**\1**',
                            preview,
                            flags=re.IGNORECASE
                        )
                
                st.markdown("**Полный текст:**")
                st.markdown(preview)

def show_welcome_screen():
    """Показывает приветственный экран"""
    st.markdown("---")
    
    # Информация
    st.info("""
    **🔍 Возможности поиска:**
    - Ищет **отдельные слова** (от 2 букв)
    - Находит **словосочетания**
    - Ищет **в заголовках** и **внутри текста**
    - **Подсвечивает** найденное
    - **Сортирует** по релевантности
    - **Прямые ссылки** на страницы Notion
    - Показывает **все найденные страницы**
    """)
    
    # Статистика
    if NOTION_API_KEY:
        st.success("✅ Notion API подключен")
    else:
        st.warning("⚠️ Notion API не настроен")

# =================== ЗАПУСК ПРИЛОЖЕНИЯ ===================
if __name__ == "__main__":
    main()
