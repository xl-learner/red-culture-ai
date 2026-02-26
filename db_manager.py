# db_manager.py
import sqlite3

def get_db_connection():
    conn = sqlite3.connect('red_culture.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row  # 让查询结果可以通过列名访问(像字典一样)
    return conn

# 1. 获取所有故事
def get_stories(category=None, search_query=None):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sql = "SELECT * FROM stories WHERE 1=1"
    params = []
    if category and category != "全部":
        sql += " AND category = ?"
        params.append(category)
    if search_query:
        sql += " AND title LIKE ?"
        params.append(f"%{search_query}%")
    rows = cursor.fetchall()
    stories = [dict(row) for row in rows]
    conn.close()
    return stories

# 2. 获取单个故事内容
def get_story_content(title):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT content FROM stories WHERE title = %s", (title,))
    result = cursor.fetchone()
    conn.close()
    return result['content'] if result else None

# 3. 记录 AI 使用日志
def log_ai_usage(action_type):
    """
    每次调用AI时执行此函数，记录一次使用
    action_type: '写作', '问答', '语音'
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO ai_logs (action_type) VALUES (%s)", (action_type,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"日志记录失败: {e}")

# 4. 获取真实统计数据
def get_dashboard_stats():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 统计故事总数
    cursor.execute("SELECT COUNT(*) as total FROM stories")
    total_stories = cursor.fetchone()['total']

    # 统计分类数量
    cursor.execute("SELECT COUNT(DISTINCT category) as cat_count FROM stories")
    cat_count = cursor.fetchone()['cat_count']

    # 统计真实的 AI 使用次数
    cursor.execute("SELECT COUNT(*) as ai_count FROM ai_logs")
    ai_count = cursor.fetchone()['ai_count']

    # 估算时长
    cursor.execute("SELECT SUM(LENGTH(content)) as total_chars FROM stories")
    res = cursor.fetchone()
    total_chars = res['total_chars'] if res['total_chars'] else 0
    total_hours = round(total_chars / 240 , 2) # 保留两位小数

    conn.close()

    return {
        "total_stories": total_stories,
        "total_categories": cat_count,
        "total_hours": total_hours,
        "ai_total_count": ai_count # 返回真实数据
    }

# 5. 动态获取所有分类
def get_all_categories():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # 查询所有不重复的分类，且不为空
    cursor.execute("SELECT DISTINCT category FROM stories WHERE category IS NOT NULL AND category != ''")
    results = cursor.fetchall()
    conn.close()
    # 把结果转换成一个纯列表，例如 ['人物传记', '重大事件', ...]
    return [row['category'] for row in results]
