from flask import Flask, request, jsonify, send_from_directory, abort
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import re
import json
import requests
from datetime import datetime
import uuid
import sys
import webbrowser
from threading import Timer

# 兼容 PyInstaller 打包后的资源路径
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
    # PyInstaller 6.x 将数据文件放在 _internal 子目录中
    internal_dir = os.path.join(BASE_DIR, '_internal')
    if os.path.exists(internal_dir) and os.path.exists(os.path.join(internal_dir, 'index.html')):
        BASE_DIR = internal_dir
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
CORS(app)

# UTF-8编码配置
app.config['JSON_AS_ASCII'] = False
app.config['JSON_SORT_KEYS'] = False

# 数据库配置
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(BASE_DIR, "zhihuiqingchun.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here'  # 请在生产环境中使用环境变量
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

db = SQLAlchemy(app)

# 确保上传文件夹存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 数据库模型
class User(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联
    files = db.relationship('UserFile', backref='user', lazy=True, cascade='all, delete-orphan')
    history_records = db.relationship('HistoryRecord', backref='user', lazy=True, cascade='all, delete-orphan')

class UserFile(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关联
    history_records = db.relationship('HistoryRecord', backref='file', lazy=True, cascade='all, delete-orphan')

class HistoryRecord(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    file_id = db.Column(db.String(36), db.ForeignKey('user_file.id'), nullable=True)
    record_type = db.Column(db.String(50), nullable=False)  # 'analysis', 'report', 'quiz'
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)  # JSON字符串存储详细内容
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# 加载岗位数据集
JOBS_DATA = []
JOB_PROFILES_DATA = {}

def load_job_datasets():
    """加载岗位数据集和岗位画像数据"""
    global JOBS_DATA, JOB_PROFILES_DATA
    try:
        with open(os.path.join(BASE_DIR, 'jobs_data.json'), 'r', encoding='utf-8') as f:
            JOBS_DATA = json.load(f)
        print(f"[Dataset] 加载岗位数据: {len(JOBS_DATA)} 条")
    except Exception as e:
        print(f"[Dataset] 加载 jobs_data.json 失败: {e}")
        JOBS_DATA = []
    
    try:
        with open(os.path.join(BASE_DIR, 'job_profiles.json'), 'r', encoding='utf-8') as f:
            JOB_PROFILES_DATA = json.load(f)
        print(f"[Dataset] 加载岗位画像: {len(JOB_PROFILES_DATA)} 条")
    except Exception as e:
        print(f"[Dataset] 加载 job_profiles.json 失败: {e}")
        JOB_PROFILES_DATA = {}

load_job_datasets()


def find_matching_jobs(query, user_skills=None, top_k=5):
    """
    从数据集中查找匹配的岗位
    优先使用 LSH + FAISS 混合检索（如果索引已构建），否则回退到规则匹配
    
    注：生产环境部署时，若 sentence-transformers 模型加载导致 worker 超时崩溃，
    可通过设置环境变量 ENABLE_HYBRID_RETRIEVAL=false 禁用混合检索。
    """
    if not JOBS_DATA:
        return []
    
    # 通过环境变量控制是否启用混合检索（默认禁用，避免服务器模型下载问题）
    enable_hybrid = os.environ.get('ENABLE_HYBRID_RETRIEVAL', 'false').lower() == 'true'
    
    if enable_hybrid:
        try:
            from backend.services.retrieval_service import get_retrieval_service
            from backend.utils.lsh_indexer import LSHIndexer
            from backend.utils.faiss_indexer import FAISSIndexer
            
            retrieval = get_retrieval_service()
            
            # 懒加载索引（仅在第一次调用时加载）
            if not retrieval.is_ready():
                try:
                    retrieval.lsh.load()
                    retrieval.faiss.load()
                    retrieval.cache_jobs(JOBS_DATA)
                    print("[find_matching_jobs] 混合检索索引懒加载成功")
                except Exception:
                    pass  # 索引未构建，回退到规则匹配
            
            if retrieval.is_ready():
                # 使用混合检索
                if user_skills and not query:
                    results = retrieval.search_by_skills(user_skills, top_k=top_k)
                elif query:
                    results = retrieval.search_by_job_name(query, top_k=top_k)
                else:
                    results = []
                
                if results:
                    # 将检索结果转换为原有格式
                    matched_jobs = []
                    for r in results:
                        job = next((j for j in JOBS_DATA if j["id"] == r["id"]), None)
                        if job:
                            matched_jobs.append(job)
                    return matched_jobs[:top_k]
        except Exception as e:
            # 混合检索失败，回退到规则匹配
            pass
    
    # 原有规则匹配逻辑（作为 fallback，也是生产环境的默认策略）
    query_lower = query.lower() if query else ''
    scored = []
    
    for job in JOBS_DATA:
        score = 0
        name = job.get('name', '')
        name_lower = name.lower()
        
        # 名称匹配
        if query_lower:
            if query_lower in name_lower:
                score += 100
            elif any(q in name_lower for q in query_lower.split()):
                score += 50
        
        # 技能匹配
        if user_skills:
            job_skills = [s.lower() for s in job.get('skills', [])]
            matched = sum(1 for s in user_skills if s.lower() in job_skills)
            score += matched * 20
        
        # 行业/描述匹配
        description = job.get('description', '')
        requirement = job.get('requirement', '')
        if query_lower and (query_lower in description.lower() or query_lower in requirement.lower()):
            score += 10
        
        if score > 0:
            scored.append((score, job))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    return [job for _, job in scored[:top_k]]


def get_job_profile(job_id):
    """获取岗位画像数据"""
    profile = JOB_PROFILES_DATA.get(str(job_id))
    if not profile:
        profile = JOB_PROFILES_DATA.get(job_id)
    return profile or {}


# 十维画像维度映射（前端key -> 岗位画像中文名）
TEN_DIM_MAP = {
    'awards': '获奖情况',
    'skills': '专业技能',
    'education': '学历证书',
    'gpa': '学习成绩',
    'internship': '实习经历',
    'innovation': '创新能力',
    'communication': '沟通协作',
    'responsibility': '责任心',
    'pressure': '抗压能力',
    'problem': '解决问题能力'
}


def match_jobs_by_ten_dimensions(user_ten_dims, top_k=10):
    """基于用户十维画像与岗位画像计算匹配度，返回最匹配的岗位列表
    user_ten_dims: dict, key为awards/skills等英文key或中文维度名，value为0-100分
    """
    if not JOB_PROFILES_DATA or not JOBS_DATA:
        return []
    
    # 统一用户画像为中文维度名，0-10分制
    user_profile = {}
    for k, v in user_ten_dims.items():
        dim_name = TEN_DIM_MAP.get(k, k)
        try:
            score = float(v)
            # 如果是0-100分制，转换为1-10分制
            if score > 10:
                score = score / 10.0
            user_profile[dim_name] = score
        except (ValueError, TypeError):
            continue
    
    if not user_profile:
        return []
    
    scored_jobs = []
    job_map = {j.get('id'): j for j in JOBS_DATA}
    
    for job_id, profile in JOB_PROFILES_DATA.items():
        job = job_map.get(int(job_id)) if str(job_id).isdigit() else job_map.get(job_id)
        if not job:
            continue
        
        # 计算欧几里得距离（越近越匹配）
        diff_sum = 0
        matched_dims = 0
        for dim_name, user_score in user_profile.items():
            job_score = profile.get(dim_name)
            if job_score is not None:
                try:
                    job_score = float(job_score)
                    diff_sum += (user_score - job_score) ** 2
                    matched_dims += 1
                except (ValueError, TypeError):
                    continue
        
        if matched_dims == 0:
            continue
        
        distance = (diff_sum / matched_dims) ** 0.5
        # 转换为匹配度分数（距离0->100分，距离10->0分）
        match_score = max(0, round(100 - distance * 10))
        
        scored_jobs.append((match_score, job, profile))
    
    scored_jobs.sort(key=lambda x: x[0], reverse=True)
    return [(score, job, profile) for score, job, profile in scored_jobs[:top_k]]


def get_dataset_job_recommendations(user_info=None, analysis_result=None, quiz_dimensions=None, target_job_query=None, top_k=5):
    """综合多策略从数据集获取推荐岗位
    - user_info: 用户信息dict，含skills等
    - analysis_result: 分析结果dict，含jobMatches/abilityProfile.tenDimensions等
    - quiz_dimensions: 测评维度得分dict（中文维度名，1-10分）
    - target_job_query: 目标岗位搜索词
    """
    if not JOBS_DATA:
        return []
    
    results = []
    seen_ids = set()
    
    # 策略1: 基于十维画像匹配（最精准）
    ten_dims = None
    if analysis_result and analysis_result.get('abilityProfile', {}).get('tenDimensions'):
        ten_dims = analysis_result['abilityProfile']['tenDimensions']
    elif quiz_dimensions:
        # 测评维度是中文1-10分，需要转换
        ten_dims = quiz_dimensions
    
    if ten_dims:
        matched = match_jobs_by_ten_dimensions(ten_dims, top_k=top_k * 2)
        for score, job, profile in matched:
            jid = job.get('id')
            if jid not in seen_ids:
                seen_ids.add(jid)
                results.append((score, job))
    
    # 策略2: 基于技能匹配
    user_skills = []
    if user_info and user_info.get('skills'):
        user_skills = user_info['skills']
    elif analysis_result and analysis_result.get('basicInfo', {}).get('skills'):
        user_skills = analysis_result['basicInfo']['skills']
    
    if user_skills:
        skill_matched = find_matching_jobs('', user_skills, top_k=top_k * 2)
        for job in skill_matched:
            jid = job.get('id')
            if jid not in seen_ids:
                seen_ids.add(jid)
                results.append((job.get('match', 70), job))
    
    # 策略3: 基于目标岗位/已有推荐匹配
    job_queries = []
    if target_job_query:
        job_queries.append(target_job_query)
    if analysis_result and analysis_result.get('jobMatches'):
        for jm in analysis_result['jobMatches'][:3]:
            if jm.get('name'):
                job_queries.append(jm['name'])
    
    for q in job_queries:
        if not q:
            continue
        q_matched = find_matching_jobs(q, user_skills, top_k=top_k)
        for job in q_matched:
            jid = job.get('id')
            if jid not in seen_ids:
                seen_ids.add(jid)
                results.append((job.get('match', 75), job))
    
    # 去重排序
    results.sort(key=lambda x: x[0], reverse=True)
    return [job for _, job in results[:top_k]]


def format_dataset_jobs_for_prompt(jobs, max_length=1200):
    """将数据集岗位格式化为prompt文本（精简版，控制Prompt长度）"""
    if not jobs:
        return ""
    lines = ["\n【数据集真实岗位（仅参考，不要直接复制到JSON中）】"]
    for idx, job in enumerate(jobs[:3], 1):  # 只取前3个
        skills = ', '.join(job.get('skills', [])[:3])
        lines.append(
            f"{idx}.{job.get('name','')}@{job.get('company','')} "
            f"薪:{job.get('salary','')} 地:{job.get('location','')} "
            f"技:{skills}"
        )
    text = '\n'.join(lines)
    if len(text) > max_length:
        text = text[:max_length] + '\n...(截断)'
    return text


def build_fallback_job_matches(matched_jobs, top_k=5):
    """从数据集匹配结果构建默认回退的jobMatches格式"""
    if not matched_jobs:
        return []
    
    result = []
    for idx, job in enumerate(matched_jobs[:top_k]):
        req_items = []
        skills = job.get('skills', [])
        if skills:
            req_items.extend(skills[:3])
        req_text = job.get('requirement', '')
        if req_text:
            lines = [l.strip() for l in req_text.split('\n') if l.strip() and len(l.strip()) > 5]
            req_items.extend(lines[:2])
        if not req_items:
            req_items = ['具备相关技能', '良好的学习能力', '团队协作能力']
        
        salary = job.get('salary', '')
        if not salary or salary == '面议':
            # 根据岗位名称推测一个合理薪资范围
            name = job.get('name', '')
            if any(k in name for k in ['架构师', '专家', '总监', '首席']):
                salary = '30-60K'
            elif any(k in name for k in ['高级', '资深']):
                salary = '20-40K'
            elif any(k in name for k in ['经理', '主管']):
                salary = '15-30K'
            else:
                salary = '8-20K'
        
        result.append({
            'name': job.get('name', ''),
            'match': job.get('match', 80 - idx * 5),
            'salary': salary,
            'company': job.get('company', ''),
            'location': job.get('location', ''),
            'reason': f"基于您的画像匹配，该岗位要求{', '.join(skills[:2]) if skills else '相关技能'}，与您较为契合",
            'requirements': req_items[:4],
            'growth': '初级 → 中级 → 高级 → 专家',
            'industry': job.get('industry', ''),
            'education': job.get('education', ''),
            'experience': job.get('experience', '')
        })
    return result


# 通义千问API配置
DASHSCOPE_API_KEY = os.environ.get('DASHSCOPE_API_KEY', '')
DASHSCOPE_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

def normalize_json_string(raw_text):
    text = raw_text.strip()
    if text.startswith('```json'):
        text = text.split('```json', 1)[1].rsplit('```', 1)[0]
    elif text.startswith('```'):
        text = text.split('```', 1)[1].rsplit('```', 1)[0]
    text = text.strip()

    # 先尝试标准解析，如果是合法JSON则直接返回
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # 将 JS/对象风格转换为 JSON 风格
    # 使用更安全的正则：只匹配行首或 {/[ 后的未引号键
    text = re.sub(r'(?<=[\{,\[])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'"\1":', text)
    text = text.replace("'", '"')
    text = re.sub(r',\s*([}\]])', r'\1', text)
    return text


def call_qwen_plus(prompt, system_prompt=None):
    """调用通义千问qwen-plus模型"""
    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": "qwen-plus",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 4000
    }
    
    try:
        response = requests.post(DASHSCOPE_API_URL, headers=headers, json=payload, timeout=60)
        result = response.json()
        
        if 'choices' in result and len(result['choices']) > 0:
            return result['choices'][0]['message']['content']
        elif 'error' in result:
            return f"API错误: {result['error'].get('message', '未知错误')}"
        else:
            return str(result)
    except Exception as e:
        return f"请求失败: {str(e)}"

@app.route('/api/analyze-resume', methods=['POST'])
def analyze_resume():
    """简历分析接口"""
    data = request.json
    user_info = data.get('userInfo', {})
    extracted_text = data.get('extractedText', '')
    parsed_data = data.get('parsedData', {})
    user_id = data.get('userId')
    
    # 合并用户信息和解析数据
    if parsed_data:
        for key in ['name', 'school', 'major', 'degree', 'graduationYear', 'gpa', 'skills', 'projects', 'internships', 'certificates']:
            if not user_info.get(key) and parsed_data.get(key):
                user_info[key] = parsed_data.get(key)
    
    system_prompt = """你是一个专业的职业规划顾问，擅长分析简历和提供个性化的职业发展建议。
请严格以JSON格式返回分析结果，包含以下字段：
1. basicInfo: 基本信息（name, school, major, degree, graduationYear, gpa, skills）
2. abilityProfile: 能力评分对象（technical, learning, communication, execution, creativity各0-100分，overall综合评分，以及tenDimensions十维画像对象，包含awards, skills, education, gpa, internship, innovation, communication, responsibility, pressure, problem各0-100分）
3. jobMatches: 推荐岗位列表，每个岗位包含name(名称), match(匹配度0-100), salary(薪资范围), reason(推荐理由), requirements(岗位要求数组，如["精通前端框架","良好的代码风格"]), growth(成长路径，如"初级 → 中级 → 高级 → 专家")
4. strengths: 核心优势数组，每个优势包含type(skill/experience/education/other), title(优势标题), desc(优势描述), score(优势强度评分0-100，越高代表这项优势越突出)
5. suggestions: 发展建议数组，每个建议包含title(建议标题), content(建议内容), priority(优先级1-5,1最高), category(建议分类，如"技能提升"/"岗位建议"/"经验积累"/"证书认证"/"求职准备"), action(操作按钮文字，如"开始学习"/"查看详情")
6. learningPath: 职业发展路径数组，每个阶段包含：
   - period(阶段名称，如"1-2年")
   - duration(时长描述)
   - title(阶段目标职称，如"初级前端工程师")
   - company(目标公司类型，如"成长型互联网公司")
   - goal(阶段核心目标描述，50字左右)
   - skills(需要掌握的技能数组，3-5项)
   - certificates(建议获取的证书数组，1-3项)
   - salary(预期薪资范围，如"10-15K")
   - milestones(关键里程碑数组，2-3项)
   - items(具体任务数组，每项包含task任务描述, status状态pending)
   路径规划要结合用户的十维画像数据（tenDimensions）和岗位画像要求，制定差异化的成长路线。
只返回JSON，不要有其他内容。"""
    
    # 从数据集中查找匹配的岗位
    target_job = data.get('targetJob', '')
    user_skills = user_info.get('skills', [])
    matched_jobs = find_matching_jobs(target_job, user_skills, top_k=5)
    
    # 构建数据集岗位信息
    dataset_jobs_info = ""
    if matched_jobs:
        dataset_jobs_info = "\n\n【数据集中的真实岗位数据（请基于这些实际数据生成推荐）】\n"
        for idx, job in enumerate(matched_jobs, 1):
            job_id = job.get('id', '')
            profile = get_job_profile(job_id)
            dataset_jobs_info += f"""
岗位{idx}：{job.get('name', '')}
- 公司：{job.get('company', '')}
- 薪资：{job.get('salary', '')}
- 地点：{job.get('location', '')}
- 学历要求：{job.get('education', '')}
- 经验要求：{job.get('experience', '')}
- 公司规模：{job.get('scale', '')}
- 技能要求：{', '.join(job.get('skills', []))}
- 岗位描述：{job.get('description', '')[:200]}
- 岗位要求：{job.get('requirement', '')[:200]}
"""
            if profile:
                dataset_jobs_info += f"- 十维画像：{json.dumps(profile, ensure_ascii=False)}\n"
    
    # 构建简历内容
    resume_content = f"""姓名：{user_info.get('name', '未提供')}
学校：{user_info.get('school', '未提供')}
专业：{user_info.get('major', '未提供')}
学历：{user_info.get('degree', '未提供')}
毕业年份：{user_info.get('graduationYear', '未提供')}
GPA：{user_info.get('gpa', '未提供')}
技能：{', '.join(user_info.get('skills', [])) if user_info.get('skills') else '未提供'}
项目经验：{json.dumps(user_info.get('projects', []), ensure_ascii=False)}
实习经历：{json.dumps(user_info.get('internships', []), ensure_ascii=False)}
证书：{user_info.get('certificates', '未提供')}"""
    
    # 如果有提取的文本内容，添加到简历内容中
    if extracted_text and len(extracted_text) > 50:
        resume_content += f"\n\n简历原文内容：\n{extracted_text[:2000]}"
    
    prompt = f"""请分析以下简历信息，生成完整的职业规划分析：
{resume_content}
{dataset_jobs_info}

请生成包含以下内容的JSON分析结果：
- basicInfo: 用户基本信息，必须包含skills技能数组
- abilityProfile: 
  - 五维能力评分（technical技术能力, learning学习能力, communication沟通能力, execution执行能力, creativity创新能力，各0-100分）以及overall综合评分
  - tenDimensions十维画像（awards获奖情况, skills专业技能, education学历证书, gpa学习成绩, internship实习经历, innovation创新能力, communication沟通协作, responsibility责任心, pressure抗压能力, problem解决问题能力，各0-100分）
- jobMatches: 3-5个推荐岗位，必须基于上方提供的【数据集真实岗位数据】生成：
  每个岗位包含name(名称，使用数据集中的真实岗位名称), match(匹配度0-100), salary(薪资范围，使用数据集中的真实薪资), reason(推荐理由), requirements(岗位要求数组，从数据集岗位描述和要求中提取), growth(成长路径文字)
  注意：不要编造不存在的岗位名称和薪资，必须使用数据集中提供的真实数据。
- strengths: 4-5个核心优势，每个包含type(skill/experience/education/other), title, desc, score(0-100分，越高代表该优势越突出)
- suggestions: 3-5条发展建议，每个包含title, content, priority(1-5,1为最高优先级), category(建议分类), action(操作按钮文字)
- learningPath: 5-6个阶段的详细职业发展路径，必须结合用户的十维画像数据和数据集岗位的技能要求制定：
  每个阶段必须包含完整字段：period(阶段名称如"入门期 0-1年"), duration(时长), title(目标职称), company(目标公司类型), goal(阶段核心目标描述50字左右), skills(需掌握技能数组，必须从数据集岗位的技能要求中选择至少3项), certificates(建议获取的证书数组，至少1项), salary(预期薪资范围如"10-15K"，不能写面议), milestones(关键里程碑数组，至少2项), items(具体任务数组，每项包含task任务描述, status状态pending)
  注意：skills 字段必须引用数据集中岗位实际要求的技能，不要编造不存在的技能名称。

请严格返回JSON格式，不要添加任何额外说明。"""
    
    result = call_qwen_plus(prompt, system_prompt)
    
    # 尝试解析JSON
    try:
        # 尝试提取JSON
        if "```json" in result:
            result = result.split("```json")[1].split("```")[0]
        elif "```" in result:
            result = result.split("```")[1].split("```")[0]
        
        # 标准化字段名（处理中文key或变体key）
        analysis = json.loads(result)
        
        # 确保strengths字段存在
        if 'strengths' not in analysis:
            analysis['strengths'] = generate_default_strengths(user_info)
        
        # 确保suggestions格式正确（如果仍是字符串数组，转换为对象数组）
        if 'suggestions' in analysis:
            analysis['suggestions'] = normalize_suggestions(analysis['suggestions'])
        
        # 确保basicInfo存在
        if 'basicInfo' not in analysis:
            analysis['basicInfo'] = {
                'name': user_info.get('name', '未提供'),
                'school': user_info.get('school', '未提供'),
                'major': user_info.get('major', '未提供'),
                'degree': user_info.get('degree', '本科'),
                'graduationYear': user_info.get('graduationYear', ''),
                'gpa': user_info.get('gpa', '')
            }
        
        # 补充缺失字段，确保与前端展示匹配
        analysis = enrich_analysis_result(analysis, user_info, matched_jobs)
        
        # 如果有用户ID，保存历史记录
        if user_id:
            save_history_record(
                user_id=user_id,
                record_type='analysis',
                title=f'简历分析 - {user_info.get("name", "未知用户")}',
                content={
                    'user_info': user_info,
                    'analysis_result': analysis
                }
            )
        
        return jsonify({
            "success": True,
            "data": analysis
        })
    except Exception as e:
        print(f"简历分析解析失败: {str(e)}")
        # 如果解析失败，返回基于数据集真实岗位的默认分析结果
        fallback_jobs = build_fallback_job_matches(matched_jobs if matched_jobs else get_dataset_job_recommendations(user_info=user_info, top_k=5), top_k=5)
        if not fallback_jobs:
            fallback_jobs = [
                {"name": "前端开发工程师", "match": 85, "salary": "15-30K", "reason": "基于您的技能匹配度最高", "requirements": ["精通前端框架", "良好的代码风格", "浏览器兼容性"], "growth": "初级 → 中级 → 高级 → 前端架构师"},
                {"name": "全栈工程师", "match": 78, "salary": "18-35K", "reason": "技术栈覆盖全面", "requirements": ["前后端都能开发", "系统设计能力", "全链路问题排查"], "growth": "全栈 → 技术负责人 → CTO"},
                {"name": "后端开发工程师", "match": 72, "salary": "16-32K", "reason": "逻辑能力强", "requirements": ["熟悉后端架构", "数据库设计", "API设计"], "growth": "初级 → 中级 → 高级 → 技术专家"}
            ]
        default_analysis = {
            "basicInfo": {
                "name": user_info.get('name', '未提供'),
                "school": user_info.get('school', '未提供'),
                "major": user_info.get('major', '未提供'),
                "degree": user_info.get('degree', '本科'),
                "graduationYear": user_info.get('graduationYear', ''),
                "gpa": user_info.get('gpa', ''),
                "skills": user_info.get('skills', [])
            },
            "abilityProfile": {
                "technical": 75,
                "learning": 78,
                "communication": 72,
                "execution": 80,
                "creativity": 70,
                "experience": 75,
                "education": 65,
                "potential": 74,
                "overall": 75
            },
            "jobMatches": fallback_jobs,
            "strengths": [
                {"type": "skill", "title": "技术能力扎实", "desc": "具备扎实的编程基础和良好的代码编写习惯"},
                {"type": "experience", "title": "项目经验丰富", "desc": "参与过多个实际项目，积累了丰富的实践经验"},
                {"type": "education", "title": "专业背景匹配", "desc": "专业对口，具备系统的理论知识"},
                {"type": "skill", "title": "学习能力强", "desc": "能够快速掌握新技术并应用于实际工作中"}
            ],
            "suggestions": [
                {"title": "深入学习核心技术栈", "content": "建议深入学习React/Vue等主流框架，掌握前端工程化相关技术", "priority": 1, "category": "技能提升", "action": "开始学习"},
                {"title": "积累项目实战经验", "content": "积极参与实际项目，提升项目开发和团队协作能力", "priority": 2, "category": "经验积累", "action": "查看方向"},
                {"title": "关注行业动态", "content": "关注前端技术发展趋势，了解新技术和新工具", "priority": 3, "category": "综合建议", "action": "查看详情"},
                {"title": "提升软技能", "content": "加强沟通能力和团队协作能力，为职业发展做准备", "priority": 4, "category": "求职准备", "action": "获取题库"}
            ],
            "learningPath": [
                {"period": "短期目标", "duration": "1-3个月", "items": [
                    {"task": "完善简历，突出项目亮点", "status": "pending"},
                    {"task": "刷算法题，每周10道", "status": "pending"},
                    {"task": "复习计算机基础知识", "status": "pending"}
                ]},
                {"period": "中期目标", "duration": "3-6个月", "items": [
                    {"task": "完成2-3个高质量项目", "status": "pending"},
                    {"task": "获取相关技术认证", "status": "pending"},
                    {"task": "准备技术面试", "status": "pending"}
                ]},
                {"period": "长期目标", "duration": "6-12个月", "items": [
                    {"task": "入职目标岗位", "status": "pending"},
                    {"task": "成为团队技术骨干", "status": "pending"},
                    {"task": "建立个人技术影响力", "status": "pending"}
                ]}
            ]
        }
        # 补充缺失字段
        default_analysis = enrich_analysis_result(default_analysis, user_info, matched_jobs)
        
        # 保存默认分析结果
        if user_id:
            save_history_record(
                user_id=user_id,
                record_type='analysis',
                title=f'简历分析 - {user_info.get("name", "未知用户")}',
                content={
                    'user_info': user_info,
                    'analysis_result': default_analysis
                }
            )
        
        return jsonify({
            "success": True,
            "data": default_analysis
        })


@app.route('/api/parse-resume', methods=['POST'])
def parse_resume():
    """AI 简历解析接口（前端上传简历文本，由后端调用模型解析）"""
    data = request.json
    content = data.get('content', '')
    
    if not content or len(content.strip()) < 10:
        return jsonify({"success": False, "error": "简历内容过短或为空"}), 400
    
    # 截断内容，防止超过 token 限制
    content_to_send = content[:5000]
    
    system_prompt = """你是一个专业的简历解析助手。请从用户提供的简历内容中提取关键信息，并以JSON格式返回。"""
    
    prompt = f"""请从以下内容中提取关键的简历信息，并以JSON格式返回。

要求提取的信息（字段名必须与下面对应）：
{{
  "name": "姓名",
  "school": "学校/大学名称",
  "major": "专业",
  "degree": "学历（本科/硕士/博士等）",
  "graduationYear": "毕业年份（仅数字，如2024）",
  "gpa": "GPA（如3.8/4.0或绩点）",
  "skills": ["技能1", "技能2"]（数组），
  "projects": [{{"name":"项目名","description":"描述","role":"角色"}}]（数组），
  "internships": [{{"company":"公司","position":"职位","duration":"时长","description":"描述"}}]（数组），
  "certificates": "证书信息"
}}

重要规则：
- 如果无法找到某个字段，返回空字符串或空数组，不要猜测
- 只返回标准JSON格式，不要包含任何其他文字
- 字段名必须英文，不要使用中文字段名
- 数值字段（如GPA、年份）需要准确提取，不确定时返回空字符串

简历内容：
{content_to_send}"""
    
    try:
        result = call_qwen_plus(prompt, system_prompt)
        
        # 尝试提取 JSON
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            parsed = json.loads(json_match.group(0))
            return jsonify({"success": True, "data": parsed})
        else:
            return jsonify({"success": False, "error": "无法从模型响应中解析 JSON", "raw": result}), 500
    except json.JSONDecodeError as e:
        return jsonify({"success": False, "error": f"JSON 解析失败: {str(e)}", "raw": locals().get('result', '')}), 500
    except Exception as e:
        return jsonify({"success": False, "error": f"解析请求失败: {str(e)}"}), 500


def generate_default_strengths(user_info):
    """根据用户信息生成默认优势，并赋予合理的强度评分"""
    strengths = []
    skills = user_info.get('skills', [])
    projects = user_info.get('projects', [])
    school = user_info.get('school', '')
    major = user_info.get('major', '')
    
    if skills and len(skills) > 0:
        skill_score = min(70 + len(skills) * 5, 95)
        strengths.append({
            "type": "skill",
            "title": "技能储备丰富",
            "desc": f"掌握{', '.join(skills[:3])}等多项技能",
            "score": skill_score
        })
    
    if projects and len(projects) > 0:
        exp_score = min(65 + len(projects) * 8, 92)
        strengths.append({
            "type": "experience",
            "title": "项目经验丰富",
            "desc": f"有{len(projects)}个实际项目经验",
            "score": exp_score
        })
    
    if school:
        strengths.append({
            "type": "education",
            "title": "院校背景良好",
            "desc": f"毕业于{school}",
            "score": 75
        })
    
    # 补充第4个通用优势
    strengths.append({
        "type": "other",
        "title": "学习能力强",
        "desc": "具备快速学习新技术和新知识的能力，能够迅速适应变化",
        "score": 80
    })
    
    if not strengths:
        strengths = [
            {"type": "skill", "title": "学习能力强", "desc": "能够快速掌握新技术", "score": 78},
            {"type": "education", "title": "专业基础扎实", "desc": f"{major}专业背景", "score": 72},
            {"type": "other", "title": "综合素质良好", "desc": "具备良好的沟通协作能力和责任心", "score": 75},
            {"type": "other", "title": "发展潜力大", "desc": "具备较大的职业发展潜力和成长空间", "score": 76}
        ]
    
    return strengths


def enrich_analysis_result(analysis, user_info, matched_jobs=None):
    """补充分析结果中缺失的字段，确保与前端展示匹配
    matched_jobs: 从数据集中匹配到的真实岗位列表，用于增强推荐内容
    """
    profile = analysis.get('abilityProfile', {})
    
    # 1. 补充四维度兼容字段
    if 'technical' not in profile:
        profile['technical'] = 70
    if 'experience' not in profile:
        profile['experience'] = round(profile.get('execution', 70) * 0.6 + profile.get('learning', 70) * 0.4)
    if 'education' not in profile:
        degree_scores = {'博士': 95, '硕士': 80, '本科': 60, '大专': 40, '高中': 20}
        edu_score = degree_scores.get(user_info.get('degree', '本科'), 60)
        top_schools = ['清华', '北大', '复旦', '浙大', '上交', '中科大', '南大', '哈工大', '西交', '同济']
        if any(s in user_info.get('school', '') for s in top_schools):
            edu_score += 10
        profile['education'] = min(edu_score, 100)
    if 'potential' not in profile:
        profile['potential'] = round(profile.get('learning', 70) * 0.5 + profile.get('creativity', 70) * 0.5)
    if 'overall' not in profile:
        profile['overall'] = round(sum([
            profile.get('technical', 70),
            profile.get('learning', 70),
            profile.get('communication', 70),
            profile.get('execution', 70),
            profile.get('creativity', 70)
        ]) / 5)
    
    # 2. 补充 tenDimensions（十维能力画像）
    if 'tenDimensions' not in profile:
        skills = user_info.get('skills', [])
        projects = user_info.get('projects', [])
        internships = user_info.get('internships', [])
        certificates = user_info.get('certificates', '')
        gpa = user_info.get('gpa', '')
        school = user_info.get('school', '')
        degree = user_info.get('degree', '本科')
        
        awards = 30
        award_keywords = ['一等奖', '二等奖', '三等奖', '优秀', '奖学金', '国家级', '省级', '校级', 'ACM', '竞赛', '冠军', '第一名']
        award_count = sum(1 for k in award_keywords if k in certificates)
        awards += min(award_count * 10, 40)
        if '国家奖学金' in certificates or '特等奖' in certificates:
            awards += 30
        
        technical_skill = min(40 + len(skills) * 5, 100)
        
        education_cert = {'博士': 95, '硕士': 80, '本科': 60, '大专': 40}.get(degree, 50)
        top_schools = ['清华', '北大', '复旦', '浙大', '上交', '中科大', '南大', '哈工大', '西交', '同济', '华东理工']
        if any(s in school for s in top_schools):
            education_cert += 10
        
        academic_score = 50
        if gpa:
            gpa_match = re.search(r'([\d.]+)', str(gpa))
            if gpa_match:
                gpa_val = float(gpa_match.group(1))
                academic_score = min(round(gpa_val * 25), 100)
        
        internship_exp = min(30 + len(internships) * 15, 100)
        top_companies = ['字节', '阿里', '腾讯', '百度', '华为', '京东', '美团', '字节跳动', '阿里巴巴']
        if any(any(c in (i.get('company', '') if isinstance(i, dict) else str(i)) for c in top_companies) for i in internships):
            internship_exp = min(internship_exp + 40, 100)
        
        innovation = min(40 + len(projects) * 8, 100)
        communication = min(50 + len(projects) * 5 + len(internships) * 8, 100)
        responsibility = min(50 + (len(projects) + len(internships)) * 5, 100)
        pressure = 60 if degree in ['本科', '硕士'] else 50
        problem = min(45 + len(projects) * 7, 100)
        
        profile['tenDimensions'] = {
            'awards': min(awards, 100),
            'skills': min(technical_skill, 100),
            'education': min(education_cert, 100),
            'gpa': min(academic_score, 100),
            'internship': min(internship_exp, 100),
            'innovation': min(innovation, 100),
            'communication': min(communication, 100),
            'responsibility': min(responsibility, 100),
            'pressure': min(pressure, 100),
            'problem': min(problem, 100)
        }
    
    analysis['abilityProfile'] = profile
    
    # 3. 补充 jobMatches 的 requirements 和 growth
    # 优先使用数据集中的真实岗位数据
    dataset_job_map = {}
    if matched_jobs:
        for dj in matched_jobs:
            dataset_job_map[dj.get('name', '')] = dj
    
    # 硬编码兜底数据（当数据集没有匹配时使用）
    job_requirements_growth = {
        '前端开发工程师': (['精通前端框架', '良好的代码风格', '浏览器兼容性'], '初级 → 中级 → 高级 → 前端架构师'),
        '后端开发工程师': (['熟悉后端架构', '数据库设计', 'API设计'], '初级 → 中级 → 高级 → 技术专家'),
        '全栈工程师': (['前后端都能开发', '系统设计能力', '全链路问题排查'], '全栈 → 技术负责人 → CTO'),
        '数据分析师': (['数据分析思维', '统计知识', '可视化能力'], '分析师 → 高级分析师 → 数据产品经理'),
        '大数据开发工程师': (['分布式系统', '海量数据处理', '实时计算'], '初级 → 中级 → 高级 → 数据架构师'),
        'AI/算法工程师': (['数学基础', '算法研究', '论文复现'], '算法工程师 → 高级工程师 → 算法专家'),
        'DevOps工程师': (['自动化运维', '容器化技术', 'CI/CD'], '运维 → DevOps → SRE → 平台架构师'),
        '测试开发工程师': (['测试策略', '自动化框架', '性能测试'], '功能测试 → 自动化测试 → 测试架构师'),
        '产品经理': (['用户洞察', '需求分析', '项目管理'], '产品助理 → 产品经理 → 高级产品 → 产品总监'),
        '运维工程师': (['Linux系统', '网络协议', '监控告警'], '运维 → 高级运维 → 运维架构师'),
        'Java开发工程师': (['Java核心', 'Spring生态', '微服务架构'], '初级 → 中级 → 高级 → 架构师'),
        'Python开发工程师': (['Python核心', 'Web框架', '数据处理'], '初级 → 中级 → 高级 → 技术专家'),
    }
    
    if 'jobMatches' in analysis:
        for job in analysis['jobMatches']:
            name = job.get('name', '')
            # 先从数据集查找匹配的岗位
            dataset_job = None
            for dj_name, dj in dataset_job_map.items():
                if dj_name in name or name in dj_name:
                    dataset_job = dj
                    break
            
            if dataset_job:
                # 使用数据集中的真实数据补充
                if not job.get('salary') or job.get('salary') == '面议':
                    job['salary'] = dataset_job.get('salary', '')
                if not job.get('company') or job.get('company') == '成长型企业':
                    job['company'] = dataset_job.get('company', '')
                if not job.get('location'):
                    job['location'] = dataset_job.get('location', '')
                if not job.get('requirements') or len(job.get('requirements', [])) < 2:
                    # 从数据集的技能、描述、要求中提取
                    req_items = []
                    ds_skills = dataset_job.get('skills', [])
                    if ds_skills:
                        req_items.extend(ds_skills[:3])
                    ds_req = dataset_job.get('requirement', '')
                    if ds_req:
                        # 简单提取要求中的关键句
                        lines = [l.strip() for l in ds_req.split('\n') if l.strip() and len(l.strip()) > 5]
                        req_items.extend(lines[:2])
                    ds_desc = dataset_job.get('description', '')
                    if ds_desc and len(req_items) < 3:
                        req_items.append(ds_desc[:50])
                    if req_items:
                        job['requirements'] = req_items[:4]
                if not job.get('growth'):
                    job['growth'] = '初级 → 中级 → 高级 → 专家'
            else:
                # 数据集没有匹配，使用硬编码兜底
                if not job.get('requirements') or not job.get('growth'):
                    matched = False
                    for key, (reqs, growth) in job_requirements_growth.items():
                        if key in name or name in key:
                            job['requirements'] = job.get('requirements') or reqs
                            job['growth'] = job.get('growth') or growth
                            matched = True
                            break
                    if not matched:
                        job['requirements'] = job.get('requirements') or ['具备相关技能', '良好的学习能力', '团队协作能力']
                        job['growth'] = job.get('growth') or '初级 → 中级 → 高级 → 专家'
    
    # 4. 补充 suggestions 的 category 和 action
    suggestion_category_action = {
        '学习': ('技能提升', '开始学习'),
        '技术': ('技能提升', '开始学习'),
        '项目': ('经验积累', '查看方向'),
        '实习': ('经验积累', '查看方向'),
        '证书': ('证书认证', '了解认证'),
        '认证': ('证书认证', '了解认证'),
        '面试': ('求职准备', '获取题库'),
        '投递': ('岗位建议', '查看详情'),
        '岗位': ('岗位建议', '查看详情'),
    }
    
    if 'suggestions' in analysis:
        for sug in analysis['suggestions']:
            if not sug.get('category') or not sug.get('action'):
                title = sug.get('title', '')
                content = sug.get('content', '')
                matched = False
                for key, (cat, act) in suggestion_category_action.items():
                    if key in title or key in content:
                        sug['category'] = sug.get('category') or cat
                        sug['action'] = sug.get('action') or act
                        matched = True
                        break
                if not matched:
                    sug['category'] = sug.get('category') or '综合建议'
                    sug['action'] = sug.get('action') or '查看详情'
    
    # 5. 补充 learningPath（丰富职业发展路径，结合十维画像和岗位数据）
    target_job_name = ''
    if 'jobMatches' in analysis and analysis['jobMatches']:
        target_job_name = analysis['jobMatches'][0].get('name', '')
    
    td = profile.get('tenDimensions', {})
    tech_score = td.get('skills', profile.get('technical', 70))
    edu_score = td.get('education', 70)
    intern_score = td.get('internship', 50)
    
    # 从数据集岗位中提取真实技能要求和薪资
    dataset_skills = []
    dataset_salary = ''
    dataset_company = ''
    if matched_jobs and len(matched_jobs) > 0:
        top_job = matched_jobs[0]
        dataset_skills = top_job.get('skills', [])
        dataset_salary = top_job.get('salary', '')
        dataset_company = top_job.get('company', '')
    
    # 根据技术分数据差异化路径
    if tech_score >= 80:
        base_skills = ['深入系统架构设计', '性能优化与调优', '技术团队管理', '云原生技术栈', 'AI工程化实践']
        cert_track = ['架构师认证', 'PMP项目管理', 'CKA/K8s认证']
        company_track = ['一线互联网大厂', '技术驱动型创业公司', '独角兽企业', '头部科技公司', '行业领军企业']
        salary_track = ['15-25K', '25-40K', '40-60K', '60-100K', '100K+', '150K+']
    elif tech_score >= 60:
        base_skills = ['主流框架精通', '微服务架构', 'DevOps实践', '数据结构与算法', '系统设计能力']
        cert_track = ['阿里云ACP', 'AWS认证', '软考中级']
        company_track = ['中大型企业', '成长型互联网公司', '行业龙头企业', '知名科技公司', '上市公司']
        salary_track = ['8-15K', '15-25K', '25-40K', '40-60K', '60-100K', '100K+']
    else:
        base_skills = ['编程基础强化', '主流技术栈学习', '项目实战经验', '代码规范与质量', '团队协作能力']
        cert_track = ['计算机等级考试', '行业入门认证', '软考初级']
        company_track = ['创业公司', '中小型企业', '外包公司', '成长型企业', '区域性企业']
        salary_track = ['5-8K', '8-15K', '15-25K', '25-40K', '40-60K', '60K+']
    
    # 如果有数据集技能，优先使用数据集的真实技能，再补充通用技能
    if dataset_skills:
        # 合并数据集技能和基础技能，去重，保留前5个
        combined_skills = dataset_skills[:3] + [s for s in base_skills if s not in dataset_skills]
        skills_track = combined_skills[:5]
    else:
        skills_track = base_skills
    
    # 如果有数据集薪资，尝试解析并用于调整薪资范围
    if dataset_salary and 'K' in dataset_salary:
        try:
            # 提取薪资数字，如 "15-30K" -> 15, 30
            salary_parts = dataset_salary.replace('K', '').replace('k', '').split('-')
            if len(salary_parts) == 2:
                low = int(salary_parts[0].strip())
                high = int(salary_parts[1].strip())
                # 根据职业发展阶段递增
                salary_track = [
                    f"{low//2}-{low}K",
                    f"{low}-{int(low*1.5)}K",
                    f"{int(low*1.2)}-{high}K",
                    f"{high}-{int(high*1.5)}K",
                    f"{int(high*1.2)}-{int(high*2)}K",
                    f"{int(high*1.5)}K+"
                ]
        except:
            pass
    
    # 如果有数据集公司，用于调整目标公司
    if dataset_company:
        company_track = [dataset_company] + [c for c in company_track if c != dataset_company]
    
    job_prefix = target_job_name[:4] if target_job_name else '技术'
    
    # 生成完整的5-6阶段默认路径
    default_learning_path = [
        {
            'period': '入门期',
            'duration': '0-1年',
            'title': f'初级{job_prefix}',
            'company': company_track[0],
            'goal': f'夯实基础技能，完成从学生到职场人的转变，积累{job_prefix}实战经验，建立良好的工作习惯',
            'skills': skills_track[:3],
            'certificates': cert_track[:1],
            'salary': salary_track[0],
            'milestones': ['独立完成第一个项目', '通过试用期考核', '建立技术博客或笔记'],
            'items': [
                {'task': '熟悉公司技术栈和开发流程', 'status': 'pending'},
                {'task': '完成导师分配的基础任务', 'status': 'pending'},
                {'task': '学习代码规范和版本控制', 'status': 'pending'}
            ]
        },
        {
            'period': '成长期',
            'duration': '1-3年',
            'title': f'中级{job_prefix}',
            'company': company_track[1],
            'goal': f'成为团队核心成员，能够独立负责模块，在{job_prefix}领域形成专业深度，开始承担更多责任',
            'skills': skills_track[1:4],
            'certificates': cert_track[:2],
            'salary': salary_track[1],
            'milestones': ['主导完成核心项目模块', '获得晋升或加薪', '开始指导新人或实习生'],
            'items': [
                {'task': '深入掌握业务领域知识', 'status': 'pending'},
                {'task': '参与技术方案设计评审', 'status': 'pending'},
                {'task': '考取专业技术认证', 'status': 'pending'}
            ]
        },
        {
            'period': '进阶期',
            'duration': '3-5年',
            'title': f'高级{job_prefix}',
            'company': company_track[2],
            'goal': f'在{job_prefix}领域建立技术影响力，能够解决复杂技术难题，推动技术创新，成为团队技术骨干',
            'skills': skills_track[2:5],
            'certificates': cert_track[1:3],
            'salary': salary_track[2],
            'milestones': ['发表技术文章或专利', '主导技术架构升级', '获得行业认可或奖项'],
            'items': [
                {'task': '主导技术架构设计', 'status': 'pending'},
                {'task': '培养团队成员技术能力', 'status': 'pending'},
                {'task': '参与行业技术交流会议', 'status': 'pending'}
            ]
        },
        {
            'period': '专家期',
            'duration': '5-8年',
            'title': f'{job_prefix}专家/架构师',
            'company': company_track[3],
            'goal': f'成为{job_prefix}领域的技术专家，具备系统架构设计能力，能够带领团队攻克技术难关',
            'skills': skills_track[3:] + ['技术战略规划', '跨团队协作'],
            'certificates': cert_track[2:] + ['行业专家认证'],
            'salary': salary_track[3],
            'milestones': ['设计并落地大型系统架构', '建立个人技术品牌', '成为公司技术决策核心成员'],
            'items': [
                {'task': '负责核心技术选型与架构设计', 'status': 'pending'},
                {'task': '指导多个团队的技术方向', 'status': 'pending'},
                {'task': '输出技术白皮书或行业标准', 'status': 'pending'}
            ]
        },
        {
            'period': '领导期',
            'duration': '8-12年',
            'title': f'{job_prefix}总监/技术负责人',
            'company': company_track[4],
            'goal': f'从技术专家向技术管理者转型，具备战略视野和团队领导力，推动技术与业务深度融合',
            'skills': ['技术战略规划', '团队管理与建设', '业务理解与洞察', '资源整合与调配', '组织能力建设'],
            'certificates': ['高级管理认证', 'MBA/EMBA'],
            'salary': salary_track[4],
            'milestones': ['带领团队完成重大业务目标', '建立高效技术组织', '推动技术驱动业务创新'],
            'items': [
                {'task': '制定技术部门发展战略', 'status': 'pending'},
                {'task': '建立高效技术团队和人才梯队', 'status': 'pending'},
                {'task': '推动技术驱动业务创新', 'status': 'pending'}
            ]
        },
        {
            'period': '巅峰期',
            'duration': '12年+',
            'title': f'CTO/VP/首席{job_prefix}',
            'company': company_track[4] if len(company_track) > 4 else company_track[-1],
            'goal': f'站在行业高度引领技术发展方向，具备商业洞察力和战略决策能力，成为行业意见领袖',
            'skills': ['企业技术战略', '商业洞察与决策', '行业影响力', '资本运作理解', '全球化视野'],
            'certificates': ['EMBA', '行业顶级认证'],
            'salary': salary_track[5] if len(salary_track) > 5 else salary_track[-1],
            'milestones': ['影响行业技术标准', '成功孵化技术产品或公司', '成为行业公认的顶级专家'],
            'items': [
                {'task': '制定公司级技术战略蓝图', 'status': 'pending'},
                {'task': '构建技术生态和合作伙伴网络', 'status': 'pending'},
                {'task': '培养下一代技术领导者', 'status': 'pending'}
            ]
        }
    ]
    
    if 'learningPath' not in analysis or not analysis['learningPath']:
        analysis['learningPath'] = default_learning_path
    else:
        # 如果已有learningPath但字段不完整或阶段太少，智能补充
        existing = analysis['learningPath']
        # 确保至少有5个阶段
        if len(existing) < 5:
            # 用默认路径补充缺失的阶段
            for i in range(len(existing), 6):
                if i < len(default_learning_path):
                    existing.append(default_learning_path[i])
        
        # 补充每个阶段的缺失字段
        for idx, path in enumerate(existing):
            if not path.get('title') or path.get('title') == path.get('period'):
                path['title'] = default_learning_path[min(idx, len(default_learning_path)-1)].get('title', f'{job_prefix}阶段目标')
            if not path.get('company') or path.get('company') == '成长型企业':
                path['company'] = default_learning_path[min(idx, len(default_learning_path)-1)].get('company', '成长型企业')
            if not path.get('goal') or len(path.get('goal', '')) < 10:
                path['goal'] = default_learning_path[min(idx, len(default_learning_path)-1)].get('goal', '持续提升专业能力，积累项目经验')
            if not path.get('skills') or len(path.get('skills', [])) < 2:
                path['skills'] = default_learning_path[min(idx, len(default_learning_path)-1)].get('skills', skills_track[:3])
            if not path.get('certificates') or len(path.get('certificates', [])) < 1:
                path['certificates'] = default_learning_path[min(idx, len(default_learning_path)-1)].get('certificates', cert_track[:1])
            if not path.get('salary') or path.get('salary') == '面议':
                path['salary'] = default_learning_path[min(idx, len(default_learning_path)-1)].get('salary', salary_track[min(idx, len(salary_track)-1)])
            if not path.get('milestones') or len(path.get('milestones', [])) < 2:
                path['milestones'] = default_learning_path[min(idx, len(default_learning_path)-1)].get('milestones', ['完成阶段性目标', '获得能力提升'])
            if not path.get('items') or len(path.get('items', [])) < 1:
                path['items'] = default_learning_path[min(idx, len(default_learning_path)-1)].get('items', [{'task': '制定学习计划', 'status': 'pending'}])
            if not path.get('duration'):
                path['duration'] = default_learning_path[min(idx, len(default_learning_path)-1)].get('duration', '')
    
    # 6. 确保 basicInfo 包含 skills
    basic_info = analysis.get('basicInfo', {})
    if 'skills' not in basic_info:
        basic_info['skills'] = user_info.get('skills', [])
    analysis['basicInfo'] = basic_info
    
    # 7. 确保 strengths 每个优势都有 score（兜底）
    if 'strengths' in analysis and analysis['strengths']:
        td = profile.get('tenDimensions', {})
        type_score_map = {
            'skill': td.get('skills', td.get('technical', 75)),
            'experience': td.get('internship', td.get('experience', 70)),
            'education': td.get('education', 75),
            'potential': td.get('innovation', td.get('potential', 72)),
            'other': td.get('problem', profile.get('overall', 70))
        }
        for s in analysis['strengths']:
            if 'score' not in s or s['score'] is None:
                s['score'] = type_score_map.get(s.get('type', 'other'), 75)
    
    return analysis


def normalize_suggestions(suggestions):
    """将字符串数组的建议转换为对象数组"""
    if not suggestions:
        return []
    
    result = []
    for i, s in enumerate(suggestions):
        if isinstance(s, str):
            result.append({
                "title": s[:30] if len(s) > 30 else s,
                "content": s,
                "priority": 1 if i < 2 else 2
            })
        elif isinstance(s, dict):
            # 确保有必需字段
            result.append({
                "title": s.get('title', s.get('name', f'建议{i+1}')),
                "content": s.get('content', s.get('desc', s.get('suggestion', ''))),
                "priority": s.get('priority', 2)
            })
    return result

@app.route('/api/generate-report', methods=['POST'])
def generate_report():
    """生成职业报告接口 - 基于数据集真实岗位生成推荐"""
    data = request.json
    user_info = data.get('userInfo', {})
    analysis_result = data.get('analysisResult', {})
    user_id = data.get('userId')
    
    # 从数据集中获取真实匹配岗位
    matched_jobs = get_dataset_job_recommendations(
        user_info=user_info,
        analysis_result=analysis_result,
        top_k=5
    )
    dataset_jobs_text = format_dataset_jobs_for_prompt(matched_jobs)
    
    # ====== Agentic RAG 增强检索 ======
    rag_context_text = ""
    retrieval_sources = []
    try:
        from backend.services.rag_service import get_rag_service
        rag = get_rag_service()
        rag_result = rag.retrieve(
            query_type="career_report",
            user_info=user_info,
            analysis_result=analysis_result
        )
        rag_context_text = rag_result.to_prompt_context()
        retrieval_sources = rag_result.sources
        if rag_context_text:
            print(f"[generate_report] RAG 检索完成，来源: {retrieval_sources}")
    except Exception as e:
        print(f"[generate_report] RAG 检索失败（不影响主流程）: {e}")
    
    # 提取用户目标岗位名称用于报告定位
    target_job_name = ''
    if analysis_result and analysis_result.get('jobMatches'):
        target_job_name = analysis_result['jobMatches'][0].get('name', '')
    if not target_job_name and matched_jobs:
        target_job_name = matched_jobs[0].get('name', '')
    
    system_prompt = """你是一位资深职业规划顾问，拥有10年以上HR和人才发展经验，擅长撰写专业、详细、可操作的职业发展报告。
请严格基于用户提供的【数据集真实岗位数据】生成报告，所有岗位名称、公司、薪资必须来自数据集，不要编造。
报告需要内容充实、分析深入、建议具体可操作，每段文字要有实质性内容，不要空洞套话。
请以JSON格式返回，不要添加任何额外说明。
"""
    
    # 精简用户信息和分析结果，只保留关键字段
    user_keys = ['name', 'age', 'education', 'major', 'school', 'skills', 'experience', 'targetPosition']
    brief_user = {k: user_info.get(k, '') for k in user_keys if user_info.get(k)}
    
    brief_analysis = {}
    if analysis_result:
        brief_analysis = {
            'jobMatches': analysis_result.get('jobMatches', [])[:2],
            'skills': analysis_result.get('skills', []),
            'experience': analysis_result.get('experience', {})
        }
    
    prompt = f"""基于以下信息生成职业发展报告（必须输出完整合法的JSON）：

用户信息：
{json.dumps(brief_user, ensure_ascii=False)}

简历分析：
{json.dumps(brief_analysis, ensure_ascii=False)}
{dataset_jobs_text}
{rag_context_text}

请严格返回以下JSON结构（不要省略任何字段，JSON必须完整可解析）：
{{
  "title": "职业发展规划报告",
  "executiveSummary": "执行摘要（200字左右）。概述用户的职业现状、核心优势、主要差距、发展方向和关键建议。必须引用数据集中的真实岗位。",
  "careerPositioning": "职业定位（150字左右）。基于用户画像和数据集岗位，明确用户当前处于职业发展的哪个阶段，适合什么类型和层级的岗位，引用具体岗位名称。",
  "coreStrengths": ["核心优势1（含具体数据支撑）", "核心优势2", "核心优势3", "核心优势4"],
  "swotAnalysis": {{
    "strengths": ["内部优势1", "内部优势2", "内部优势3"],
    "weaknesses": ["内部劣势1", "内部劣势2"],
    "opportunities": ["外部机会1", "外部机会2"],
    "threats": ["外部威胁1", "外部威胁2"]
  }},
  "skillGapAnalysis": {{
    "currentSkills": ["用户已掌握的技能1", "已掌握技能2"],
    "requiredSkills": ["目标岗位要求的技能1", "要求技能2", "要求技能3"],
    "gapSkills": ["差距技能1", "差距技能2"],
    "priority": "高/中/低",
    "closingPlan": "弥补差距的具体计划（100字左右）"
  }},
  "industryAnalysis": "行业趋势分析（150字左右）。分析目标岗位所在行业的发展趋势、人才需求变化、技术演进方向，引用数据集岗位的行业分布。",
  "competitiveAnalysis": "竞争力分析（150字左右）。将用户能力与数据集中目标岗位的要求进行对比，分析相对优势和劣势。",
  "salaryForecast": [
    {{"stage": "1-2年", "range": "具体薪资范围", "note": "该阶段薪资定位说明"}},
    {{"stage": "3-5年", "range": "具体薪资范围", "note": "该阶段薪资定位说明"}},
    {{"stage": "5-8年", "range": "具体薪资范围", "note": "该阶段薪资定位说明"}},
    {{"stage": "8年+", "range": "具体薪资范围", "note": "该阶段薪资定位说明"}}
  ],
  "certificationPlan": [
    {{"name": "证书名称", "time": "建议考取时间", "importance": "高/中/低", "description": "证书价值说明"}}
  ],
  "interviewStrategy": "面试策略（150字左右）。针对目标岗位，提供简历优化、技术面试准备、行为面试技巧、项目展示方法等具体建议。",
  "riskAssessment": [
    {{"risk": "风险描述", "level": "高/中/低", "solution": "具体应对方案"}}
  ],
  "timeline": [
    {{"phase": "阶段名称", "time": "时间范围", "goals": ["目标1", "目标2"], "actions": ["具体行动1", "具体行动2"], "milestones": ["里程碑1"]}}
  ],
  "actionSteps": ["可操作的步骤1", "步骤2", "步骤3", "步骤4", "步骤5"],
  "recommendedJobs": [
    {{"name": "岗位名称（必须来自数据集）", "company": "公司名", "salary": "薪资", "location": "地点", "reason": "匹配理由", "requirements": ["要求1", "要求2"]}}
  ]
}}

重要约束：
- recommendedJobs中的岗位必须严格来自上方【数据集真实岗位数据】
- salaryForecast中的薪资必须参考数据集中真实岗位的薪资范围
- certificationPlan中的证书建议要与数据集岗位的技能要求相关
- 所有文字内容要具体、有深度，不要空洞套话
- 不要编造任何不存在的岗位名称、公司或薪资数据
"""    
    result = call_qwen_plus(prompt, system_prompt)
    
    try:
        if "```json" in result:
            result = result.split("```json")[1].split("```", 1)[0]
        elif "```" in result:
            result = result.split("```", 1)[1].split("```", 1)[0]
        
        try:
            report = json.loads(result)
        except json.JSONDecodeError:
            normalized = normalize_json_string(result)
            report = json.loads(normalized)
        
        # 清洗AI返回的字段类型，确保字符串字段不为对象
        def sanitize_string(val):
            if val is None:
                return ''
            if isinstance(val, str):
                return val
            if isinstance(val, (int, float, bool)):
                return str(val)
            if isinstance(val, dict):
                # 字典直接序列化为JSON字符串，避免递归提取导致数据丢失
                return json.dumps(val, ensure_ascii=False)
            if isinstance(val, list):
                return ', '.join(str(sanitize_string(item)) for item in val)
            return str(val)
        
        string_fields = ['title', 'summary', 'executiveSummary', 'careerPositioning',
                        'industryAnalysis', 'competitiveAnalysis', 'interviewStrategy']
        for field in string_fields:
            if field in report:
                report[field] = sanitize_string(report[field])
        
        if 'coreStrengths' in report and isinstance(report['coreStrengths'], list):
            report['coreStrengths'] = [sanitize_string(s) for s in report['coreStrengths']]
        
        if 'actionSteps' in report and isinstance(report['actionSteps'], list):
            report['actionSteps'] = [sanitize_string(s) for s in report['actionSteps']]
        
        if 'recommendedJobs' in report and isinstance(report['recommendedJobs'], list):
            for rj in report['recommendedJobs']:
                for key in ['name', 'company', 'salary', 'location', 'reason']:
                    if key in rj:
                        rj[key] = sanitize_string(rj[key])
        
        if 'salaryForecast' in report and isinstance(report['salaryForecast'], list):
            for sf in report['salaryForecast']:
                for key in ['stage', 'range', 'note']:
                    if key in sf:
                        sf[key] = sanitize_string(sf[key])
        
        if 'certificationPlan' in report and isinstance(report['certificationPlan'], list):
            for cp in report['certificationPlan']:
                for key in ['name', 'time', 'importance', 'description']:
                    if key in cp:
                        cp[key] = sanitize_string(cp[key])
        
        if 'riskAssessment' in report and isinstance(report['riskAssessment'], list):
            for ra in report['riskAssessment']:
                for key in ['risk', 'level', 'solution']:
                    if key in ra:
                        ra[key] = sanitize_string(ra[key])
        
        if 'timeline' in report and isinstance(report['timeline'], list):
            for tl in report['timeline']:
                for key in ['phase', 'time']:
                    if key in tl:
                        tl[key] = sanitize_string(tl[key])
                for arr_key in ['goals', 'actions', 'milestones']:
                    if arr_key in tl and isinstance(tl[arr_key], list):
                        tl[arr_key] = [sanitize_string(s) for s in tl[arr_key]]
        
        if 'swotAnalysis' in report and isinstance(report['swotAnalysis'], dict):
            for key in ['strengths', 'weaknesses', 'opportunities', 'threats']:
                if key in report['swotAnalysis'] and isinstance(report['swotAnalysis'][key], list):
                    report['swotAnalysis'][key] = [sanitize_string(s) for s in report['swotAnalysis'][key]]
        
        if 'skillGapAnalysis' in report and isinstance(report['skillGapAnalysis'], dict):
            sga = report['skillGapAnalysis']
            for key in ['currentSkills', 'requiredSkills', 'gapSkills']:
                if key in sga and isinstance(sga[key], list):
                    sga[key] = [sanitize_string(s) for s in sga[key]]
            for key in ['priority', 'closingPlan']:
                if key in sga:
                    sga[key] = sanitize_string(sga[key])
        
        # 将数据集真实岗位绑定到报告推荐中
        if 'recommendedJobs' not in report or not report['recommendedJobs']:
            report['recommendedJobs'] = build_fallback_job_matches(matched_jobs, top_k=3)
        else:
            for rj in report['recommendedJobs']:
                rj_name = rj.get('name', '')
                matched = None
                for dj in matched_jobs:
                    if dj.get('name', '') == rj_name or rj_name in dj.get('name', '') or dj.get('name', '') in rj_name:
                        matched = dj
                        break
                if matched:
                    rj['company'] = rj.get('company') or matched.get('company', '')
                    rj['salary'] = rj.get('salary') or matched.get('salary', '')
                    rj['location'] = rj.get('location') or matched.get('location', '')
                    rj['requirements'] = rj.get('requirements') or matched.get('requirements', [])[:3]
        
        # 确保扩展字段存在
        report.setdefault('executiveSummary', report.get('summary', ''))
        report.setdefault('swotAnalysis', {
            'strengths': report.get('coreStrengths', [])[:3],
            'weaknesses': ['行业竞争加剧', '技术迭代快'],
            'opportunities': ['数字化转型需求旺盛', '新兴技术领域人才缺口大'],
            'threats': ['经济环境不确定性', 'AI对基础岗位的替代风险']
        })
        report.setdefault('skillGapAnalysis', {
            'currentSkills': user_info.get('skills', []),
            'requiredSkills': ['目标岗位核心技能'],
            'gapSkills': ['待补充技能'],
            'priority': '高',
            'closingPlan': '建议通过系统学习和项目实践逐步弥补技能差距。'
        })
        report.setdefault('industryAnalysis', '目标行业正处于快速发展期，对专业人才需求持续增长。')
        report.setdefault('competitiveAnalysis', '用户具备良好的基础能力，在同龄人中具有一定竞争力。')
        report.setdefault('salaryForecast', [
            {'stage': '1-2年', 'range': '10-15K', 'note': '入门期，以积累经验和技能为主'},
            {'stage': '3-5年', 'range': '20-35K', 'note': '成长期，技能成熟后可获得显著薪资提升'},
            {'stage': '5-8年', 'range': '35-50K', 'note': '成熟期，具备独立负责能力'},
            {'stage': '8年+', 'range': '50K+', 'note': '专家期，薪资与个人价值强相关'}
        ])
        report.setdefault('certificationPlan', [
            {'name': '行业相关技术认证', 'time': '1年内', 'importance': '中', 'description': '提升专业认可度'}
        ])
        report.setdefault('interviewStrategy', '建议重点准备项目经验阐述和技术深度问题，同时关注行为面试中的STAR法则应用。')
        report.setdefault('riskAssessment', [
            {'risk': '技术更新换代快', 'level': '中', 'solution': '保持持续学习习惯，关注行业前沿动态'},
            {'risk': '行业竞争加剧', 'level': '中', 'solution': '打造个人技术品牌，积累差异化优势'}
        ])
        report.setdefault('timeline', [
            {'phase': '短期', 'time': '0-1年', 'goals': ['夯实基础'], 'actions': ['系统学习核心技术', '完成2-3个项目'], 'milestones': ['通过试用期']}
        ])
        
        # 保存历史记录
        if user_id:
            save_history_record(
                user_id=user_id,
                record_type='report',
                title=f'职业规划报告 - {user_info.get("name", "未知用户")}',
                content={
                    'user_info': user_info,
                    'analysis_result': analysis_result,
                    'report': report
                }
            )
        
        return jsonify({
            "success": True,
            "data": report,
            "retrieval_context": {
                "sources": retrieval_sources,
                "method": "AgenticRAG" if retrieval_sources else "rule-based",
            }
        })
    except Exception as e:
        print(f"报告生成解析失败: {e}")
        fallback_jobs = build_fallback_job_matches(matched_jobs, top_k=3)
        job_names = [j['name'] for j in fallback_jobs]
        companies = list(set([j.get('company', '') for j in fallback_jobs if j.get('company')]))[:2]
        
        default_report = {
            "title": "职业发展规划报告",
            "executiveSummary": f"基于您的简历分析，您在技术能力和项目经验方面具备良好基础，推荐关注{', '.join(job_names[:2])}等真实岗位机会。建议在未来1-2年内聚焦核心技能提升，3-5年内向中高级岗位发展。",
            "careerPositioning": f"您的能力与{job_names[0] if job_names else '目标岗位'}方向较为匹配，建议聚焦{'、'.join(companies)}等类型的真实企业，从基础岗位做起逐步积累。",
            "coreStrengths": ["技术基础扎实，具备快速学习能力", "项目实践经验丰富，有实际成果产出", "综合素质良好，沟通协作能力强", "学习能力突出，能快速适应新技术"],
            "swotAnalysis": {
                "strengths": ["技术基础扎实", "学习能力强", "项目经验丰富"],
                "weaknesses": ["高级技能有待提升", "行业人脉资源有限"],
                "opportunities": ["数字化转型带来大量岗位需求", "新兴技术领域人才缺口大"],
                "threats": ["行业竞争加剧", "技术迭代速度快"]
            },
            "skillGapAnalysis": {
                "currentSkills": user_info.get('skills', []),
                "requiredSkills": ["分布式系统", "微服务架构", "性能优化"],
                "gapSkills": ["高级架构设计能力", "大规模系统经验"],
                "priority": "高",
                "closingPlan": "建议通过系统学习在线课程、参与开源项目、考取相关认证等方式逐步弥补技能差距。"
            },
            "industryAnalysis": "互联网行业持续保持高速发展，尤其是人工智能、云计算、大数据等领域人才需求旺盛。数据集中的岗位覆盖了从初级到高级的完整职业路径，为用户提供丰富的选择空间。",
            "competitiveAnalysis": f"与数据集中{job_names[0] if job_names else '目标岗位'}的要求相比，您在基础技能方面具备优势，但在高级技能和项目深度方面还有提升空间。",
            "salaryForecast": [
                {"stage": "1-2年", "range": "8-15K", "note": "入门期，以积累经验和技能为主"},
                {"stage": "3-5年", "range": "15-30K", "note": "成长期，技能成熟后可获得显著薪资提升"},
                {"stage": "5-8年", "range": "30-50K", "note": "成熟期，具备独立负责核心模块能力"},
                {"stage": "8年+", "range": "50K+", "note": "专家期，薪资与个人价值和行业影响力强相关"}
            ],
            "certificationPlan": [
                {"name": "阿里云ACP认证", "time": "6个月内", "importance": "高", "description": "提升云计算领域专业认可度，符合数据集岗位技能要求"},
                {"name": "AWS解决方案架构师", "time": "1年内", "importance": "中", "description": "增强云架构设计能力，拓宽职业选择面"}
            ],
            "interviewStrategy": "建议重点准备项目经验的STAR法则阐述，技术面试中注重算法和数据结构的深度理解，同时准备好对简历中每个技术点的深入追问。",
            "riskAssessment": [
                {"risk": "技术更新换代快，现有技能可能过时", "level": "中", "solution": "建立持续学习机制，每季度学习一项新技术，关注行业趋势报告"},
                {"risk": "行业竞争加剧，初级岗位供给过剩", "level": "中", "solution": "通过项目作品和技术博客建立个人品牌，提升差异化竞争力"}
            ],
            "timeline": [
                {"phase": "入门期", "time": "0-1年", "goals": ["掌握岗位核心技能", "完成独立项目"], "actions": ["系统学习技术栈", "参与实际项目开发", "建立代码规范意识"], "milestones": ["通过试用期考核", "独立完成第一个项目"]}
            ],
            "actionSteps": ["制定6个月技能提升计划，明确每周学习目标", "每月完成1个实战项目并发布到GitHub", "每季度参加1次技术分享或行业会议", "建立技术博客，每月输出2篇技术文章", "主动寻求导师指导，定期复盘职业发展"],
            "recommendedJobs": fallback_jobs
        }
        
        if user_id:
            save_history_record(
                user_id=user_id,
                record_type='report',
                title=f'职业规划报告 - {user_info.get("name", "未知用户")}',
                content={
                    'user_info': user_info,
                    'analysis_result': analysis_result,
                    'report': default_report
                }
            )
        
        return jsonify({
            "success": True,
            "data": default_report
        })

@app.route('/api/quiz-analysis', methods=['POST'])
def quiz_analysis():
    """问卷测评分析接口 - 调用LLM深度分析用户职业倾向"""
    data = request.json
    answers = data.get('answers', {})
    questions = data.get('questions', [])
    user_id = data.get('userId')
    
    # 1. 计算各维度得分
    dimension_scores = {}
    dimension_weights = {}
    for q in questions:
        dim = q.get('dimension', 'other')
        weight = q.get('weight', 1.0)
        # 兼容字符串和数字id
        ans = answers.get(str(q['id']), answers.get(q['id'], 0))
        try:
            ans = float(ans)
        except (ValueError, TypeError):
            ans = 0
        if dim not in dimension_scores:
            dimension_scores[dim] = 0
            dimension_weights[dim] = 0
        dimension_scores[dim] += weight * ans
        dimension_weights[dim] += weight
    
    normalized_scores = {}
    for dim in dimension_scores:
        if dimension_weights[dim] > 0:
            normalized_scores[dim] = round(dimension_scores[dim] / dimension_weights[dim], 1)
    
    # 2. 把问卷答案整理成可读文本
    level_desc = {1: '非常不同意', 2: '不同意', 3: '一般', 4: '同意', 5: '非常同意'}
    answer_lines = []
    for q in questions:
        qid = str(q['id'])
        ans = answers.get(qid, answers.get(q['id'], 0))
        try:
            ans = int(float(ans))
        except:
            ans = 0
        desc = level_desc.get(ans, str(ans))
        answer_lines.append(f"{qid}. {q.get('text', '')} -> {desc}({ans}分)")
    
    # 3. 构建LLM prompt - 要求返回十维画像（中文维度名，10分制）
    system_prompt = """你是一位资深职业规划顾问，拥有丰富的HR和人才测评经验。
请根据用户的问卷回答，将其能力映射到以下十个维度（与个人能力画像一致），每个维度给出1-10分的评分和文字分析。

十个维度（必须使用这些中文维度名）：
- 获奖情况：用户在竞赛、奖学金、荣誉等方面的表现倾向
- 专业技能：技术能力、专业知识的掌握程度
- 学历证书：学历背景、证书获取的重视程度和匹配度
- 学习成绩：学习能力和学业表现
- 实习经历：实践经验、实习意愿和经历丰富度
- 创新能力：创新思维、解决新问题的能力
- 沟通协作：团队合作、沟通协调的能力
- 责任心：责任感、执行力和任务完成度
- 抗压能力：面对压力和挑战的应对能力
- 解决问题能力：逻辑思维、分析和解决复杂问题的能力

请严格以JSON格式返回，包含以下字段：
{
    "overallScore": 综合评分(0-100整数),
    "personalityType": "性格类型标签，如'创新型技术领军人才'、'稳健型运营专家'等",
    "summary": "整体分析摘要(80字左右)",
    "dimensionScores": {"获奖情况": 1-10整数, "专业技能": 1-10整数, "学历证书": 1-10整数, "学习成绩": 1-10整数, "实习经历": 1-10整数, "创新能力": 1-10整数, "沟通协作": 1-10整数, "责任心": 1-10整数, "抗压能力": 1-10整数, "解决问题能力": 1-10整数},
    "dimensionAnalysis": {"获奖情况": "分析文字(40字左右)", ...},
    "strengths": ["核心优势1", "核心优势2", "核心优势3", "核心优势4"],
    "weaknesses": ["待提升点1", "待提升点2"],
    "jobMatches": [
        {"name": "岗位名称", "match": 匹配度0-100, "reason": "匹配理由(30字左右)", "category": "岗位类别如技术/产品/运营/数据/金融"}
    ],
    "suggestions": [
        {"title": "建议标题", "content": "建议内容(50字左右)", "priority": 1-3(1最高)}
    ]
}

注意：
- dimensionScores必须使用上述10个中文维度名，每个维度评分1-10分
- dimensionAnalysis也必须使用上述10个中文维度名
- jobMatches推荐4-6个岗位，覆盖不同方向
- 所有文字内容使用中文
- 只返回JSON，不要有任何额外说明"""
    
    # 3.5 基于测评维度得分从数据集匹配真实岗位
    # 先将normalized_scores映射为中文十维画像（1-10分）
    quiz_dim_map = {
        'technical': '专业技能', 'creative': '创新能力', 'learning': '解决问题能力',
        'communication': '沟通协作', 'execution': '责任心', 'service': '沟通协作',
        'independent': '抗压能力', 'growth': '解决问题能力', 'stability': '抗压能力',
        'leadership': '责任心', 'teamwork': '沟通协作', 'motivation': '获奖情况',
        'salary': '学习成绩', 'balance': '抗压能力', 'culture': '沟通协作',
        'mobility': '实习经历', 'internet': '专业技能', 'finance': '专业技能',
        'product': '创新能力'
    }
    quiz_ten_dims = {}
    for k, v in normalized_scores.items():
        mapped_dim = quiz_dim_map.get(k, '专业技能')
        quiz_ten_dims[mapped_dim] = max(quiz_ten_dims.get(mapped_dim, 0), round(v * 2))
    ten_dim_names = ['获奖情况', '专业技能', '学历证书', '学习成绩', '实习经历', '创新能力', '沟通协作', '责任心', '抗压能力', '解决问题能力']
    for d in ten_dim_names:
        if d not in quiz_ten_dims:
            quiz_ten_dims[d] = 6
    
    matched_jobs = get_dataset_job_recommendations(
        quiz_dimensions=quiz_ten_dims,
        top_k=6
    )
    dataset_jobs_text = format_dataset_jobs_for_prompt(matched_jobs)
    
    # 4. 构建LLM prompt - 要求返回十维画像（中文维度名，10分制）
    system_prompt = """你是一位资深职业规划顾问，拥有丰富的HR和人才测评经验。
请根据用户的问卷回答，将其能力映射到以下十个维度（与个人能力画像一致），每个维度给出1-10分的评分和文字分析。

十个维度（必须使用这些中文维度名）：
- 获奖情况：用户在竞赛、奖学金、荣誉等方面的表现倾向
- 专业技能：技术能力、专业知识的掌握程度
- 学历证书：学历背景、证书获取的重视程度和匹配度
- 学习成绩：学习能力和学业表现
- 实习经历：实践经验、实习意愿和经历丰富度
- 创新能力：创新思维、解决新问题的能力
- 沟通协作：团队合作、沟通协调的能力
- 责任心：责任感、执行力和任务完成度
- 抗压能力：面对压力和挑战的应对能力
- 解决问题能力：逻辑思维、分析和解决复杂问题的能力

请严格以JSON格式返回，包含以下字段：
{
    "overallScore": 综合评分(0-100整数),
    "personalityType": "性格类型标签，如'创新型技术领军人才'、'稳健型运营专家'等",
    "summary": "整体分析摘要(80字左右)",
    "dimensionScores": {"获奖情况": 1-10整数, "专业技能": 1-10整数, ...},
    "dimensionAnalysis": {"获奖情况": "分析文字(40字左右)", ...},
    "strengths": ["核心优势1", "核心优势2", "核心优势3", "核心优势4"],
    "weaknesses": ["待提升点1", "待提升点2"],
    "jobMatches": [
        {"name": "岗位名称（必须来自数据集真实岗位）", "match": 匹配度0-100, "reason": "匹配理由(30字左右)", "category": "岗位类别如技术/产品/运营/数据/金融"}
    ],
    "suggestions": [
        {"title": "建议标题", "content": "建议内容(50字左右)", "priority": 1-3(1最高)}
    ]
}

重要约束：
- jobMatches中的岗位名称必须严格来自提供的【数据集真实岗位数据】
- 不要编造任何不存在的岗位名称
- dimensionScores必须使用上述10个中文维度名
- 只返回JSON，不要有任何额外说明"""
    
    prompt = f"""请为以下用户进行职业规划分析，并将其能力映射到十维画像：

【问卷原始回答】(共{len(questions)}题，1-5分，5分代表非常同意)
{chr(10).join(answer_lines)}

{dataset_jobs_text}

请给出：
1. 综合评分(0-100)和性格类型标签
2. 整体分析摘要
3. 十维画像评分（获奖情况/专业技能/学历证书/学习成绩/实习经历/创新能力/沟通协作/责任心/抗压能力/解决问题能力），每个维度1-10分
4. 每个维度的文字分析
5. 3-5个核心优势和2个待提升点
6. 4-6个最匹配的岗位推荐（必须严格来自上方数据集真实岗位数据）
7. 3-5条发展建议

只返回JSON格式。"""
    
    result = call_qwen_plus(prompt, system_prompt)
    
    # 5. 解析LLM返回
    try:
        if "```json" in result:
            result = result.split("```json")[1].split("```")[0]
        elif "```" in result:
            result = result.split("```")[1].split("```")[0]
        
        analysis = json.loads(result.strip())
        
        # 字段兜底 - 确保dimensionScores使用十维画像中文名+10分制
        ten_dims = ['获奖情况', '专业技能', '学历证书', '学习成绩', '实习经历', '创新能力', '沟通协作', '责任心', '抗压能力', '解决问题能力']
        analysis.setdefault('overallScore', 75)
        analysis.setdefault('personalityType', '综合型人才')
        analysis.setdefault('summary', '用户综合素质良好，具备较强的学习能力和发展潜力。')
        # 如果LLM没返回十维画像，用问卷维度映射生成
        if not analysis.get('dimensionScores') or not any(k in ten_dims for k in analysis.get('dimensionScores', {}).keys()):
            analysis['dimensionScores'] = quiz_ten_dims
        # 确保dimensionAnalysis也有十维
        dim_analysis = analysis.get('dimensionAnalysis', {})
        for d in ten_dims:
            if d not in dim_analysis:
                score = analysis['dimensionScores'].get(d, 6)
                dim_analysis[d] = f"{d}得分{score}分，表现{'优秀' if score >= 8 else '良好' if score >= 6 else '一般'}。"
        analysis['dimensionAnalysis'] = dim_analysis
        analysis.setdefault('strengths', ['学习能力较强', '综合素质良好'])
        analysis.setdefault('weaknesses', ['可进一步提升专业技能'])
        analysis.setdefault('jobMatches', [])
        analysis.setdefault('suggestions', [])
        
        # 用数据集真实岗位替换/补全jobMatches
        valid_job_names = {j.get('name', '') for j in matched_jobs}
        llm_jobs = analysis.get('jobMatches', [])
        
        # 过滤掉不在数据集中的岗位
        filtered_llm_jobs = []
        for job in llm_jobs:
            name = job.get('name', '')
            # 检查是否在数据集匹配结果中
            matched_dataset_job = None
            for dj in matched_jobs:
                if dj.get('name', '') == name or name in dj.get('name', '') or dj.get('name', '') in name:
                    matched_dataset_job = dj
                    break
            if matched_dataset_job:
                job['name'] = matched_dataset_job.get('name', name)
                job['company'] = job.get('company') or matched_dataset_job.get('company', '')
                job['salary'] = job.get('salary') or matched_dataset_job.get('salary', '')
                job['location'] = job.get('location') or matched_dataset_job.get('location', '')
                filtered_llm_jobs.append(job)
        
        # 如果过滤后不足4个，用数据集匹配结果补充
        if len(filtered_llm_jobs) < 4:
            used_names = {j['name'] for j in filtered_llm_jobs}
            for dj in matched_jobs:
                if dj.get('name', '') not in used_names:
                    filtered_llm_jobs.append({
                        'name': dj.get('name', ''),
                        'match': dj.get('match', 75),
                        'reason': f"基于您的测评画像，该岗位要求{', '.join(dj.get('skills', [])[:2]) if dj.get('skills') else '相关能力'}，与您较为契合",
                        'category': dj.get('industry', '综合'),
                        'company': dj.get('company', ''),
                        'salary': dj.get('salary', ''),
                        'location': dj.get('location', '')
                    })
                    if len(filtered_llm_jobs) >= 6:
                        break
        
        analysis['jobMatches'] = filtered_llm_jobs[:6]
        
        # 统一jobMatches格式
        for job in analysis.get('jobMatches', []):
            if 'matchRate' not in job and 'match' in job:
                job['matchRate'] = job['match']
            if 'name' not in job and 'job' in job:
                job['name'] = job['job']
            job.setdefault('reason', '综合素质匹配')
            job.setdefault('category', '综合')
        
        # 保存历史记录
        if user_id:
            save_history_record(
                user_id=user_id,
                record_type='quiz',
                title='职业测评分析',
                content={
                    'dimension_scores': normalized_scores,
                    'analysis_result': analysis
                }
            )
        
        return jsonify({
            "success": True,
            "data": analysis
        })
    except Exception as e:
        print(f'LLM解析失败: {e}')
        # 返回基于数据集真实岗位的兜底结果
        ten_dims = ['获奖情况', '专业技能', '学历证书', '学习成绩', '实习经历', '创新能力', '沟通协作', '责任心', '抗压能力', '解决问题能力']
        fallback_jobs = build_fallback_job_matches(matched_jobs, top_k=4)
        default_analysis = {
            "overallScore": 75,
            "personalityType": "综合型人才",
            "summary": "用户综合素质良好，具备较强的学习能力和发展潜力。",
            "dimensionScores": quiz_ten_dims,
            "dimensionAnalysis": {d: f"{d}得分{quiz_ten_dims[d]}分，表现{'优秀' if quiz_ten_dims[d] >= 8 else '良好' if quiz_ten_dims[d] >= 6 else '一般'}。" for d in ten_dims},
            "strengths": ["学习能力较强", "综合素质良好"],
            "weaknesses": ["可进一步提升专业技能"],
            "jobMatches": fallback_jobs,
            "suggestions": [
                {"title": "提升专业技能", "content": "针对目标岗位，系统学习核心技术和工具，积累实战经验。", "priority": 1},
                {"title": "增加项目经验", "content": "通过实习或个人项目，积累实际工作经验和作品集。", "priority": 2},
                {"title": "拓展行业视野", "content": "关注行业动态，了解目标岗位的最新发展趋势和要求。", "priority": 3}
            ]
        }
        
        if user_id:
            save_history_record(
                user_id=user_id,
                record_type='quiz',
                title='职业测评分析',
                content={
                    'dimension_scores': normalized_scores,
                    'analysis_result': default_analysis
                }
            )
        
        return jsonify({
            "success": True,
            "data": default_analysis
        })

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({"status": "ok", "service": "智绘青春AI服务"})


# ==========================================
# KG4Career岗位画像API
# ==========================================

# 岗位画像维度定义
STANDARD_DIMENSIONS = [
    "获奖情况", "专业技能", "学历证书", "学习成绩", "实习经历"
]

ABSTRACT_DIMENSIONS = [
    "创新能力", "沟通协作", "责任心", "抗压能力", "解决问题能力"
]

ALL_DIMENSIONS = STANDARD_DIMENSIONS + ABSTRACT_DIMENSIONS

# ==========================================
# 用户管理API
# ==========================================

@app.route('/api/auth/register', methods=['POST'])
def register():
    """用户注册"""
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    if not all([username, email, password]):
        return jsonify({"success": False, "error": "用户名、邮箱和密码都是必需的"})
    
    if User.query.filter_by(username=username).first():
        return jsonify({"success": False, "error": "用户名已存在"})
    
    if User.query.filter_by(email=email).first():
        return jsonify({"success": False, "error": "邮箱已被注册"})
    
    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password)
    )
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        "success": True,
        "data": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "created_at": user.created_at.isoformat()
        }
    })

