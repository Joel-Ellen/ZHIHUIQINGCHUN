package tk.zc.zhqc.service;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 智绘青春 - 职业规划知识图谱拓扑服务
 *
 * 采用轻量级内存无向图结构，重构原 Python 项目中的 KG4Career 知识图谱
 * （原: NetworkX 图 + TransE/R-GCN 嵌入 → 现: ConcurrentHashMap 邻接表 + BFS 多跳搜索）
 *
 * 核心能力：
 * - 基于技能共现关系构建无向技能图
 * - BFS 广度优先搜索计算一阶和二阶邻居（隐性潜在技能发现）
 * - 线程安全的单例模式
 *
 * IMA 知识库参考：
 * - 无直接 SDK 依赖，纯 Java 数据结构实现
 * - 原 Python KG4Career: backend/services/kg_service.py + backend/models/kg_schema.py
 *
 * @author 智绘青春
 * @since 2026-06-06
 */
public class CareerGraphService {

    /* ============================================================
     * 单例实现（线程安全 - 饿汉模式）
     * ============================================================ */

    private static final CareerGraphService INSTANCE = new CareerGraphService();

    private CareerGraphService() {
        // 私有构造函数，防止外部实例化
    }

    public static CareerGraphService getInstance() {
        return INSTANCE;
    }


    /* ============================================================
     * 图数据结构
     * Key: 技能名称（已标准化为小写）
     * Value: 该技能的所有邻居技能集合（线程安全 Set）
     * ============================================================ */

    /** 无向图的邻接表 */
    private final ConcurrentHashMap<String, Set<String>> adjacencyMap = new ConcurrentHashMap<>();

    /** 图是否已初始化 */
    private volatile boolean initialized = false;


    /* ============================================================
     * 图构建
     * ============================================================ */

    /**
     * 从岗位数据批量构建技能图。
     *
     * 构建逻辑（对应原 Python build_kg.py）：
     * - 遍历所有岗位，提取每个岗位的技能列表
     * - 同一岗位内的所有技能两两建立无向边（共现关系）
     * - 边权重隐式由共现次数决定（存储为邻接表的多重 key）
     *
     * 性能说明：一次性全量构建，不在循环中查询数据库
     *
     * @param jobSkillMap 岗位ID → 技能列表 的映射
     *                    例如: { 1: ["Java", "Spring", "MySQL"], 2: ["Python", "Django", "MySQL"] }
     */
    public void buildGraph(Map<Long, List<String>> jobSkillMap) {
        if (jobSkillMap == null || jobSkillMap.isEmpty()) {
            return;
        }

        // 清空旧图
        adjacencyMap.clear();

        // 遍历所有岗位
        for (Map.Entry<Long, List<String>> entry : jobSkillMap.entrySet()) {
            List<String> skills = entry.getValue();
            if (skills == null || skills.size() < 2) {
                continue; // 单技能岗位不产生边
            }

            // 标准化为小写
            List<String> normalized = new ArrayList<>(skills.size());
            for (String s : skills) {
                if (s != null && !s.isBlank()) {
                    normalized.add(s.toLowerCase().trim());
                }
            }

            // 同一岗位内所有技能两两建立双向边
            for (int i = 0; i < normalized.size(); i++) {
                String skillA = normalized.get(i);
                for (int j = i + 1; j < normalized.size(); j++) {
                    String skillB = normalized.get(j);
                    addEdge(skillA, skillB);
                }
            }
        }

        initialized = true;
    }

    /**
     * 添加一条无向边（A→B 和 B→A）。
     * 使用 computeIfAbsent 保证线程安全。
     */
    private void addEdge(String skillA, String skillB) {
        // A → B
        adjacencyMap.computeIfAbsent(skillA, k -> ConcurrentHashMap.newKeySet()).add(skillB);
        // B → A（无向图）
        adjacencyMap.computeIfAbsent(skillB, k -> ConcurrentHashMap.newKeySet()).add(skillA);
    }


