import streamlit as st
import requests
import json
import datetime
import time

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
            # Получаем строки таблицы
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
            
            # Также проверяем свойства с типом 'rich_text'
            if prop_value.get('type') == 'rich_text':
                rich_text = prop_value.get('rich_text', [])
                for text_item in rich_text:
                    if 'plain_text' in text_item:
                        return text_item['plain_text']
        
        return "Без названия"
    except:
        return "Без названия"

def search_notion_with_fallback(query, filter_by_nolan=True):
    """Умный поиск в Notion с несколькими стратегиями"""
    if not NOTION_API_KEY:
        return None, "❌ API ключ Notion не найден"
    
    results = []
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    
    # Стратегия 1: Поиск по всем страницам Notion
    url = "https://api.notion.com/v1/search"
    
    # Разбиваем запрос на слова
    query_words = query.lower().split()
    
    # Ключевые слова для Нолана
    nolan_keywords = ["нолан", "nolan", "кристофер", "christopher", "опенгеймер", 
                     "oppenheimer", "интерстеллар", "inception", "тенет", "tenet", 
                     "интерстеллар", "interstellar", "дюнкерк", "dunkirk"]
    
    # Функция проверки релевантности
    def check_relevance(text):
        text_lower = text.lower()
        
        # Проверяем наличие всех слов запроса
        all_words_match = all(word in text_lower for word in query_words if len(word) > 2)
        
        # Проверяем фильтр по Нолану
        nolan_match = not filter_by_nolan or any(keyword in text_lower for keyword in nolan_keywords)
        
        return all_words_match or nolan_match
    
    try:
        # Поиск с помощью Notion API
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
        
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            pages = data.get("results", [])
            
            for page in pages:
                try:
                    # Получаем заголовок
                    title = get_page_title(page)
                    
                    # Получаем ID и URL
                    page_id = page.get('id', '')
                    page_url = page.get('url', f"https://www.notion.so/{page_id.replace('-', '')}")
                    
                    # Получаем содержимое страницы
                    content_text, content_error = get_page_content(page_id)
                    
                    if content_error:
                        # Если не удалось получить содержимое, используем только заголовок
                        full_text = title
                    else:
                        full_text = title + " " + content_text
                    
                    # Проверяем релевантность
                    if check_relevance(full_text):
                        # Дата последнего редактирования
                        last_edited = page.get('last_edited_time', '')
                        if last_edited:
                            try:
                                dt = datetime.datetime.fromisoformat(last_edited.replace('Z', '+00:00'))
                                last_edited = dt.strftime("%d.%m.%Y %H:%M")
                            except:
                                pass
                        
                        # Создаем сниппет
                        snippet = create_highlighted_snippet(title, content_text, query)
                        
                        # Вычисляем релевантность
                        relevance_score = calculate_relevance_score(full_text, query)
                        
                        results.append({
                            'title': title,
                            'content': content_text if not content_error else "",
                            'snippet': snippet,
                            'link': page_url,
                            'source': 'Notion',
                            'last_edited': last_edited,
                            'id': page_id,
                            'relevance': relevance_score
                        })
                        
                except Exception as e:
                    continue
            
            # Сортируем по релевантности
            results.sort(key=lambda x: x['relevance'], reverse=True)
            
            return results[:15], None  # Ограничиваем 15 результатами
        
        elif response.status_code == 401:
            return None, "❌ Неверный API ключ Notion"
        elif response.status_code == 429:
            return None, "❌ Превышен лимит запросов. Подождите минуту."
        else:
            return None, f"❌ Ошибка API: {response.status_code}"
    
    except Exception as e:
        return None, f"❌ Ошибка подключения: {e}"

