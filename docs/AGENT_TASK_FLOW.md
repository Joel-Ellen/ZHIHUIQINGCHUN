# 智绘青春 — Agent 任务流全景图

> 本文档梳理"智绘青春"职业规划智能体项目的完整 Agent 任务流，
> 覆盖**原始 Python 全栈架构**与**重构后苍穹低代码 + AI Agent + Java 微服务架构**两条链路。

---

## 一、架构总览

```text
┌─────────────────────────────────────────────────────────────────────┐
│                    智绘青春 Agent 任务流                              │
│                                                                     │
│  用户入口 (Web桌面端 / 移动H5端)                                      │
│       │                                                             │
│       ▼                                                             │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐                        │
│  │ 简历上传  │   │ 职业测评  │   │ 岗位探索  │    ◄── 三大人机交互入口   │
│  └────┬─────┘   └────┬─────┘   └────┬─────┘                        │
│       │               │               │                             │
│       └───────────────┼───────────────┘                             │
│                       ▼                                             │
│         ┌─────────────────────────┐                                 │
│         │   AI自主规划智能体 (ReAct) │   ◄── 核心Agent引擎            │
│         │   zhc_career_expert      │                                 │
│         └───────────┬─────────────┘                                 │
│                     │                                               │
│     ┌───────────────┼───────────────┐                               │
│     ▼               ▼               ▼                               │
│ ┌───────┐   ┌───────────┐   ┌───────────┐                          │
│ │文档解析│   │ 知识库检索 │   │ 十维画像   │   ◄── 工具链 (Tools)     │
│ │ 工具  │   │zhc_job_kb │   │ 匹配评估   │                          │
│ └───┬───┘   └─────┬─────┘   └─────┬─────┘                          │
│     │             │               │                                  │
│     └─────────────┼───────────────┘                                  │
│                   ▼                                                 │
│     ┌─────────────────────────┐                                     │
│     │ 知识图谱二阶拓扑强化      │   ◄── Java CareerGraphService       │
│     │ (BFS 隐性技能发现)       │                                     │
│     └───────────┬─────────────┘                                     │
│                 ▼                                                   │
│     ┌─────────────────────────┐                                     │
│     │ 报告生成 & 异步持久化     │   ◄── SaveServiceHelper → PostgreSQL │
│     └───────────┬─────────────┘                                     │
│                 ▼                                                   │
│     ┌─────────────────────────┐                                     │
│     │ 前端渲染报告 + TreeView   │   ◄── 用户查看结果                   │
│     └─────────────────────────┘                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、Agent 任务流详细阶段

### 阶段 0：系统初始化 (离线)

| 步骤 | 原始 Python 实现 | 重构苍穹实现 | 说明 |
|------|-----------------|-------------|------|
| 0.1 数据清洗 | `convert_profiles.py` 将 `job_profiles.json` 转为 `job_profiles.js` | 本地 Python 脚本拆分 `jobs_data.json` (8300+条) 为独立 `.txt` 平面文件 | 每个岗位一个文件 |
| 0.2 知识库导入 | - | 将 `.txt` 文件群导入苍穹企业知识库 `zhc_job_kb` | 绑定 `BAAI/BGE-M3-Embedding` 向量化 |
| 0.3 索引构建 | `build_indices.py` → FAISS + LSH 索引文件 | 苍穹内置切片策略：1500字符/块，10%重叠 | 混合检索 (向量+BM25) |
| 0.4 知识图谱 | `build_kg.py` → NetworkX 图 → `kg_graph.pkl` | `CareerGraphService.buildGraph()` 内存邻接表 | 技能共现关系建边 |
| 0.5 GNN训练 | `build_gnn.py` → TransE + R-GCN 模型 | BFS 两跳邻居算法替代 GNN 推理 | 冷启动场景无需GPU |
| 0.6 知识库配置 | - | 切片策略、Reranker (`BGE-Reranker-V2-M3`)、相似度阈值 0.65、Top-K 8 | 一次配置持久生效 |

---

> 📋 **苍穹表单设计器配置指南**: 如果需要在实际平台中逐字段配置"简历识别"页面，请参照独立参考卡 → [简历识别_表单配置参考卡.md](简历识别_表单配置参考卡.md)

### 阶段 1：用户交互入口 → 触发 Agent

```
┌───────────────────┐        ┌───────────────────┐
│   Web 桌面端       │        │   移动端 H5         │
│ zc_history_record  │        │ zc_history_record   │
│       _web         │        │       _mobile       │
└────────┬──────────┘        └────────┬──────────┘
         │                            │
         │  用户操作流程:               │
         │  ① 选择记录类型              │
         │     (analysis/report/quiz)  │
         │  ② 上传简历文件              │
         │     (PDF/Word/图片)          │
         │  ③ 点击 [🚀 开始AI分析]     │
         │                            │
         ▼                            ▼
