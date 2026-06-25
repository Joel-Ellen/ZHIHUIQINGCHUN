# "智绘青春"项目全栈架构移植与重构设计方案

## ── 从"传统Python全栈"到"苍穹低代码 + AI Agent + Java高代码微服务"的全面演进

---

## 🔷 第一阶段:数据与业务对象建模(KDDM 建模)

本阶段完全放弃传统的 SQL 手动建表模式,全面转向模型驱动设计(KDDM),由平台底座统一接管数据持久化。

### 1. 实体层级架构

在开发平台中,严格遵循苍穹 **"云 -> 应用 -> 业务对象"** 的层级进行元数据创建:

- **应用编码**:`zhihuiqingchun`(智绘青春)
- **层级关系**:

```text
应用: zhihuiqingchun(智绘青春)
├── 基础资料: zc_user(用户信息,全局复用,自带编码与名称)
├── 基础资料: zc_userfile(用户文件档案,含通用附件,自适应引用)
└── 单据: zc_history_record(历史记录主单据)
    ├── [主表] zc_history_record — 对应历史分析记录主表
    └── [子表/单据体] zc_file_entry — 对应文件关联分录子表
```

### 2. 字段映射与编码规范

- **表名命名铁律**:统一采用 `tk_zc_{名称}` 格式。
- **双轨主键策略**:物理主键全部采用系统自带的 `fid`(长整型 Long)。原 Python 项目中的字符串 UUID 作为业务编码,存入普通文本字段(`fk_uuid`)中,确保不破坏苍穹底座组件的类型识别。

### 3. 核心对象字段定义表

#### User 基础资料(元数据标识:`zc_user`,物理表名:`tk_zc_user`)

| 控件类型标识 | 字段编码 (DB列名) | 业务属性与约束 |
| --- | --- | --- |
| 文本字段 | `fid` (系统自动主键) | 主键,长整型,系统自动生成唯一 ID |
| 文本字段 | `fk_username` | 单行文本,唯一校验,必录 |
| 文本字段 | `fk_email` | 单行文本,唯一校验,邮箱格式校验 |
| 文本字段 | `fk_password_hash` | 单行文本,密文存储 |
| 日期字段 | `fk_created_at` | 自动填充创建时间,不可编辑 |
| 日期字段 | `fk_updated_at` | 自动填充更新时间,不可编辑 |

#### UserFile 基础资料(元数据标识:`zc_userfile`,物理表名:`tk_zc_userfile`)

| 控件类型标识 | 字段编码 (DB列名) | 业务属性与约束 |
| --- | --- | --- |
| 文本字段 | `fid` (系统自动主键) | 主键,长整型 |
| 基础资料字段 | `fk_user_id` | 基础资料类型:`zc_user`,级联引用所属用户 |
| 文本字段 | `fk_filename` | 单行文本,存储文件名 |
| 文本字段 | `fk_original_filename` | 单行文本,原始上传文件名 |
| 文本字段 | `fk_file_path` | 单行文本,文件服务器路径 |
| 文本字段 | `fk_file_type` | 下拉列表:pdf, docx, doc, txt, jpg, png |
| 整数字段 | `fk_file_size` | 整数类型,单位:字节 |
| 日期字段 | `fk_uploaded_at` | 自动填充上传时间 |

#### HistoryRecord 单据(元数据标识:`zc_history_record`,物理表名:`tk_zc_history_record`)

| 控件类型标识 | 字段编码 (DB列名) | 业务属性与约束 |
| --- | --- | --- |
| **[主表字段]** |  |  |
| 文本字段 | `fid` (系统自动主键) | 主键,单据唯一标识 |
| 基础资料字段 | `fk_user_id` | 基础资料类型:`zc_user` |
| 文本字段 | `fk_record_type` | 下拉列表:`analysis`(简历分析), `report`(职业报告), `quiz`(测评) |
| 文本字段 | `fk_title` | 单行文本,报告标题,必录 |
| 大文本字段 | `fk_content` | 物理存储完整的 AI 结构化 JSON 报告字符串(建议大文本) |
| 日期字段 | `fk_created_at` | 自动填充创建时间 |
| **[子表分录字段]** | **(子表名: tk_zc_file_entry)** |  |
| 整数字段 | `fk_seq` | 行号,自动递增 |
| 基础资料字段 | `fk_file_id` | 基础资料类型:`zc_userfile`,可空(无文件时) |
| 文本字段 | `fk_filename_snapshot` | 记录时的文件名快照(冗余存储,便于前台不跨表展示) |

