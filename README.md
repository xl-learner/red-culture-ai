# 赣红智声 — 江西红色文化智能讲述平台

基于大语言模型（GLM-4）和 RAG 检索增强生成的江西红色文化智能讲述系统。支持 AI 写作、语音合成、多轮对话问答，让静止的红色历史资料"活"起来。

## 功能特性

- **AI 智能创作**：输入主题关键词，AI 自动生成生动的演讲稿，支持多播音员语音合成
- **RAG 增强问答**：基于本地向量知识库的检索增强生成，回答准确、有据可依，支持多轮对话上下文
- **红色故事库**：收录 56 篇江西红色故事，支持分类筛选和关键词搜索
- **语音合成**：集成 Edge TTS，支持多种播音员声音，一键生成 MP3 音频
- **数据看板**：首页展示故事收录统计、AI 响应次数等实时数据

## 技术架构

| 层级 | 技术 |
|------|------|
| 前端交互 | Streamlit (Python) |
| 大语言模型 | 智谱 AI GLM-4 |
| 向量数据库 | ChromaDB (cosine 距离) |
| Embedding 模型 | BAAI/bge-small-zh-v1.5 (本地部署, 512维) |
| 语音合成 | Microsoft Edge TTS |
| 数据存储 | SQLite |

## 项目结构

```
red-culture-ai/
├── app.py              # Streamlit 主应用（页面路由、UI 交互）
├── ai_engine.py         # AI 引擎（文本生成、语音合成、RAG 问答、多轮对话管理）
├── rag_engine.py        # RAG 检索引擎（文本向量化、ChromaDB 存储与检索、关键词加权）
├── db_manager.py        # 数据库管理（故事 CRUD、统计查询）
├── red_culture.db       # SQLite 数据库（56 篇红色故事）
├── requirements.txt     # Python 依赖
├── .env.example         # 环境变量模板
├── chroma_db/           # 向量数据库持久化目录（自动生成）
├── audio/               # 生成的语音文件
├── img/                 # 图片资源
└── .streamlit/          # Streamlit 配置文件
```

## 快速部署

### 1. 环境要求

- Python 3.10+
- Windows / macOS / Linux

### 2. 克隆项目

```bash
git clone https://github.com/your-username/red-culture-ai.git
cd red-culture-ai
```

### 3. 创建虚拟环境

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 4. 安装依赖

```bash
pip install -r requirements.txt
```

### 5. 配置 API Key

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填入你的智谱 AI API Key
# 获取地址: https://open.bigmodel.cn/usercenter/apikeys
```

### 6. 启动应用

```bash
python -m streamlit run app.py
```

首次启动会自动：
- 下载 Embedding 模型（约 100MB，通过 HF 镜像站）
- 读取数据库中的故事并构建向量索引（约 1-2 分钟）

启动后浏览器访问 `http://localhost:8501` 即可使用。

## 注意事项

- **API Key**：需要注册智谱 AI 账号并获取 API Key，首次注册有免费额度
- **Embedding 模型**：首次运行会自动从 HuggingFace 镜像站下载，约 100MB
- **向量索引**：`chroma_db/` 目录由程序自动生成和维护，删除后重启会自动重建
- **语音文件**：生成的 MP3 文件保存在 `audio/` 目录下，不上传 Git