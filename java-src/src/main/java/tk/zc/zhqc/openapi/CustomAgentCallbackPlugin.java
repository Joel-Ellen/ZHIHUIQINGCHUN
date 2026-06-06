package tk.zc.zhqc.openapi;

import kd.bos.bill.IBillWebApiPlugin;
import kd.bos.dataentity.entity.DynamicObject;
import kd.bos.dataentity.entity.DynamicObjectCollection;
import kd.bos.entity.api.ApiResult;
import kd.bos.entity.operate.OperateOption;
import kd.bos.exception.KDBizException;
import kd.bos.servicehelper.BusinessDataServiceHelper;
import kd.bos.servicehelper.operation.SaveServiceHelper;
import kd.bos.servicehelper.operation.OperationResult;
import tk.zc.zhqc.service.CareerGraphService;

import java.math.BigDecimal;
import java.util.*;

/**
 * 智绘青春 - 自定义 WebAPI 网关插件
 *
 * 实现 IBillWebApiPlugin 接口，作为苍穹 Agent 智能体与业务单据之间的桥梁。
 * 接收 Agent 异步传回的 JSON 参数，调用技能图谱服务进行二阶拓扑强化，
 * 然后通过 SaveServiceHelper.saveOperate 将增强后的报告持久化到 PostgreSQL。
 *
 * 请求体 JSON 格式（由 Agent 智能体生成后 POST 过来）：
 * <pre>
 * {
 *   "user_id": "U001",
 *   "record_type": "analysis",
 *   "title": "张三的简历分析报告",
 *   "content": "{...完整的JSON报告字符串...}",
 *   "skills": ["Java", "Spring", "MySQL"],
 *   "file_id": "F20260606001",
 *   "file_name": "张三_简历.pdf"
 * }
 * </pre>
 *
 * IMA 知识库参考：
 * - IBillWebApiPlugin: doCustomService(Map<String, Object> params)
 * - ApiResult: ApiResult.success(data) / ApiResult.fail(errorMessage)
 * - BusinessDataServiceHelper.newDynamicObject(entityName, fillDefVal, option)
 * - SaveServiceHelper.saveOperate(entityNumber, DynamicObject[], OperateOption)
 * - DynamicObject.set(fieldName, value) 设置字段值
 * - 基础资料字段：方式二（newDynamicObject + setId）简化设置
 *
 * @author 智绘青春
 * @since 2026-06-06
 */
public class CustomAgentCallbackPlugin implements IBillWebApiPlugin {

    /* ============================================================
     * 常量定义
     * ============================================================ */

    /** 历史记录单据实体标识 */
    private static final String ENTITY_HISTORY = "zc_history_record";

    /** 用户基础资料实体标识 */
    private static final String ENTITY_USER = "zc_user";

    /** 文件基础资料实体标识 */
    private static final String ENTITY_FILE = "zc_userfile";

    /** 文件分录实体标识（单据体） */
    private static final String ENTRY_FILE = "entryentity";

    /** 成功错误码 */
    private static final String SUCCESS_CODE = "success";


    /* ============================================================
     * IBillWebApiPlugin 核心方法
     * IMA 确认: doCustomService(Map<String, Object> params) → ApiResult
     * ============================================================ */

