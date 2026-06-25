"""
构建 KG4Career 知识图谱 (NetworkX 版本)
用法: python -m backend.scripts.build_kg
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.utils.data_loader import load_jobs_data, load_job_profiles
from backend.services.kg_service import KGService


def build_knowledge_graph():
    """从岗位数据构建知识图谱"""
    print("=" * 60)
    print("[BuildKG] 开始构建 KG4Career 知识图谱")
    print("=" * 60)

    # 1. 加载数据
    print("\n[Step 1/3] 加载数据...")
    jobs_data = load_jobs_data()
    job_profiles = load_job_profiles()
    if not jobs_data:
        print("[BuildKG] 错误: 岗位数据为空")
        return
    print(f"[BuildKG] 加载 {len(jobs_data)} 条岗位数据")

    # 2. 初始化服务
    print("\n[Step 2/3] 初始化知识图谱服务...")
    kg = KGService()

    # 3. 构建知识图谱
    print("\n[Step 3/3] 构建知识图谱...")
    kg.build_from_jobs_data(jobs_data, job_profiles)

    # 4. 保存图谱
    kg.save()

    # 5. 统计信息
    print("\n[BuildKG] 知识图谱统计:")
    stats = kg.get_stats()
    for label, count in stats.items():
        print(f"  {label}: {count}")

    # 6. 快速验证查询
    print("\n[BuildKG] 验证 GraphRAG 查询...")
    
    # 技能查询
    results = kg.query_graph_rag("jobs_by_skills", skills=["Python"], limit=3)
    print(f"  技能查询 'Python': {len(results)} 个岗位")
    
    # 网络查询
    sample_job = jobs_data[0]["name"]
    network = kg.query_graph_rag("job_network", job_name=sample_job, depth=1)
    if network:
        n = network[0]
        print(f"  岗位网络 '{sample_job}': {len(n['skills'])} 技能, {len(n['similar_jobs'])} 相似岗位")

    print("\n" + "=" * 60)
    print("[BuildKG] 知识图谱构建完成!")
    print("=" * 60)


if __name__ == "__main__":
    build_knowledge_graph()
