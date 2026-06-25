【文件夹作用】
本文件夹为构建脚本目录，提供索引构建、知识图谱构建及图神经网络模型训练等一键化初始化能力。

【各文件描述】
- init_all.py：一键初始化脚本，按顺序执行索引构建与知识图谱构建任务。
- build_indices.py：构建LSH + FAISS混合检索索引的脚本。
- build_kg.py：构建Neo4j知识图谱的脚本，将岗位画像数据导入图数据库。
- build_gnn.py：训练TransE + R-GCN图神经网络模型的脚本。
- __init__.py：Python包初始化文件。
