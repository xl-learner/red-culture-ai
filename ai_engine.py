# ai_engine.py
import sys
import os
import asyncio
import socket
import re
import subprocess

# 尝试加载 .env 文件（如果存在）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # 如果未安装 python-dotenv，则忽略

import edge_tts
from zhipuai import ZhipuAI
import streamlit as st
import requests
from rag_engine import get_rag_engine

# ================= 配置区域 =================
# API Key - 优先从 .env 文件或系统环境变量读取
# 获取地址: https://open.bigmodel.cn/usercenter/apikeys
API_KEY = os.getenv("ZHIPUAI_API_KEY", "your_api_key_here")

# 默认声音
VOICE_NAME = "zh-CN-YunyangNeural"

# 多轮对话上下文最大 token 数（预留空间给 RAG 检索内容和系统提示）
MAX_CONTEXT_TOKENS = 6000

# ===========================================


def remove_markdown_symbols(text):
    """清洗 Markdown 符号，只留纯文本"""
    text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"^\s*[\-\*]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"^\s*>\s+", "", text, flags=re.MULTILINE)
    return text


def generate_story_text(prompt_text, mode="story"):
    """
    mode="story": 创作模式，适合演讲。
    mode="chat":  问答模式，适合百科。
    """
    print(f"正在请求AI生成内容：{prompt_text} (模式: {mode}) ...")

    if "your_api_key_here" in API_KEY or "这里填" in API_KEY:
        return (
            "请配置有效的智谱AI API密钥。\n"
            "在环境变量中设置 ZHIPUAI_API_KEY 或在 ai_engine.py 中填写正确的 API_KEY。"
        )

    if mode == "story":
        system_prompt = (
            "你是一名江西红色文化的金牌讲解员，你的语言风格生动、激昂、富有感染力，"
            "适合青年学生听。文章结构要清晰，要有'同学们'之类的互动感。"
        )
    else:
        system_prompt = (
            "你是一名博学的红色历史研究员。请用客观、准确、简洁的语言回答用户的问题。"
            "直接回答核心内容，不要用演讲语气，不要说'同学们'，不要长篇大论。"
        )

    try:
        client = ZhipuAI(api_key=API_KEY)
        response = client.chat.completions.create(
            model="glm-4.7",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt_text},
            ],
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI生成出错: {e}"