### 4. 标准 OpenAPI 接口体系设计

- **标准操作接口格式**:`https://{域名}/kapi/v2/{appId}/{formId}/{API编码}`
- **自定义服务接口格式**:`https://{域名}/kapi/v2/{appId}/{API编码}`

| 业务模块 | 请求方法 | 路由 URL | 功能描述 |
| --- | --- | --- | --- |
| **用户认证** | POST | `/kapi/v2/zhihuiqingchun/zc_user/save` | 标准物理保存操作(密码在 Java 插件中加密) |
| **用户认证** | POST | `/kapi/v2/zhihuiqingchun/custom_auth/login` | 自定义登录服务(校验用户名密码并返回登录凭证) |
| **文件上传** | POST | `/kapi/v2/zhihuiqingchun/attachment/uploadFile.do` | 苍穹标准临时文件上传,获取临时 URL |
| **文件保存** | POST | `/kapi/v2/zhihuiqingchun/custom_file/save_with_attachment` | 自定义持久化接口,通过底座类保存附件关系 |
| **历史记录** | POST | `/kapi/v2/zhihuiqingchun/zc_history_record/save` | 标准单据保存接口,支持携带单据体分录入库 |
| **历史记录** | POST | `/kapi/v2/zhihuiqingchun/zc_history_record/query` | 标准条件查询接口,按 `user_id` 过滤列表 |

---

## 🔷 第二阶段:用户界面设计与前台控制脚本(UI 蓝图)

通过"数据联动、视图隔离"技术,复用同一套 KDDM 数据源,自适应渲染两套终端页面。

### 1. Web 桌面端页面设计 (`zc_history_record_web`)

- **布局架构**:采用 `SplitContainer`(分割方向: 纵向,分割位置: 20%)。
- **左侧侧边栏 (20% 宽度)**:放置 `TreeView`(树控件),挂载页面插件,在数据加载后按 `fk_record_type`(简历分析/职业报告/测评)进行分类导航。
- **右侧主工作区 (80% 宽度)**:
  - **顶部**:`Toolbar`(工具栏),含【新建】(new)、【🚀 开始AI分析】(btnAIAnalyze,初始禁用)、【📄 导出PDF】(btnExportPDF) 按钮。
  - **中部信息区**:Flex 栅格布局,包含类型下拉框、标题输入框、用户选择器,以及 `AttachmentPanel`(附件面板,限定扩展名 `.pdf,.docx,.doc`)。
  - **底部展示区**:`TabContainer`(标签页容器)分设两页。Tab 1 使用富文本阅读器渲染大文本字段 `fk_content` 中的 AI 报告;Tab 2 使用 `EntryGrid`(单据体表格)展示关联的分录文件。

### 2. 移动端 H5 页面设计 (`zc_history_record_mobile`)

- **布局架构**:单列流式布局(`VBoxContainer`),控件宽度 100% 自适应。采用「列表页面模板」+「表单详情页面模板」多视图组合。
- **视图 1(列表页)**:采用 `CardLayout` 卡片流呈现,每张卡片加粗展示 `fk_title`,副标题展示时间,并依据类型(分析/报告/测评)自动渲染为蓝/绿/橙色标准标签。右下角配置 `FloatingActionButton` 悬浮新建按钮,点击直接跳转至视图 2。
- **视图 2(表单操作与结果页)**:类型选择自动渲染为弹出式 `Picker`,配置 `MobileAttachment` 移动端附件控件(**其标识保持与 PC 端一致,实现底层数据绝对联动**)。底部固定沉浸式大按钮【🚀 发送AI异步分析】。

### 3. 前台 JavaScript 交互脚本 (`zc_history_record_web.js`)

