"""
Agentic RAG + GraphRAG 增强生成服务
以 KG4Career 知识图谱 + 岗位数据集为双源知识库
"""
import json
from typing import List, Dict, Any, Optional

from backend.services.retrieval_service import HybridRetrievalService, get_retrieval_service
from backend.services.kg_service import KGService, get_kg_service
from backend.config import RAG_MAX_RETRIEVAL_STEPS, RAG_CONTEXT_MAX_TOKENS, RAG_SIMILARITY_THRESHOLD


class RAGContext:
    """RAG 上下文块"""
    def __init__(self):
        self.retrieved_jobs: List[Dict] = []      # FAISS 检索到的岗位
        self.kg_paths: List[Dict] = []            # GraphRAG 查询结果
        self.user_profile: Dict = {}              # 用户画像
        self.sources: List[str] = []              # 信息来源追踪

    def to_prompt_context(self) -> str:
        """将上下文组装为 Prompt 文本（限制长度避免AI输出截断）"""
        sections = []
        
        # 只保留前3个最相关的岗位，避免Prompt过长
        jobs = self.retrieved_jobs[:3] if self.retrieved_jobs else []
        if jobs:
            sections.append("【检索到的真实岗位数据】")
            for i, job in enumerate(jobs, 1):
                desc = job.get('description', '')[:60].replace('"', '').replace("'", "")
                skills = ', '.join(job.get('skills', [])[:5]).replace('"', '')
                sections.append(
                    f"{i}. {job['name']} ({job['company']}) - "
                    f"地点:{job['location']} 薪资:{job['salary']} "
                    f"技能:{skills}"
                )
        
        # 知识图谱路径只保留最简信息
        if self.kg_paths:
            sections.append("\n【知识图谱关联】")
            for path in self.kg_paths[:2]:
                if isinstance(path, dict):
                    # 只提取名称信息，避免JSON嵌套
                    simple = {k: v for k, v in path.items() if k in ['name', 'gap_skill']}
                    sections.append(str(simple))
        
        text = "\n".join(sections)
        # 硬截断到800字符以内
        if len(text) > 800:
            text = text[:800] + "\n...(检索上下文截断)"
        return text

    def estimate_tokens(self) -> int:
        """估算上下文 token 数（粗略估计：1汉字 ≈ 1.5 tokens）"""
        text = self.to_prompt_context()
        return int(len(text) * 1.5)