async def text_to_speech_async(text, output_filename, voice):
    """异步语音合成"""
    clean_text = remove_markdown_symbols(text)
    clean_text = clean_text.replace("#", "").replace("*", "").replace("`", "")
    voice_id = voice if voice else "zh-CN-YunyangNeural"

    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            print(f"尝试语音合成（第{attempt + 1}次/共{max_retries}次）...")
            os.makedirs(os.path.dirname(output_filename) or ".", exist_ok=True)
            communicate = edge_tts.Communicate(
                clean_text, voice_id, rate="+0%", volume="+0%"
            )
            await communicate.save(output_filename)

            if os.path.exists(output_filename) and os.path.getsize(output_filename) > 0:
                print(f"语音合成成功: {output_filename}")
                return True
            else:
                print("生成的文件无效，重试中...")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2

        except Exception as e:
            print(f"第{attempt + 1}次语音合成失败: {e}")
            if attempt < max_retries - 1:
                print(f"等待 {retry_delay} 秒后重试...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
            else:
                print("已达到最大重试次数，语音合成失败")
                raise


def text_to_speech(text, output_filename="audio/output.mp3", voice="zh-CN-YunyangNeural"):
    """同步封装：供外部直接调用"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                asyncio.wait_for(
                    text_to_speech_async(text, output_filename, voice),
                    timeout=120,
                )
            )
            return result
        except asyncio.TimeoutError:
            print("语音合成超时（120秒）")
            return False
    except Exception as e:
        print(f"语音合成失败: {e}")
        return False
    finally:
        try:
            loop.close()
        except Exception:
            pass


def estimate_tokens(text):
    """
    估算文本的 token 数量。
    中文约 1.5 字符/token，英文/数字/符号约 4 字符/token。
    """
    if not text:
        return 0
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]', text))
    other_chars = max(len(text) - chinese_chars, 0)
    return int(chinese_chars / 1.5 + other_chars / 4) + 1


def _expand_query_with_history(current_query, history_messages):
    """
    查询扩展：从历史对话中提取故事标题，拼入当前查询以提升检索命中率。
    
    例如：用户问"请介绍一下这个事件"，从上一轮AI回复中提取到《井冈山会师》，
    扩展为 "请介绍一下这个事件 井冈山会师"，确保关键词匹配。
    
    无历史或历史中无标题时，直接返回原问题。
    """
    if not history_messages:
        return current_query

    # 从最近一条 assistant 消息中提取《...》标题
    titles = []
    for msg in reversed(history_messages):
        if msg["role"] == "assistant":
            found = re.findall(r'《(.+?)》', msg["content"])
            titles.extend(found)
            if titles:
                break  # 只取最近一轮的标题

    if not titles:
        return current_query

    # 去重，拼接标题，扩展查询
    unique_titles = list(dict.fromkeys(titles))  # 保持顺序去重
    title_suffix = " ".join(unique_titles[:3])  # 最多取3个标题
    expanded = f"{current_query} {title_suffix}"

    print(f"[查询扩展] '{current_query[:30]}...' -> '{expanded[:60]}...'")
    return expanded


def _apply_sliding_window(history_messages, max_tokens, reserved_tokens):
    """
    滑动窗口截断：保留最近 N 轮对话，确保总 token 数不超过限制。
    
    Args:
        history_messages: 历史消息列表 [{"role": ..., "content": ...}, ...]
        max_tokens: 总 token 上限
        reserved_tokens: 已占用的 token 数（系统提示 + RAG 上下文 + 当前问题）
    
    Returns:
        截断后的消息列表（只保留最近若干完整轮次）
    """
    available = max_tokens - reserved_tokens
    if available <= 0:
        return []  # 连基础内容都放不下，放弃历史

    # 将历史消息按轮次分组（user + assistant 为一轮）
    rounds = []
    i = 0
    while i < len(history_messages):
        pair = []
        pair.append(history_messages[i])
        if i + 1 < len(history_messages):
            pair.append(history_messages[i + 1])
        rounds.append(pair)
        i += 2

    # 从最近一轮开始向前累加，直到超出 token 预算
    kept_rounds = []
    used = 0
    for rnd in reversed(rounds):
        rnd_tokens = sum(estimate_tokens(msg["content"]) for msg in rnd)
        if used + rnd_tokens > available:
            break
        kept_rounds.append(rnd)
        used += rnd_tokens

    # 恢复为正序的扁平消息列表
    kept_rounds.reverse()
    result = []
    for rnd in kept_rounds:
        result.extend(rnd)
    return result


def generate_rag_answer(prompt_text, history_messages=None, max_context_tokens=None):
    """
    RAG 增强问答：支持多轮对话上下文管理。
    
    先从本地知识库检索相关内容，再结合历史对话上下文，让 LLM 基于检索结果
    和上下文连贯地回答。通过滑动窗口截断确保不超出 token 限制。
    
    Args:
        prompt_text: 当前用户问题
        history_messages: 历史对话消息列表 [{"role": "user", "content": "..."}, ...]
        max_context_tokens: 上下文最大 token 数，默认使用 MAX_CONTEXT_TOKENS
    
    Returns:
        AI 回答文本（含参考来源）
    """
    if max_context_tokens is None:
        max_context_tokens = MAX_CONTEXT_TOKENS

    print(f"[RAG问答] 用户问题: {prompt_text}")
    if history_messages:
        print(f"[RAG问答] 历史对话 {len(history_messages)} 条消息，将结合上下文回答")

    if "your_api_key_here" in API_KEY or "这里填" in API_KEY:
        return "请配置有效的智谱AI API密钥。在环境变量中设置 ZHIPUAI_API_KEY。"

    # 1. 确保向量索引已构建
    rag = get_rag_engine()
    try:
        index_count = rag.build_index()
        if index_count == 0:
            return "知识库为空，请先导入红色故事数据。"
    except Exception as e:
        print(f"[RAG] 索引构建失败: {e}")
        return f"知识库索引初始化失败: {e}"

    # 2. 查询扩展：从历史回复中提取标题拼入查询，检索相关内容
    history = history_messages or []
    search_query = _expand_query_with_history(prompt_text, history)
    try:
        retrieved_docs = rag.retrieve(search_query)
    except Exception as e:
        print(f"[RAG] 检索失败: {e}")
        return f"知识库检索失败: {e}"

    if not retrieved_docs:
        return "抱歉，在本知识库中没有找到与您问题相关的内容。请尝试其他问题。"

    # 3. 构建上下文
    context = rag.build_context(retrieved_docs)

    # 4. 构建 RAG Prompt
    system_prompt = (
        "你是一名博学的江西红色文化研究员。请严格基于以下【参考资料】回答用户问题。\n"
        "要求：\n"
        "1. 优先使用参考资料中的信息，用自己的语言组织回答。\n"
        "2. 回答末尾请注明信息来源（引用故事标题）。\n"
        "3. 如果参考资料不足以回答，请诚实说明。\n"
        "4. 回答要简洁、准确，不要长篇大论。\n"
        "5. 如果当前问题与对话历史相关（如使用了「它」、「这个」等指代词），请结合历史上下文理解用户意图。"
    )

    user_message = (
        f"【参考资料】\n{context}\n\n"
        f"【用户问题】{prompt_text}\n\n"
        "请基于以上参考资料回答。"
    )

    # 5. 构建完整 messages 列表（含历史对话 + 滑动窗口截断）
    # 先计算基础 token 占用
    base_tokens = (
        estimate_tokens(system_prompt)
        + estimate_tokens(user_message)
        + 200  # 预留一些 buffer
    )

    # 对历史消息应用滑动窗口
    truncated_history = _apply_sliding_window(history, max_context_tokens, base_tokens)

    if len(truncated_history) < len(history):
        print(f"[RAG问答] 滑动窗口截断: {len(history)} -> {len(truncated_history)} 条历史消息")

    # 组装最终 messages
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(truncated_history)
    messages.append({"role": "user", "content": user_message})

    total_estimated = base_tokens + sum(
        estimate_tokens(msg["content"]) for msg in truncated_history
    )
    print(f"[RAG问答] 预估 token: {total_estimated} / {max_context_tokens}")

    try:
        client = ZhipuAI(api_key=API_KEY)
        response = client.chat.completions.create(
            model="glm-4.7",
            messages=messages,
        )
        answer = response.choices[0].message.content

        # 6. 附加检索来源信息
        sources = "\n\n---\n📚 **参考来源：**\n"
        seen_titles = set()
        for doc in retrieved_docs:
            if doc["title"] not in seen_titles:
                seen_titles.add(doc["title"])
                sources += f"- 《{doc['title']}》（相关度: {doc['score']:.2f}）\n"

        return answer + sources

    except Exception as e:
        return f"AI生成出错: {e}"
