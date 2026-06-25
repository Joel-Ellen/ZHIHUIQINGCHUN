"""
智绘青春 - 全局配置
"""
import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).parent

# 数据目录
DATA_DIR = BASE_DIR / "data"
VECTORS_DIR = DATA_DIR / "vectors"
INDICES_DIR = DATA_DIR / "indices"
MODELS_DIR = DATA_DIR / "models"

# 数据集路径
JOBS_DATA_PATH = BASE_DIR.parent / "jobs_data.json"
JOB_PROFILES_PATH = BASE_DIR.parent / "job_profiles.json"

# 向量维度配置
# BGE-M3: 768维 | paraphrase-multilingual-MiniLM-L12-v2: 384维
TEXT_EMBEDDING_DIM = 384  # 根据 EMBEDDING_MODEL 自动适配
PROFILE_DIM = 10          # 十维画像维度
HYBRID_DIM = TEXT_EMBEDDING_DIM + PROFILE_DIM  # 混合向量维度 = 394

# LSH 配置
LSH_NUM_PERM = 128        # MinHash 置换函数数量
LSH_NUM_BANDS = 16        # LSH 带数
LSH_ROWS_PER_BAND = 8     # 每带行数 (16 * 8 = 128)
LSH_THRESHOLD = 0.15      # Jaccard 相似度阈值（短查询vs长文档需降低）
LSH_INDEX_PATH = INDICES_DIR / "lsh_index.pkl"

# FAISS 配置
FAISS_INDEX_PATH = INDICES_DIR / "faiss.index"
FAISS_INDEX_TYPE = "HNSWFlat"  # 可选: Flat, HNSWFlat, IVFFlat, IVFPQ
FAISS_METRIC = "IP"        # 内积 (IP) 或 L2 距离
FAISS_EF_CONSTRUCTION = 200
FAISS_EF_SEARCH = 128
FAISS_M = 32               # HNSW 每个节点的最大连接数

# 嵌入模型配置
# BGE-M3 (768维, 约2GB) - 中文效果最佳，但下载大
# paraphrase-multilingual-MiniLM-L12-v2 (384维, 约120MB) - 轻量快速，适合本地部署
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DEVICE = "cpu"   # 或 "cuda" (如果有GPU)
EMBEDDING_BATCH_SIZE = 64
EMBEDDING_MAX_LENGTH = 256

# Neo4j 配置
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "zhihuiqingchun")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "kg4career")

# TransE + R-GCN 配置
TRANSE_EMBEDDING_DIM = 128
TRANSE_MARGIN = 1.0
TRANSE_EPOCHS = 500
TRANSE_LR = 0.001
TRANSE_MODEL_PATH = MODELS_DIR / "transe_model.pt"

RGCN_HIDDEN_DIM = 64
RGCN_OUT_DIM = 32
RGCN_NUM_LAYERS = 2
RGCN_DROPOUT = 0.3
RGCN_EPOCHS = 300
RGCN_LR = 0.005
RGCN_MODEL_PATH = MODELS_DIR / "rgcn_model.pt"

# 检索配置
RETRIEVAL_TOP_K = 5
RETRIEVAL_LSH_CANDIDATE_FACTOR = 10  # LSH 粗筛候选集倍数 (Top-K * 10)

# LLM 配置（与现有 backend.py 保持一致）
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
LLM_MODEL = "qwen-plus"
LLM_TEMPERATURE = 0.7
LLM_MAX_TOKENS = 2000

# Agentic RAG 配置
RAG_MAX_RETRIEVAL_STEPS = 3
RAG_CONTEXT_MAX_TOKENS = 1500
RAG_SIMILARITY_THRESHOLD = 0.75

# 冷启动配置
COLD_START_MIN_SKILLS = 1
COLD_START_GNN_HOPS = 2
