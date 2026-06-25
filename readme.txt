================================================================================
                         智绘青春 - 职业规划智能体
================================================================================

【文件夹作用】
本文件夹是"智绘青春 - 职业规划智能体"项目的完整代码包，基于 KG4Career 
岗位画像生成系统构建。项目融合了大语言模型（通义千问）、知识图谱、
向量检索（LSH+FAISS）、图神经网络（GNN）等前沿技术，为用户提供个性化
的职业规划分析、岗位推荐、能力评估与成长路径规划服务。

技术架构涵盖：
- Agentic RAG + GraphRAG 混合检索
- LSH + FAISS 向量索引
- TransE + R-GCN 知识图谱嵌入
- React 前端 + Flask 后端

================================================================================
                              文件说明
================================================================================

【前端文件】

  index.html          - 前端主页面。基于 React 18 构建的单页面应用，
                        采用黄绿色青春活力主题设计。包含用户系统、简历
                        上传、岗位探索、智能分析、职业规划报告等核心
                        功能模块。通过 CDN 引入 React、ECharts、
                        PDF.js 等第三方库。

  api.js              - 前端 API 调用模块。封装了与后端 Flask 服务的
                        通信接口，采用四组件架构（感知→推理→决策→行动）
                        驱动智能交互。

  jobs_data.js        - 前端岗位数据脚本。包含大量岗位信息的 JavaScript
                        变量，用于前端展示岗位列表和详情。

  job_profiles.js     - 前端岗位画像数据脚本。包含各岗位的十维画像数据
                        （薪资、技能、学历、性格匹配度等），供前端直接引用。

【后端文件】

  backend.py          - Flask 后端主服务入口。提供用户注册/登录、简历
                        解析、岗位推荐、职业规划报告生成、历史记录管理等
                        RESTful API 接口。集成通义千问大模型进行智能分析。

  init_db.py          - 数据库初始化脚本。创建 SQLite 数据库表结构
                        （用户表、文件表、历史记录表），并可生成默认
                        管理员账号。

  convert_profiles.py - 数据格式转换工具。将 JSON 格式的岗位画像数据
                        转换为前端可直接引用的 JavaScript 文件。

  requirements.txt    - Python 依赖清单。包含 Flask、Flask-CORS、
                        FAISS、sentence-transformers、PyTorch、
                        torch-geometric、Neo4j 驱动、scikit-learn 等。

【数据文件】

  jobs_data.json      - 岗位原始数据（JSON 格式）。与 jobs_data.js 
                        内容对应，供后端模块读取和处理。

  job_profiles.json   - 岗位画像数据（JSON 格式）。各岗位的十维特征
                        画像，用于知识图谱构建和推荐计算。

  job_profiles_data.json - 岗位画像的完整数据集（含维度定义）。
                           是生成 job_profiles.js 的源数据。

  job_profiles_data.js   - 岗位画像数据的轻量版 JS 脚本。

【backend/ 子目录】

  backend/config.py          - 全局配置文件。定义向量维度、FAISS/LSH
                               参数、Neo4j 连接信息、LLM API 配置、
                               GNN 训练参数等。

  backend/__init__.py        - Python 包初始化文件。

  backend/models/
    kg_schema.py             - 知识图谱 Schema 定义。包含岗位、技能、
                               公司、行业等实体类型及关系定义。

  backend/services/
    embedding_service.py     - 文本嵌入服务。基于 sentence-transformers
                               生成岗位描述和简历的向量表示。
    retrieval_service.py     - 混合检索服务。整合 LSH 粗筛与 FAISS
                               精排，实现高效的相似岗位检索。
    rag_service.py           - Agentic RAG 服务。多轮检索增强生成，
                               支持上下文感知的智能问答与报告生成。
    kg_service.py            - 知识图谱服务。提供 Neo4j 图数据库的
                               查询、路径分析、子图检索等功能。
    gnn_service.py           - 图神经网络服务。基于 TransE 和 R-GCN
                               实现知识图谱嵌入与推理。

  backend/scripts/
    init_all.py              - 一键初始化脚本。顺序执行索引构建和
                               知识图谱构建。
    build_indices.py         - 构建 LSH + FAISS 混合检索索引。
    build_kg.py              - 构建 Neo4j 知识图谱。
    build_gnn.py             - 训练 TransE + R-GCN 图神经网络模型。

  backend/utils/
    data_loader.py           - 数据加载工具。统一读取岗位数据和画像数据。
    faiss_indexer.py         - FAISS 索引工具。支持 HNSWFlat、IVFFlat
                               等多种索引结构的构建与查询。
    lsh_indexer.py           - LSH 索引工具。基于 MinHash 实现快速
                               近似最近邻检索。

  backend/data/
    vectors/job_vectors.pkl      - 预计算的岗位向量（供 FAISS 使用）。
    indices/faiss.index          - FAISS 向量索引文件。
    indices/lsh_index.pkl        - LSH 哈希索引文件。
    models/transe_model.pt       - TransE 知识图谱嵌入模型。
    models/rgcn_model.pt         - R-GCN 图神经网络模型。
    models/gnn_metadata.pkl      - GNN 模型元数据。
    kg_graph.pkl                 - 序列化后的知识图谱对象。

================================================================================
                              快速启动
================================================================================

1. 安装依赖：    pip install -r requirements.txt
2. 初始化数据库： python init_db.py
3. 构建索引：    python -m backend.scripts.init_all  （可选，首次运行）
4. 启动服务：    python backend.py
5. 访问页面：    浏览器打开 index.html

================================================================================
