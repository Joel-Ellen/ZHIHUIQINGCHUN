【文件夹作用】
本文件夹为后端核心服务模块目录，封装了文本嵌入、混合检索、RAG问答、知识图谱查询及图神经网络推理等关键能力。

【各文件描述】
- embedding_service.py：文本嵌入服务，基于sentence-transformers生成岗位描述和简历的向量表示。
- retrieval_service.py：混合检索服务，整合LSH粗筛与FAISS精排，实现高效的相似岗位检索。
- rag_service.py：Agentic RAG服务，支持多轮检索增强生成，实现上下文感知的智能问答与报告生成。
- kg_service.py：知识图谱服务，提供Neo4j图数据库的查询、路径分析、子图检索等功能。
- gnn_service.py：图神经网络服务，基于TransE和R-GCN实现知识图谱嵌入与推理计算。
- __init__.py：Python包初始化文件。
