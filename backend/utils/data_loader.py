"""
数据加载与预处理工具
"""
import json
from pathlib import Path
from typing import List, Dict, Any


def load_jobs_data(path: Path = None) -> List[Dict[str, Any]]:
    """加载岗位数据集"""
    if path is None:
        path = Path(__file__).parent.parent.parent / "jobs_data.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[DataLoader] 加载 jobs_data.json 失败: {e}")
        return []


def load_job_profiles(path: Path = None) -> Dict[str, Dict[str, int]]:
    """加载岗位画像数据集"""
    if path is None:
        path = Path(__file__).parent.parent.parent / "job_profiles.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[DataLoader] 加载 job_profiles.json 失败: {e}")
        return {}


def build_job_text(job: Dict[str, Any]) -> str:
    """将岗位信息拼接为文本，用于嵌入编码"""
    parts = [
        f"岗位名称: {job.get('name', '')}",
        f"公司: {job.get('company', '')}",
        f"行业: {job.get('industry', '')}",
        f"地点: {job.get('location', '')}",
        f"薪资: {job.get('salary', '')}",
        f"学历要求: {job.get('education', '')}",
        f"经验要求: {job.get('experience', '')}",
        f"技能要求: {', '.join(job.get('skills', []))}",
        f"岗位描述: {job.get('description', '')}",
        f"岗位要求: {job.get('requirement', '')}",
    ]
    return "\n".join(parts)


def build_profile_vector(profile: Dict[str, int]) -> List[float]:
    """将十维画像转换为向量（10维，已归一化为0-10分制）"""
    dimensions = [
        "获奖情况", "专业技能", "学历证书", "学习成绩",
        "实习经历", "创新能力", "沟通协作", "责任心",
        "抗压能力", "解决问题能力"
    ]
    return [float(profile.get(dim, 5)) for dim in dimensions]


def normalize_profile_scores(profile: Dict[str, int]) -> Dict[str, float]:
    """将画像分数归一化到 0-10 范围"""
    return {k: min(max(float(v), 0), 10) for k, v in profile.items()}