```

#### 1.1 前端脚本交互链 (zc-history-record-web.js / zc-history-record-mobile.js)

| 交互编号 | 触发事件 | 执行逻辑 | 涉及控件 |
|---------|---------|---------|---------|
| **交互一** | `attachmentpanelap1.afterUpload` | ① 启用 AI 分析按钮 ② 提取文件名写入 `fk_filename_snapshot` 分录 ③ 若标题为空则自动填充 | `attachmentpanelap1`, `btnAIAnalyze`/`btnSendAI` |
| **交互二** | `fk_record_type.onValueChange` | ① `quiz` 类型 → 隐藏附件面板 + 禁用 AI 按钮 ② `analysis`/`report` → 显示附件面板 | `attachmentpanelap1`, `fk_record_type` |
| **交互三** | `btnAIAnalyze.onClick` / `btnSendAI.onClick` | **★ 核心触发点**：收集单据数据 → 调用 Agent API | `btnAIAnalyze`, `btnSendAI` |
| **交互四** | `btnExportPDF.onClick` | PDF 导出（预留，提示即将上线） | `btnExportPDF` |
| **交互五** (移动端) | `fabNew.onClick` | 悬浮按钮 → 跳转新增页面 | `fabNew` |

#### 1.2 Agent API 调用参数构建

```javascript
// 前端构建的 Agent 输入参数
const agentInput = {
    recordType: 'analysis' | 'report' | 'quiz',  // 记录类型
    title: 'xxx - 分析报告',                       // 报告标题
    fileUrls: ['https://...'],                     // 附件文件URL列表
    fileName: '张三_简历.pdf',                      // 文件名
    userId: 'U001',                                // 用户ID
    currentFid: 'xxx'                              // 当前单据FID
};

// 调用方式 (二选一):
// 方式A: 苍穹助手SDK
this.$api.callAgent({ agentCode: 'zhc_career_expert', input: agentInput });

// 方式B: HTTP直调
fetch('/kapi/v2/zhihuiqingchun/custom_agent_analyze', {
    method: 'POST',
    body: JSON.stringify(agentInput)
});
```

---

### 阶段 2：AI 自主规划智能体 (ReAct Agent) 核心执行

> **Agent 标识**: `zhc_career_expert`
> **类型**: AI 自主规划类型 (ReAct 模式)
> **LLM**: `qwen-plus` @ `https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`

```
                  ┌──────────────────────────┐
                  │   Agent System Prompt     │
                  │   角色: 职业规划专家        │
                  │   任务: 5步自主工作流       │
                  └──────────┬───────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
```

#### 2.1 [Step 1] 文档解析 — 简历内容提取

| 项目 | 原始 Python | 重构苍穹 |
|------|------------|---------|
| **工具** | `POST /api/parse-resume` → `call_qwen_plus()` | 金蝶复杂文档解析 V2 (`KdComplexDocExtractAction#complexDocExtract`) |
| **输入** | 简历 PDF/Word 文本内容 (截断至5000字) | 附件面板上传的文件 URL |
| **输出** | 结构化 JSON: name, school, major, degree, skills[], projects[], internships[] | 简历关键文本 (结构化提取结果) |
| **系统提示** | "你是一个专业的简历解析助手..." | 工具内置解析逻辑 |
| **容错** | 内容<10字返回400错误 | 工具级异常处理 |

