# rag_engine.py
# RAG 检索增强生成引擎
# 使用本地 Embedding 模型将红色故事知识库向量化，检索相关内容增强 LLM 回答

import os
import re

# 使用 HuggingFace 国内镜像站，解决模型下载被墙问题
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import chromadb
from sentence_transformers import SentenceTransformer
from db_manager import get_stories


# ================= 配置 =================
# 向量数据库持久化目录
CHROMA_DB_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")
# 集合名称
COLLECTION_NAME = "red_culture_stories"
# 检索返回的 Top-K 数量（增大以提升召回率，LLM 会自行筛选）
TOP_K = 5
# Embedding 模型名称（首次运行从 hf-mirror.com 下载，约 100MB）
# BAAI/bge-small-zh-v1.5：中文优化，512 维，检索精度高
EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"

# 最低相关度阈值（低于此分数的结果将被过滤）
MIN_SCORE_THRESHOLD = 0.05


class RAGEngine:
    """RAG 引擎：负责文本向量化、存储、检索"""

    def __init__(self):
        self._embedding_model = None
        self._chroma_client = None
        self._collection = None

    @property
    def embedding_model(self):
        if self._embedding_model is None:
            print(f"[RAG] 正在加载 Embedding 模型: {EMBEDDING_MODEL} ...")
            self._embedding_model = SentenceTransformer(EMBEDDING_MODEL)
            print("[RAG] Embedding 模型加载完成。")
        return self._embedding_model

    @property
    def chroma_client(self):
        if self._chroma_client is None:
            os.makedirs(CHROMA_DB_DIR, exist_ok=True)
            self._chroma_client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
        return self._chroma_client

    @property
    def collection(self):
        if self._collection is None:
            self._collection = self.chroma_client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    # ---------- 文本分块 ----------
    @staticmethod
    def _split_text(text, max_chars=500):
        """按段落拆分文本，每段不超过 max_chars 字符"""
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        chunks = []
        current_chunk = ""
        for para in paragraphs:
            if len(current_chunk) + len(para) <= max_chars:
                current_chunk += ("\n" if current_chunk else "") + para
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                if len(para) > max_chars:
                    sentences = para.replace("。", "。\n").split("\n")
                    sub_chunk = ""
                    for sent in sentences:
                        if len(sub_chunk) + len(sent) <= max_chars:
                            sub_chunk += sent
                        else:
                            if sub_chunk:
                                chunks.append(sub_chunk)
                            sub_chunk = sent
                    if sub_chunk:
                        if chunks and len(chunks[-1]) + len(sub_chunk) <= max_chars:
                            chunks[-1] += sub_chunk
                        else:
                            chunks.append(sub_chunk)
                else:
                    chunks.append(para)
                current_chunk = ""
        if current_chunk:
            chunks.append(current_chunk)
        return chunks

    # ---------- 构建/重建向量索引 ----------
    def build_index(self, force_rebuild=False):
        """
        从 SQLite 数据库中读取所有故事，向量化后存入 ChromaDB。
        自动检测模型变化，模型不同时自动重建索引。
        force_rebuild=True 时强制重建（清空旧数据）。
        """
        existing_count = self.collection.count()
        need_rebuild = force_rebuild

        if existing_count > 0 and not force_rebuild:
            # 检查距离度量是否匹配（L2 -> cosine 需要重建）
            coll_meta = self.collection.metadata or {}
            stored_model = coll_meta.get("embedding_model", "")
            stored_space = coll_meta.get("hnsw:space", "")
            if stored_space and stored_space != "cosine":
                print(f"[RAG] 检测到距离度量变化 ({stored_space} -> cosine)，自动重建索引...")
                need_rebuild = True
            elif stored_model != EMBEDDING_MODEL:
                print(f"[RAG] 检测到模型变化 ({stored_model or '无记录'} -> {EMBEDDING_MODEL})，自动重建索引...")
                need_rebuild = True
            else:
                print(f"[RAG] 向量索引已存在 ({existing_count} 条)，模型匹配，跳过构建。")
                return existing_count

        if need_rebuild and existing_count > 0:
            print(f"[RAG] 正在清空旧索引 ({existing_count} 条)...")
            self.chroma_client.delete_collection(COLLECTION_NAME)
            self._collection = None

        stories = get_stories()
        if not stories:
            print("[RAG] 数据库中没有故事，跳过索引构建。")
            return 0

        print(f"[RAG] 正在从数据库读取 {len(stories)} 篇故事...")

        documents = []
        metadatas = []
        ids = []

        for story in stories:
            chunks = self._split_text(story["content"])
            for i, chunk in enumerate(chunks):
                chunk_id = f"{story['id']}_{i}"
                documents.append(chunk)
                metadatas.append({
                    "story_id": story["id"],
                    "title": story["title"],
                    "category": story.get("category", ""),
                    "chunk_index": i,
                })
                ids.append(chunk_id)

        print(f"[RAG] 共切分为 {len(documents)} 个文本块，正在向量化...")

        embeddings = self.embedding_model.encode(
            documents,
            show_progress_bar=True,
            normalize_embeddings=True,
        ).tolist()

        # 记录当前模型名称，用于后续自动检测模型变化
        self.collection.modify(metadata={"embedding_model": EMBEDDING_MODEL})

        BATCH_SIZE = 100
        for start in range(0, len(documents), BATCH_SIZE):
            end = min(start + BATCH_SIZE, len(documents))
            self.collection.add(
                embeddings=embeddings[start:end],
                documents=documents[start:end],
                metadatas=metadatas[start:end],
                ids=ids[start:end],
            )
            print(f"[RAG] 已存入 {end}/{len(documents)} 条")

        print(f"[RAG] 向量索引构建完成，共 {len(documents)} 条。")
        return len(documents)

    # ---------- 检索 ----------
    def retrieve(self, query, top_k=TOP_K):
        """
        根据用户查询检索最相关的文本块。
        1. 向量检索获取候选
        2. 关键词加权：标题与查询词匹配的文档加分
        3. 过滤低于阈值的结果
        返回: [{"content": ..., "title": ..., "category": ..., "score": ...}, ...]
        """
        # BGE 模型检索时添加指令前缀，提升语义匹配精度
        query_with_instruction = f"为这个句子生成表示以用于检索相关文章：{query}"
        query_embedding = self.embedding_model.encode(
            [query_with_instruction],
            normalize_embeddings=True,
        ).tolist()

        # 多检索一些候选，后续用关键词加权和阈值过滤
        fetch_k = max(top_k * 3, 10)
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=fetch_k,
            include=["documents", "metadatas", "distances"],
        )

        retrieved = []
        if results["documents"] and results["documents"][0]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                # cosine distance: score = 1 - distance
                score = round(1 - dist, 4)
                retrieved.append({
                    "content": doc,
                    "title": meta.get("title", ""),
                    "category": meta.get("category", ""),
                    "score": score,
                })

        # 关键词加权：用滑动窗口提取2-4字词组，匹配标题的文档加分
        # 例如查询"井冈山会师"可提取"井冈""井冈山""井冈山会""冈山会师"等子串
        chinese_chars = re.sub(r'[^\u4e00-\u9fff]', '', query)
        query_terms = set()
        for n in (2, 3, 4):
            for i in range(len(chinese_chars) - n + 1):
                term = chinese_chars[i:i + n]
                query_terms.add(term)
        # 过滤常见无意义词
        stop_words = {'这个', '那个', '什么', '怎么', '为什么', '请问', '一下', '介绍', '详细', '请', '的', '了', '是'}
        query_terms -= stop_words
        
        if query_terms:
            for item in retrieved:
                title = item["title"]
                keyword_match = any(term in title for term in query_terms)
                if keyword_match:
                    item["score"] = round(min(item["score"] + 0.3, 1.0), 4)

        # 按分数重新排序
        retrieved.sort(key=lambda x: x["score"], reverse=True)

        # 过滤低于阈值的结果
        filtered = [r for r in retrieved if r["score"] >= MIN_SCORE_THRESHOLD]

        return filtered[:top_k]

    # ---------- 构建检索上下文 ----------
    def build_context(self, retrieved_docs):
        """将检索到的文档拼接为 prompt 上下文"""
        if not retrieved_docs:
            return ""

        parts = []
        for i, doc in enumerate(retrieved_docs, 1):
            parts.append(
                f"【参考资料 {i}】《{doc['title']}》(分类:{doc['category']})\n"
                f"{doc['content']}"
            )
        return "\n\n".join(parts)


# ================= 全局单例 =================
_rag_engine = None


def get_rag_engine():
    """获取 RAG 引擎全局单例"""
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine()
    return _rag_engine