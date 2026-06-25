【文件夹作用】
本文件夹为工具模块目录，提供统一的数据加载、FAISS索引管理和LSH索引管理等通用功能，供上层服务调用。

【各文件描述】
- data_loader.py：数据加载工具，统一读取岗位数据和画像数据，为模型训练与索引构建提供标准化数据接口。
- faiss_indexer.py：FAISS索引工具，支持HNSWFlat、IVFFlat等多种索引结构的构建与查询操作。
- lsh_indexer.py：LSH索引工具，基于MinHash实现快速的近似最近邻检索。
- __init__.py：Python包初始化文件。
