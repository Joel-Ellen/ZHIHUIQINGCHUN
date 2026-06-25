"""
KG4Career 知识图谱 Schema 定义
Neo4j 图模型：节点类型、关系类型、Cypher 查询模板
"""
from enum import Enum
from typing import Dict, List, Any


# ========== 节点标签 ==========
class NodeLabel(str, Enum):
    JOB = "Job"
    SKILL = "Skill"
    INDUSTRY = "Industry"
    LOCATION = "Location"
    COMPANY = "Company"
    EDUCATION_LEVEL = "EducationLevel"
    EXPERIENCE_LEVEL = "ExperienceLevel"
    CAREER_PATH = "CareerPath"
    DIMENSION = "Dimension"
    STUDENT = "Student"


# ========== 关系类型 ==========
class RelationType(str, Enum):
    REQUIRES_SKILL = "REQUIRES_SKILL"
    BELONGS_TO = "BELONGS_TO"
    LOCATED_IN = "LOCATED_IN"
    OFFERED_BY = "OFFERED_BY"
    REQUIRES_EDUCATION = "REQUIRES_EDUCATION"
    REQUIRES_EXPERIENCE = "REQUIRES_EXPERIENCE"
    SIMILAR_TO = "SIMILAR_TO"
    PROMOTES_TO = "PROMOTES_TO"
    TRANSITIONS_TO = "TRANSITIONS_TO"
    HAS_DIMENSION = "HAS_DIMENSION"
    HAS_SKILL = "HAS_SKILL"           # Student -> Skill
    STUDIED_AT = "STUDIED_AT"         # Student -> School (预留)


# ========== 节点属性定义 ==========
NODE_PROPERTIES = {
    NodeLabel.JOB: {
        "id": "integer",
        "name": "string",
        "salary": "string",
        "description": "string",
        "requirement": "string",
    },
    NodeLabel.SKILL: {
        "name": "string",
    },
    NodeLabel.INDUSTRY: {
        "name": "string",
    },
    NodeLabel.LOCATION: {
        "name": "string",
    },
    NodeLabel.COMPANY: {
        "name": "string",
        "scale": "string",
    },
    NodeLabel.EDUCATION_LEVEL: {
        "level": "string",
    },
    NodeLabel.EXPERIENCE_LEVEL: {
        "level": "string",
    },
    NodeLabel.DIMENSION: {
        "name": "string",
    },
    NodeLabel.STUDENT: {
        "id": "string",
        "name": "string",
        "school": "string",
        "major": "string",
    },
}


# ========== 约束语句 ==========
CONSTRAINTS = [
    "CREATE CONSTRAINT job_id IF NOT EXISTS FOR (j:Job) REQUIRE j.id IS UNIQUE",
    "CREATE CONSTRAINT skill_name IF NOT EXISTS FOR (s:Skill) REQUIRE s.name IS UNIQUE",
    "CREATE CONSTRAINT industry_name IF NOT EXISTS FOR (i:Industry) REQUIRE i.name IS UNIQUE",
    "CREATE CONSTRAINT location_name IF NOT EXISTS FOR (l:Location) REQUIRE l.name IS UNIQUE",
    "CREATE CONSTRAINT company_name IF NOT EXISTS FOR (c:Company) REQUIRE c.name IS UNIQUE",
    "CREATE CONSTRAINT dimension_name IF NOT EXISTS FOR (d:Dimension) REQUIRE d.name IS UNIQUE",
]

# ========== 索引语句 ==========
INDEXES = [
    "CREATE INDEX job_name_idx IF NOT EXISTS FOR (j:Job) ON (j.name)",
    "CREATE INDEX skill_name_idx IF NOT EXISTS FOR (s:Skill) ON (s.name)",
]


