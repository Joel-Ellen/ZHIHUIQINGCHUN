"""
LSH + FAISS 两级混合检索服务
第一级: LSH 粗筛 (O(1))
第二级: FAISS 精排 (近似 O(1))
"""
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from backend.config import RETRIEVAL_TOP_K, RETRIEVAL_LSH_CANDIDATE_FACTOR
from backend.utils.lsh_indexer import LSHIndexer
from backend.utils.faiss_indexer import FAISSIndexer
from backend.services.embedding_service import EmbeddingService, build_hybrid_vector
from backend.utils.data_loader import build_job_text, build_profile_vector


class HybridRetrievalService:
    """混合检索服务 - LSH + FAISS 两级架构"""

    def __init__(
        self,
        lsh_indexer: Optional[LSHIndexer] = None,
        faiss_indexer: Optional[FAISSIndexer] = None,
        embedding_service: Optional[EmbeddingService] = None,
    ):
        self.lsh = lsh_indexer or LSHIndexer()
        self.faiss = faiss_indexer or FAISSIndexer()
        self.embedder = embedding_service or EmbeddingService()
        
        # 缓存岗位数据（用于结果反查）
        self.jobs_cache: Dict[int, Dict[str, Any]] = {}

    def is_ready(self) -> bool:
        """检查服务是否就绪"""
        return (
            self.lsh.is_built
            and self.faiss.is_built
            and self.embedder.is_ready
        )

    def cache_jobs(self, jobs_data: List[Dict[str, Any]]):
        """缓存岗位数据，用于检索结果反查"""
        self.jobs_cache = {job["id"]: job for job in jobs_data}
        print(f"[HybridRetrieval] 缓存岗位数据: {len(self.jobs_cache)} 条")

    def search(
        self,
        query_text: str,
        profile_vector: Optional[List[float]] = None,
        top_k: int = RETRIEVAL_TOP_K,
        use_lsh: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        混合检索入口
        
        Args:
            query_text: 查询文本（如用户简历内容、岗位名称、技能描述）
            profile_vector: 十维画像向量（10维，可选，用于增强检索）
            top_k: 返回结果数
            use_lsh: 是否使用 LSH 粗筛（False则直接FAISS全量搜索）
        
        Returns:
            检索结果列表，每项包含岗位信息和相似度分数
        """
        if not self.is_ready():
            raise RuntimeError("混合检索服务未就绪，请先构建索引")
        
        # Step 1: 文本编码
        text_embedding = self.embedder.encode_single(query_text)
        
        # Step 2: 构建混合查询向量
        if profile_vector is not None:
            query_vector = build_hybrid_vector(text_embedding, profile_vector)
        else:
            # 无画像时，只用文本向量，画像部分填0
            profile_zero = np.zeros(10, dtype=np.float32)
            query_vector = build_hybrid_vector(text_embedding, profile_zero, text_weight=1.0, profile_weight=0.0)
        
        query_vector = query_vector.reshape(1, -1)
        
        # Step 3: 第一级 - LSH 粗筛
        candidate_ids = None
        if use_lsh:
            lsh_candidates = self.lsh.query(query_text, top_k=top_k * RETRIEVAL_LSH_CANDIDATE_FACTOR)
            if len(lsh_candidates) > 0:
                candidate_ids = lsh_candidates
                print(f"[HybridRetrieval] LSH 粗筛: {len(candidate_ids)} 个候选")
            else:
                print(f"[HybridRetrieval] LSH 粗筛无结果，降级为全量搜索")
        
        # Step 4: 第二级 - FAISS 精排
        distances, indices = self.faiss.search(query_vector, top_k=top_k, candidate_ids=candidate_ids)
        
        # Step 5: 组装结果
        results = []
        for i in range(min(top_k, len(indices[0]))):
            job_id = int(indices[0][i])
            score = float(distances[0][i])
            
            job = self.jobs_cache.get(job_id, {})
            if job:
                results.append({
                    "id": job_id,
                    "name": job.get("name", ""),
                    "company": job.get("company", ""),
                    "salary": job.get("salary", ""),
                    "location": job.get("location", ""),
                    "industry": job.get("industry", ""),
                    "skills": job.get("skills", []),
                    "education": job.get("education", ""),
                    "experience": job.get("experience", ""),
                    "description": job.get("description", ""),
                    "requirement": job.get("requirement", ""),
                    "similarity_score": round(score, 4),
                    "retrieval_path": "LSH+FAISS" if use_lsh and candidate_ids else "FAISS",
                })
        
        return results

    def search_by_skills(
        self,
        skills: List[str],
        profile_vector: Optional[List[float]] = None,
        top_k: int = RETRIEVAL_TOP_K
    ) -> List[Dict[str, Any]]:
        """基于技能列表检索岗位"""
        query_text = f"技能: {', '.join(skills)}"
        return self.search(query_text, profile_vector, top_k)

    def search_by_job_name(
        self,
        job_name: str,
        profile_vector: Optional[List[float]] = None,
        top_k: int = RETRIEVAL_TOP_K
    ) -> List[Dict[str, Any]]:
        """基于岗位名称检索相似岗位"""
        query_text = f"岗位名称: {job_name}"
        return self.search(query_text, profile_vector, top_k)

    def search_by_resume(
        self,
        resume_text: str,
        profile_vector: Optional[List[float]] = None,
        top_k: int = RETRIEVAL_TOP_K
    ) -> List[Dict[str, Any]]:
        """基于简历全文检索匹配岗位"""
        return self.search(resume_text, profile_vector, top_k)

    def get_debug_info(self) -> Dict[str, Any]:
        """获取检索系统调试信息"""
        return {
            "lsh_built": self.lsh.is_built,
            "lsh_docs": len(self.lsh.job_keywords) if self.lsh.is_built else 0,
            "lsh_keywords": len(self.lsh.inverted_index) if self.lsh.is_built else 0,
            "faiss_built": self.faiss.is_built,
            "faiss_total": self.faiss.index.ntotal if self.faiss.is_built else 0,
            "embedder_ready": self.embedder.is_ready,
            "jobs_cached": len(self.jobs_cache),
        }


# ========== 全局单例 ==========
_retrieval_service: Optional[HybridRetrievalService] = None


def get_retrieval_service() -> HybridRetrievalService:
    """获取混合检索服务单例"""
    global _retrieval_service
    if _retrieval_service is None:
        _retrieval_service = HybridRetrievalService()
    return _retrieval_service