@app.route('/api/auth/login', methods=['POST'])
def login():
    """用户登录"""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not all([username, password]):
        return jsonify({"success": False, "error": "用户名和密码都是必需的"})
    
    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"success": False, "error": "用户名或密码错误"})
    
    return jsonify({
        "success": True,
        "data": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "created_at": user.created_at.isoformat()
        }
    })

@app.route('/api/files/upload', methods=['POST'])
def upload_file():
    """文件上传"""
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "没有文件"})
    
    file = request.files['file']
    user_id = request.form.get('user_id')
    
    if not user_id:
        return jsonify({"success": False, "error": "用户ID是必需的"})
    
    if file.filename == '':
        return jsonify({"success": False, "error": "没有选择文件"})
    
    if file:
        filename = secure_filename(file.filename)
        # 生成唯一文件名
        unique_filename = f"{uuid.uuid4()}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        file.save(file_path)
        
        # 保存到数据库
        user_file = UserFile(
            user_id=user_id,
            filename=unique_filename,
            original_filename=filename,
            file_path=file_path,
            file_type=file.content_type or 'application/octet-stream',
            file_size=os.path.getsize(file_path)
        )
        
        db.session.add(user_file)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "data": {
                "id": user_file.id,
                "filename": user_file.original_filename,
                "file_type": user_file.file_type,
                "file_size": user_file.file_size,
                "uploaded_at": user_file.uploaded_at.isoformat()
            }
        })

