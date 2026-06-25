"""
训练 TransE + R-GCN 模型
用法: python -m backend.scripts.build_gnn
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pickle
import random
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch_geometric.data import Data
from collections import defaultdict

from backend.services.kg_service import KGService
from backend.services.gnn_service import TransE, RGCNModel, ColdStartService
from backend.utils.data_loader import load_jobs_data, load_job_profiles
from backend.config import (
    TRANSE_EMBEDDING_DIM, TRANSE_MARGIN, TRANSE_LR,
    RGCN_HIDDEN_DIM, RGCN_OUT_DIM, RGCN_NUM_LAYERS, RGCN_DROPOUT, RGCN_LR,
    TRANSE_MODEL_PATH, RGCN_MODEL_PATH, MODELS_DIR,
)


# CPU 优化
torch.set_num_threads(4)

# 设置随机种子
torch.manual_seed(42)
np.random.seed(42)
random.seed(42)


def extract_triples_from_kg(kg_service: KGService):
    """从 NetworkX 图谱中提取三元组"""
    triples = []
    entity_map = {}  # entity_name -> id
    relation_map = {}  # relation_name -> id
    
    def get_entity_id(node_id: str):
        if node_id not in entity_map:
            entity_map[node_id] = len(entity_map)
        return entity_map[node_id]
    
    def get_relation_id(rel_name: str):
        if rel_name not in relation_map:
            relation_map[rel_name] = len(relation_map)
        return relation_map[rel_name]
    
    for u, v, attrs in kg_service.graph.edges(data=True):
        rel_type = attrs.get("type", "UNKNOWN")
        h = get_entity_id(u)
        r = get_relation_id(rel_type)
        t = get_entity_id(v)
        triples.append((h, r, t))
    
    return triples, entity_map, relation_map


def train_transe(triples, num_entities, num_relations, epochs=30, batch_size=512):
    """训练 TransE 模型"""
    print(f"[TransE] 开始训练: {num_entities} 实体, {num_relations} 关系, {len(triples)} 三元组")
    
    model = TransE(num_entities, num_relations, TRANSE_EMBEDDING_DIM, TRANSE_MARGIN)
    optimizer = optim.Adam(model.parameters(), lr=TRANSE_LR)
    
    # 构建尾实体池用于负采样
    all_tails = list(set(t[2] for t in triples))
    
    best_loss = float('inf')
    for epoch in range(epochs):
        random.shuffle(triples)
        total_loss = 0
        num_batches = 0
        
        for i in range(0, len(triples), batch_size):
            batch = triples[i:i + batch_size]
            heads = torch.tensor([t[0] for t in batch])
            relations = torch.tensor([t[1] for t in batch])
            tails = torch.tensor([t[2] for t in batch])
            
            # 负采样：随机替换尾实体
            neg_tails = torch.tensor([random.choice(all_tails) for _ in batch])
            
            optimizer.zero_grad()
            loss = model(heads, relations, tails, neg_tails)
            loss.backward()
            optimizer.step()
            
            # 归一化实体嵌入
            model.entity_embeddings.weight.data = nn.functional.normalize(
                model.entity_embeddings.weight.data, p=2, dim=1
            )
            
            total_loss += loss.item()
            num_batches += 1
        
        avg_loss = total_loss / max(num_batches, 1)
        if avg_loss < best_loss:
            best_loss = avg_loss
        
        if (epoch + 1) % 10 == 0:
            print(f"[TransE] Epoch {epoch + 1}/{epochs}, Loss: {avg_loss:.4f}")
    
    print(f"[TransE] 训练完成, Best Loss: {best_loss:.4f}")
    return model


def build_pyg_data(kg_service: KGService, entity_map: dict, transe_model: TransE):
    """构建 PyG Data 对象用于 R-GCN 训练"""
    num_nodes = len(entity_map)
    
    # 节点特征：TransE 嵌入
    with torch.no_grad():
        node_features = transe_model.entity_embeddings.weight.clone()
    
    # 边索引和边类型
    edge_index = []
    edge_type = []
    
    for u, v, attrs in kg_service.graph.edges(data=True):
        rel_type = attrs.get("type", "UNKNOWN")
        src = entity_map[u]
        dst = entity_map[v]
        rel_id = relation_map[rel_type]
        edge_index.append([src, dst])
        edge_type.append(rel_id)
    
    edge_index = torch.tensor(edge_index, dtype=torch.long).t().contiguous()
    edge_type = torch.tensor(edge_type, dtype=torch.long)
    
    return Data(x=node_features, edge_index=edge_index, edge_type=edge_type, num_nodes=num_nodes)


def train_rgcn(pyg_data, job_profiles, entity_map, kg_service, epochs=50):
    """训练 R-GCN 模型"""
    print(f"[R-GCN] 开始训练: {pyg_data.num_nodes} 节点, {len(relation_map)} 关系类型")
    
    # 构建 Job 节点的标签（十维画像）
    dimension_names = [
        "获奖情况", "专业技能", "学历证书", "学习成绩",
        "实习经历", "创新能力", "沟通协作", "责任心",
        "抗压能力", "解决问题能力"
    ]
    
    # 找到所有 Job 节点
    job_node_ids = []
    job_labels = []
    job_id_to_node = {}  # job_data_id -> node_id
    
    for node_id, attrs in kg_service.graph.nodes(data=True):
        if attrs.get("label") == "Job":
            data_id = attrs.get("id")
            if data_id is not None and str(data_id) in job_profiles:
                profile = job_profiles[str(data_id)]
                label_vec = [profile.get(d, 50) / 10.0 for d in dimension_names]  # 0-10 范围
                
                entity_key = f"Job::{data_id}"
                if entity_key in entity_map:
                    node_idx = entity_map[entity_key]
                    job_node_ids.append(node_idx)
                    job_labels.append(label_vec)
                    job_id_to_node[data_id] = node_idx
    
    if not job_node_ids:
        print("[R-GCN] 警告: 没有可用的 Job 节点标签，跳过训练")
        return None
    
    job_node_ids = torch.tensor(job_node_ids, dtype=torch.long)
    job_labels = torch.tensor(job_labels, dtype=torch.float32)
    
    print(f"[R-GCN] 监督节点数: {len(job_node_ids)}")
    
    # 创建模型
    model = RGCNModel(
        in_channels=TRANSE_EMBEDDING_DIM,
        hidden_channels=RGCN_HIDDEN_DIM,
        out_channels=10,  # 十维画像
        num_relations=len(relation_map),
        num_layers=RGCN_NUM_LAYERS,
        dropout=RGCN_DROPOUT,
    )
    
    optimizer = optim.Adam(model.parameters(), lr=RGCN_LR)
    criterion = nn.MSELoss()
    
    best_loss = float('inf')
    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()
        
        out = model(pyg_data.x, pyg_data.edge_index, pyg_data.edge_type)
        
        # 只计算 Job 节点的损失
        pred = out[job_node_ids]
        loss = criterion(pred, job_labels)
        
        loss.backward()
        optimizer.step()
        
        if loss.item() < best_loss:
            best_loss = loss.item()
        
        if (epoch + 1) % 10 == 0:
            print(f"[R-GCN] Epoch {epoch + 1}/{epochs}, Loss: {loss.item():.4f}")
    
    print(f"[R-GCN] 训练完成, Best Loss: {best_loss:.4f}")
    return model


def save_metadata(entity_map, relation_map, jobs_data):
    """保存训练元数据"""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    meta = {
        "entity_map": entity_map,
        "relation_map": relation_map,
        "num_jobs": len(jobs_data),
    }
    with open(MODELS_DIR / "gnn_metadata.pkl", "wb") as f:
        pickle.dump(meta, f)
    print(f"[BuildGNN] 元数据已保存")


def main():
    print("=" * 60)
    print("[BuildGNN] 开始训练 TransE + R-GCN 模型")
    print("=" * 60)
    
    # 1. 加载知识图谱
    print("\n[Step 1/5] 加载知识图谱...")
    kg = KGService()
    kg.load()
    if not kg.is_connected:
        print("[BuildGNN] 错误: 知识图谱未构建，请先运行 build_kg.py")
        return
    
    # 2. 提取三元组
    print("\n[Step 2/5] 提取三元组...")
    global relation_map
    triples, entity_map, relation_map = extract_triples_from_kg(kg)
    print(f"[BuildGNN] 三元组: {len(triples)}, 实体: {len(entity_map)}, 关系: {len(relation_map)}")
    
    # 3. 训练 TransE
    print("\n[Step 3/5] 训练 TransE...")
    transe_model = train_transe(
        triples, len(entity_map), len(relation_map),
        epochs=50, batch_size=256
    )
    
    # 4. 构建 PyG 数据并训练 R-GCN
    print("\n[Step 4/5] 训练 R-GCN...")
    pyg_data = build_pyg_data(kg, entity_map, transe_model)
    job_profiles = load_job_profiles()
    rgcn_model = train_rgcn(pyg_data, job_profiles, entity_map, kg, epochs=30)
    
    # 5. 保存模型
    print("\n[Step 5/5] 保存模型...")
    service = ColdStartService(transe_model, rgcn_model)
    service.entity_map = entity_map
    service.relation_map = relation_map
    service.save_models()
    
    jobs_data = load_jobs_data()
    save_metadata(entity_map, relation_map, jobs_data)
    
    # 6. 快速验证
    print("\n[验证] 冷启动预测测试...")
    test_profile = service.predict_profile(
        school="测试大学",
        major="计算机科学",
        skills=["Python", "Java"],
    )
    for dim, score in test_profile.items():
        print(f"  {dim}: {score}")
    
    print("\n" + "=" * 60)
    print("[BuildGNN] GNN 模型训练完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
