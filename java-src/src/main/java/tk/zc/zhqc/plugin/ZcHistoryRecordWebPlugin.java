package tk.zc.zhqc.plugin;

import kd.bos.bill.AbstractBillPlugIn;
import kd.bos.context.RequestContext;
import kd.bos.dataentity.entity.DynamicObject;
import kd.bos.dataentity.entity.DynamicObjectCollection;
import kd.bos.entity.datamodel.EventObject;
import kd.bos.form.control.Control;
import kd.bos.form.control.TreeView;
import kd.bos.form.control.TreeNode;
import kd.bos.form.control.events.ItemClickEvent;
import kd.bos.form.control.events.BeforeItemClickEvent;
import kd.bos.orm.qfilter.QFilter;
import kd.bos.orm.qfilter.QCP;
import kd.bos.servicehelper.BusinessDataServiceHelper;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 智绘青春 - 历史记录 Web 页面控制插件
 *
 * 核心功能：
 * 1. afterBindData: 使用 QFilter 批量查当前用户历史记录，
 *    Java Stream groupingBy 按类型归类，构建 TreeView 节点树
 * 2. itemClick: 拦截工具栏 btnExportPDF 按钮，预留 PDF 导出操作
 *
 * IMA 知识库参考：
 * - AbstractBillPlugIn 生命周期: registerListener → afterBindData → itemClick
 * - QFilter 数组间 ORM 引擎自动 and 关联
 * - TreeNode 构造: TreeNode(parentId, id, text, isParent)
 * - TreeView.addNode() 添加节点树
 *
 * @author 智绘青春
 * @since 2026-06-06
 */
public class ZcHistoryRecordWebPlugin extends AbstractBillPlugIn {

    /* ============================================================
     * 常量定义
     * ============================================================ */

    /** 历史记录单据实体标识 */
    private static final String ENTITY_HISTORY = "zc_history_record";

    /** 查询字段：主键、标题、记录类型、创建时间 */
    private static final String SELECT_FIELDS =
            "id,fk_title,fk_record_type,fk_created_at";

    /** TreeView 控件标识（与页面设计器中的控件 key 一致） */
    private static final String TREE_VIEW_KEY = "historyTreeView";

    /** 工具栏控件标识 */
    private static final String TOOLBAR_KEY = "mainToolbar";

    /** 工具栏按钮标识 */
    private static final String BTN_EXPORT_PDF = "btnExportPDF";
    private static final String BTN_AI_ANALYZE = "btnAIAnalyze";

    /** TreeView 根节点 ID */
    private static final String ROOT_NODE_ID = "root";

    /** 三大分类的树节点 ID 前缀 */
    private static final String CAT_ANALYSIS  = "cat_analysis";
    private static final String CAT_REPORT    = "cat_report";
    private static final String CAT_QUIZ      = "cat_quiz";

    /** 记录类型 → 分类名称 映射 */
    private static final Map<String, String> TYPE_TO_CATEGORY = Map.of(
            "analysis", "简历分析",
            "report",   "职业报告",
            "quiz",     "测评记录"
    );

    /** 分类节点默认排序 */
    private static final List<String> CATEGORY_ORDER = List.of("analysis", "report", "quiz");


    /* ============================================================
     * 生命周期：注册事件监听
     * IMA 确认：registerListener 中调用 addItemClickListeners 注册工具栏
     * ============================================================ */

    @Override
    public void registerListener(EventObject e) {
        super.registerListener(e);
        // 监听主工具栏按钮点击（IMA 确认: addItemClickListeners(toolbarKey)）
        this.addItemClickListeners(TOOLBAR_KEY);
    }


    /* ============================================================
     * 生命周期：数据绑定后构建 TreeView 节点树
     * IMA 确认：afterBindData 在界面数据包构建完毕、控件状态刷新后触发
     * 注意：不可在此处修改字段值，仅做控件状态设置
     * ============================================================ */

