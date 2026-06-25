"""
构建 LSH + FAISS 混合检索索引
用法: python -m backend.scripts.build_indices
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
from tqdm import tqdm

from backend.utils.data_loader import load_jobs_data, load_job_profiles, build_job_text, build_profile_vector
from backend.services.embedding_service import EmbeddingService, build_hybrid_vector, save_vectors
from backend.utils.lsh_indexer import LSHIndexer
from backend.utils.faiss_indexer import FAISSIndexer
from backend.config import VECTORS_DIR, INDICES_DIR


def build_all_indices():
    """一键构建所有索引"""
    print("=" * 60)
    print("[BuildIndices] 开始构建 LSH + FAISS 混合检索索引")
    print("=" * 60)

    # 1. 加载数据
    print("\n[Step 1/5] 加载岗位数据...")
    jobs_data = load_jobs_data()
    job_profiles = load_job_profiles()
    if not jobs_data:
        print("[BuildIndices] 错误: 岗位数据为空")
        return
    print(f"[BuildIndices] 加载 {len(jobs_data)} 条岗位数据")

    # 2. 文本嵌入
    print("\n[Step 2/5] 编码岗位文本嵌入...")
    embedder = EmbeddingService()
    if not embedder.is_ready:
        print("[BuildIndices] 错误: 嵌入模型未加载")
        return

    texts = [build_job_text(job) for job in jobs_data]
    job_ids = [job["id"] for job in jobs_data]

    # 批量编码
    all_embeddings = []
    batch_size = 32
    for i in tqdm(range(0, len(texts), batch_size), desc="编码文本"):
        batch_texts = texts[i:i + batch_size]
        batch_embs = embedder.encode(batch_texts)
        all_embeddings.append(batch_embs)
    text_embeddings = np.vstack(all_embeddings)
    print(f"[BuildIndices] 文本嵌入完成: shape={text_embeddings.shape}")

    # 3. 构建混合向量（文本 + 十维画像）
    print("\n[Step 3/5] 构建混合向量...")
    hybrid_vectors = []
    for i, job in enumerate(tqdm(jobs_data, desc="混合向量")):
        profile = job_profiles.get(str(job["id"]), {})
        profile_vec = build_profile_vector(profile)
        hybrid = build_hybrid_vector(text_embeddings[i], profile_vec)
        hybrid_vectors.append(hybrid)
    hybrid_vectors = np.array(hybrid_vectors, dtype=np.float32)
    print(f"[BuildIndices] 混合向量完成: shape={hybrid_vectors.shape}")

    # 保存向量和ID映射
    save_vectors(hybrid_vectors, job_ids)

    # 4. 构建 LSH 索引（关键词倒排索引）
    print("\n[Step 4/5] 构建 LSH 索引...")
    lsh = LSHIndexer()
    lsh.build_index(jobs_data, job_ids)
    lsh.save()
    print(f"[BuildIndices] LSH 索引已保存")

    # 5. 构建 FAISS 索引
    print("\n[Step 5/5] 构建 FAISS 索引...")
    faiss_index = FAISSIndexer()
    faiss_index.build_index(hybrid_vectors, job_ids)
    faiss_index.save()
    print(f"[BuildIndices] FAISS 索引已保存")

    print("\n" + "=" * 60)
    print("[BuildIndices] 所有索引构建完成!")
    print(f"  - 向量文件: {VECTORS_DIR / 'job_vectors.pkl'}")
    print(f"  - LSH 索引: {INDICES_DIR / 'lsh_index.pkl'}")
    print(f"  - FAISS 索引: {INDICES_DIR / 'faiss.index'}")
    print("=" * 60)

    # 6. 快速验证
    print("\n[验证] 执行测试查询...")
    test_query = "Python 后端开发 熟悉 Django Flask"
    candidates = lsh.query(test_query, top_k=50)
    print(f"  LSH 粗筛: {len(candidates)} 个候选")

    query_emb = embedder.encode_single(test_query)
    profile_zero = np.zeros(10, dtype=np.float32)
    query_hybrid = build_hybrid_vector(query_emb, profile_zero, text_weight=1.0, profile_weight=0.0)
    query_hybrid = query_hybrid.reshape(1, -1)

    distances, indices = faiss_index.search(query_hybrid, top_k=5, candidate_ids=candidates)
    print(f"  FAISS 精排 Top-5:")
    for i in range(min(5, len(indices[0]))):
        job_id = int(indices[0][i])
        score = float(distances[0][i])
        job = next((j for j in jobs_data if j["id"] == job_id), None)
        if job:
            print(f"    {i+1}. {job['name']} ({job['company']}) - 相似度: {score:.4f}")


if __name__ == "__main__":
    build_all_indices()