    /* ============================================================
     * 图查询：两跳邻居（核心算法）
     * ============================================================ */

    /**
     * 基于广度优先搜索（BFS）计算给定技能集合的一阶和二阶邻居。
     *
     * 算法流程（对应原 Python gnn_service.py 的冷启动 GNN 推理）：
     * 1. 将所有当前技能作为起始节点集合 S0
     * 2. BFS 第一层：直接邻居（1-hop）→ 加入结果集
     * 3. BFS 第二层：邻居的邻居（2-hop）→ 加入结果集
     * 4. 排除 S0 中已有的技能、已访问节点
     * 5. 返回两跳内发现的新技能（即"隐性潜在技能"）
     *
     * 性能复杂度：O(|V| + |E|)，其中 V 为可达节点数，E 为边数
     *
     * @param currentSkills 用户当前拥有的技能列表
     * @return 两跳内发现的扩展技能集合（排除已有技能）
     */
    public Set<String> getTwoHopNeighbors(List<String> currentSkills) {
        if (!initialized || currentSkills == null || currentSkills.isEmpty()) {
            return Collections.emptySet();
        }

        // 标准化输入技能为小写
        Set<String> userSkills = new HashSet<>();
        for (String s : currentSkills) {
            if (s != null && !s.isBlank()) {
                userSkills.add(s.toLowerCase().trim());
            }
        }

        // BFS 数据结构
        Set<String> visited = new HashSet<>();   // 已访问节点（防止环路）
        Set<String> discovered = new HashSet<>(); // 新发现的潜在技能
        Deque<String> queue = new ArrayDeque<>(); // BFS 队列
        Map<String, Integer> distance = new HashMap<>(); // 距离记录

        // 初始化：所有用户技能加入队列，距离 0
        for (String skill : userSkills) {
            if (adjacencyMap.containsKey(skill)) {
                queue.addLast(skill);
                visited.add(skill);
                distance.put(skill, 0);
            }
        }

        // BFS 主循环，搜索深度最多 2 跳
        while (!queue.isEmpty()) {
            String current = queue.removeFirst();
            int currentDist = distance.get(current);

            // 超过两跳停止搜索
            if (currentDist >= 2) {
                continue;
            }

            // 遍历当前节点的所有邻居
            Set<String> neighbors = adjacencyMap.get(current);
            if (neighbors == null) {
                continue;
            }

            for (String neighbor : neighbors) {
                if (!visited.contains(neighbor)) {
                    visited.add(neighbor);
                    int newDist = currentDist + 1;
                    distance.put(neighbor, newDist);

                    // 非用户已有技能 → 加入发现集
                    if (!userSkills.contains(neighbor)) {
                        discovered.add(neighbor);
                    }

                    // 继续 BFS（仅当未达到最大深度时）
                    if (newDist < 2) {
                        queue.addLast(neighbor);
                    }
                }
            }
        }

        return discovered;
    }


    /* ============================================================
     * 辅助查询方法
     * ============================================================ */

    /**
     * 获取图中技能总数。
     */
    public int getVertexCount() {
        return adjacencyMap.size();
    }

    /**
     * 检查图是否已初始化。
     */
    public boolean isInitialized() {
        return initialized;
    }

    /**
     * 查询某个技能的直接邻居（一阶）。
     *
     * @param skill 技能名称
     * @return 直接邻居集合，不存在则返回空集
     */
    public Set<String> getDirectNeighbors(String skill) {
        if (skill == null || !initialized) {
            return Collections.emptySet();
        }
        Set<String> neighbors = adjacencyMap.get(skill.toLowerCase().trim());
        return (neighbors != null) ? Collections.unmodifiableSet(neighbors) : Collections.emptySet();
    }

    /**
     * 重置图（用于重新加载数据）。
     */
    public void reset() {
        adjacencyMap.clear();
        initialized = false;
    }
}
