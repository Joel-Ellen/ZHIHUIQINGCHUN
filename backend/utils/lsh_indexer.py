"""
LSH (Locality Sensitive Hashing) 索引工具
使用基于技能关键词的倒排索引实现粗筛
兼容原有接口，内部改为关键词匹配策略
"""
import pickle
import re
import json
from typing import List, Dict, Set, Optional
from pathlib import Path

from backend.config import LSH_INDEX_PATH


class LSHIndexer:
    """LSH 索引管理器（基于关键词倒排索引）"""

    def __init__(self, index_path: Path = LSH_INDEX_PATH):
        self.index_path = index_path
        self.inverted_index: Dict[str, Set[int]] = {}  # keyword -> set(job_ids)
        self.job_keywords: Dict[int, Set[str]] = {}    # job_id -> set(keywords)
        self._job_data_map: Dict[int, dict] = {}       # job_id -> job dict (for fallback)

    @staticmethod
    def _extract_keywords(text: str) -> Set[str]:
        """从文本中提取候选关键词"""
        if not text:
            return set()
        keywords = set()
        # 1. 提取英文单词（技能名如 Python, Java, TensorFlow, SpringBoot 等）
        for word in re.findall(r'[A-Za-z+#]+', text):
            w = word.lower()
            if len(w) >= 2:
                keywords.add(w)
        # 2. 提取连续中文字符作为关键词（职位名、技术栈等）
        for seg in re.findall(r'[\u4e00-\u9fff]{2,8}', text):
            keywords.add(seg)
        return keywords

    def build_index(self, jobs_data: List[Dict], ids: List[int]) -> "LSHIndexer":
        """
        构建关键词倒排索引
        
        Args:
            jobs_data: 岗位数据列表（字典格式，需包含 name, skills, description, requirement）
            ids: 对应的岗位ID列表
        """
        print(f"[LSHIndexer] 构建关键词倒排索引: {len(jobs_data)} 条文档")
        
        self.inverted_index = {}
        self.job_keywords = {}
        self._job_data_map = {}

        for job, job_id in zip(jobs_data, ids):
            keywords = set()
            
            # 从 skills 字段提取（核心技能关键词）
            for skill in job.get("skills", []):
                if isinstance(skill, str) and len(skill) >= 1:
                    keywords.add(skill.lower())
            
            # 从 name, description, requirement 提取
            for field in ["name", "description", "requirement"]:
                text = job.get(field, "")
                if isinstance(text, str):
                    keywords.update(self._extract_keywords(text))
            
            self.job_keywords[job_id] = keywords
            self._job_data_map[job_id] = job
            
            for kw in keywords:
                self.inverted_index.setdefault(kw, set()).add(job_id)
            
            if (len(self.job_keywords)) % 1000 == 0:
                print(f"[LSHIndexer] 已处理 {len(self.job_keywords)}/{len(jobs_data)}")

        print(f"[LSHIndexer] 索引构建完成，共 {len(self.job_keywords)} 条，关键词 {len(self.inverted_index)} 个")
        return self

    def query(self, text: str, top_k: int = 100) -> List[int]:
        """
        查询相似文档
        
        Args:
            text: 查询文本
            top_k: 返回的最大候选数
        
        Returns:
            候选岗位ID列表（按匹配关键词数降序）
        """
        if not self.inverted_index:
            raise RuntimeError("LSH 索引未构建，请先调用 build_index()")
        
        query_keywords = self._extract_keywords(text)
        # 额外处理：将查询文本按空格/逗号分词也加入关键词
        for raw_kw in re.split(r'[,，\s]+', text):
            raw = raw_kw.strip()
            if len(raw) >= 2:
                query_keywords.add(raw.lower())
        
        if not query_keywords:
            return []
        
        # 统计每个 job_id 匹配的关键词数
        scores: Dict[int, int] = {}
        for kw in query_keywords:
            # 精确匹配
            for job_id in self.inverted_index.get(kw, set()):
                scores[job_id] = scores.get(job_id, 0) + 3  # 精确匹配权重高
            
            # 前缀匹配（如 "spring" 匹配 "springboot"）
            for indexed_kw, job_ids in self.inverted_index.items():
                if indexed_kw != kw and (indexed_kw.startswith(kw) or kw.startswith(indexed_kw)):
                    for job_id in job_ids:
                        scores[job_id] = scores.get(job_id, 0) + 1
        
        # 按匹配分数降序，取 top_k
        sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [job_id for job_id, _ in sorted_results[:top_k]]

    def save(self, path: Path = None):
        """保存索引到文件"""
        if path is None:
            path = self.index_path
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "wb") as f:
            pickle.dump({
                "inverted_index": {k: list(v) for k, v in self.inverted_index.items()},
                "job_keywords": {k: list(v) for k, v in self.job_keywords.items()},
            }, f)
        print(f"[LSHIndexer] 索引已保存: {path}")

    def load(self, path: Path = None) -> "LSHIndexer":
        """从文件加载索引"""
        if path is None:
            path = self.index_path
        
        if not path.exists():
            raise FileNotFoundError(f"LSH 索引文件不存在: {path}")
        
        with open(path, "rb") as f:
            data = pickle.load(f)
        
        self.inverted_index = {k: set(v) for k, v in data["inverted_index"].items()}
        self.job_keywords = {k: set(v) for k, v in data["job_keywords"].items()}
        
        print(f"[LSHIndexer] 索引已加载: {len(self.job_keywords)} 条, 关键词 {len(self.inverted_index)} 个, path={path}")
        return self

    @property
    def is_built(self) -> bool:
        return len(self.inverted_index) > 0 and len(self.job_keywords) > 0