# ========== GraphRAG 查询模板 ==========
class GraphRAGQueries:
    """预定义的 GraphRAG Cypher 查询模板"""

    @staticmethod
    def find_jobs_by_skills(skills: List[str], limit: int = 10) -> str:
        """根据技能查找岗位"""
        return f"""
        MATCH (j:Job)-[:REQUIRES_SKILL]->(s:Skill)
        WHERE s.name IN {skills}
        RETURN j, count(s) AS match_count
        ORDER BY match_count DESC
        LIMIT {limit}
        """

    @staticmethod
    def find_similar_jobs(job_name: str, limit: int = 5) -> str:
        """查找相似岗位"""
        return f"""
        MATCH (j1:Job {{name: '{job_name}'}})-[:SIMILAR_TO]->(j2:Job)
        RETURN j2
        LIMIT {limit}
        """

    @staticmethod
    def find_promotion_path(job_name: str, max_depth: int = 3) -> str:
        """查找晋升路径"""
        return f"""
        MATCH path = (j1:Job {{name: '{job_name}'}})-[:PROMOTES_TO*1..{max_depth}]->(j2:Job)
        RETURN path
        """

    @staticmethod
    def find_transition_options(job_name: str, limit: int = 5) -> str:
        """查找转岗方向"""
        return f"""
        MATCH (j1:Job {{name: '{job_name}'}})-[:TRANSITIONS_TO]->(j2:Job)
        RETURN j2
        LIMIT {limit}
        """

    @staticmethod
    def get_job_network(job_name: str, depth: int = 2) -> str:
        """获取岗位关联网络（技能+相似+晋升+转岗）"""
        return f"""
        MATCH (j:Job {{name: '{job_name}'}})
        OPTIONAL MATCH (j)-[:REQUIRES_SKILL]->(s:Skill)
        OPTIONAL MATCH (j)-[:SIMILAR_TO]->(sim:Job)
        OPTIONAL MATCH (j)-[:PROMOTES_TO]->(promo:Job)
        OPTIONAL MATCH (j)-[:TRANSITIONS_TO]->(trans:Job)
        OPTIONAL MATCH (j)-[:BELONGS_TO]->(ind:Industry)
        RETURN j, collect(DISTINCT s) AS skills,
               collect(DISTINCT sim) AS similar_jobs,
               collect(DISTINCT promo) AS promotion_targets,
               collect(DISTINCT trans) AS transition_targets,
               collect(DISTINCT ind) AS industries
        """

    @staticmethod
    def find_jobs_by_industry_location(industry: str, location: str, limit: int = 10) -> str:
        """按行业和地点筛选岗位"""
        return f"""
        MATCH (j:Job)-[:BELONGS_TO]->(i:Industry {{name: '{industry}'}})
        MATCH (j)-[:LOCATED_IN]->(l:Location {{name: '{location}'}})
        RETURN j
        LIMIT {limit}
        """

    @staticmethod
    def get_skill_gap(current_skills: List[str], target_job: str) -> str:
        """计算技能差距：目标岗位所需技能 - 当前技能"""
        return f"""
        MATCH (j:Job {{name: '{target_job}'}})-[:REQUIRES_SKILL]->(s:Skill)
        WHERE NOT s.name IN {current_skills}
        RETURN s.name AS gap_skill
        """

    @staticmethod
    def multi_hop_reasoning(start_skill: str, end_job: str, max_hops: int = 4) -> str:
        """多跳推理：从技能到岗位的关联路径"""
        return f"""
        MATCH path = (s:Skill {{name: '{start_skill}'}})<-[:REQUIRES_SKILL]-(j:Job)-[:SIMILAR_TO|TRANSITIONS_TO|PROMOTES_TO*1..{max_hops}]-(target:Job {{name: '{end_job}'}})
        RETURN path
        LIMIT 5
        """


# ========== 知识图谱构建辅助函数 ==========
def build_job_nodes(jobs_data: List[Dict]) -> List[Dict[str, Any]]:
    """从岗位数据构建 Job 节点"""
    nodes = []
    for job in jobs_data:
        nodes.append({
            "label": NodeLabel.JOB.value,
            "properties": {
                "id": job.get("id"),
                "name": job.get("name", ""),
                "salary": job.get("salary", ""),
                "description": job.get("description", ""),
                "requirement": job.get("requirement", ""),
            }
        })
    return nodes


def build_skill_nodes(jobs_data: List[Dict]) -> List[Dict[str, Any]]:
    """从岗位数据提取 Skill 节点（去重）"""
    skills = set()
    for job in jobs_data:
        for skill in job.get("skills", []):
            skills.add(skill)
    return [{"label": NodeLabel.SKILL.value, "properties": {"name": s}} for s in sorted(skills)]


def build_relations(jobs_data: List[Dict]) -> List[Dict[str, Any]]:
    """从岗位数据构建关系"""
    relations = []
    for job in jobs_data:
        job_name = job.get("name", "")
        job_id = job.get("id")

        # Job -> REQUIRES_SKILL -> Skill
        for skill in job.get("skills", []):
            relations.append({
                "from_label": NodeLabel.JOB.value,
                "from_key": "id",
                "from_value": job_id,
                "to_label": NodeLabel.SKILL.value,
                "to_key": "name",
                "to_value": skill,
                "type": RelationType.REQUIRES_SKILL.value,
            })

        # Job -> BELONGS_TO -> Industry
        if job.get("industry"):
            relations.append({
                "from_label": NodeLabel.JOB.value,
                "from_key": "id",
                "from_value": job_id,
                "to_label": NodeLabel.INDUSTRY.value,
                "to_key": "name",
                "to_value": job["industry"],
                "type": RelationType.BELONGS_TO.value,
            })

        # Job -> LOCATED_IN -> Location
        if job.get("location"):
            relations.append({
                "from_label": NodeLabel.JOB.value,
                "from_key": "id",
                "from_value": job_id,
                "to_label": NodeLabel.LOCATION.value,
                "to_key": "name",
                "to_value": job["location"],
                "type": RelationType.LOCATED_IN.value,
            })

        # Job -> OFFERED_BY -> Company
        if job.get("company"):
            relations.append({
                "from_label": NodeLabel.JOB.value,
                "from_key": "id",
                "from_value": job_id,
                "to_label": NodeLabel.COMPANY.value,
                "to_key": "name",
                "to_value": job["company"],
                "type": RelationType.OFFERED_BY.value,
            })

    return relations