def get_page_content(page_id):
    """Получает содержимое страницы Notion"""
    if not NOTION_API_KEY:
        return "", "❌ API ключ Notion не найден"
    
    try:
        # Получаем блоки страницы
        url = f"https://api.notion.com/v1/blocks/{page_id}/children"
        headers = {
            "Authorization": f"Bearer {NOTION_API_KEY}",
            "Notion-Version": "2022-06-28"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            blocks = data.get('results', [])
            text_content = extract_text_from_blocks(blocks)
            return text_content, None
        else:
            return "", f"❌ Ошибка: {response.status_code}"
    
    except Exception as e:
        return "", f"❌ Ошибка подключения: {e}"

def create_highlighted_snippet(title, content, query, max_length=300):
    """Создает сниппет с подсветкой найденных слов"""
    # Объединяем заголовок и содержимое для поиска
    full_text = title + " " + content
    full_text_lower = full_text.lower()
    query_lower = query.lower()
    
    # Ищем все слова запроса
    query_words = query_lower.split()
    
    # Находим лучшую позицию для сниппета
    best_position = -1
    best_score = 0
    
    for i in range(0, len(full_text_lower) - 50):
        score = 0
        text_slice = full_text_lower[i:i+200]
        
        # Считаем сколько слов запроса в этом срезе
        for word in query_words:
            if len(word) > 2 and word in text_slice:
                score += 10
        
        if score > best_score:
            best_score = score
            best_position = i
    
    # Если не нашли хорошей позиции, берем начало
    if best_position == -1:
        snippet = full_text[:max_length]
        if len(full_text) > max_length:
            snippet += "..."
        return snippet
    
    # Вырезаем сниппет вокруг лучшей позиции
    start = max(0, best_position - 50)
    end = min(len(full_text), best_position + 250)
    
    snippet = full_text[start:end]
    
    # Добавляем многоточия
    if start > 0:
        snippet = "..." + snippet
    if end < len(full_text):
        snippet = snippet + "..."
    
    # Подсвечиваем слова запроса
    for word in query_words:
        if len(word) > 2:
            # Игнорируем регистр при подсветке
            snippet_lower = snippet.lower()
            word_start = snippet_lower.find(word)
            
            while word_start != -1:
                # Заменяем найденное слово на подсвеченную версию
                original_word = snippet[word_start:word_start + len(word)]
                highlighted = f"**{original_word}**"
                
                snippet = snippet[:word_start] + highlighted + snippet[word_start + len(word):]
                
                # Ищем следующее вхождение
                snippet_lower = snippet.lower()
                word_start = snippet_lower.find(word, word_start + len(highlighted) - 2)
    
    return snippet

def calculate_relevance_score(text, query):
    """Вычисляет оценку релевантности"""
    text_lower = text.lower()
    query_lower = query.lower()
    query_words = query_lower.split()
    
    score = 0
    
    # Бонус за точное совпадение фразы
    if query_lower in text_lower:
        score += 100
    
    # Бонус за каждое слово
    for word in query_words:
        if len(word) > 2:
            # В заголовке
            if word in text_lower:
                score += 30
            # В содержимом
            count = text_lower.count(word)
            score += min(count, 5) * 10
    
    # Бонус за близость слов друг к другу
    if len(query_words) > 1:
        # Ищем позиции всех слов
        positions = []
        for word in query_words:
            if len(word) > 2:
                pos = text_lower.find(word)
                if pos != -1:
                    positions.append(pos)
        
        # Если нашли несколько слов, вычисляем их близость
        if len(positions) > 1:
            positions.sort()
            total_distance = sum(positions[i+1] - positions[i] for i in range(len(positions)-1))
            if total_distance < 100:  # Слова близко друг к другу
                score += 50
    
    return score

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
    st.title("🔍 Улучшенный поиск по Notion")
    st.markdown("Ищет по **названиям и содержимому** ваших страниц Notion")
    
    # ========== SIDEBAR ==========
    st.sidebar.title("⚙️ Настройки поиска")
    
    # Настройки
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        filter_nolan = st.checkbox("Только Нолан", value=True,
                                 help="Показывать только связанное с Кристофером Ноланом")
    
    with col2:
        search_mode = st.selectbox(
            "Режим поиска",
            ["📝 Быстрый (только заголовки)", "🔍 Глубокий (заголовки + содержимое)"],
            index=1
        )
    
    # Статистика API
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔑 Статус API")
    
    status_col1, status_col2 = st.sidebar.columns(2)
    
    with status_col1:
        st.write("**Notion:**")
        st.write("✅" if NOTION_API_KEY else "❌")
        
        st.write("**Google News:**")
        st.write("✅" if SERPER_API_KEY else "⚠️")
    
    with status_col2:
        st.write("**Фильмы:**")
        st.write("✅" if OMDB_API_KEY else "⚠️")
    
    # Инструкция
    with st.sidebar.expander("📖 Как пользоваться"):
        st.markdown("""
        ### 🔍 **Что ищет:**
        1. **В заголовках** всех ваших страниц Notion
        2. **В содержимом** страниц (текст, списки, таблицы)
        3. **В новостях** о Кристофере Нолане
        
        ### ✨ **Особенности:**
        - **Подсвечивает** найденные слова
        - **Сортирует** по релевантности
        - **Показывает** ссылки на страницы Notion
        - **Кэширует** результаты для скорости
        
        ### 💡 **Советы:**
        - Используйте **ключевые слова**
        - **Цитируйте** точные фразы
        - **Фильтруйте** по тематике Нолана
        """)
    
    # ========== ПОИСКОВАЯ ФОРМА ==========
    st.markdown("---")
    
    col1, col2 = st.columns([4, 1])
    
    with col1:
        query = st.text_input(
            "Введите запрос:",
            placeholder="Например: 'новый проект', 'интервью 2024', 'награды'...",
            key="search_query",
            help="Ищет по названиям и содержимому страниц"
        )
    
    with col2:
        st.write("")
        st.write("")
        search_clicked = st.button("🔍 Найти", type="primary", use_container_width=True)
    
    if search_clicked and query:
        # Индикатор поиска
        with st.spinner(f"🔍 Ищу '{query}'..."):
            # Задержка для плавности
            time.sleep(0.5)
            
            # Поиск в Notion
            notion_results, notion_error = search_notion_with_fallback(query, filter_by_nolan=filter_nolan)
            
            # Поиск новостей
            news_results, news_error = fetch_google_news(query)
        
        # ========== РЕЗУЛЬТАТЫ ==========
        if notion_error:
            st.error(f"**Ошибка Notion:** {notion_error}")
        elif news_error:
            st.warning(f"**Новости:** {news_error}")
        
        # Notion результаты
        st.subheader(f"📚 Страницы Notion ({len(notion_results) if notion_results else 0})")
        
        if notion_results:
            # Показать первые 10 результатов
            for i, page in enumerate(notion_results[:10]):
                with st.expander(f"**{i+1}. {page['title']}**", expanded=i < 2):
                    # Метаинформация
                    meta_col1, meta_col2 = st.columns(2)
                    
                    with meta_col1:
                        if page.get('last_edited'):
                            st.caption(f"📅 {page['last_edited']}")
                    
                    with meta_col2:
                        st.caption(f"⭐ Релевантность: {page['relevance']}")
                    
                    # Сниппет с подсветкой
                    st.markdown("**Найдено:**")
                    st.markdown(page['snippet'])
                    
                    # Ссылки
                    link_col1, link_col2 = st.columns(2)
                    
                    with link_col1:
                        st.markdown(f"[🔗 Открыть в Notion]({page['link']})")
                    
                    with link_col2:
                        # Кнопка для показа полного текста
                        if page['content'] and st.button(f"📄 Показать текст", key=f"text_{i}"):
                            st.text_area("Содержимое страницы:", page['content'][:1000], height=200)
                    
                    st.markdown("---")
        else:
            st.info("😔 В ваших страницах Notion ничего не найдено")
        
        # Новости
        st.markdown("---")
        st.subheader(f"🌐 Новости ({len(news_results) if news_results else 0})")
        
        if news_results:
            for i, article in enumerate(news_results[:5]):
                with st.expander(f"**{i+1}. {article['title']}**"):
                    st.markdown(f"**📰 Источник:** {article['source']}")
                    st.write(article['snippet'])
                    st.markdown(f"[📖 Читать статью →]({article['link']})")
        else:
            st.info("📰 Новостей по запросу не найдено")
        
        # Быстрые запросы
        st.markdown("---")
        st.subheader("💡 Попробуйте также:")
        
        quick_queries = [
            ("🎬 Новые проекты", "Что сейчас снимает Нолан"),
            ("🏆 Награды", "Оскар и другие премии"),
            ("📰 Интервью", "Последние интервью режиссера"),
            ("🎞️ Фильмография", "Все фильмы Кристофера Нолана"),
            ("🤝 Коллаборации", "С кем работает Нолан"),
            ("📅 График", "Планы и расписание")
        ]
        
        cols = st.columns(3)
        for idx, (title, desc) in enumerate(quick_queries):
            with cols[idx % 3]:
                if st.button(title, key=f"quick_{idx}"):
                    st.session_state.search_query = desc
                    st.rerun()
    
    # ========== ПРИ ПУСТОМ ПОИСКЕ ==========
    else:
        st.markdown("---")
        
        # Примеры
        st.subheader("✨ Примеры запросов:")
        
        examples = [
            ("🎬 Новые фильмы", "Что сейчас в работе у Нолана?"),
            ("🏆 Оскар 2024", "Награды за Опенгеймер"),
            ("📰 Интервью", "Последние выступления режиссера"),
            ("🎞️ Фильмография", "Все работы Кристофера Нолана"),
            ("🤝 Актеры", "С кем работает Нолан"),
            ("📅 Расписание", "Планы на будущее")
        ]
        
        for title, desc in examples:
            if st.button(f"{title}: {desc}", key=f"example_{title}"):
                st.session_state.search_query = desc
                st.rerun()
        
        st.markdown("---")
        
        # Статистика
        st.info("""
        **📊 Возможности поиска:**
        - Ищет в **названиях** всех ваших страниц Notion
        - Ищет в **содержимом** страниц (текст, списки, таблицы)
        - **Подсвечивает** найденные слова
        - **Сортирует** по релевантности
        - Показывает **актуальные новости**
        """)
    
    # ========== ФУТЕР ==========
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; font-size: 0.9em; padding: 10px;">
        <p>🔍 Поиск по Notion | Ищет в названиях и содержимом | Автоматически подсвечивает найденное</p>
    </div>
    """, unsafe_allow_html=True)

# =================== ЗАПУСК ПРИЛОЖЕНИЯ ===================
if __name__ == "__main__":
    main()
