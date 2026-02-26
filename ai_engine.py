# ai_engine.py
import asyncio
import edge_tts
from zhipuai import ZhipuAI
import re

# ================= 配置区域 =================
# 1. API Key
API_KEY = "465ead53815946e28ff7355d7a46e7cf.zcZ7G0RARRhCzQbF"

# 2. 这里是可以选择的声音列表
# xiaoxiao: 温暖女声, yunyang: 专业男播音, yunxi: 活泼男声
VOICE_NAME = "zh-CN-YunyangNeural"


# ===========================================

# 辅助函数：清洗Markdown符号，只留纯文本给语音合成
def remove_markdown_symbols(text):
    # 去掉每行开头或结尾处的连续 # 及其两侧空白
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    # 去掉加粗的 **
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    # 去掉列表的 - 或 *（行首）
    text = re.sub(r'^\s*[\-\*]\s+', '', text, flags=re.MULTILINE)
    # 去掉链接 [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # 去掉引用符号 >
    text = re.sub(r'^\s*>\s+', '', text, flags=re.MULTILINE)
    return text

# 1. 智能文案生成函数 (增加了 mode 参数)
def generate_story_text(prompt_text, mode="story"):
    """
    mode="story": 创作模式，激情澎湃，适合演讲。
    mode="chat":  问答模式，客观冷静，适合百科。
    """
    print(f"正在请求AI生成内容：{prompt_text} (模式: {mode}) ...")

    if "这里填" in API_KEY:
        return "请填写 API Key..."

    #根据模式选择不同的“人设”
    if mode == "story":
        system_prompt = "你是一名江西红色文化的金牌讲解员，你的语言风格生动、激昂、富有感染力，适合青年学生听。文章结构要清晰，要有‘同学们’之类的互动感。"
    else: # chat 模式
        system_prompt = "你是一名博学的红色历史研究员。请用客观、准确、简洁的语言回答用户的问题。直接回答核心内容，不要用演讲语气，不要说'同学们'，不要长篇大论。"

    try:
        client = ZhipuAI(api_key=API_KEY)
        response = client.chat.completions.create(
            model="glm-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt_text}
            ],
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI生成出错: {e}"


# 2. 语音合成函数 (文本 -> MP3文件)
async def text_to_speech_async(text, output_filename, voice):
    """
    异步函数：将文字转换为语音文件
    """
     # 默认使用 voice 参数，如果没传则用男声
    clean_text = remove_markdown_symbols(text)
    clean_text = clean_text.replace('#', '').replace('*', '').replace('`', '')
    voice_id = voice if voice else "zh-CN-YunyangNeural"
    communicate = edge_tts.Communicate(clean_text, voice_id)
    await communicate.save(output_filename)


def text_to_speech(text, output_filename="output.mp3", voice="zh-CN-YunyangNeural"):
    """
    封装函数：供外部直接调用，不需要管异步逻辑
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # 把 voice 参数传进去
        loop.run_until_complete(text_to_speech_async(text, output_filename, voice))
        return True
    except Exception as e:
        print(f"语音合成失败: {e}")
        return False