@app.route('/api/files/<user_id>', methods=['GET'])
def get_user_files(user_id):
    """获取用户文件列表"""
    files = UserFile.query.filter_by(user_id=user_id).order_by(UserFile.uploaded_at.desc()).all()
    
    return jsonify({
        "success": True,
        "data": [{
            "id": f.id,
            "filename": f.original_filename,
            "file_type": f.file_type,
            "file_size": f.file_size,
            "uploaded_at": f.uploaded_at.isoformat()
        } for f in files]
    })

@app.route('/api/history/<user_id>', methods=['GET'])
def get_user_history(user_id):
    """获取用户历史记录"""
    records = HistoryRecord.query.filter_by(user_id=user_id).order_by(HistoryRecord.created_at.desc()).all()
    
    return jsonify({
        "success": True,
        "data": [{
            "id": r.id,
            "record_type": r.record_type,
            "title": r.title,
            "content": json.loads(r.content) if r.content else {},
            "file_id": r.file_id,
            "created_at": r.created_at.isoformat()
        } for r in records]
    })

def save_history_record(user_id, record_type, title, content, file_id=None):
    """保存历史记录的辅助函数"""
    record = HistoryRecord(
        user_id=user_id,
        file_id=file_id,
        record_type=record_type,
        title=title,
        content=json.dumps(content, ensure_ascii=False)
    )
    db.session.add(record)
    db.session.commit()
    return record