#### 2.2 [Step 2] 技能评估 — 知识库检索

| 项目 | 原始 Python | 重构苍穹 |
|------|------------|---------|
| **工具** | `HybridRetrievalService`: LSH粗筛 → FAISS精排 | 企业知识库 `zhc_job_kb` |
| **检索流程** | ① 技能文本向量化 (paraphrase-multilingual-MiniLM-L12-v2, 384维) ② LSH MinHash 粗筛 (候选集=Top-K×10) ③ FAISS HNSWFlat 精排 (内积相似度) | ① 技能文本传入知识库 ② 混合检索: 向量 (BGE-M3) + BM25 ③ BGE-Reranker-V2-M3 重排序 ④ 相似度阈值 0.65, Top-K 8 |
| **输出** | 匹配的岗位列表 (id, name, company, salary, skills, match_score) | 检索到的岗位知识片段 (含来源标注) |
| **配置** | `RETRIEVAL_TOP_K=5`, `FAISS_EF_SEARCH=128` | 通用分块: 1500字符, 重叠10% |

#### 2.3 [Step 3] 十维画像匹配 — 能力评估

| 项目 | 原始 Python | 重构苍穹 |
|------|------------|---------|
| **评估维度** | 10维: awards(获奖), skills(技能), education(学历), gpa(成绩), internship(实习), innovation(创新), communication(沟通), responsibility(责任), pressure(抗压), problem(解决问题) | 同左 (System Prompt 中约束) |
| **评分范围** | 0-100 分制 (内部归一化为 0-10) | 0-10 分制 (直接使用) |
| **匹配算法** | 欧几里得距离 → 匹配度: `max(0, 100 - distance*10)` | Agent LLM 推理 + 知识库岗位画像对齐 |
| **五维能力** | technical, learning, communication, execution, creativity + overall | 同上 (System Prompt 约束) |

#### 2.4 [Step 4] 生成报告 — 结构化 JSON 输出

Agent 必须输出如下标准 JSON 结构：

```json
{
  "basicInfo": {
    "name": "张三", "school": "XX大学", "major": "计算机科学",
    "degree": "本科", "graduationYear": "2025", "gpa": "3.6",
    "skills": ["Java", "Spring", "MySQL"]
  },
  "abilityProfile": {
    "technical": 80, "learning": 85, "communication": 70,
    "execution": 75, "creativity": 72, "overall": 76,
    "tenDimensions": {
      "awards": 6, "skills": 8, "education": 7, "gpa": 7,
      "internship": 5, "innovation": 6, "communication": 7,
      "responsibility": 8, "pressure": 7, "problem": 8
    }
  },
  "jobMatches": [
    {
      "name": "Java开发工程师", "match": 85, "salary": "15-30K",
      "reason": "基于您的技能匹配度最高",
      "requirements": ["精通Java", "熟悉Spring框架", "数据库设计能力"],
      "growth": "初级 → 中级 → 高级 → 架构师"
    }
  ],
  "strengths": [
    { "type": "skill", "title": "技术基础扎实", "desc": "...", "score": 85 }
  ],
  "suggestions": [
    { "title": "深入学习Spring生态", "content": "...", "priority": 1,
      "category": "技能提升", "action": "开始学习" }
  ],
  "learningPath": [
    {
      "period": "入门期 0-1年", "duration": "1年",
      "title": "初级Java开发工程师", "company": "成长型互联网公司",
      "goal": "掌握企业级Java开发全流程...",
      "skills": ["Java SE", "Spring Boot", "MySQL", "Git"],
      "certificates": ["Oracle Java认证"],
      "salary": "8-12K",
      "milestones": ["完成首个商用项目", "通过试用期考核"],
      "items": [
        { "task": "完成Spring Boot实战课程", "status": "pending" }
      ]
    }
  ],
  "skillGapAnalysis": {
    "missing_skills": ["Docker", "微服务架构"],
    "recommended_courses": ["..."],
    "graphDiscoveredSkills": ["Kubernetes", "CI/CD"],
    "graphEnhanced": true
  },
  "summary": "综合来看，您在技术方面..."
}
```