    @Override
    public void afterBindData(EventObject e) {
        super.afterBindData(e);

        // 1. 获取当前登录用户 ID（IMA 确认: RequestContext.get().getUserId()）
        RequestContext ctx = RequestContext.get();
        long currentUserId = Long.parseLong(ctx.getUserId());

        // 2. 构建 QFilter：按用户 ID 过滤（IMA 确认: QFilter 数组间自动 and 关联）
        QFilter userFilter = new QFilter("fk_user_id", QCP.equals, currentUserId);

        // 3. 批量一次性查出该用户的所有历史记录（严禁循环内查数据库）
        DynamicObject[] allRecords = BusinessDataServiceHelper.load(
                ENTITY_HISTORY,
                SELECT_FIELDS,
                new QFilter[]{userFilter}
        );

        // 4. 使用 Java Stream 在内存中按 record_type 归类
        //    IMA 性能铁律：所有分类操作用 Collectors.groupingBy 在内存完成
        Map<String, List<DynamicObject>> grouped = java.util.Arrays
                .stream(allRecords)
                .collect(Collectors.groupingBy(
                        obj -> {
                            String type = obj.getString("fk_record_type");
                            return (type != null) ? type : "unknown";
                        }
                ));

        // 5. 构建 TreeView 根节点
        TreeView treeView = this.getView().getControl(TREE_VIEW_KEY);
        TreeNode root = new TreeNode("", ROOT_NODE_ID, "我的历史记录");
        root.setIsOpened(true); // 默认展开根节点

        // 6. 按固定顺序（analysis → report → quiz）构建分类节点
        int totalCount = 0;
        for (String recordType : CATEGORY_ORDER) {
            List<DynamicObject> records = grouped.getOrDefault(recordType, java.util.Collections.emptyList());
            String catName = TYPE_TO_CATEGORY.getOrDefault(recordType, recordType);
            String catNodeId = "cat_" + recordType;

            // 分类节点文本含计数
            TreeNode catNode = new TreeNode(
                    ROOT_NODE_ID,
                    catNodeId,
                    catName + " (" + records.size() + ")"
            );
            catNode.setIsOpened(true);

            // 7. 为每个历史记录创建叶子节点
            for (DynamicObject record : records) {
                Long recordId = record.getLong("id");
                String title = record.getString("fk_title");
                // 节点 ID 格式: record_{主键ID}
                String leafNodeId = "record_" + recordId;

                TreeNode leafNode = new TreeNode(
                        catNodeId,
                        leafNodeId,
                        (title != null && !title.isEmpty()) ? title : "未命名记录",
                        false  // isParent = false 表示叶子节点
                );

                catNode.addChild(leafNode);
                totalCount++;
            }

            root.addChild(catNode);
        }

        // 更新根节点标题含总数
        root.setText("我的历史记录 (" + totalCount + ")");

        // 8. 将整棵树添加到 TreeView 控件（IMA 确认: treeView.addNode(root)）
        treeView.addNode(root);
    }


    /* ============================================================
     * 事件回调：工具栏按钮点击
     * IMA 确认：itemClick 中通过 evt.getItemKey() 判断被点击按钮
     * ============================================================ */

    @Override
    public void itemClick(ItemClickEvent evt) {
        super.itemClick(evt);
        String itemKey = evt.getItemKey();

        // === 导出 PDF 按钮（预留） ===
        if (BTN_EXPORT_PDF.equals(itemKey)) {
            this.getView().showMessage("PDF 导出功能即将上线，敬请期待！");
            // TODO: 第四步可在此实现 PDF 生成逻辑
            return;
        }

        // === AI 分析按钮 ===
        if (BTN_AI_ANALYZE.equals(itemKey)) {
            // 逻辑由前台脚本调用 Agent API 处理
            // 此处可做前置校验（如检查附件是否已上传）
            return;
        }
    }


    /* ============================================================
     * 事件回调：按钮点击前拦截
     * IMA 确认：beforeItemClick 可在操作执行前校验，evt.setCancel(true) 取消
     * ============================================================ */

    @Override
    public void beforeItemClick(BeforeItemClickEvent evt) {
        super.beforeItemClick(evt);
        String itemKey = evt.getItemKey();

        // PDF 导出：检查是否有选中记录
        if (BTN_EXPORT_PDF.equals(itemKey)) {
            TreeView treeView = this.getView().getControl(TREE_VIEW_KEY);
            // 暂不做强制校验，保留入口
        }
    }
}