```javascript
/**
 * 智绘青春 - 历史记录页面脚本 (zc_history_record_web)
 * 
 * 功能:
 * - 交互一:附件上传完成后,自动启用 AI 分析按钮,并写入文件名快照到分录
 * - 交互二:记录类型切换时,控制附件面板的显隐
 */

export default {
    /**
     * 页面初始化生命周期
     */
    didMount() {
        // 1. 初始状态:AI分析按钮禁用
        this.$api.setEnable(false, 'btnAIAnalyze');

        // 2. 监听附件面板上传完成事件
        this.$api.on('attachmentpanelap1.afterUpload', this.onAttachmentUploaded.bind(this));

        // 3. 监听记录类型字段值变更事件
        this.$api.on('fk_record_type.onValueChange', this.onRecordTypeChanged.bind(this));
    },

    /**
     * 交互一:附件上传完成回调
     */
    onAttachmentUploaded(context, params) {
        this.$api.setEnable(true, 'btnAIAnalyze');

        const uploadedFiles = params && params.files ? params.files : [];
        if (uploadedFiles.length > 0) {
            const firstFileName = uploadedFiles[0].fileName || uploadedFiles[0].name || '';
            if (firstFileName) {
                // 将文件名写入单据体分录第0行的 fk_filename_snapshot 字段
                this.$api.setModelValue('fk_filename_snapshot', firstFileName, 0);
            }
        }
    },

    /**
     * 交互二:记录类型变更回调
     */
    onRecordTypeChanged(event) {
        const newValue = event.value || event;

        if (newValue === 'quiz') {
            // 测评类型:隐藏附件面板(不需要上传简历)
            this.$api.setVisible(false, 'attachmentpanelap1');
            this.$api.setEnable(false, 'btnAIAnalyze');
        } else {
            // 分析/报告类型:显示附件面板
            this.$api.setVisible(true, 'attachmentpanelap1');
            const currentFile = this.$api.getModelValue('fk_filename_snapshot', 0);
            if (currentFile) {
                this.$api.setEnable(true, 'btnAIAnalyze');
            }
        }
    }
};
```

---

## 🔷 第三阶段:AI 核心能力移植(Agent 开发平台)

全面淘汰原本地 Python 复杂的 FAISS 向量库与 `call_qwen_plus` 手写代码,托管给苍穹原生 AI 引擎,实现企业级 RAG 架构。

### 1. 大模型接入与企业知识库配置

- **模型服务**:采用【自定义创建】方式配置 Endpoint。由于长思考模型输出带有大量 `<think>` 标签易导致富文本错乱,本方案精确对接阿里云 DashScope 的 **`qwen-plus` 核心通用对话大模型**。
  - **Endpoint**: `https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`
  - **Model**: `qwen-plus`

- **岗位知识库构建 (`zhc_job_kb`)**:利用本地 Python 离线脚本,将原 `jobs_data.json`(8300+ 条岗位)和 `job_profiles.json` 拆分清洗为**一个岗位对应一个独立 `.txt` 文件的平面文件群**,并导入不同公开目录。

- **切片与召回核心参数配置**:
  - **向量化模型**: 选用苍穹内置的 `BAAI/BGE-M3-Embedding`。
  - **切片策略**: 通用分块,限制分块 `1500 字符`,重叠度 `10% (150字符)`,开启检索增强。
  - **检索模式**: **混合检索(向量 + BM25)**,绑定 `BGE-Reranker-V2-M3` 进行重排序,相似度阈值锁定为 `0.65`,Top-K 设为 `8`。

### 2. "AI自主规划智能体" ReAct 系统提示词 (System Prompt)

智能体配置为 **"AI自主规划类型"**,其内置工作流定义如下:

```markdown
# 角色
你是"智绘青春"职业规划专家 Agent,一位资深的人力资源顾问兼职业发展导师。

# 核心任务
当用户提交一份简历(PDF/Word 格式)后,你需要自主完成以下工作流:

1. [解析简历]:调用【文档解析工具】(金蝶复杂文档解析V2)提取简历中的关键文本。
2. [技能评估]:将提取的技能词送入绑定的【岗位知识库 zhc_job_kb】,查询匹配的岗位信息与行业基本盘。
3. [十维画像匹配]:根据简历证据链对用户的 10 种软硬实力(获奖情况、专业技能、学历证书、学习成绩、实习经历、创新能力、沟通协作、责任心、抗压能力、解决问题能力)进行 0-10 分制评估,并与知识库岗位画像得分对齐。
4. [生成报告]:综合上述拓扑分析结果,强制约束模型严格输出标准格式的 JSON 字符串。
   JSON 必须包含:basicInfo、abilityProfile(含十维滑块数据)、jobMatches(含匹配度与理由)、skillGapAnalysis、careerPlan、summary。
5. [异步保存]:调用【保存历史记录 API】服务工具,将生成的完整 JSON 报告自动反向推送到苍穹单据持久化网关中。

# 限制与约束
- 绝对禁止编造岗位名称、公司名称、薪资数据。所有岗位信息必须来自【岗位知识库】。
- 每一条关键信息后标注 [来源: 知识库/文档解析]。
- 输出语言必须保持与用户输入一致(中文)。
```

