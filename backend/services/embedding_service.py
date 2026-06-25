"""
文本嵌入服务 - 基于 Sentence-Transformers (BGE-M3)
"""
import os
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

import numpy as np
from typing import List, Union
from pathlib import Path
import pickle

from backend.config import (
    EMBEDDING_MODEL, EMBEDDING_DEVICE, EMBEDDING_BATCH_SIZE, EMBEDDING_MAX_LENGTH,
    TEXT_EMBEDDING_DIM, VECTORS_DIR
)


class EmbeddingService:
    """单例模式的嵌入服务"""
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            print(f"[EmbeddingService] 加载模型: {EMBEDDING_MODEL}")
            self._model = SentenceTransformer(EMBEDDING_MODEL, device=EMBEDDING_DEVICE)
            try:
                dim = self._model.get_embedding_dimension()
            except Exception:
                dim = self._model.get_sentence_embedding_dimension()
            print(f"[EmbeddingService] 模型加载完成，维度: {dim}")
        except Exception as e:
            print(f"[EmbeddingService] 模型加载失败: {e}")
            self._model = None

    @property
    def is_ready(self) -> bool:
        return self._model is not None

    def encode(self, texts: Union[str, List[str]], batch_size: int = None) -> np.ndarray:
        """编码文本为向量"""
        if not self.is_ready:
            raise RuntimeError("嵌入模型未加载")
        if isinstance(texts, str):
            texts = [texts]
        batch_size = batch_size or EMBEDDING_BATCH_SIZE
        embeddings = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True  # L2 归一化，便于内积计算
        )
        return embeddings.astype(np.float32)

    def encode_single(self, text: str) -> np.ndarray:
        """编码单条文本"""
        return self.encode(text)[0]


def build_hybrid_vector(
    text_embedding: np.ndarray,
    profile_vector: np.ndarray,
    text_weight: float = 0.8,
    profile_weight: float = 0.2
) -> np.ndarray:
    """
    构建混合向量：文本嵌入 + 十维画像
    
    Args:
        text_embedding: 文本嵌入向量 (768维, 已L2归一化)
        profile_vector: 十维画像向量 (10维, 0-10分)
        text_weight: 文本向量权重
        profile_weight: 画像向量权重
    
    Returns:
        混合向量 (778维)
    """
    # 画像向量归一化到 [-1, 1] 范围
    profile_norm = (np.array(profile_vector, dtype=np.float32) - 5) / 5
    
    # 加权拼接
    hybrid = np.concatenate([
        text_embedding * text_weight,
        profile_norm * profile_weight
    ])
    
    return hybrid.astype(np.float32)


def save_vectors(vectors: np.ndarray, ids: List[int], path: Path = None):
    """保存向量和对应ID"""
    if path is None:
        path = VECTORS_DIR / "job_vectors.pkl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump({"vectors": vectors, "ids": ids}, f)
    print(f"[EmbeddingService] 向量已保存: {path}")


def load_vectors(path: Path = None) -> tuple:
    """加载向量和对应ID"""
    if path is None:
        path = VECTORS_DIR / "job_vectors.pkl"
    if not path.exists():
        return None, None
    with open(path, "rb") as f:
        data = pickle.load(f)
    return data["vectors"], data["ids"]