#### 2.5 [Step 5] 异步保存 — 持久化到业务单据

| 项目 | 原始 Python | 重构苍穹 |
|------|------------|---------|
| **方式** | `save_history_record()` → Flask SQLAlchemy → SQLite | Agent 调用 OpenAPI 工具 → `CustomAgentCallbackPlugin.doCustomService()` → PostgreSQL |
| **调用链** | Agent 输出 JSON → 后端直接 `db.session.add()` | Agent → `/kapi/v2/zhihuiqingchun/custom_agent_callback` → `SaveServiceHelper.saveOperate()` |
| **单据结构** | `HistoryRecord` 表 (id, user_id, file_id, record_type, title, content, created_at) | 主表 `tk_zc_history_record` + 子表 `tk_zc_file_entry` |
| **双主键策略** | Python UUID (字符串) 作为物理主键 | `fid`(Long) 物理主键 + `fk_uuid`(String) 业务编码 |

---

### 阶段 3：Java 后端微服务增强处理

> 在数据落地前，由 Java 插件对 Agent 输出进行**二次加工强化**

```
Agent 输出 JSON
      │
      ▼
┌─────────────────────────────────────┐
│  CustomAgentCallbackPlugin           │
│  (/kapi/v2/zhihuiqingchun/           │
│        custom_agent_callback)        │
│                                      │
│  Step 1: 参数解析与校验               │
│     user_id, record_type, title,     │
│     content, skills[], file_id       │
│           │                          │
│  Step 2: 图谱二阶拓扑强化             │
│     CareerGraphService               │
│     .getTwoHopNeighbors(skills)      │
│           │                          │
│  Step 3: enrichContent()             │
│     注入 graphDiscoveredSkills       │
│     到 JSON content 中               │
│           │                          │
│  Step 4: 创建 KDDM 动态数据对象       │
│     DynamicObject + 基础资料引用      │
│           │                          │
│  Step 5: SaveServiceHelper           │
│     .saveOperate() → PostgreSQL      │
│           │                          │
│  Step 6: 返回 ApiResult              │
│     { recordId, discoveredSkills,    │
│       graphEnhanced }                │
└─────────────────────────────────────┘
      │
      ▼
  前端收到结果 → 刷新 TreeView → 展示报告
```

#### 3.1 知识图谱服务 (CareerGraphService.java)

| 步骤 | 操作 | 说明 |
|------|------|------|
| 初始化 | `buildGraph(jobSkillMap)` | 遍历所有岗位的技能列表，同一岗位内的技能两两建立无向边 (共现关系) |
| 数据结构 | `ConcurrentHashMap<String, Set<String>>` | 线程安全邻接表 |
| 核心算法 | `getTwoHopNeighbors(currentSkills)` | BFS 广度优先搜索，最大深度=2，排除已有技能 |
| 复杂度 | O(\|V\| + \|E\|) | 纯内存计算，无需查库 |
| 对比原系统 | 替代 TransE + R-GCN GNN 推理 | 冷启动无需 GPU，零模型加载时间 |

---

### 阶段 4：前端结果渲染与交互

#### 4.1 页面插件 (ZcHistoryRecordWebPlugin.java) 职责

| 生命周期 | 方法 | 功能 |
|---------|------|------|
| 注册监听 | `registerListener()` | 注册工具栏按钮点击监听 (`mainToolbar`) |
| 数据绑定后 | `afterBindData()` | ① `QFilter` 批量查用户历史记录 (前100条) ② Java Stream `groupingBy` 按 `fk_record_type` 分类 ③ 构建 TreeView 节点树 (analysis/report/quiz 三大类) |
| 按钮点击 | `itemClick()` | 拦截 `btnExportPDF` / `btnAIAnalyze` |
| 点击前拦截 | `beforeItemClick()` | PDF导出前置校验 |

#### 4.2 前端结果处理