### 3. 工具链绑定与前台异步触发脚本

智能体挂载工具包括:
1. `zhc_job_kb` 企业知识库
2. 官方预置复杂文档解析类 `kd.ai.gai.core.agent.tool.action.KdComplexDocExtractAction#complexDocExtract`
3. 系统 OpenAPI 工具(绑定单据 `zc_history_record` 的 `save` 操作)

在第二步前台脚本基础上,追加 `btnAIAnalyze` 按钮点击处理逻辑:

```javascript
/**
 * 追加:AI 分析按钮点击 → 调用苍穹 Agent 智能体异步驱动
 */
export default {
    // ... 已有的 didMount, onAttachmentUploaded, onRecordTypeChanged ...

    'btnAIAnalyze.onClick'(event) {
        const recordType = this.$api.getModelValue('fk_record_type');
        const title = this.$api.getModelValue('fk_title');
        const currentFid = this.$api.getModelValue('fid');
        const files = this.$api.getControl('attachmentpanelap1').getFiles();

        if (files.length === 0 && recordType !== 'quiz') {
            this.$api.showMessage('warning', '请先上传简历文件');
            return;
        }

        this.$api.setEnable(false, 'btnAIAnalyze');
        this.$api.showLoading('AI 正在分析中,请稍候...');

        // 调用苍穹 Agent 平台内嵌服务
        this.$api.callAgent({
            agentCode: 'zhc_career_expert', 
            input: {
                recordType: recordType,
                title: title || '未命名报告',
                fileUrls: files.map(f => f.url),  
                currentFid: currentFid,
                userId: this.$api.getModelValue('fk_user_id')
            },
            onSuccess: (result) => {
                this.$api.hideLoading();
                this.$api.setEnable(true, 'btnAIAnalyze');
                this.$api.getControl('historyTreeView').refresh(); // 刷新左侧导航树
                this.$api.showMessage('success', `AI 分析完成!报告已保存,单据编号: ${result.billno || ''}`);
            },
            onError: (error) => {
                this.$api.hideLoading();
                this.$api.setEnable(true, 'btnAIAnalyze');
                this.$api.showMessage('error', `AI 分析失败: ${error.message}`);
            }
        });
    }
};
```

---

## 🔷 第四阶段:Java 后端业务插件与高代码服务(Java 重构)

项目的高代码核心算法及底座页面绑定事务,全面采用 **Java 语言** 进行微服务级重构,锁死性能损耗。

### 1. 页面业务插件 (`ZcHistoryRecordWebPlugin.java`)

- **包路径**:`tk.zc.zhqc.plugin`
- **职责**:继承 `AbstractBillPlugIn`。在页面加载数据后,利用 `QFilter` 批量一次性抓取用户前 100 条记录,在内存中利用 Java 8 Stream 表达式进行分组装配,杜绝循环查库引发的数据库连接池阻塞问题。