    @Override
    public ApiResult doCustomService(Map<String, Object> params) {
        // ====== 第 1 步：参数解析与校验 ======
        // IMA 确认：params 是苍穹自动将 JSON 请求体转为 Map<String, Object>

        String userId;
        String recordType;
        String title;
        String content;
        List<String> skills;
        String fileId;
        String fileName;

        try {
            userId     = getStringParam(params, "user_id", true);
            recordType = getStringParam(params, "record_type", true);
            title      = getStringParam(params, "title", true);
            content    = getStringParam(params, "content", true);
            fileId     = getStringParam(params, "file_id", false);
            fileName   = getStringParam(params, "file_name", false);

            // 技能列表：可能为 List<String> 或 JSON 数组（ArrayList）
            Object skillsObj = params.get("skills");
            if (skillsObj instanceof List) {
                skills = castToStringList((List<?>) skillsObj);
            } else {
                skills = Collections.emptyList();
            }
        } catch (IllegalArgumentException e) {
            return ApiResult.fail(createErrorMap("900101", "参数校验失败: " + e.getMessage()));
        }

        // ====== 第 2 步：调用技能图谱服务进行二阶拓扑强化 ======
        Set<String> discoveredSkills = Collections.emptySet();
        if (!skills.isEmpty()) {
            CareerGraphService graphService = CareerGraphService.getInstance();

            if (graphService.isInitialized()) {
                // BFS 两跳搜索 → 发现隐性潜在技能
                discoveredSkills = graphService.getTwoHopNeighbors(skills);
            }
            // 注意：如果图未初始化（jobs_data 未加载），跳过图谱强化但不报错
        }

        // ====== 第 3 步：构建增强后的 content（融入图谱发现） ======
        String enrichedContent = enrichContent(content, skills, discoveredSkills);

        // ====== 第 4 步：创建实体数据包并设置字段值 ======
        // IMA 确认：newDynamicObject(entityName, fillDefVal, option)
        //          fillDefVal=true 填充默认值（如编码规则自动生成编号）
        DynamicObject bill = BusinessDataServiceHelper.newDynamicObject(
                ENTITY_HISTORY,
                true,
                OperateOption.create()
        );

        // --- 设置单据头字段 ---
        bill.set("fk_record_type", recordType);
        bill.set("fk_title", title);
        bill.set("fk_content", enrichedContent); // 大文本字段存储增强后的 JSON

        // --- 设置基础资料字段：用户 ---
        // IMA 确认方式二：创建空对象，只设置 ID（简化逻辑）
        DynamicObject userRef = BusinessDataServiceHelper.newDynamicObject(ENTITY_USER);
        userRef.set("number", userId);  // 使用业务编码 number 引用
        bill.set("fk_user_id", userRef);

        // --- 设置单据体：关联文件分录 ---
        if (fileId != null && !fileId.isBlank()) {
            DynamicObjectCollection entryCollection = bill.getDynamicObjectCollection(ENTRY_FILE);
            if (entryCollection != null) {
                DynamicObject entryRow = entryCollection.addNew();

                // 行号
                entryRow.set("fk_seq", BigDecimal.ONE);

                // 基础资料字段：文件
                DynamicObject fileRef = BusinessDataServiceHelper.newDynamicObject(ENTITY_FILE);
                fileRef.set("number", fileId);
                entryRow.set("fk_file_id", fileRef);

                // 文件名快照
                if (fileName != null && !fileName.isBlank()) {
                    entryRow.set("fk_filename_snapshot", fileName);
                }
            }
        }

        // ====== 第 5 步：调用 SaveServiceHelper 持久化 ======
        // IMA 确认：saveOperate(entityNumber, DynamicObject[], OperateOption)
        //          返回 OperationResult，可用 isSuccess() 判断
        OperationResult saveResult;
        try {
            saveResult = SaveServiceHelper.saveOperate(
                    ENTITY_HISTORY,
                    new DynamicObject[]{bill},
                    OperateOption.create()
            );
        } catch (KDBizException e) {
            return ApiResult.fail(createErrorMap("900102",
                    "单据保存异常: " + e.getMessage()));
        }

        // ====== 第 6 步：构建返回结果 ======
        if (saveResult.isSuccess()) {
            // 提取新创建单据的主键 ID
            DynamicObject[] savedObjs = saveResult.getDataEntities();
            Map<String, Object> resultData = new LinkedHashMap<>();
            resultData.put("message", "报告保存成功");
            resultData.put("discoveredSkills", new ArrayList<>(discoveredSkills));
            resultData.put("graphEnhanced", !discoveredSkills.isEmpty());

            if (savedObjs != null && savedObjs.length > 0) {
                Object pkValue = savedObjs[0].getPkValue();
                resultData.put("recordId", pkValue);
            }

            return ApiResult.success(resultData);
        } else {
            // 保存失败：提取错误信息
            String errorMsg = saveResult.getMessage();
            if (errorMsg == null || errorMsg.isEmpty()) {
                errorMsg = "未知保存错误";
            }
            return ApiResult.fail(createErrorMap("900103", "单据保存失败: " + errorMsg));
        }
    }


    /* ============================================================
     * 私有辅助方法
     * ============================================================ */

    /**
     * 从 Map 中安全提取必需/可选字符串参数。
     */
    private String getStringParam(Map<String, Object> params, String key, boolean required) {
        Object value = params.get(key);
        if (value == null) {
            if (required) {
                throw new IllegalArgumentException("缺少必填参数: " + key);
            }
            return null;
        }
        return value.toString();
    }

    /**
     * 将 List<?> 转换为 List<String>（处理 JSON 数字/字符串混合场景）。
     */
    @SuppressWarnings("unchecked")
    private List<String> castToStringList(List<?> rawList) {
        List<String> result = new ArrayList<>(rawList.size());
        for (Object item : rawList) {
            if (item != null) {
                result.add(item.toString().trim());
            }
        }
        return result;
    }

    /**
     * 创建错误 Map，用于 ApiResult.fail()。
     */
    private Map<String, Object> createErrorMap(String code, String message) {
        Map<String, Object> error = new LinkedHashMap<>();
        error.put("code", code);
        error.put("message", message);
        return error;
    }

    /**
     * 在原始 content JSON 中注入图谱发现的新技能。
     *
     * 增强方式：在 skillGapAnalysis 字段中追加 graph_discovered_skills，
     * 供前端展示"AI 发现的隐性潜在技能"。
     */
    private String enrichContent(String rawContent, List<String> originalSkills, Set<String> discoveredSkills) {
        if (discoveredSkills.isEmpty()) {
            return rawContent;
        }

        try {
            // 尝试在 JSON 的 skillGapAnalysis 中追加图谱发现
            // 简单且安全的方式：在 JSON 尾部追加扩展字段
            StringBuilder enriched = new StringBuilder(rawContent.trim());

            // 如果原 JSON 以 } 结尾，在闭合前插入扩展字段
            if (enriched.charAt(enriched.length() - 1) == '}') {
                // 移除尾部 }
                enriched.setLength(enriched.length() - 1);

                // 构建扩展字段 JSON 片段
                enriched.append(",\n  \"graphEnhanced\": true");
                enriched.append(",\n  \"graphDiscoveredSkills\": [");

                List<String> sorted = new ArrayList<>(discoveredSkills);
                Collections.sort(sorted);
                for (int i = 0; i < sorted.size(); i++) {
                    if (i > 0) enriched.append(", ");
                    enriched.append("\"").append(escapeJson(sorted.get(i))).append("\"");
                }
                enriched.append("]");

                // 补回尾部 }
                enriched.append("\n}");
            }

            return enriched.toString();
        } catch (Exception e) {
            // JSON 处理失败时，返回原始 content（不丢失数据）
            return rawContent;
        }
    }

    /**
     * 简单的 JSON 字符串转义（处理双引号和反斜杠）。
     */
    private String escapeJson(String s) {
        return s.replace("\\", "\\\\").replace("\"", "\\\"");
    }
}