```javascript
// 分析成功回调 (zc-history-record-web.js)
_onAnalysisSuccess(result) {
    this.$api.hideLoading();
    this.$api.setEnable(true, 'btnAIAnalyze');

    // 1. 刷新左侧TreeView导航树
    treeView.refresh();

    // 2. 展示成功消息 (含图谱发现技能数)
    const discoveredCount = result.discoveredSkills?.length || 0;
    // → "✅ AI分析完成！报告已保存，记录编号: xxx"
    // → "🔍 图谱发现 N 个隐性潜在技能"
}
```

---

## 三、全链路时序图

```text
时间轴 ──────────────────────────────────────────────────────────────────────►

用户        前端JS        苍穹Agent平台      Java插件        知识库/图谱      数据库
 │           │               │                │               │              │
 │ 上传简历  │               │                │               │              │
 ├──────────►│               │                │               │              │
 │           │ afterUpload   │                │               │              │
 │           │ →启用AI按钮    │                │               │              │
 │           │               │                │               │              │
 │ 点击AI分析│               │                │               │              │
 ├──────────►│               │                │               │              │
 │           │ callAgent()   │                │               │              │
 │           ├──────────────►│                │               │              │
 │           │               │ [ReAct Loop]   │               │              │
 │           │               │               │               │              │
 │           │               │ ① 文档解析      │               │              │
 │           │               ├───────────────────────────────────────────────┤
 │           │               │               │ KdComplexDocExtract          │
 │           │               │               │               │              │
 │           │               │ ② 技能评估      │               │              │
 │           │               ├───────────────────────────────┤              │
 │           │               │               │  zhc_job_kb   │              │
 │           │               │               │  混合检索      │              │
 │           │               │               │◄──────────────┤              │
 │           │               │               │               │              │
 │           │               │ ③ 十维画像匹配  │               │              │
 │           │               │  (LLM推理)     │               │              │
 │           │               │               │               │              │
 │           │               │ ④ 生成JSON报告  │               │              │
 │           │               │  (qwen-plus)   │               │              │
 │           │               │               │               │              │
 │           │               │ ⑤ 异步保存      │               │              │
 │           │               ├───────────────┤               │              │
 │           │               │               │ doCustomService              │
 │           │               │               │               │              │
 │           │               │               │ 图谱二阶强化   │              │
 │           │               │               ├──────────────►│              │
 │           │               │               │◄──────────────┤              │
 │           │               │               │               │              │
 │           │               │               │ enrichContent │              │
 │           │               │               │               │              │
 │           │               │               │ saveOperate   │              │
 │           │               │               ├──────────────────────────────►│
 │           │               │               │◄──────────────────────────────┤
 │           │               │               │               │              │
 │           │  onSuccess()  │               │               │              │
 │           │◄──────────────┤               │               │              │
 │           │               │               │               │              │
 │           │ 刷新TreeView  │               │               │              │
 │           │ 展示报告       │               │               │              │
 │◄──────────┤               │               │               │              │
 │           │               │               │               │              │
```

---

## 四、新旧架构映射关系总表