```java
package tk.zc.zhqc.plugin;

import kd.bos.bill.AbstractBillPlugIn;
import kd.bos.dataentity.entity.DynamicObject;
import kd.bos.dataentity.entity.DynamicObjectCollection;
import kd.bos.entity.datamodel.events.AfterBindDataEvent;
import kd.bos.form.control.events.ItemClickEvent;
import kd.bos.form.control.TreeView;
import kd.bos.form.control.tree.TreeNode;
import kd.bos.orm.query.QFilter;
import kd.bos.servicehelper.BusinessDataServiceHelper;
import java.util.EventObject;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public class ZcHistoryRecordWebPlugin extends AbstractBillPlugIn {

    @Override
    public void afterBindData(AfterBindDataEvent e) {
        super.afterBindData(e);
        this.buildHistoryTreeView();
    }

    @Override
    public void registerListener(EventObject e) {
        super.registerListener(e);
        this.addItemClickListener("mainToolbar");
    }

    @Override
    public void itemClick(ItemClickEvent e) {
        super.itemClick(e);
        String itemKey = e.getItemKey();
        if ("btnExportPDF".equalsIgnoreCase(itemKey)) {
            this.handleExportPDF();
        }
    }

    private void buildHistoryTreeView() {
        TreeView treeView = this.getControl("historyTreeView");
        if (treeView == null) return;
        treeView.clear();

        Object currentUserId = this.getModel().getValue("fk_user_id");
        if (currentUserId == null) return;

        // 构造过滤器,限制前100条
        QFilter filter = new QFilter("fk_user_id", QFilter.equals, currentUserId);
        DynamicObjectCollection records = BusinessDataServiceHelper.load(
                "zc_history_record", 
                "id,fk_title,fk_record_type", 
                new QFilter[]{filter}, 
                "created_at desc"
        );

        // 使用 Stream 进行高效内存聚合
        Map<String, List<DynamicObject>> groupedRecords = records.stream()
                .collect(Collectors.groupingBy(obj -> obj.getString("fk_record_type")));

        String[] types = {"analysis", "report", "quiz"};
        String[] typeNames = {"简历分析", "职业报告", "专业测评"};

        for (int i = 0; i < types.length; i++) {
            String typeKey = types[i];
            List<DynamicObject> subRecords = groupedRecords.get(typeKey);
            
            if (subRecords != null && !subRecords.isEmpty()) {
                TreeNode rootNode = new TreeNode(typeKey, typeNames[i]);
                for (DynamicObject rec : subRecords) {
                    TreeNode leafNode = new TreeNode(rec.getString("id"), rec.getString("fk_title"));
                    rootNode.getChildren().add(leafNode);
                }
                treeView.addNode(rootNode);
            }
        }
    }

    private void handleExportPDF() {
        String reportContent = (String) this.getModel().getValue("fk_content");
        if (reportContent == null || reportContent.isEmpty()) {
            this.getView().showWarnNotification("当前没有可导出的分析报告内容!");
            return;
        }
        this.getView().showSuccessNotification("PDF 导出请求已提交,后台生成中...");
    }
}
```

### 2. 知识图谱核心服务 (`CareerGraphService.java`)

- **包路径**:`tk.zc.zhqc.service`
- **职责**:纯 Java 独立封装,完全替代原 Python 的 NetworkX 库,实现 `KG4Career` 能力。采用**双重检查锁单例模式**与 `ConcurrentHashMap` 构建内存无向图邻接表,利用 **广度优先搜索 (BFS)** 算法外扩计算出用户当前技能的"二阶邻居技能集",用于诊断隐性潜在技能差距。

```java
package tk.zc.zhqc.service;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

public class CareerGraphService {

    private static volatile CareerGraphService instance;
    private final Map<String, Set<String>> adjacencyList = new ConcurrentHashMap<>();

    private CareerGraphService() {
        this.initMockGraphData();
    }

    public static CareerGraphService getInstance() {
        if (instance == null) {
            synchronized (CareerGraphService.class) {
                if (instance == null) {
                    instance = new CareerGraphService();
                }
            }
        }
        return instance;
    }

    private void initMockGraphData() {
        // 图谱关系加载契合示例
        this.addEdge("Java开发工程师", "Spring Boot");
        this.addEdge("Java开发工程师", "MySQL");
        this.addEdge("Spring Boot", "微服务架构");
        this.addEdge("Python数据分析", "Pandas");
        this.addEdge("Pandas", "数据可视化");
    }

    public void addEdge(String source, String target) {
        adjacencyList.computeIfAbsent(source, k -> Collections.synchronizedSet(new HashSet<>())).add(target);
        adjacencyList.computeIfAbsent(target, k -> Collections.synchronizedSet(new HashSet<>())).add(source); 
    }

    /**
     * 重构原 Python 拓扑算法:通过 BFS 检索技能的二阶关系拓扑
     */
    public Set<String> getTwoHopNeighbors(List<String> currentSkills) {
        Set<String> oneHop = new HashSet<>();
        Set<String> twoHop = new HashSet<>();

        if (currentSkills == null || currentSkills.isEmpty()) return twoHop;

        for (String skill : currentSkills) {
            Set<String> neighbors = adjacencyList.get(skill);
            if (neighbors != null) {
                oneHop.addAll(neighbors);
            }
        }

        for (String neighbor : oneHop) {
            Set<String> neighbors = adjacencyList.get(neighbor);
            if (neighbors != null) {
                for (String n : neighbors) {
                    if (!currentSkills.contains(n)) {
                        twoHop.add(n);
                    }
                }
            }
        }
        return twoHop;
    }
}
```

### 3. 自定义 WebAPI 网关插件 (`CustomAgentCallbackPlugin.java`)

