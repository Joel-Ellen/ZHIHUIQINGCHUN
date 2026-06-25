"""
知识图谱服务 (NetworkX 版本)
提供知识图谱的构建和 GraphRAG 查询
兼容 Neo4j 版本的 API 接口，可无缝切换
"""
import pickle
import re
from collections import defaultdict
from typing import List, Dict, Any, Optional, Set, Tuple
from pathlib import Path

import networkx as nx

from backend.config import DATA_DIR
from backend.models.kg_schema import (
    NodeLabel, RelationType,
    build_job_nodes, build_skill_nodes, build_relations
)

GRAPH_PATH = DATA_DIR / "kg_graph.pkl"


class KGService:
    """NetworkX 知识图谱服务"""

    def __init__(self, graph_path: Path = GRAPH_PATH):
        self.graph_path = graph_path
        self.graph: nx.DiGraph = nx.DiGraph()
        self._is_loaded = False
        # 节点ID计数器（用于生成唯一节点ID）
        self._node_counters: Dict[str, int] = defaultdict(int)

    # ---------- 连接/加载 ----------

    def connect(self) -> "KGService":
        """连接/加载知识图谱"""
        if self.graph_path.exists():
            try:
                self.load()
                print(f"[KGService] 知识图谱已加载: {self.graph.number_of_nodes()} 节点, {self.graph.number_of_edges()} 边")
            except Exception as e:
                print(f"[KGService] 加载图谱失败: {e}")
        return self

    def close(self):
        """关闭服务（保存图谱）"""
        if len(self.graph) > 0:
            self.save()

    @property
    def is_connected(self) -> bool:
        return len(self.graph) > 0

    # ---------- 节点操作 ----------

    def _get_node_id(self, label: str, key_value: Any) -> str:
        """生成唯一节点ID: label::key_value"""
        return f"{label}::{key_value}"

    def add_node(self, label: str, properties: Dict[str, Any]) -> str:
        """添加节点，返回节点ID"""
        # 确定唯一键
        if "id" in properties:
            key_value = properties["id"]
        elif "name" in properties:
            key_value = properties["name"]
        else:
            self._node_counters[label] += 1
            key_value = self._node_counters[label]
        
        node_id = self._get_node_id(label, key_value)
        self.graph.add_node(node_id, label=label, **properties)
        return node_id

    def get_nodes_by_label(self, label: str) -> List[Dict[str, Any]]:
        """获取指定标签的所有节点"""
        result = []
        for node_id, attrs in self.graph.nodes(data=True):
            if attrs.get("label") == label:
                data = dict(attrs)
                data.pop("label", None)
                data["_node_id"] = node_id
                result.append(data)
        return result

    # ---------- 关系操作 ----------

    def add_edge(self, from_id: str, to_id: str, rel_type: str, **properties):
        """添加关系边"""
        if from_id in self.graph and to_id in self.graph:
            self.graph.add_edge(from_id, to_id, type=rel_type, **properties)

    def get_edges_by_type(self, rel_type: str) -> List[Tuple[str, str, Dict]]:
        """获取指定类型的所有边"""
        result = []
        for u, v, attrs in self.graph.edges(data=True):
            if attrs.get("type") == rel_type:
                result.append((u, v, dict(attrs)))
        return result

    # ---------- 批量导入 ----------

    def batch_import_nodes(self, nodes: List[Dict[str, Any]], batch_size: int = 500):
        """批量导入节点"""
        for node in nodes:
            self.add_node(node["label"], node["properties"])

    def batch_import_relations(self, relations: List[Dict[str, Any]], batch_size: int = 500):
        """批量导入关系"""
        for rel in relations:
            from_id = self._get_node_id(rel["from_label"], rel["from_value"])
            to_id = self._get_node_id(rel["to_label"], rel["to_value"])
            self.add_edge(from_id, to_id, rel["type"])

    # ---------- 初始化/清空 ----------

    def init_schema(self):
        """Schema 初始化（NetworkX 中无实际约束，仅打印信息）"""
        print("[KGService] Schema 初始化完成 (NetworkX 无显式约束)")

    def clear_all(self):
        """清空图谱"""
        self.graph.clear()
        self._node_counters.clear()
        print("[KGService] 知识图谱已清空")

    # ---------- 核心：从岗位数据构建图谱 ----------

    def build_from_jobs_data(self, jobs_data: List[Dict], job_profiles: Dict = None):
        """从岗位数据构建完整知识图谱"""
        print(f"[KGService] 开始构建知识图谱，岗位数: {len(jobs_data)}")
        self.clear_all()

        # 1. 导入 Job 节点
        job_nodes = build_job_nodes(jobs_data)
        self.batch_import_nodes(job_nodes)
        print(f"[KGService] 已导入 {len(job_nodes)} 个 Job 节点")

        # 2. 导入 Skill 节点
        skill_nodes = build_skill_nodes(jobs_data)
        self.batch_import_nodes(skill_nodes)
        print(f"[KGService] 已导入 {len(skill_nodes)} 个 Skill 节点")

        # 3. 导入 Industry/Location/Company 节点
        industries = list(set(j.get("industry", "") for j in jobs_data if j.get("industry")))
        locations = list(set(j.get("location", "") for j in jobs_data if j.get("location")))
        companies = list(set(j.get("company", "") for j in jobs_data if j.get("company")))

        for name in industries:
            self.add_node(NodeLabel.INDUSTRY.value, {"name": name})
        for name in locations:
            self.add_node(NodeLabel.LOCATION.value, {"name": name})
        for name in companies:
            self.add_node(NodeLabel.COMPANY.value, {"name": name})

        print(f"[KGService] 已导入 {len(industries)} 个 Industry, {len(locations)} 个 Location, {len(companies)} 个 Company")

        # 4. 导入基础关系
        relations = build_relations(jobs_data)
        self.batch_import_relations(relations)
        print(f"[KGService] 已导入 {len(relations)} 个基础关系")

        # 5. 导入十维画像关联
        if job_profiles:
            self._import_dimensions(jobs_data, job_profiles)

        # 6. 基于数据推导额外关系（SIMILAR_TO, PROMOTES_TO, TRANSITIONS_TO）
        self._derive_similarity_relations(jobs_data)
        self._derive_promotion_relations(jobs_data)

        print(f"[KGService] 知识图谱构建完成: {self.graph.number_of_nodes()} 节点, {self.graph.number_of_edges()} 边")

    def _import_dimensions(self, jobs_data: List[Dict], job_profiles: Dict):
        """导入岗位十维画像"""
        dimensions = [
            "获奖情况", "专业技能", "学历证书", "学习成绩",
            "实习经历", "创新能力", "沟通协作", "责任心",
            "抗压能力", "解决问题能力"
        ]
        for dim_name in dimensions:
            self.add_node(NodeLabel.DIMENSION.value, {"name": dim_name})

        for job in jobs_data:
            job_id = job.get("id")
            profile = job_profiles.get(str(job_id), {})
            from_id = self._get_node_id(NodeLabel.JOB.value, job_id)
            for dim_name, score in profile.items():
                to_id = self._get_node_id(NodeLabel.DIMENSION.value, dim_name)
                self.add_edge(from_id, to_id, RelationType.HAS_DIMENSION.value, score=float(score))

    def _derive_similarity_relations(self, jobs_data: List[Dict]):
        """基于技能重叠度推导 SIMILAR_TO 关系"""
        # 为每个岗位构建技能集合
        job_skills: Dict[int, Set[str]] = {}
        for job in jobs_data:
            job_skills[job["id"]] = set(job.get("skills", []))

        # 计算技能 Jaccard 相似度，阈值 0.3
        job_ids = list(job_skills.keys())
        similar_count = 0
        for i in range(len(job_ids)):
            for j in range(i + 1, len(job_ids)):
                id1, id2 = job_ids[i], job_ids[j]
                skills1, skills2 = job_skills[id1], job_skills[id2]
                if not skills1 or not skills2:
                    continue
                intersection = len(skills1 & skills2)
                union = len(skills1 | skills2)
                if union > 0 and intersection / union >= 0.3:
                    from_id = self._get_node_id(NodeLabel.JOB.value, id1)
                    to_id = self._get_node_id(NodeLabel.JOB.value, id2)
                    self.add_edge(from_id, to_id, RelationType.SIMILAR_TO.value, similarity=round(intersection / union, 3))
                    similar_count += 1

        print(f"[KGService] 已推导 {similar_count} 个 SIMILAR_TO 关系")

    def _derive_promotion_relations(self, jobs_data: List[Dict]):
        """基于岗位名称层级推导 PROMOTES_TO 关系"""
        # 简单的规则：初级 -> 中级 -> 高级 -> 资深/专家
        level_keywords = {
            "初级": 1, "实习": 0, "助理": 1,
            "中级": 2, "": 2,
            "高级": 3, "资深": 4, "专家": 4, "架构师": 4,
            "主管": 3, "经理": 4, "总监": 5, "负责人": 4,
        }

        def get_level(name: str) -> int:
            for kw, lv in sorted(level_keywords.items(), key=lambda x: -len(x[0])):
                if kw in name:
                    return lv
            return 2

        # 按岗位名称分组，同名称不同级别之间建立晋升路径
        job_name_map: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
        for job in jobs_data:
            # 去除级别关键词得到基础名称
            base_name = name = job.get("name", "")
            for kw in level_keywords:
                base_name = base_name.replace(kw, "")
            base_name = base_name.strip()
            if base_name:
                job_name_map[base_name].append((job["id"], get_level(name)))

        promo_count = 0
        for base_name, jobs in job_name_map.items():
            if len(jobs) < 2:
                continue
            jobs_sorted = sorted(jobs, key=lambda x: x[1])
            for i in range(len(jobs_sorted) - 1):
                if jobs_sorted[i][1] < jobs_sorted[i + 1][1]:
                    from_id = self._get_node_id(NodeLabel.JOB.value, jobs_sorted[i][0])
                    to_id = self._get_node_id(NodeLabel.JOB.value, jobs_sorted[i + 1][0])
                    self.add_edge(from_id, to_id, RelationType.PROMOTES_TO.value)
                    promo_count += 1

        print(f"[KGService] 已推导 {promo_count} 个 PROMOTES_TO 关系")

    # ---------- GraphRAG 查询 ----------

    def query_graph_rag(self, query_type: str, **kwargs) -> List[Dict]:
        """
        GraphRAG 查询接口
        将 Cypher 查询转换为 NetworkX 图遍历
        """
        queries = {
            "jobs_by_skills": self._find_jobs_by_skills,
            "similar_jobs": self._find_similar_jobs,
            "promotion_path": self._find_promotion_path,
            "transition_options": self._find_transition_options,
            "job_network": self._get_job_network,
            "skill_gap": self._get_skill_gap,
            "multi_hop": self._multi_hop_reasoning,
        }

        if query_type not in queries:
            raise ValueError(f"未知查询类型: {query_type}")

        return queries[query_type](**kwargs)

    def _find_jobs_by_skills(self, skills: List[str], limit: int = 10) -> List[Dict]:
        """根据技能查找岗位"""
        job_scores: Dict[str, int] = defaultdict(int)
        for skill_name in skills:
            skill_id = self._get_node_id(NodeLabel.SKILL.value, skill_name)
            if skill_id in self.graph:
                for pred_id in self.graph.predecessors(skill_id):
                    edge_data = self.graph.get_edge_data(pred_id, skill_id)
                    if edge_data and edge_data.get("type") == RelationType.REQUIRES_SKILL.value:
                        job_scores[pred_id] += 1

        sorted_jobs = sorted(job_scores.items(), key=lambda x: x[1], reverse=True)[:limit]
        return [self._node_to_dict(node_id, match_count=score) for node_id, score in sorted_jobs]

    def _find_similar_jobs(self, job_name: str, limit: int = 5) -> List[Dict]:
        """查找相似岗位"""
        # 先找到 Job 节点
        job_id = None
        for node_id, attrs in self.graph.nodes(data=True):
            if attrs.get("label") == NodeLabel.JOB.value and attrs.get("name") == job_name:
                job_id = node_id
                break
        if not job_id:
            return []

        results = []
        for succ_id in self.graph.successors(job_id):
            edge_data = self.graph.get_edge_data(job_id, succ_id)
            if edge_data and edge_data.get("type") == RelationType.SIMILAR_TO.value:
                results.append(self._node_to_dict(succ_id))
        return results[:limit]

    def _find_promotion_path(self, job_name: str, max_depth: int = 3, limit: int = 5) -> List[Dict]:
        """查找晋升路径"""
        start_id = None
        for node_id, attrs in self.graph.nodes(data=True):
            if attrs.get("label") == NodeLabel.JOB.value and attrs.get("name") == job_name:
                start_id = node_id
                break
        if not start_id:
            return []

        # DFS 找最长路径
        paths = []
        stack = [(start_id, [start_id])]
        while stack:
            current, path = stack.pop()
            if len(path) > max_depth + 1:
                continue
            has_promo = False
            for succ_id in self.graph.successors(current):
                edge_data = self.graph.get_edge_data(current, succ_id)
                if edge_data and edge_data.get("type") == RelationType.PROMOTES_TO.value:
                    has_promo = True
                    new_path = path + [succ_id]
                    if len(new_path) > 1:
                        paths.append(new_path)
                    stack.append((succ_id, new_path))
            if not has_promo and len(path) > 1:
                paths.append(path)

        # 去重，取最长路径
        unique_paths = []
        seen = set()
        for p in sorted(paths, key=len, reverse=True):
            key = tuple(p)
            if key not in seen:
                seen.add(key)
                unique_paths.append(p)

        return [{
            "path": [self._node_to_dict(nid) for nid in path],
            "length": len(path) - 1,
        } for path in unique_paths[:limit]]

    def _find_transition_options(self, job_name: str, limit: int = 5) -> List[Dict]:
        """查找转岗方向（基于技能相似度高的岗位）"""
        # 找到目标岗位
        job_id = None
        for node_id, attrs in self.graph.nodes(data=True):
            if attrs.get("label") == NodeLabel.JOB.value and attrs.get("name") == job_name:
                job_id = node_id
                break
        if not job_id:
            return []

        # 获取目标岗位的技能
        job_skills = set()
        for succ_id in self.graph.successors(job_id):
            edge_data = self.graph.get_edge_data(job_id, succ_id)
            if edge_data and edge_data.get("type") == RelationType.REQUIRES_SKILL.value:
                job_skills.add(succ_id)

        # 找其他岗位，计算技能重叠
        scores = []
        for node_id, attrs in self.graph.nodes(data=True):
            if attrs.get("label") != NodeLabel.JOB.value or node_id == job_id:
                continue
            other_skills = set()
            for succ_id in self.graph.successors(node_id):
                edge_data = self.graph.get_edge_data(node_id, succ_id)
                if edge_data and edge_data.get("type") == RelationType.REQUIRES_SKILL.value:
                    other_skills.add(succ_id)
            if job_skills and other_skills:
                overlap = len(job_skills & other_skills) / len(job_skills)
                if overlap >= 0.3:
                    scores.append((node_id, overlap))

        scores.sort(key=lambda x: x[1], reverse=True)
        return [self._node_to_dict(node_id, transition_score=round(score, 3)) for node_id, score in scores[:limit]]

    def _get_job_network(self, job_name: str, depth: int = 2) -> List[Dict]:
        """获取岗位关联网络"""
        job_id = None
        for node_id, attrs in self.graph.nodes(data=True):
            if attrs.get("label") == NodeLabel.JOB.value and attrs.get("name") == job_name:
                job_id = node_id
                break
        if not job_id:
            return []

        # BFS 收集 depth 范围内的所有节点
        visited = {job_id: 0}
        queue = [job_id]
        while queue:
            current = queue.pop(0)
            if visited[current] >= depth:
                continue
            for neighbor in list(self.graph.successors(current)) + list(self.graph.predecessors(current)):
                if neighbor not in visited:
                    visited[neighbor] = visited[current] + 1
                    queue.append(neighbor)

        # 分类统计
        skills = []
        similar_jobs = []
        promo_targets = []
        trans_targets = []
        industries = []

        for node_id, dist in visited.items():
            if node_id == job_id:
                continue
            attrs = self.graph.nodes[node_id]
            label = attrs.get("label")
            if label == NodeLabel.SKILL.value:
                skills.append(self._node_to_dict(node_id))
            elif label == NodeLabel.JOB.value:
                # 判断关系类型
                if self.graph.has_edge(job_id, node_id):
                    edge_type = self.graph.get_edge_data(job_id, node_id, {}).get("type")
                    if edge_type == RelationType.SIMILAR_TO.value:
                        similar_jobs.append(self._node_to_dict(node_id))
                    elif edge_type == RelationType.PROMOTES_TO.value:
                        promo_targets.append(self._node_to_dict(node_id))
                    elif edge_type == RelationType.TRANSITIONS_TO.value:
                        trans_targets.append(self._node_to_dict(node_id))
                elif self.graph.has_edge(node_id, job_id):
                    edge_type = self.graph.get_edge_data(node_id, job_id, {}).get("type")
                    if edge_type == RelationType.SIMILAR_TO.value:
                        similar_jobs.append(self._node_to_dict(node_id))
            elif label == NodeLabel.INDUSTRY.value:
                industries.append(self._node_to_dict(node_id))

        return [{
            "job": self._node_to_dict(job_id),
            "skills": skills,
            "similar_jobs": similar_jobs,
            "promotion_targets": promo_targets,
            "transition_targets": trans_targets,
            "industries": industries,
        }]

    def _get_skill_gap(self, current_skills: List[str], target_job: str) -> List[Dict]:
        """计算技能差距"""
        # 找到目标岗位
        job_id = None
        for node_id, attrs in self.graph.nodes(data=True):
            if attrs.get("label") == NodeLabel.JOB.value and attrs.get("name") == target_job:
                job_id = node_id
                break
        if not job_id:
            return []

        # 获取目标岗位所需技能
        required_skills = set()
        for succ_id in self.graph.successors(job_id):
            edge_data = self.graph.get_edge_data(job_id, succ_id)
            if edge_data and edge_data.get("type") == RelationType.REQUIRES_SKILL.value:
                skill_name = self.graph.nodes[succ_id].get("name", "")
                required_skills.add(skill_name)

        gap = required_skills - set(current_skills)
        return [{"gap_skill": s} for s in sorted(gap)]

    def _multi_hop_reasoning(self, start_skill: str, end_job: str, max_hops: int = 4) -> List[Dict]:
        """多跳推理：从技能到岗位"""
        start_id = self._get_node_id(NodeLabel.SKILL.value, start_skill)
        
        # 找到 end_job 节点
        end_id = None
        for node_id, attrs in self.graph.nodes(data=True):
            if attrs.get("label") == NodeLabel.JOB.value and attrs.get("name") == end_job:
                end_id = node_id
                break
        
        if not start_id or start_id not in self.graph or not end_id:
            return []

        # BFS 找路径
        paths = []
        queue = [(start_id, [start_id])]
        visited_paths = set()
        while queue:
            current, path = queue.pop(0)
            if len(path) > max_hops + 1:
                continue
            if current == end_id and len(path) > 1:
                path_tuple = tuple(path)
                if path_tuple not in visited_paths:
                    visited_paths.add(path_tuple)
                    paths.append(path)
                continue
            for neighbor in list(self.graph.successors(current)) + list(self.graph.predecessors(current)):
                if neighbor not in path:
                    queue.append((neighbor, path + [neighbor]))

        return [{
            "path": [self._node_to_dict(nid) for nid in path],
            "length": len(path) - 1,
        } for path in paths[:5]]

    # ---------- 工具方法 ----------

    def _node_to_dict(self, node_id: str, **extra) -> Dict[str, Any]:
        """将节点转换为字典"""
        attrs = dict(self.graph.nodes[node_id])
        attrs.pop("label", None)
        result = {"_node_id": node_id, **attrs}
        result.update(extra)
        return result

    def get_stats(self) -> Dict[str, int]:
        """获取知识图谱统计信息"""
        stats = defaultdict(int)
        for _, attrs in self.graph.nodes(data=True):
            label = attrs.get("label", "Unknown")
            stats[label] += 1
        stats["Relations"] = self.graph.number_of_edges()
        return dict(stats)

    # ---------- 保存/加载 ----------

    def save(self, path: Path = None):
        """保存图谱到文件"""
        if path is None:
            path = self.graph_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({
                "graph": self.graph,
                "node_counters": dict(self._node_counters),
            }, f)
        print(f"[KGService] 知识图谱已保存: {path}")

    def load(self, path: Path = None) -> "KGService":
        """从文件加载图谱"""
        if path is None:
            path = self.graph_path
        if not path.exists():
            raise FileNotFoundError(f"图谱文件不存在: {path}")
        with open(path, "rb") as f:
            data = pickle.load(f)
        self.graph = data["graph"]
        self._node_counters = defaultdict(int, data.get("node_counters", {}))
        self._is_loaded = True
        return self


# ========== 全局单例 ==========
_kg_service: Optional[KGService] = None


def get_kg_service() -> KGService:
    """获取知识图谱服务单例"""
    global _kg_service
    if _kg_service is None:
        _kg_service = KGService().connect()
    return _kg_service