def count_tokens(text):
    """计算文本token数（粗略估算：中文1字符≈1.5token，英文1词≈1.3token）"""
    if not text:
        return 0
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars * 1.5 + other_chars * 1.3)


def estimate_tokens_for_jobs(jobs):
    """估算一批岗位数据的token数"""
    total = 0
    for job in jobs:
        job_text = f"{job.get('name','')}{job.get('company','')}{job.get('description','')}{job.get('requirement','')}{','.join(job.get('skills',[]))}"
        total += count_tokens(job_text)
    return total


def generate_profile_prompt(jobs):
    """生成岗位画像的prompt"""
    system_prompt = """你是一个专业的HR专家和岗位分析师。请根据岗位的描述和要求，为每个岗位生成画像评分。

评分维度（共10个，满分10分）：
【标准化指标】（从岗位描述中可客观提取）：
1. 获奖情况 - 岗位对荣誉/奖励的重视程度
2. 专业技能 - 岗位对专业技术能力的要求
3. 学历证书 - 岗位对学历和证书的要求
4. 学习成绩 - 岗位对学术成绩的重视程度
5. 实习经历 - 岗位对实践经验的要求

【抽象化指标】（需要从岗位描述推断）：
6. 创新能力 - 岗位对创新思维的要求
7. 沟通协作 - 岗位对沟通和团队协作的要求
8. 责任心 - 岗位对责任感和可靠性的要求
9. 抗压能力 - 岗位对高压环境下工作的要求
10. 解决问题能力 - 岗位对问题解决能力的要求

请以JSON数组格式返回，每个岗位返回一个对象：
[{"id": 岗位id, "profile": {"获奖情况":分数, "专业技能":分数, ...}}, ...]

只返回JSON，不要有其他内容。"""

    # 构建岗位信息文本
    jobs_text = []
    for job in jobs:
        job_info = {
            "id": job.get("id"),
            "name": job.get("name", ""),
            "company": job.get("company", ""),
            "description": job.get("description", ""),
            "requirement": job.get("requirement", ""),
            "skills": job.get("skills", []),
            "education": job.get("education", ""),
            "experience": job.get("experience", "")
        }
        jobs_text.append(json.dumps(job_info, ensure_ascii=False))
    
    user_prompt = "请分析以下岗位并生成画像评分：\n" + "\n---\n".join(jobs_text)
    
    return system_prompt, user_prompt