class AgenticRAGService:
    """
    Agentic RAG 服务
    
    ReAct 风格 Agent 循环：
    - Thought: 分析用户需求，确定检索策略
    - Action: 执行检索（FAISS / GraphRAG / 画像匹配）
    - Observation: 整合检索结果
    """

    def __init__(
        self,
        retrieval_service: Optional[HybridRetrievalService] = None,
        kg_service: Optional[KGService] = None,
    ):
        self.retrieval = retrieval_service or get_retrieval_service()
        self.kg = kg_service or get_kg_service()

    def plan_retrieval_strategy(self, query_type: str, user_info: Dict) -> List[str]:
        """
        规划检索策略
        
        Args:
            query_type: 'resume_analysis' | 'career_report' | 'transition_advice'
            user_info: 用户信息
        
        Returns:
            检索动作列表
        """
        strategies = {
            "resume_analysis": ["faiss_skills", "faiss_resume", "kg_skill_gap"],
            "career_report": ["faiss_target_job", "kg_promotion_path", "kg_similar_jobs"],
            "transition_advice": ["faiss_skills", "kg_transition_options", "kg_skill_gap"],
        }
        return strategies.get(query_type, ["faiss_skills"])

    def _ensure_services_ready(self):
        """确保检索和图谱服务已就绪"""
        # 懒加载检索索引
        if not self.retrieval.is_ready():
            try:
                from backend.utils.data_loader import load_jobs_data
                self.retrieval.lsh.load()
                self.retrieval.faiss.load()
                self.retrieval.cache_jobs(load_jobs_data())
                print("[AgenticRAG] 检索服务懒加载成功")
            except Exception as e:
                print(f"[AgenticRAG] 检索服务加载失败: {e}")
        
        # 懒加载知识图谱
        if not self.kg.is_connected:
            try:
                self.kg.load()
                print("[AgenticRAG] 知识图谱懒加载成功")
            except Exception as e:
                print(f"[AgenticRAG] 知识图谱加载失败: {e}")

    def retrieve(
        self,
        query_type: str,
        user_info: Dict,
        analysis_result: Dict = None,
        max_steps: int = RAG_MAX_RETRIEVAL_STEPS,
    ) -> RAGContext:
        """
        执行 Agentic RAG 检索
        
        Args:
            query_type: 查询类型
            user_info: 用户信息
            analysis_result: 分析结果（可选，用于增强上下文）
            max_steps: 最大检索步数
        
        Returns:
            RAG 上下文
        """
        context = RAGContext()
        context.user_profile = user_info
        
        # 确保服务就绪
        self._ensure_services_ready()
        
        # Step 1: 规划检索策略
        strategy = self.plan_retrieval_strategy(query_type, user_info)
        print(f"[AgenticRAG] 检索策略: {strategy}")
        
        # Step 2: 执行检索动作
        for step, action in enumerate(strategy[:max_steps]):
            print(f"[AgenticRAG] Step {step + 1}: {action}")
            
            if action == "faiss_skills":
                skills = user_info.get("skills", [])
                if skills:
                    results = self.retrieval.search_by_skills(skills, top_k=5)
                    context.retrieved_jobs.extend(results)
                    context.sources.append(f"FAISS技能检索: {', '.join(skills)}")
            
            elif action == "faiss_resume":
                resume_text = self._build_resume_text(user_info)
                if resume_text:
                    profile = analysis_result.get("abilityProfile", {}).get("tenDimensions", {}) if analysis_result else None
                    profile_vec = list(profile.values()) if profile else None
                    results = self.retrieval.search_by_resume(resume_text, profile_vec, top_k=5)
                    context.retrieved_jobs.extend(results)
                    context.sources.append("FAISS简历全文检索")
            
            elif action == "faiss_target_job":
                target = analysis_result.get("jobMatches", [{}])[0].get("name", "") if analysis_result else ""
                if target:
                    results = self.retrieval.search_by_job_name(target, top_k=5)
                    context.retrieved_jobs.extend(results)
                    context.sources.append(f"FAISS目标岗位检索: {target}")
            
            elif action == "kg_promotion_path":
                target = analysis_result.get("jobMatches", [{}])[0].get("name", "") if analysis_result else ""
                if target and self.kg.is_connected:
                    paths = self.kg.query_graph_rag("promotion_path", job_name=target, max_depth=3)
                    context.kg_paths.extend(paths)
                    context.sources.append(f"GraphRAG晋升路径: {target}")
            
            elif action == "kg_transition_options":
                target = analysis_result.get("jobMatches", [{}])[0].get("name", "") if analysis_result else ""
                if target and self.kg.is_connected:
                    options = self.kg.query_graph_rag("transition_options", job_name=target, limit=5)
                    context.kg_paths.extend(options)
                    context.sources.append(f"GraphRAG转岗方向: {target}")
            
            elif action == "kg_skill_gap":
                skills = user_info.get("skills", [])
                target = analysis_result.get("jobMatches", [{}])[0].get("name", "") if analysis_result else ""
                if target and skills and self.kg.is_connected:
                    gaps = self.kg.query_graph_rag("skill_gap", current_skills=skills, target_job=target)
                    context.kg_paths.extend(gaps)
                    context.sources.append(f"GraphRAG技能差距: {target}")
            
            # 检查上下文大小，避免超出限制
            if context.estimate_tokens() > RAG_CONTEXT_MAX_TOKENS:
                print(f"[AgenticRAG] 上下文已接近上限，提前结束检索")
                break
        
        # 去重
        seen_ids = set()
        unique_jobs = []
        for job in context.retrieved_jobs:
            if job["id"] not in seen_ids:
                seen_ids.add(job["id"])
                unique_jobs.append(job)
        context.retrieved_jobs = unique_jobs[:10]  # 最多保留10条
        
        return context

    def build_augmented_prompt(
        self,
        base_prompt: str,
        context: RAGContext,
        require_citation: bool = True,
    ) -> str:
        """
        构建增强 Prompt
        
        Args:
            base_prompt: 原始 Prompt
            context: RAG 上下文
            require_citation: 是否要求标注引用来源
        
        Returns:
            增强后的 Prompt
        """
        context_text = context.to_prompt_context()
        
        citation_instruction = """
【引用要求】
请在输出中使用 [来源: 类型-名称] 格式标注信息来源，例如：
- [来源: 岗位数据集-Java开发工程师]
- [来源: 知识图谱-晋升路径]
确保每一条具体信息都可以追溯到上述上下文中的真实数据。
""" if require_citation else ""
        
        augmented = f"""【系统指令】
你是一个专业的职业规划顾问。请严格基于以下【检索到的真实数据】回答用户问题。
不要编造任何不存在的岗位名称、公司、薪资或技能。如果上下文信息不足，请明确说明。

{context_text}

{citation_instruction}

---
【用户请求】
{base_prompt}
"""
        return augmented

    @staticmethod
    def _build_resume_text(user_info: Dict) -> str:
        """从用户信息构建简历文本"""
        parts = [
            f"姓名: {user_info.get('name', '')}",
            f"学校: {user_info.get('school', '')}",
            f"专业: {user_info.get('major', '')}",
            f"学历: {user_info.get('degree', '')}",
            f"技能: {', '.join(user_info.get('skills', []))}",
        ]
        return "\n".join(parts)


# ========== 全局单例 ==========
_rag_service: Optional[AgenticRAGService] = None


def get_rag_service() -> AgenticRAGService:
    """获取 RAG 服务单例"""
    global _rag_service
    if _rag_service is None:
        _rag_service = AgenticRAGService()
    return _rag_service