| 功能模块 | 原始 Python 实现 | 重构苍穹实现 | 重构类型 |
|---------|-----------------|-------------|---------|
| **数据持久化** | Flask SQLAlchemy + SQLite | KDDM 业务对象建模 + PostgreSQL | 零代码建模 |
| **用户界面** | `index.html` (React 18 SPA) + `api.js` | 页面设计器拖拽 + 前台 JS 脚本 | 低代码+轻量JS |
| **API 路由** | Flask `@app.route()` 手动注册 | 开放平台标准 API + `IBillWebApiPlugin` | 低代码配置+少量Java |
| **文档解析** | `POST /api/parse-resume` → `call_qwen_plus()` | 金蝶复杂文档解析 V2 (预置工具) | 零代码工具挂载 |
| **LLM 调用** | `call_qwen_plus()` 手写 HTTP 请求 | AI服务云配置中心 (自定义 Endpoint) | 零代码图形化对接 |
| **向量检索** | LSH (MinHash) + FAISS (HNSWFlat) 手写代码 | 企业知识库组件 (BGE-M3 + BM25 + Reranker) | 低代码配置托管 |
| **知识图谱** | NetworkX + TransE/R-GCN (PyTorch) | `CareerGraphService` (ConcurrentHashMap + BFS) | 高代码纯Java重构 |
| **Agent 控制** | `AgenticRAGService` (ReAct 手写循环) | AI 自主规划智能体 (System Prompt 托管) | 零代码Prompt驱动 |
| **岗位数据** | `jobs_data.json` (8300+条), `job_profiles.json` | 拆分为独立 `.txt` 导入企业知识库 | 数据清洗+零代码导入 |
| **画像匹配** | 欧几里得距离公式 (Python) | Agent LLM 推理 + 知识库画像对齐 | 推理模式转变 |
| **报告持久化** | `save_history_record()` (SQLAlchemy ORM) | `SaveServiceHelper.saveOperate()` (KDDM ORM) | Java微服务 |
| **前端状态管理** | React State + `api.js` 回调 | 苍穹 `$api` 控件 API (getModelValue/setModelValue) | 平台内置 |
| **部署方式** | `python backend.py` 手动启动 | 协同开发平台 (DCS) + CI/CD 轻轨线 | 云端一体化 |

---

## 五、核心文件索引

### 重构目标架构 (苍穹平台)

| 文件 | 路径 | 角色 |
|------|------|------|
| Web 桌面端脚本 | [frontend-scripts/zc-history-record-web.js](frontend-scripts/zc-history-record-web.js) | PC 端 4 大交互逻辑 |
| 移动端 H5 脚本 | [frontend-scripts/zc-history-record-mobile.js](frontend-scripts/zc-history-record-mobile.js) | 移动端 4 大交互逻辑 |
| 页面控制插件 | [java-src/.../plugin/ZcHistoryRecordWebPlugin.java](java-src/src/main/java/tk/zc/zhqc/plugin/ZcHistoryRecordWebPlugin.java) | TreeView 构建 + 工具栏事件 |
| 知识图谱服务 | [java-src/.../service/CareerGraphService.java](java-src/src/main/java/tk/zc/zhqc/service/CareerGraphService.java) | BFS 二阶邻居技能发现 |
| API 网关插件 | [java-src/.../openapi/CustomAgentCallbackPlugin.java](java-src/src/main/java/tk/zc/zhqc/openapi/CustomAgentCallbackPlugin.java) | Agent 回调接收 + 图谱增强 + 持久化 |

### 原始 Python 架构

| 文件 | 路径 | 角色 |
|------|------|------|
| Flask 主服务 | [backend.py](backend.py) | API 路由 + LLM 调用 + 数据匹配 |
| 前端 API 模块 | [api.js](api.js) | 四组件架构 (感知→推理→决策→行动) |
| RAG 服务 | [backend/services/rag_service.py](backend/services/rag_service.py) | Agentic RAG ReAct 循环 |
| 混合检索 | [backend/services/retrieval_service.py](backend/services/retrieval_service.py) | LSH+FAISS 两级检索 |
| 知识图谱 | [backend/services/kg_service.py](backend/services/kg_service.py) | NetworkX GraphRAG 查询 |
| GNN 服务 | [backend/services/gnn_service.py](backend/services/gnn_service.py) | TransE + R-GCN 嵌入推理 |
| 全局配置 | [backend/config.py](backend/config.py) | 向量维度/检索参数/LLM配置 |

### 表单配置参考

| 文件 | 说明 |
|------|------|
| [简历识别_表单配置参考卡.md](简历识别_表单配置参考卡.md) | **苍穹平台"简历识别"表单设计器逐字段填写指南**（控件布局 + 属性面板 + JS脚本 + Agent对接映射） |

### 设计文档

| 文件 | 说明 |
|------|------|
| [README.md](README.md) | 五阶段重构设计方案 (KDDM建模→UI→Agent→Java→映射矩阵) |
| [智绘青春_Linux服务器部署手册.md](智绘青春_Linux服务器部署手册.md) | 原始 Python 项目 Linux 部署指南 |
| [readme.txt](readme.txt) | 原始项目文件说明与快速启动 |