@app.route('/api/job-profiles/batch', methods=['POST'])
def generate_job_profiles_batch():
    """批量生成岗位画像（自动分批，确保每次≤128k tokens）"""
    data = request.json
    jobs = data.get('jobs', [])
    
    if not jobs:
        return jsonify({"success": False, "error": "没有岗位数据"})
    
    # 128k tokens 的安全阈值（约100k tokens）
    MAX_TOKENS = 100000
    MARGIN = 5000  # 预留空间
    
    # 分批处理
    batches = []
    current_batch = []
    current_tokens = 0
    
    for job in jobs:
        job_tokens = estimate_tokens_for_jobs([job]) + 2000  # 估算prompt overhead
        if current_tokens + job_tokens > MAX_TOKENS - MARGIN and current_batch:
            batches.append(current_batch)
            current_batch = [job]
            current_tokens = job_tokens
        else:
            current_batch.append(job)
            current_tokens += job_tokens
    
    if current_batch:
        batches.append(current_batch)
    
    all_profiles = []
    batch_results = []
    
    for i, batch in enumerate(batches):
        system_prompt, user_prompt = generate_profile_prompt(batch)
        
        # 调用API
        result = call_qwen_plus(user_prompt, system_prompt)
        
        # 解析结果
        try:
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                result = result.split("```")[1].split("```")[0]
            
            profiles = json.loads(result)
            all_profiles.extend(profiles)
            batch_results.append({
                "batch": i + 1,
                "total_batches": len(batches),
                "jobs_count": len(batch),
                "success": True
            })
        except Exception as e:
            batch_results.append({
                "batch": i + 1,
                "total_batches": len(batches),
                "jobs_count": len(batch),
                "success": False,
                "error": str(e)
            })
            # 使用默认评分
            for job in batch:
                all_profiles.append({
                    "id": job.get("id"),
                    "profile": {dim: 5.0 for dim in ALL_DIMENSIONS}
                })
    
    return jsonify({
        "success": True,
        "data": {
            "profiles": all_profiles,
            "batch_info": batch_results,
            "total_jobs": len(jobs),
            "total_batches": len(batches)
        }
    })