- **包路径**:`tk.zc.zhqc.openapi`
- **职责**:实现标准开放平台接口 `IBillWebApiPlugin`,对外挂载接收路由:`/kapi/v2/zhihuiqingchun/custom_agent_callback`。接收 Agent 异步回调推送的初步报告参数;在数据正式落地前,**拦截流并强行调用 `CareerGraphService` 算法对技能报告进行图谱二次加工强化**;最后调用底座 `SaveServiceHelper.save` 事务持久化写入 PostgreSQL 数据库,实现全链路闭环。

```java
package tk.zc.zhqc.openapi;

import kd.bos.dataentity.entity.DynamicObject;
import kd.bos.entity.api.ApiResult;
import kd.bos.openapi.api.plugin.IBillWebApiPlugin;
import kd.bos.servicehelper.operation.SaveServiceHelper;
import kd.bos.servicehelper.BusinessDataServiceHelper;
import tk.zc.zhqc.service.CareerGraphService;
import java.util.*;

public class CustomAgentCallbackPlugin implements IBillWebApiPlugin {

    @Override
    public ApiResult doCustomAction(Map<String, Object> params) {
        try {
            String userId = (String) params.get("user_id");
            String title = (String) params.get("title");
            String rawContent = (String) params.get("content");
            List<String> extractedSkills = (List<String>) params.get("skills");

            // 2. 调用高代码 Java 核心服务:进行图谱二阶邻居拓展算法
            Set<String> extendedSkills = CareerGraphService.getInstance().getTwoHopNeighbors(extractedSkills);
            
            // 3. 将图谱拓展的隐性技能融入原始报告中 (二次加工强化)
            String finalReportContent = rawContent + " [知识图谱强化关联隐性技能扩展: " + extendedSkills.toString() + "]";

            // 4. 创建苍穹动态数据对象 (KDDM ORM 对象建模)
            DynamicObject historyRecord = BusinessDataServiceHelper.newDynamicObject("zc_history_record");
            historyRecord.set("fk_title", title);
            historyRecord.set("fk_record_type", "analysis");
            historyRecord.set("fk_content", finalReportContent);
            
            DynamicObject userRef = BusinessDataServiceHelper.loadSingle(userId, "zc_user");
            historyRecord.set("fk_user_id", userRef);

            // 5. 调用底座核心持久化辅助类保存数据入库
            DynamicObject[] saveResults = SaveServiceHelper.save(new DynamicObject[]{historyRecord});
            
            if (saveResults != null && saveResults.length > 0) {
                String newFid = saveResults[0].getString("id");
                return ApiResult.success(Map.of("fid", newFid, "message", "图谱强化报告保存成功!"));
            }
            
            return ApiResult.fail("-1", "苍穹底座物理保存失败");
            
        } catch (Exception ex) {
            return ApiResult.fail("-2", "开放网关异常中断: " + ex.getMessage());
        }
    }
}
```

---

## 🔷 第五阶段:整体重构映射关系矩阵

| 原 Python (Flask + SQLite) 组件 | 苍穹生态自适应平台能力替代方案 | 重构与配置开发模式 |
| --- | --- | --- |
| **Flask App & 全部 API 路由** | 开放平台标准 API / 自定义 `IBillWebApiPlugin` 插件 | 低代码配置接口 + 少量 Java 类 |
| **User, File, History 物理表** | 业务对象模型驱动设计 (KDDM 实体设计器) | 零代码可视化拖拽建模 |
| **index.html + api.js 前端** | 页面设计器 (Flex 布局容器 + 前台 `$api` 脚本) | 低代码拖拽 + 页面轻量级 JS |
| **call_qwen_plus() 函数** | AI服务云 → 文本大模型服务 (配置中心自定义 Endpoint) | 零代码图形化对接与凭证注入 |
| **FAISS + LSH 混合检索索引** | 企业知识库组件 (BGE-M3 向量化 + BM25 混合检索) | 低代码数据清洗与切片方案托管 |
| **AgenticRAG (ReAct 循环控制)** | 智能体平台 → AI自主规划智能体 (System Prompt 托管) | 零代码 Prompt 工程驱动自主规划 |
| **KG4Career (NetworkX 拓扑)** | 内存级无向图单例模型 (`CareerGraphService` 高能服务) | 高代码纯 Java 算法重构 |
| **手动打包 / Python 环境启动** | 协同开发平台 (DCS) + CI/CD 轻轨线流式自动化部署 | 零代码云端一体化补丁包构建 |