"""
FAISS 索引工具
支持 HNSWFlat、IVFFlat、Flat 等多种索引类型
"""
import faiss
import numpy as np
from typing import List, Tuple, Optional
from pathlib import Path

from backend.config import (
    FAISS_INDEX_PATH, FAISS_INDEX_TYPE, FAISS_METRIC,
    FAISS_EF_CONSTRUCTION, FAISS_EF_SEARCH, FAISS_M,
    HYBRID_DIM
)


class FAISSIndexer:
    """FAISS 索引管理器"""

    def __init__(
        self,
        dim: int = HYBRID_DIM,
        index_type: str = FAISS_INDEX_TYPE,
        metric: str = FAISS_METRIC,
        index_path: Path = FAISS_INDEX_PATH,
        ef_construction: int = FAISS_EF_CONSTRUCTION,
        ef_search: int = FAISS_EF_SEARCH,
        m: int = FAISS_M,
    ):
        self.dim = dim
        self.index_type = index_type
        self.metric = metric
        self.index_path = index_path
        self.ef_construction = ef_construction
        self.ef_search = ef_search
        self.m = m
        
        self.index: Optional[faiss.Index] = None
        self.id_map: List[int] = []  # faiss 内部索引 -> job_id 映射

    def _create_index(self) -> faiss.Index:
        """创建 FAISS 索引"""
        metric_type = faiss.METRIC_INNER_PRODUCT if self.metric == "IP" else faiss.METRIC_L2
        
        if self.index_type == "Flat":
            # 精确搜索，适合小规模数据
            index = faiss.IndexFlat(self.dim, metric_type)
        elif self.index_type == "HNSWFlat":
            # 近似搜索，HNSW 图索引，适合中等规模数据
            index = faiss.IndexHNSWFlat(self.dim, self.m, metric_type)
            index.hnsw.efConstruction = self.ef_construction
            index.hnsw.efSearch = self.ef_search
        elif self.index_type == "IVFFlat":
            # 倒排文件索引，需要训练
            quantizer = faiss.IndexFlat(self.dim, metric_type)
            nlist = max(1, min(4096, self.dim * 2))  # 聚类中心数
            index = faiss.IndexIVFFlat(quantizer, self.dim, nlist, metric_type)
        elif self.index_type == "IVFPQ":
            # 乘积量化压缩索引，适合大规模数据
            quantizer = faiss.IndexFlat(self.dim, metric_type)
            nlist = max(1, min(4096, self.dim * 2))
            m = 16  # 子向量数
            nbits = 8  # 每个子向量量化位数
            index = faiss.IndexIVFPQ(quantizer, self.dim, nlist, m, nbits, metric_type)
        else:
            raise ValueError(f"不支持的索引类型: {self.index_type}")
        
        return index

    def build_index(self, vectors: np.ndarray, ids: List[int]) -> "FAISSIndexer":
        """
        构建 FAISS 索引
        
        Args:
            vectors: 向量矩阵 (N, dim), float32
            ids: 对应的岗位ID列表
        
        Returns:
            self
        """
        print(f"[FAISSIndexer] 构建索引: {len(vectors)} 条, dim={self.dim}, type={self.index_type}, metric={self.metric}")
        
        # 确保向量是 float32 且连续内存
        vectors = np.ascontiguousarray(vectors.astype(np.float32))
        
        # 创建索引
        base_index = self._create_index()
        
        # 使用 IDMap 包装以支持自定义ID
        self.index = faiss.IndexIDMap(base_index)
        self.id_map = ids
        
        # 对于 IVFFlat/IVFPQ 需要先训练
        if self.index_type in ("IVFFlat", "IVFPQ"):
            print(f"[FAISSIndexer] 训练 IVFFlat/IVFPQ 索引...")
            self.index.train(vectors)
        
        # 添加向量
        faiss_ids = np.array(ids, dtype=np.int64)
        self.index.add_with_ids(vectors, faiss_ids)
        
        print(f"[FAISSIndexer] 索引构建完成，总向量数: {self.index.ntotal}")
        return self

    def search(
        self,
        query_vectors: np.ndarray,
        top_k: int = 5,
        candidate_ids: Optional[List[int]] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        向量相似度搜索
        
        Args:
            query_vectors: 查询向量 (N, dim) 或 (dim,)
            top_k: 返回Top-K结果
            candidate_ids: 候选ID列表（从LSH粗筛传入，限制搜索范围）
        
        Returns:
            distances: (N, top_k) 距离/相似度分数
            indices: (N, top_k) 岗位ID
        """
        if self.index is None:
            raise RuntimeError("FAISS 索引未构建，请先调用 build_index()")
        
        # 确保查询向量格式正确
        if query_vectors.ndim == 1:
            query_vectors = query_vectors.reshape(1, -1)
        query_vectors = np.ascontiguousarray(query_vectors.astype(np.float32))
        
        # 如果有候选ID限制，使用 IDSelector
        if candidate_ids is not None and len(candidate_ids) > 0:
            # FAISS IDSelectorBatch
            id_selector = faiss.IDSelectorBatch(np.array(candidate_ids, dtype=np.int64))
            params = faiss.SearchParametersIVF(sel=id_selector) if hasattr(self.index, 'nlist') else faiss.SearchParametersHNSW(sel=id_selector)
            distances, indices = self.index.search(query_vectors, top_k, params=params)
        else:
            distances, indices = self.index.search(query_vectors, top_k)
        
        return distances, indices

    def save(self, path: Path = None):
        """保存索引到文件"""
        if path is None:
            path = self.index_path
        path.parent.mkdir(parents=True, exist_ok=True)
        
        faiss.write_index(self.index, str(path))
        print(f"[FAISSIndexer] 索引已保存: {path}")

    def load(self, path: Path = None) -> "FAISSIndexer":
        """从文件加载索引"""
        if path is None:
            path = self.index_path
        
        if not path.exists():
            raise FileNotFoundError(f"FAISS 索引文件不存在: {path}")
        
        self.index = faiss.read_index(str(path))
        print(f"[FAISSIndexer] 索引已加载: {self.index.ntotal} 条, path={path}")
        return self

    @property
    def is_built(self) -> bool:
        return self.index is not None and self.index.ntotal > 0