@app.route('/api/job-profiles/single', methods=['POST'])
def generate_job_profile_single():
    """为单个岗位生成画像"""
    data = request.json
    job = data.get('job', {})
    
    if not job:
        return jsonify({"success": False, "error": "没有岗位数据"})
    
    system_prompt = """你是一个专业的HR专家和岗位分析师。请根据岗位的描述和要求，为岗位生成画像评分。

评分维度（共10个，满分10分）：
【标准化指标】：
1. 获奖情况 - 岗位对荣誉/奖励的重视程度
2. 专业技能 - 岗位对专业技术能力的要求
3. 学历证书 - 岗位对学历和证书的要求
4. 学习成绩 - 岗位对学术成绩的重视程度
5. 实习经历 - 岗位对实践经验的要求

【抽象化指标】：
6. 创新能力 - 岗位对创新思维的要求
7. 沟通协作 - 岗位对沟通和团队协作的要求
8. 责任心 - 岗位对责任感和可靠性的要求
9. 抗压能力 - 岗位对高压环境下工作的要求
10. 解决问题能力 - 岗位对问题解决能力的要求

请以JSON格式返回：
{"id":岗位id, "name":"岗位名称", "profile":{"获奖情况":分数, "专业技能":分数, ...}}

只返回JSON，不要有其他内容。"""

    job_info = {
        "id": job.get("id"),
        "name": job.get("name", ""),
        "company": job.get("company", ""),
        "description": job.get("description", ""),
        "requirement": job.get("requirement", ""),
        "skills": job.get("skills", []),
        "education": job.get("education", ""),
        "experience": job.get("experience", "")
    }
    
    user_prompt = f"请分析以下岗位并生成画像评分：\n{json.dumps(job_info, ensure_ascii=False)}"
    
    result = call_qwen_plus(user_prompt, system_prompt)
    
    try:
        if "```json" in result:
            result = result.split("```json")[1].split("```")[0]
        elif "```" in result:
            result = result.split("```")[1].split("```")[0]
        
        profile = json.loads(result)
        return jsonify({
            "success": True,
            "data": profile
        })
    except Exception as e:
        # 返回默认评分
        return jsonify({
            "success": True,
            "data": {
                "id": job.get("id"),
                "name": job.get("name", ""),
                "profile": {dim: 5.0 for dim in ALL_DIMENSIONS},
                "note": "使用默认评分"
            }
        })


