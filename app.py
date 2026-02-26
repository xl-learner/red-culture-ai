# app.py
import streamlit as st
import os
import time
from db_manager import get_stories, get_story_content, get_dashboard_stats, log_ai_usage,get_all_categories
from ai_engine import generate_story_text, text_to_speech

# ================= 1. 页面配置 =================
st.set_page_config(
    page_title="赣红智声 - 江西红色文化智能讲述平台",
    page_icon="🇨🇳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS 样式
st.markdown("""
    <style>
    .main-title { font-size: 3.5em; color: #D32F2F; text-align: center; font-weight: 800; font-family: "Microsoft YaHei"; }
    .sub-title { font-size: 1.2em; color: #888; text-align: center; margin-bottom: 30px; letter-spacing: 2px; }
    .stButton>button { background-color: #D32F2F; color: white; border-radius: 8px; }
    .stButton>button:hover { background-color: #B71C1C; }
    </style>
""", unsafe_allow_html=True)

# ================= 2. 侧边栏 =================
if os.path.exists("img/sidebar_logo.png"):
    st.sidebar.image("img/sidebar_logo.png", width=100)
st.sidebar.title("🚩 导航菜单")
page = st.sidebar.radio("功能模块：", ["🏠 首页数据看板", "📖 红色故事库", "🎙️ AI 智能创作", "💬 红色百科问答"])

# 在侧边栏增加一个全局设置
st.sidebar.markdown("---")
st.sidebar.markdown("### 🔊 播音员设置")
# 定义声音映射
voice_options = {
    "🎙️ 云扬 (沉稳男声)": "zh-CN-YunyangNeural",
    "🎙️ 晓晓 (亲切女声)": "zh-CN-XiaoxiaoNeural",
    "🎙️ 云希 (活泼少年)": "zh-CN-YunxiNeural"
}
selected_voice_label = st.sidebar.selectbox("选择讲解员声音：", list(voice_options.keys()))
selected_voice_id = voice_options[selected_voice_label]  # 获取对应的ID传给AI

st.sidebar.info("💡 提示：在上方切换声音后，点击生成语音即可听到不同角色的解说。")
st.sidebar.markdown("Designed by zwl")

# ================= 3. 首页 (接入真实数据) =================
if page == "🏠 首页数据看板":
    st.markdown('<div class="main-title">赣红智声</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">—— 基于大模型的江西红色文化智能讲述系统 ——</div>', unsafe_allow_html=True)

    if os.path.exists("img/banner.jpg"):
        st.image("img/banner.jpg", use_container_width=True)

    st.divider()

    # >>> 获取真实数据库统计 <<<
    try:
        stats = get_dashboard_stats()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📚 故事总收录", f"{stats['total_stories']} 篇", "不断更新")
        col2.metric("🏷️ 故事分类", f"{stats['total_categories']} 大类", "涵盖全面")
        col3.metric("🤖 AI 响应次数", f"{stats['ai_total_count']} 次", "实时交互数据")
        # 估算时长：假设语速：240字/分钟，保留2位小数，
        col4.metric("⏳ 累计内容时长", f"{stats['total_hours']} 分钟", "基于标准语速(240字/分)估算")

    except Exception as e:
        st.error(f"连接数据库失败，无法加载数据看板: {e}")

    st.divider()
    
    # 使用 Tabs 标签页让内容更紧凑
    tab1, tab2, tab3 = st.tabs(["🌟 项目背景", "🛠️ 技术架构", "💡 创新亮点"])

    with tab1:
        c1, c2 = st.columns([1, 2])
        with c1:
            intro_path = "img/intro.jpg"
            if os.path.exists(intro_path):
                st.image(intro_path, caption="星星之火，可以燎原", use_container_width=True)
            else:
                st.info("图片加载中...")
        with c2:
            st.markdown("""
                ### 传承红色基因
                江西是一片充满红色记忆的红土地。从南昌起义的第一声枪响，到井冈山的星星之火，再到瑞金的红都风云，孕育了伟大的井冈山精神、苏区精神和长征精神。
                本项目利用最新的人工智能技术，通过 **AI 写作** 和 **AI 语音**，让静止的历史资料“活”起来。
                **本项目旨在：**
                1. 解决传统文字资料枯燥乏味的问题。
                2. 利用 **AIGC (生成式人工智能)** 技术，为红色故事赋予新的生命力。
                3. 通过互动问答，增强青年学生的参与感。
                """)

    with tab2:
        st.markdown("""
            本系统采用前后端分离的现代化架构：
            *   **前端交互**：Streamlit (Python)
            *   **数据存储**：SQLite 嵌入式数据库
            *   **核心大脑**：智谱 AI (GLM-4) 大语言模型
            *   **语音引擎**：Microsoft Edge TTS
            """)

    with tab3:
        st.success("✅ **情感化表达**：AI 不仅生成文字，还能模拟真人的情感语调。")
        st.info("✅ **个性化定制**：用户想听什么，AI 就讲什么，打破了千篇一律的解说词。")

# ================= 4. 红色故事库 (搜索+分类) =================
elif page == "📖 红色故事库":
    st.title("📖 经典红色故事点播")

    # --- 1. 获取动态分类 ---
    # 从数据库查出所有分类
    db_categories = get_all_categories()
    # 组合成下拉菜单选项：['全部'] + ['人物传记', '重大事件'...]
    filter_options = ["全部"] + db_categories

    # --- 2. 顶部筛选区 ---
    c1, c2 = st.columns([1, 2])
    with c1:
        # 使用动态获取的列表
        category_filter = st.selectbox("📂 分类筛选", filter_options)
    with c2:
        search_keyword = st.text_input("🔍 搜索故事标题", placeholder="输入关键词，如：井冈山")

    st.markdown("---")

    # --- 3. 获取数据 & 分页逻辑 ---
    try:
        # 获取符合条件的所有故事
        all_stories = get_stories(category_filter, search_keyword)

        if not all_stories:
            st.warning("⚠️ 没有找到符合条件的故事。")
        else:
            # === 分页配置 ===
            ITEMS_PER_PAGE = 10  # 每页显示 10 条
            total_items = len(all_stories)
            # 计算总页数 (向上取整)
            total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

            # 初始化页码状态
            if 'story_page' not in st.session_state:
                st.session_state.story_page = 1

            # 防止筛选后页码超出范围（比如原来在第5页，筛选后只有1页了）
            if st.session_state.story_page > total_pages:
                st.session_state.story_page = 1

            # === 布局：左侧列表，右侧详情 ===
            col_list, col_content = st.columns([1, 2.5])

            with col_list:
                st.markdown(f"**共 {total_items} 篇** (第 {st.session_state.story_page}/{total_pages} 页)")

                # 计算当前页的数据切片
                start_idx = (st.session_state.story_page - 1) * ITEMS_PER_PAGE
                end_idx = start_idx + ITEMS_PER_PAGE
                current_page_stories = all_stories[start_idx:end_idx]

                # 显示当前页的故事列表
                page_titles = [s['title'] for s in current_page_stories]
                # 注意：key需要动态变化，否则翻页时会报错
                selected_title = st.radio("故事列表：", page_titles, key=f"radio_page_{st.session_state.story_page}")

                # === 翻页按钮 ===
                st.markdown("<br>", unsafe_allow_html=True)
                b_col1, b_col2 = st.columns(2)
                with b_col1:
                    if st.button("⬅️ 上一页", disabled=(st.session_state.story_page == 1)):
                        st.session_state.story_page -= 1
                        st.rerun()
                with b_col2:
                    if st.button("下一页 ➡️", disabled=(st.session_state.story_page == total_pages)):
                        st.session_state.story_page += 1
                        st.rerun()

            with col_content:
                if selected_title:
                    # 获取选中故事的详情
                    content = get_story_content(selected_title)

                    # 漂亮的展示框
                    st.markdown(f"## {selected_title}")

                    # 找到当前故事的分类
                    current_cat = next((s['category'] for s in all_stories if s['title'] == selected_title), "未知")
                    st.caption(f"🏷️ 分类：{current_cat} | 🎙️ 当前语音：{selected_voice_label}")

                    # 文本显示区域 (固定高度，带滚动条，防止页面忽长忽短)
                    st.markdown(
                        f"""
                        <div style="height: 200px; overflow-y: auto; background-color: #262730; padding: 20px; border-radius: 10px; border: 1px solid #444;">
                            <p style="color: #eee; line-height: 1.6;">{content}</p>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    st.markdown("---")

                    # 播放按钮
                    if st.button("🔊 生成语音讲解", key="db_tts", use_container_width=True):
                        with st.spinner(f"正在使用【{selected_voice_label}】合成语音..."):
                            filename = "db_story_audio.mp3"
                            if text_to_speech(content, filename, selected_voice_id):
                                st.audio(filename, format="audio/mp3")
                                st.success("🎉 讲解生成完毕！")
                                log_ai_usage("语音合成")
                            else:
                                st.error("语音合成失败。")

    except Exception as e:
        st.error(f"数据库查询出错: {e}")

# ================= 5. AI 创作 (接入声音选择) =================
elif page == "🎙️ AI 智能创作":
    # --- 1. 初始化 Session State (记忆存储) ---
    if "ai_creation_data" not in st.session_state:
        st.session_state.ai_creation_data = {
            "topic": "",
            "text": "",
            "audio_file": None,
            "has_generated": False,
            "voice_id": ""
        }

    st.markdown('<div class="main-title" style="font-size: 2.5em;">🎙️ 红色故事智能创作室</div>', unsafe_allow_html=True)
    st.caption("💡 请输入关键词，AI 将为您现场写稿，并由精选播音员深情朗读。")

    st.divider()

    # --- 2. 输入区 ---
    with st.form("creation_form", border=False):
        col_input, col_btn = st.columns([4, 1])

        with col_input:
            user_input = st.text_input(
                "请输入创作主题",
                placeholder="例如：用生动的语言讲一下朱德的扁担...",
                label_visibility="collapsed"
            )

        with col_btn:
            submit_click = st.form_submit_button("✨ 立即创作", use_container_width=True, type="primary")

    # --- 3. 核心逻辑 A：全新创作 (用户点击了按钮) ---
    if submit_click and user_input:
        st.session_state.ai_creation_data["topic"] = user_input

        # A. 生成文案
        with st.spinner("✍️ AI 正在奋笔疾书..."):
            generated_text = generate_story_text(user_input, mode="story")
            st.session_state.ai_creation_data["text"] = generated_text
            st.session_state.ai_creation_data["has_generated"] = True
            log_ai_usage("AI写作")

        # B. 首次生成语音
        if "API Key" not in generated_text:
            with st.spinner(f"🎙️ 【{selected_voice_label}】正在录制语音..."):
                audio_filename = f"tts_{int(time.time())}.mp3"
                if text_to_speech(generated_text, audio_filename, selected_voice_id):
                    st.session_state.ai_creation_data["audio_file"] = audio_filename
                    st.session_state.ai_creation_data["voice_id"] = selected_voice_id
                    log_ai_usage("语音合成")
                else:
                    st.error("语音合成失败")



    # --- 4. 核心逻辑 B：静默切换播音员 (监听侧边栏变化) ---
    # 如果不是刚点击创作按钮，但已经生成过内容，此时检查侧边栏声音是否变了
    elif st.session_state.ai_creation_data.get("has_generated"):
        current_saved_voice = st.session_state.ai_creation_data.get("voice_id", "")

        # 发现侧边栏的声音ID 和 存起来的声音ID 不一样！触发重新录制！
        if selected_voice_id != current_saved_voice and current_saved_voice != "":
            with st.spinner(f"🔄 检测到播音员切换，正在请【{selected_voice_label}】重新录制..."):
                generated_text = st.session_state.ai_creation_data["text"]
                audio_filename = f"tts_{int(time.time())}.mp3"

                if text_to_speech(generated_text, audio_filename, selected_voice_id):
                    # 录制成功，更新状态
                    st.session_state.ai_creation_data["audio_file"] = audio_filename
                    st.session_state.ai_creation_data["voice_id"] = selected_voice_id
                    log_ai_usage("语音合成")
                else:
                    st.error("重新生成语音失败")



    # --- 5. 结果展示区 (读取最新状态展示) ---
    if st.session_state.ai_creation_data.get("has_generated"):
        st.markdown("### 🎬 创作成果")

        res_col1, res_col2 = st.columns([2, 1])

        with res_col1:
            st.markdown("#### 📜 演说文案")
            content = st.session_state.ai_creation_data["text"]
            st.markdown(
                f"""
                <div style="background-color: #2b2b2b; padding: 20px; border-radius: 10px; border-left: 5px solid #D32F2F; color: #E0E0E0; line-height: 1.8;">
                    {content}
                </div>
                """,
                unsafe_allow_html=True
            )

        with res_col2:
            st.markdown("#### 🎧 语音试听")
            with st.container(border=True):
                st.markdown(f"**当前播音员：**\n\n`{selected_voice_label}`")
                st.divider()

                audio_path = st.session_state.ai_creation_data["audio_file"]
                if audio_path and os.path.exists(audio_path):
                    st.audio(audio_path, format="audio/mp3")

                    with open(audio_path, "rb") as file:
                        st.download_button(
                            label="📥 下载音频 MP3",
                            data=file,
                            file_name="red_story_ai.mp3",
                            mime="audio/mp3",
                            use_container_width=True
                        )
                else:
                    st.warning("音频文件丢失或生成失败")

            st.markdown("<br>", unsafe_allow_html=True)
            # 这里是真正需要 rerun 的地方，因为要把底层的状态清空并刷新页面
            if st.button("🗑️ 清空重置", use_container_width=True):
                st.session_state.ai_creation_data = {
                    "topic": "",
                    "text": "",
                    "audio_file": None,
                    "has_generated": False,
                    "voice_id": ""
                }
                st.rerun()

    else:
        st.info("👋 欢迎来到创作室！在上方输入主题按回车，即可生成专属红色故事。")

# ================= 6. 问答 =================
elif page == "💬 红色百科问答":
    st.title("💬 红色文化智能问答")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("请输入问题，例如：南昌起义是什么时候..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                response_text = generate_story_text(prompt, mode="chat")
                st.markdown(response_text)
                log_ai_usage("智能问答")
        st.session_state.messages.append({"role": "assistant", "content": response_text})
