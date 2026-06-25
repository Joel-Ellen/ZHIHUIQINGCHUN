# 🎓 智绘青春 (ZHIHUIQINGCHUN) — 智能职业规划系统

> **AI 驱动的个性化职业规划平台** — 融合大语言模型、知识图谱、向量检索与图神经网络，为大学生提供从简历分析到职业路径规划的全链路智能服务。

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.x-green.svg)](https://flask.palletsprojects.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg)](https://react.dev/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.x-EE4C2C.svg)](https://pytorch.org/)
[![FAISS](https://img.shields.io/badge/FAISS-latest-orange.svg)](https://github.com/facebookresearch/faiss)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📖 目录

- [项目背景](#-项目背景)
- [核心功能](#-核心功能)
- [技术架构](#-技术架构)
- [项目结构](#-项目结构)
- [快速开始](#-快速开始)
- [配置说明](#-配置说明)
- [API 接口文档](#-api-接口文档)
- [技术详解](#-技术详解)
- [部署指南](#-部署指南)
- [重构演进](#-重构演进)
- [常见问题](#-常见问题)
- [致谢](#-致谢)

---

## 🎯 项目背景

**智绘青春** 是一个面向大学生的智能职业规划平台。针对当前大学生普遍存在的**职业方向迷茫、自我认知不足、岗位信息碎片化**三大痛点，系统通过 AI 技术实现：

- 📄 **简历智能解析** — 上传简历即可自动提取技能、教育背景、项目经历
- 🧠 **十维能力画像** — 从十个维度量化评估个人职业竞争力
- 🔍 **精准岗位匹配** — 基于向量检索与知识图谱的混合推荐
- 🗺️ **职业路径规划** — 晋升路径、转岗方向、技能差距分析
- 📊 **可视化报告** — 自动生成图文并茂的职业规划分析报告

系统整合了 **大语言模型（通义千问）**、**LSH + FAISS 混合向量检索**、**NetworkX 知识图谱**、**TransE + R-GCN 图神经网络** 四大 AI 技术栈，构建了完整的 KG4Career（面向职业规划的知识图谱）技术体系。

---

## ✨ 核心功能

### 1. 用户系统
- 注册 / 登录 / 个人信息管理
- 简历文件上传与管理（支持 PDF、DOCX、TXT）
- 历史分析记录查看与回溯

### 2. 简历智能分析
- 基于通义千问大模型的简历深度解析
- 自动提取：技能标签、教育背景、项目经验、实习经历
- 十维能力画像量化评估：
  | 维度 | 说明 | 维度 | 说明 |
  |------|------|------|------|
  | 技术能力 | 编程/工具掌握程度 | 学习能力 | 新知识吸收速度 |
  | 沟通能力 | 表达与协作水平 | 领导力 | 团队管理潜力 |
  | 创新能力 | 创造性思维 | 执行力 | 任务完成效率 |
  | 专业匹配度 | 专业与岗位契合度 | 薪资竞争力 | 市场薪资定位 |
  | 行业认知 | 行业理解深度 | 综合素质 | 整体竞争力 |

### 3. 岗位智能探索
- **关键词检索**：基于 LSH（局部敏感哈希）的快速粗筛
- **向量语义检索**：基于 FAISS 的深度语义匹配
- **十维画像匹配**：结合画像特征的混合相似度计算
- **知识图谱导航**：可视化岗位关联网络

### 4. 职业规划报告
- **Agentic RAG 增强生成**：ReAct 风格智能体循环检索与推理
- **GraphRAG 知识增强**：从知识图谱中提取晋升路径、转岗方向
- **技能差距分析**：对比当前能力与目标岗位要求的差距
- **学习路径推荐**：基于技能差距的个性化提升建议
- **冷启动预测**：低年级学生通过 GNN 推断潜在能力

### 5. 可视化大屏
- ECharts 驱动的交互式数据可视化
- 雷达图：十维能力画像展示
- 力导向图：知识图谱关系网络
- 柱状图/折线图：薪资分布与趋势

---

## 🏗️ 技术架构

### 整体架构图

```text
┌──────────────────────────────────────────────────────────────────────┐
│                         用户交互层 (Presentation)                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │     index.html (React 18 SPA)                                  │  │
│  │     ├── 用户登录/注册    ├── 简历上传/管理                      │  │
│  │     ├── 岗位探索/搜索    ├── 智能分析报告                       │  │
│  │     └── ECharts 可视化   └── PDF.js 简历预览                    │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                    │                                  │
│                                    ▼                                  │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                     API 网关层 (api.js)                          │  │
│  │     四组件架构: 感知(Perceive) → 推理(Reason) →                  │  │
│  │                 决策(Decide) → 行动(Act)                         │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                    │                                  │
│                                    ▼                                  │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                  应用服务层 (Flask REST API)                     │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │  │
│  │  │ 用户服务  │  │ 文件服务  │  │ 分析服务  │  │  报告服务     │   │  │
│  │  │ /api/auth │  │ /api/file│  │/api/analyze│  │ /api/report  │   │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────────┘   │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                    │                                  │
│        ┌───────────────┬───────────┼───────────┬──────────────┐       │
│        ▼               ▼           ▼           ▼              ▼       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────┐  │
│  │ 嵌入服务  │  │ 检索服务  │  │ 图谱服务  │  │ RAG服务  │  │ GNN  │  │
│  │Sentence- │  │LSH+FAISS │  │NetworkX  │  │Agentic   │  │TransE│  │
│  │Transform │  │ 混合检索  │  │ 知识图谱  │  │ RAG+     │  │+R-GCN│  │
│  │          │  │          │  │          │  │ GraphRAG │  │      │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────┘  │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                    数据存储层                                    │  │
│  │  ┌────────┐  ┌────────┐  ┌──────────┐  ┌──────────────────┐   │  │
│  │  │ SQLite │  │ FAISS  │  │ NetworkX │  │ PyTorch 模型      │   │  │
│  │  │ 用户/  │  │ 向量   │  │ 知识图谱 │  │ TransE + R-GCN   │   │  │
│  │  │ 记录   │  │ 索引   │  │ 图结构   │  │ 图神经网络       │   │  │
│  │  └────────┘  └────────┘  └──────────┘  └──────────────────┘   │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                    │                                  │
│                                    ▼                                  │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                    外部 AI 服务                                  │  │
│  │           通义千问 (Qwen-Plus) — DashScope API                   │  │
│  │           简历分析 · 报告生成 · 智能问答                          │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### 技术栈一览

| 层级 | 技术 | 版本 | 用途 |
|------|------|------|------|
| **前端** | React (CDN) | 18.x | SPA 单页面应用 |
| | ECharts (CDN) | 5.x | 数据可视化图表 |
| | PDF.js (CDN) | 3.x | 简历 PDF 预览解析 |
| **后端** | Python | 3.9+ | 主语言 |
| | Flask | 2.x | Web 框架 |
| | Flask-CORS | 3.x | 跨域支持 |
| | Flask-SQLAlchemy | 3.x | ORM 框架 |
| | Werkzeug | 2.x | WSGI 工具 |
| **AI/ML** | PyTorch | 2.x | 深度学习框架 |
| | PyTorch Geometric | 2.3+ | 图神经网络库 |
| | sentence-transformers | 2.2+ | 文本嵌入模型 |
| | FAISS | 1.7+ | 向量相似度搜索 |
| | scikit-learn | 1.3+ | 机器学习工具 |
| | datasketch | 1.5+ | LSH MinHash |
| **知识图谱** | NetworkX | — | 图结构管理 |
| | Neo4j (可选) | 5.x | 图数据库 |
| **LLM** | 通义千问 (Qwen-Plus) | — | 大模型 API |
| **数据库** | SQLite | — | 用户与记录存储 |
| **部署** | PyInstaller | 6.x | Windows 打包 |
| | Gunicorn | — | Linux 生产部署 |
| | Nginx | — | 反向代理 |

---

## 📁 项目结构

```text
zhihuiqingchun/
│
├── 📄 backend.py                      # Flask 后端主入口 (2560行)
│   ├── 用户认证 API (/api/auth/*)
│   ├── 文件管理 API (/api/file/*)
│   ├── 简历分析 API (/api/analyze/*)
│   ├── 岗位推荐 API (/api/recommend/*)
│   ├── 报告生成 API (/api/report/*)
│   └── 历史记录 API (/api/history/*)
│
├── 🌐 index.html                      # 前端 SPA 主页面 (11006行, React 18)
├── 📡 api.js                          # 前端 API 调用模块 (207行)
│
├── 📊 jobs_data.json                  # 岗位原始数据集 (~8.3MB)
├── 📊 job_profiles.json               # 岗位画像数据
├── 📊 job_profiles_data.json          # 完整岗位画像数据集 (~3.3MB)
├── 📊 jobs_data.js                    # 前端岗位数据脚本
├── 📊 job_profiles.js                 # 前端岗位画像脚本
├── 📊 job_profiles_data.js            # 前端岗位画像（轻量版）
│
├── 🔧 init_db.py                      # 数据库初始化脚本
├── 🔧 convert_profiles.py             # 数据格式转换工具
├── 📋 requirements.txt                # Python 依赖清单
├── 📋 readme.txt                      # 快速入门说明
│
├── 📂 backend/                        # Python 后端模块包
│   ├── __init__.py
│   ├── config.py                      # 全局配置（88行）
│   │   ├── 向量维度配置
│   │   ├── LSH/FAISS 参数
│   │   ├── 嵌入模型配置
│   │   ├── Neo4j 连接配置
│   │   ├── TransE/R-GCN 超参数
│   │   └── LLM API 配置
│   │
│   ├── 📂 models/                     # 数据模型/Schema 定义
│   │   ├── __init__.py
│   │   └── kg_schema.py               # 知识图谱 Schema
│   │       ├── 10 种节点类型 (Job/Skill/Industry/Location...)
│   │       ├── 10 种关系类型 (REQUIRES/SIMILAR/PROMOTES...)
│   │       └── Cypher 查询模板
│   │
│   ├── 📂 services/                   # 核心业务服务层
│   │   ├── __init__.py
│   │   ├── embedding_service.py       # 文本嵌入服务 (117行)
│   │   │   └── sentence-transformers → 384维向量
│   │   ├── retrieval_service.py       # LSH+FAISS 混合检索 (171行)
│   │   │   └── LSH粗筛 → FAISS精排 → 混合相似度
│   │   ├── kg_service.py              # 知识图谱服务 (568行)
│   │   │   └── NetworkX/Neo4j 图查询与路径分析
│   │   ├── rag_service.py             # Agentic RAG 服务 (273行)
│   │   │   └── ReAct 循环 + GraphRAG 增强生成
│   │   └── gnn_service.py             # GNN 图神经网络 (235行)
│   │       └── TransE + R-GCN + 冷启动预测
│   │
│   ├── 📂 scripts/                    # 构建/初始化脚本
│   │   ├── __init__.py
│   │   ├── init_all.py                # 一键初始化所有组件
│   │   ├── build_indices.py           # 构建 LSH + FAISS 索引
│   │   ├── build_kg.py                # 构建知识图谱
│   │   └── build_gnn.py               # 训练 TransE + R-GCN 模型
│   │
│   ├── 📂 utils/                      # 工具模块
│   │   ├── __init__.py
│   │   ├── data_loader.py             # 统一数据加载器
│   │   ├── faiss_indexer.py           # FAISS 索引管理器
│   │   └── lsh_indexer.py             # LSH MinHash 索引管理器
│   │
│   └── 📂 data/                       # 预计算数据文件
│       ├── 📂 vectors/
│       │   └── job_vectors.pkl         # 预计算岗位向量 (18MB)
│       ├── 📂 indices/
│       │   ├── faiss.index             # FAISS HNSWFlat 索引 (21MB)
│       │   └── lsh_index.pkl           # LSH MinHash 索引 (6.7MB)
│       ├── 📂 models/
│       │   ├── transe_model.pt         # TransE 嵌入模型 (12MB)
│       │   ├── rgcn_model.pt           # R-GCN 图神经网络 (280KB)
│       │   └── gnn_metadata.pkl        # GNN 训练元数据 (740KB)
│       └── kg_graph.pkl               # 知识图谱序列化 (25MB)
│
├── 📂 frontend-scripts/               # 苍穹低代码平台前端脚本
│   ├── zc-history-record-web.js       # Web 桌面端页面脚本
│   └── zc-history-record-mobile.js    # 移动端 H5 页面脚本
│
├── 📂 java-src/                       # 苍穹平台 Java 高代码微服务
│   └── src/main/java/tk/zc/zhqc/
│       ├── openapi/
│       │   └── CustomAgentCallbackPlugin.java   # 自定义 API 网关
│       ├── plugin/
│       │   └── ZcHistoryRecordWebPlugin.java    # Web 页面控制器
│       └── service/
│           └── CareerGraphService.java          # 知识图谱拓扑服务
│
└── 📂 docs/                           # 项目文档
    ├── AGENT_TASK_FLOW.md             # Agent 任务流全景图
    ├── Linux服务器部署手册.md          # Linux 生产环境部署指南
    ├── 简历识别_表单配置参考卡.md       # 苍穹平台表单配置参考
    └── 苍穹低代码重构设计方案.md        # 平台重构演进方案
```

---

## 🚀 快速开始

### 环境要求

| 组件 | 最低版本 | 推荐版本 |
|------|----------|----------|
| Python | 3.9 | 3.10+ |
| pip | 21.0+ | 24.0+ |
| 内存 | 8 GB | 16 GB+ |
| 磁盘 | 5 GB | 10 GB+ (含模型) |
| 操作系统 | Windows 10 / Linux | Windows 11 / Ubuntu 22.04 |

> **注意**：首次运行需要下载 sentence-transformers 嵌入模型（约 120MB），请保持网络畅通。

### 一、克隆项目

```bash
git clone https://github.com/Joel-Ellen/ZHIHUIQINGCHUN.git
cd zhihuiqingchun
```

### 二、安装依赖

```bash
# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 三、初始化系统

```bash
# 1. 初始化数据库（创建用户表、文件表、历史记录表）
python init_db.py

# 2. 构建索引和知识图谱（首次运行必须执行）
python -m backend.scripts.init_all
```

> `init_all` 将依次执行：
> 1. **构建 LSH 关键词索引** → 生成 `backend/data/indices/lsh_index.pkl`
> 2. **构建 FAISS 向量索引** → 生成 `backend/data/indices/faiss.index`
> 3. **构建知识图谱** → 生成 `backend/data/kg_graph.pkl`
> 4. **训练 TransE 模型** → 生成 `backend/data/models/transe_model.pt`
> 5. **训练 R-GCN 模型** → 生成 `backend/data/models/rgcn_model.pt`
>
> ⏱️ 首次构建预计耗时 **10-30 分钟**（取决于硬件配置）。

### 四、启动服务

```bash
# 开发模式启动
python backend.py
```

启动后：
- 🌐 后端 API：`http://localhost:5000`
- 🌐 前端页面：直接在浏览器打开 `index.html`，或访问 `http://localhost:5000`

### 五、配置 LLM API Key（重要）

系统依赖通义千问大模型进行简历分析和报告生成。使用前需要配置 API Key：

```bash
# Windows (PowerShell)
$env:DASHSCOPE_API_KEY="your-api-key-here"

# Windows (CMD)
set DASHSCOPE_API_KEY=your-api-key-here

# Linux/Mac
export DASHSCOPE_API_KEY="your-api-key-here"
```

> 🔑 获取 API Key：访问 [阿里云 DashScope 控制台](https://dashscope.console.aliyun.com/) 开通服务并创建 API Key。

---

## ⚙️ 配置说明

所有可配置参数集中在 [`backend/config.py`](backend/config.py) 中，按功能分为以下模块：

### 向量与索引配置

```python
# 文本嵌入维度（取决于所选模型）
TEXT_EMBEDDING_DIM = 384    # MiniLM-L12-v2: 384维 | BGE-M3: 768维
PROFILE_DIM = 10             # 十维画像固定维度
HYBRID_DIM = 394             # 混合向量 = 384 + 10

# FAISS 索引类型
FAISS_INDEX_TYPE = "HNSWFlat"  # 可选: Flat | HNSWFlat | IVFFlat | IVFPQ
FAISS_METRIC = "IP"            # IP(内积) | L2(欧氏距离)

# LSH 参数
LSH_NUM_PERM = 128           # MinHash 置换函数数量（越大越精确）
LSH_THRESHOLD = 0.15         # Jaccard 相似度阈值
```

### 嵌入模型配置

```python
# 可选模型（修改后需重新构建索引）
# "paraphrase-multilingual-MiniLM-L12-v2"  → 384维，120MB，轻量快速
# "BAAI/bge-m3"                            → 768维，2GB，中文效果最佳
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DEVICE = "cpu"     # 或 "cuda"（需要 GPU + CUDA）
```

### GNN 模型配置

```python
# TransE（知识图谱嵌入）
TRANSE_EMBEDDING_DIM = 128   # 嵌入维度
TRANSE_EPOCHS = 500          # 训练轮数
TRANSE_LR = 0.001            # 学习率

# R-GCN（关系图卷积网络）
RGCN_HIDDEN_DIM = 64         # 隐藏层维度
RGCN_OUT_DIM = 32            # 输出维度
RGCN_DROPOUT = 0.3           # Dropout 比例
```

### LLM 配置

```python
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
LLM_MODEL = "qwen-plus"      # 可选: qwen-turbo | qwen-plus | qwen-max
LLM_TEMPERATURE = 0.7
LLM_MAX_TOKENS = 2000
```

---

## 📡 API 接口文档

### 基础信息

- **Base URL**: `http://localhost:5000/api`
- **Content-Type**: `application/json`
- **文件上传**: `multipart/form-data`

### 通用响应格式

```json
{
  "success": true,
  "data": { ... },
  "message": "操作成功"
}
```

### 1. 用户认证 `/api/auth`

#### POST `/api/auth/register` — 用户注册

```json
// Request
{
  "username": "zhangsan",
  "email": "zhangsan@example.com",
  "password": "securePassword123"
}

// Response
{
  "success": true,
  "data": {
    "userId": "550e8400-e29b-41d4-a716-446655440000",
    "username": "zhangsan"
  }
}
```

#### POST `/api/auth/login` — 用户登录

```json
// Request
{
  "email": "zhangsan@example.com",
  "password": "securePassword123"
}

// Response
{
  "success": true,
  "data": {
    "userId": "550e8400-e29b-41d4-a716-446655440000",
    "token": "session-token-xxx"
  }
}
```

### 2. 文件管理 `/api/file`

#### POST `/api/file/upload` — 上传简历文件

```
Content-Type: multipart/form-data
Body:
  - file: <PDF/DOCX/TXT 文件>
  - userId: "550e8400-e29b-41d4-a716-446655440000"
```

#### GET `/api/file/list/<userId>` — 获取用户文件列表

### 3. 简历分析 `/api/analyze`

#### POST `/api/analyze/resume` — 智能分析简历

```json
// Request
{
  "userId": "550e8400-...",
  "fileId": "file-uuid-xxx"
}

// Response
{
  "success": true,
  "data": {
    "skills": ["Python", "Java", "React", "机器学习"],
    "education": {
      "school": "XX大学",
      "major": "计算机科学与技术",
      "degree": "本科"
    },
    "abilityProfile": {
      "overallScore": 78,
      "tenDimensions": {
        "techAbility": 82,
        "learningAbility": 75,
        "communication": 68,
        "leadership": 60,
        "innovation": 72,
        "execution": 80,
        "majorMatch": 85,
        "salaryCompetitiveness": 70,
        "industryCognition": 65,
        "comprehensiveQuality": 76
      }
    },
    "jobMatches": [
      {
        "name": "Java开发工程师",
        "company": "XX科技",
        "matchScore": 0.89,
        "salary": "15-25K"
      }
    ]
  }
}
```

#### POST `/api/analyze/text` — 分析文本描述

直接提交文本描述（不通过简历文件），适用于快速测评场景。

### 4. 岗位推荐 `/api/recommend`

#### POST `/api/recommend/jobs` — 智能岗位推荐

```json
// Request
{
  "userId": "550e8400-...",
  "skills": ["Python", "SQL", "数据分析"],
  "preferredIndustry": "互联网",
  "preferredLocation": "北京",
  "topK": 10
}
```

### 5. 职业报告 `/api/report`

#### POST `/api/report/generate` — 生成职业规划报告

```json
// Request
{
  "userId": "550e8400-...",
  "analysisResult": { ... },
  "reportType": "career_plan"
}

// Response
{
  "success": true,
  "data": {
    "reportId": "report-uuid-xxx",
    "title": "张三的职业规划分析报告",
    "sections": [
      {
        "type": "overview",
        "title": "综合评估",
        "content": "..."
      },
      {
        "type": "skill_gap",
        "title": "技能差距分析",
        "content": "..."
      },
      {
        "type": "path",
        "title": "职业发展路径",
        "content": "..."
      }
    ],
    "recommendations": [...]
  }
}
```

### 6. 历史记录 `/api/history`

#### GET `/api/history/list/<userId>` — 获取历史记录

#### GET `/api/history/detail/<recordId>` — 获取记录详情

#### DELETE `/api/history/delete/<recordId>` — 删除记录

---

## 🔬 技术详解

### 1. KG4Career 技术体系

本项目构建了完整的 **KG4Career**（面向职业规划的知识图谱）技术体系，包含五大核心服务：

#### 1.1 文本嵌入服务 (`embedding_service.py`)

基于 `sentence-transformers` 库，将非结构化的岗位描述文本和简历内容映射为稠密向量。

```text
岗位描述: "负责Java后端开发，熟悉Spring Boot..."
      │
      ▼  sentence-transformers (MiniLM-L12-v2)
      │
向量: [0.12, -0.34, 0.56, ..., 0.78]  (384维)
```

- **默认模型**：`paraphrase-multilingual-MiniLM-L12-v2`（384维，支持中英双语）
- **可选升级**：`BAAI/bge-m3`（768维，中文语义理解更优）
- **批量处理**：支持批量编码，加速索引构建

#### 1.2 混合检索服务 (`retrieval_service.py`)

采用 **LSH 粗筛 → FAISS 精排** 两级检索策略，兼顾速度与精度：

```text
用户查询: "Python 数据分析 北京"
      │
      ▼  LSH MinHash 关键词粗筛
      │  (从 11,369 条岗位中筛选 ~100 条候选)
      │
      ▼  FAISS HNSWFlat 向量精排
      │  (在 100 条候选中计算 394 维混合余弦相似度)
      │
      ▼  Top-K 结果 (K=5)
[
  { name: "数据分析师", score: 0.92 },
  { name: "Python开发工程师", score: 0.87 },
  ...
]
```

**混合向量 = 文本嵌入(384维) + 画像特征(10维)**

#### 1.3 知识图谱服务 (`kg_service.py`)

基于 NetworkX 构建的职业规划知识图谱，支持：

- **节点类型**（10种）：岗位、技能、公司、行业、地点、学历、专业、证书、工具、职级
- **关系类型**（10种）：REQUIRES_SKILL、SIMILAR_TO、PROMOTES_TO、LOCATED_IN、BELONGS_TO 等
- **图分析算法**：
  - 最短路径查询（技能补全路径）
  - 多跳邻居探索（相关岗位发现）
  - 子图分析（行业生态理解）
  - 中心度计算（核心技能识别）

```text
[Python] ──REQUIRES──▶ [数据分析师] ◀──PROMOTES_TO── [高级数据分析师]
   │                        │                              │
   │                   SIMILAR_TO                    REQUIRES_SKILL
   │                        │                              │
   ▼                        ▼                              ▼
[后端开发] ◀──REQUIRES── [Java] ◀──REQUIRES── [Spark]
```

#### 1.4 Agentic RAG 服务 (`rag_service.py`)

ReAct（Reasoning + Acting）风格的智能体循环检索增强生成：

```text
┌─────────────────────────────────────────────┐
│            Agentic RAG 循环                   │
│                                              │
│  ┌─────────┐    ┌─────────┐    ┌──────────┐ │
│  │ Thought  │───▶│ Action  │───▶│Observation│ │
│  │ 分析需求  │    │ 执行检索  │    │ 整合结果  │ │
│  └─────────┘    └─────────┘    └──────────┘ │
│        ▲                              │      │
│        └──────────────────────────────┘      │
│              循环至上下文充足                   │
└─────────────────────────────────────────────┘
```

**检索策略自动规划**：
- `resume_analysis` → FAISS技能检索 + FAISS简历检索 + GraphRAG技能差距
- `career_report` → FAISS目标岗位 + GraphRAG晋升路径 + GraphRAG相似岗位
- `transition_advice` → FAISS技能检索 + GraphRAG转岗方向 + GraphRAG技能差距

#### 1.5 GNN 图神经网络服务 (`gnn_service.py`)

针对**低年级学生简历信息稀疏**的冷启动问题：

```text
学生: 只填了 "会 Python"
      │
      ▼  TransE 知识图谱嵌入
      │   知识图谱中 "Python" 与哪些岗位/技能关联？
      │
      ▼  R-GCN 关系图卷积
      │   通过这些关系传播推断 → 该学生可能还适合学 Java、SQL...
      │
      ▼  冷启动预测
      推荐: 后端开发 (0.78) | 数据分析 (0.72) | 测试开发 (0.65)
```

- **TransE**：将知识图谱三元组 (h, r, t) 嵌入低维向量空间
- **R-GCN**：聚合多关系邻居节点信息，进行节点分类与链接预测
- **冷启动策略**：通过已有技能在图谱中做多跳传播，推断潜在能力

### 2. 数据流全景

```text
用户上传简历 PDF
      │
      ▼
PDF.js 前端预览 + 文本提取
      │
      ▼
POST /api/analyze/resume
      │
      ├──▶ 通义千问大模型分析
      │      ├── 提取技能标签
      │      ├── 识别教育背景
      │      ├── 解析项目经历
      │      └── 生成十维画像
      │
      ├──▶ FAISS 向量检索
      │      └── 匹配最相似的 Top-K 岗位
      │
      ├──▶ GraphRAG 知识图谱查询
      │      ├── 晋升路径
      │      ├── 技能差距
      │      └── 转岗方向
      │
      └──▶ Agentic RAG 上下文整合
             │
             ▼
        通义千问生成最终报告
             │
             ▼
        返回前端 ECharts 可视化
```

---

## 🚢 部署指南

### Windows 桌面部署

使用 PyInstaller 打包为独立可执行文件：

```bash
# 1. 安装 PyInstaller
pip install pyinstaller

# 2. 打包
pyinstaller 智绘青春.spec

# 3. 输出在 dist/智绘青春/ 目录
#    双击 智绘青春.exe 即可运行
```

### Linux 服务器部署

详细部署指南请参考：[`docs/Linux服务器部署手册.md`](docs/Linux服务器部署手册.md)

#### 快速部署（Gunicorn + Nginx）

```bash
# 1. 安装系统依赖
sudo apt update && sudo apt install -y python3-pip python3-venv nginx

# 2. 创建虚拟环境
python3 -m venv venv && source venv/bin/activate

# 3. 安装项目依赖
pip install -r requirements.txt
pip install gunicorn

# 4. 初始化
python init_db.py
python -m backend.scripts.init_all

# 5. 配置 Systemd 服务
sudo cp zhihuiqingchun.service /etc/systemd/system/
sudo systemctl enable --now zhihuiqingchun

# 6. 配置 Nginx 反向代理
sudo cp zhihuiqingchun.nginx /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/zhihuiqingchun.nginx /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### Docker 部署（推荐）

```dockerfile
# 可自行创建 Dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN python init_db.py && python -m backend.scripts.init_all

EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "backend:app"]
```

---

## 🔄 重构演进

本项目经历了从 **传统 Python 全栈** 到 **苍穹低代码 + AI Agent + Java 高代码微服务** 的架构演进。

### 当前架构（第一阶段）

```text
React SPA (CDN) → Flask REST API → SQLite
                                  → FAISS 向量检索
                                  → NetworkX 知识图谱
                                  → 通义千问 LLM
                                  → TransE + R-GCN
```

### 目标架构（第二阶段）

```text
苍穹低代码 UI → 苍穹 Agent 智能体 → Java 微服务 (PostgreSQL)
              → 苍穹 OpenAPI 网关 → CareerGraphService (BFS拓扑)
              → KDDM 模型驱动      → SaveServiceHelper (持久化)
              → 苍穹附件中心       → QFilter + Stream groupingBy
```

详细重构方案请参考：[`docs/苍穹低代码重构设计方案.md`](docs/苍穹低代码重构设计方案.md)

Agent 任务流全景请参考：[`docs/AGENT_TASK_FLOW.md`](docs/AGENT_TASK_FLOW.md)

---

## ❓ 常见问题

<details>
<summary><b>Q1: 启动报错 "No module named 'xxx'"？</b></summary>

请确保已安装全部依赖：
```bash
pip install -r requirements.txt
```
如果使用了虚拟环境，请确认已激活。
</details>

<details>
<summary><b>Q2: FAISS 索引构建失败 / 内存不足？</b></summary>

FAISS HNSWFlat 索引需要约 2-3GB 可用内存。如果内存紧张，可以：
1. 在 `config.py` 中将 `FAISS_INDEX_TYPE` 改为 `"Flat"`（更低内存）
2. 关闭其他占用内存的程序后重试
3. 在 Linux 上增加 swap 空间
</details>

<details>
<summary><b>Q3: 大模型分析没有响应？</b></summary>

请检查：
1. `DASHSCOPE_API_KEY` 环境变量是否正确设置
2. API Key 是否已开通通义千问服务
3. 网络是否能访问 `dashscope.aliyuncs.com`
4. API 余额是否充足
</details>

<details>
<summary><b>Q4: 如何更新岗位数据？</b></summary>

1. 更新 `jobs_data.json` 文件（添加/修改/删除岗位条目）
2. 重新构建索引：
```bash
python -m backend.scripts.build_indices
python -m backend.scripts.build_kg
```
3. 如有需要，重新训练 GNN 模型：
```bash
python -m backend.scripts.build_gnn
```
</details>

<details>
<summary><b>Q5: 前端页面无法连接后端 API？</b></summary>

1. 确认 `backend.py` 正在运行（默认 5000 端口）
2. 检查 `api.js` 中的 `BASE_URL` 是否指向正确的后端地址
3. 如果跨域报错，确认 `Flask-CORS` 已正确安装和配置
4. 检查防火墙是否放行 5000 端口
</details>

<details>
<summary><b>Q6: 如何从 Neo4j 切换到本地 NetworkX？</b></summary>

在 `config.py` 中确保未设置 Neo4j 连接环境变量，系统会自动回退到 NetworkX 本地模式。
或者删除/注释 NEO4J 相关环境变量：
```bash
unset NEO4J_URI NEO4J_USER NEO4J_PASSWORD
```
</details>

---

## 🤝 贡献指南

本项目为 **2026 年中国大学生计算机设计大赛** 参赛作品。

### 贡献者

- **Joel-Ellen** — 全栈开发 & 架构设计
- 感谢所有参与测试和反馈的同学与老师

### 提交规范

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

---

## 📄 开源协议

本项目基于 **MIT License** 开源。

---

## 🙏 致谢

本项目得益于以下开源项目：

| 项目 | 用途 |
|------|------|
| [Flask](https://flask.palletsprojects.com/) | Python Web 框架 |
| [React](https://react.dev/) | 前端 UI 框架 |
| [PyTorch](https://pytorch.org/) | 深度学习框架 |
| [PyTorch Geometric](https://pyg.org/) | 图神经网络库 |
| [FAISS](https://github.com/facebookresearch/faiss) | 向量相似度搜索 |
| [sentence-transformers](https://www.sbert.net/) | 文本嵌入模型 |
| [NetworkX](https://networkx.org/) | 图结构分析 |
| [ECharts](https://echarts.apache.org/) | 数据可视化 |
| [PDF.js](https://mozilla.github.io/pdf.js/) | PDF 解析 |
| [DashScope](https://dashscope.aliyun.com/) | 通义千问 API |
| [datasketch](https://ekzhu.com/datasketch/) | LSH MinHash |
| [Neo4j](https://neo4j.com/) | 图数据库 |

---

<p align="center">
  <sub>Made with ❤️ for the 2026 China University Computer Design Competition</sub>
</p>