@app.route('/api/job-profiles/init', methods=['POST'])
def init_all_profiles():
    """初始化所有岗位画像（用于首次生成，会分批处理）"""
    data = request.json
    jobs = data.get('jobs', [])
    
    if not jobs:
        return jsonify({"success": False, "error": "没有岗位数据"})
    
    # 返回分批信息，让前端可以分批请求
    MAX_TOKENS = 100000
    batches = []
    current_batch = []
    current_tokens = 0
    
    for job in jobs:
        job_tokens = estimate_tokens_for_jobs([job]) + 2000
        if current_tokens + job_tokens > MAX_TOKENS and current_batch:
            batches.append(current_batch)
            current_batch = [job]
            current_tokens = job_tokens
        else:
            current_batch.append(job)
            current_tokens += job_tokens
    
    if current_batch:
        batches.append(current_batch)
    
    return jsonify({
        "success": True,
        "data": {
            "total_jobs": len(jobs),
            "total_batches": len(batches),
            "batches": [{"index": i, "count": len(b)} for i, b in enumerate(batches)]
        }
    })


@app.route('/api/dimensions', methods=['GET'])
def get_dimensions():
    """获取岗位画像维度定义"""
    return jsonify({
        "success": True,
        "data": {
            "standard": [{"name": d, "category": "标准化指标"} for d in STANDARD_DIMENSIONS],
            "abstract": [{"name": d, "category": "抽象化指标"} for d in ABSTRACT_DIMENSIONS],
            "all": [{"name": d, "category": "标准化指标" if d in STANDARD_DIMENSIONS else "抽象化指标"} for d in ALL_DIMENSIONS]
        }
    })


