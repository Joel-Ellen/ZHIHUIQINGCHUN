"""
一键初始化所有技术模块
用法: python -m backend.scripts.init_all
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.scripts.build_indices import build_all_indices
from backend.scripts.build_kg import build_knowledge_graph


def init_all():
    """一键初始化所有模块"""
    print("\n" + "=" * 70)
    print(" 智绘青春 - 三大技术架构一键初始化 ")
    print(" LSH+FAISS | Agentic RAG+GraphRAG | TransE+R-GCN ")
    print("=" * 70 + "\n")

    # 1. 构建 LSH + FAISS 索引
    print("[Phase 1/2] 构建 LSH + FAISS 混合检索索引\n")
    try:
        build_all_indices()
    except Exception as e:
        print(f"[Phase 1] 索引构建失败: {e}")
        print("  提示: 请确保模型下载完成，磁盘空间充足")

    # 2. 构建知识图谱
    print("\n[Phase 2/2] 构建 KG4Career 知识图谱\n")
    try:
        build_knowledge_graph()
    except Exception as e:
        print(f"[Phase 2] 知识图谱构建失败: {e}")
        print("  提示: 请确保 Neo4j 已启动")

    print("\n" + "=" * 70)
    print(" 初始化完成！")
    print(" 接下来请启动后端服务: python backend.py")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    init_all()