# ========== 三大技术架构新增 API ==========

# 混合检索 API
@app.route('/api/search/hybrid', methods=['POST'])
def hybrid_search():
    """LSH + FAISS 混合检索接口"""
    try:
        from backend.services.retrieval_service import get_retrieval_service
        from backend.services.embedding_service import build_hybrid_vector
        import numpy as np
        
        data = request.json
        query = data.get('query', '')
        query_type = data.get('type', 'text')  # text | skills | resume
        top_k = data.get('top_k', 5)
        
        retrieval = get_retrieval_service()
        
        # 懒加载索引
        if not retrieval.is_ready():
            from backend.utils.lsh_indexer import LSHIndexer
            from backend.utils.faiss_indexer import FAISSIndexer
            from backend.utils.data_loader import load_jobs_data
            
            try:
                retrieval.lsh.load()
                retrieval.faiss.load()
                retrieval.cache_jobs(load_jobs_data())
                print("[HybridSearch] 索引懒加载成功")
            except Exception as e:
                return jsonify({"success": False, "error": f"索引未构建: {str(e)}"})
        
        if query_type == 'skills':
            skills = data.get('skills', [])
            results = retrieval.search_by_skills(skills, top_k=top_k)
        elif query_type == 'resume':
            profile = data.get('profile', {})
            profile_vec = list(profile.values()) if profile else None
            results = retrieval.search_by_resume(query, profile_vec, top_k=top_k)
        else:
            results = retrieval.search(query, top_k=top_k)
        
        return jsonify({
            "success": True,
            "data": {
                "query": query,
                "type": query_type,
                "count": len(results),
                "results": results
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/search/debug', methods=['GET'])
def search_debug():
    """检索系统调试信息"""
    try:
        from backend.services.retrieval_service import get_retrieval_service
        retrieval = get_retrieval_service()
        info = retrieval.get_debug_info()
        return jsonify({"success": True, "data": info})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# 知识图谱 API
@app.route('/api/kg/query', methods=['POST'])
def kg_query():
    """GraphRAG 查询接口"""
    try:
        from backend.services.kg_service import get_kg_service
        
        data = request.json
        query_type = data.get('query_type', 'job_network')
        params = data.get('params', {})
        
        kg = get_kg_service()
        if not kg.is_connected:
            return jsonify({"success": False, "error": "知识图谱未加载，请先运行构建脚本"})
        
        results = kg.query_graph_rag(query_type, **params)
        return jsonify({"success": True, "data": results})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/kg/stats', methods=['GET'])
def kg_stats():
    """知识图谱统计信息"""
    try:
        from backend.services.kg_service import get_kg_service
        kg = get_kg_service()
        if not kg.is_connected:
            return jsonify({"success": False, "error": "知识图谱未加载，请先运行构建脚本"})
        stats = kg.get_stats()
        return jsonify({"success": True, "data": stats})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/kg/job-network/<job_name>', methods=['GET'])
def kg_job_network(job_name):
    """获取岗位关联网络"""
    try:
        from backend.services.kg_service import get_kg_service
        kg = get_kg_service()
        if not kg.is_connected:
            return jsonify({"success": False, "error": "知识图谱未加载，请先运行构建脚本"})
        
        results = kg.query_graph_rag("job_network", job_name=job_name)
        return jsonify({"success": True, "data": results})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# 冷启动 API
@app.route('/api/cold-start/predict', methods=['POST'])
def cold_start_predict():
    """冷启动画像补全"""
    try:
        from backend.services.gnn_service import get_cold_start_service
        
        data = request.json
        school = data.get('school', '')
        major = data.get('major', '')
        skills = data.get('skills', [])
        gpa = data.get('gpa', '')
        
        service = get_cold_start_service()
        profile = service.predict_profile(school, major, skills, gpa)
        
        return jsonify({
            "success": True,
            "data": {
                "profile": profile,
                "is_predicted": service.is_ready()
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/gnn/status', methods=['GET'])
def gnn_status():
    """GNN 模型状态"""
    try:
        from backend.services.gnn_service import get_cold_start_service
        from backend.config import TRANSE_MODEL_PATH, RGCN_MODEL_PATH
        
        service = get_cold_start_service()
        return jsonify({
            "success": True,
            "data": {
                "transe_ready": service.transe is not None,
                "rgcn_ready": service.rgcn is not None,
                "transe_model_exists": TRANSE_MODEL_PATH.exists(),
                "rgcn_model_exists": RGCN_MODEL_PATH.exists(),
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# RAG 调试 API
@app.route('/api/rag/context', methods=['POST'])
def rag_context():
    """获取 RAG 上下文（调试用）"""
    try:
        from backend.services.rag_service import get_rag_service
        
        data = request.json
        query_type = data.get('query_type', 'resume_analysis')
        user_info = data.get('userInfo', {})
        analysis_result = data.get('analysisResult', {})
        
        rag = get_rag_service()
        context = rag.retrieve(query_type, user_info, analysis_result)
        
        return jsonify({
            "success": True,
            "data": {
                "context_text": context.to_prompt_context(),
                "retrieved_jobs": context.retrieved_jobs,
                "kg_paths": context.kg_paths,
                "sources": context.sources,
                "estimated_tokens": context.estimate_tokens(),
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ========== 静态文件服务 ==========

@app.route('/')
def serve_index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    if path.startswith('api/'):
        abort(404)
    full_path = os.path.join(BASE_DIR, path)
    if os.path.exists(full_path) and os.path.isfile(full_path):
        return send_from_directory(BASE_DIR, path)
    abort(404)

# ========== 主程序入口 ==========

def open_browser():
    webbrowser.open('http://127.0.0.1:5000/')

if __name__ == '__main__':
    # 创建数据库表
    with app.app_context():
        db.create_all()
        print("数据库表已创建")
    
    print("=" * 60)
    print("智绘青春 - 职业规划智能体")
    print("KG4Career 知识图谱 + LSH+FAISS 混合检索 + Agentic RAG + TransE/R-GCN")
    print("=" * 60)
    print("服务启动中，稍后自动打开浏览器...")
    print("=" * 60)
    
    Timer(1.5, open_browser).start()
    app.run(host='0.0.0.0', port=5000, debug=False)
