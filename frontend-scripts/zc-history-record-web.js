/**
 * 智绘青春 - Web 桌面端历史记录页面脚本
 * 绑定页面: zc_history_record_web
 *
 * 功能清单:
 *   交互一：附件上传完成 → 自动启用 AI 分析按钮 + 写入文件名到分录
 *   交互二：记录类型切换 → quiz 隐藏附件面板，analysis/report 显示
 *   交互三：AI 分析按钮 → 调用苍穹 Agent 智能体异步分析
 *   交互四：导出 PDF 按钮（预留 UI）
 *
 * IMA 知识库确认的 API:
 *   - this.$api.getControl(key)         获取控件
 *   - this.$api.setEnable(bool, key)    设置启用/禁用
 *   - this.$api.setVisible(bool, key)   设置可见/隐藏
 *   - this.$api.getModelValue(key, row?) 读取字段值
 *   - this.$api.setModelValue(key, val, row?) 设置字段值
 *   - this.$api.on('eventName', callback) 事件绑定
 *   - didMount() / willUnmount()         生命周期
 *   - 'attachmentpanelap1.afterUpload'   附件上传完成事件
 *   - 'fieldKey.onValueChange'           字段值变更事件
 *
 * @author 智绘青春
 * @since 2026-06-06
 */

export default {

    /* ============================================================
     * 生命周期：页面初始化
     * IMA 确认：didMount 在页面渲染完成后触发
     * ============================================================ */

    didMount() {
        // 1. 初始状态：AI 分析按钮禁用（未上传文件前不可用）
        this.$api.setEnable(false, 'btnAIAnalyze');

        // 2. 监听附件面板上传完成事件
        //    IMA 确认: attachmentpanelap1.afterUpload 在文件上传到服务器后触发
        this.$api.on('attachmentpanelap1.afterUpload', this._onAttachmentUploaded.bind(this));

        // 3. 监听记录类型字段值变更事件
        //    IMA 确认: fk_record_type.onValueChange 在字段值改变时触发
        this.$api.on('fk_record_type.onValueChange', this._onRecordTypeChanged.bind(this));

        // 4. 页面打开时，根据当前记录类型初始化附件面板状态
        this._syncAttachmentPanelState();
    },


    /* ============================================================
     * 生命周期：页面卸载
     * ============================================================ */

    willUnmount() {
        // 苍穹框架自动清理事件绑定，此处留空
    },


    /* ============================================================
     * 交互一：附件上传完成回调
     *
     * 触发时机：用户在附件面板中完成文件上传后
     * 行为：
     *   1. 启用 "开始 AI 分析" 按钮
     *   2. 将第一个文件名自动写入单据体分录 fk_filename_snapshot
     * ============================================================ */

    _onAttachmentUploaded(context, params) {
        // 1. 启用 AI 分析按钮
        this.$api.setEnable(true, 'btnAIAnalyze');

        // 2. 获取上传文件列表
        const files = this._extractFiles(params);

        if (files.length > 0) {
            const firstName = files[0].fileName || files[0].name || '';

            if (firstName) {
                // 3. 写入单据体分录第 0 行
                this.$api.setModelValue('fk_filename_snapshot', firstName, 0);

                // 4. 如果标题为空，自动填充默认标题
                const currentTitle = this.$api.getModelValue('fk_title');
                if (!currentTitle || currentTitle.trim() === '') {
                    this.$api.setModelValue('fk_title', firstName.replace(/\.(pdf|docx|doc)$/i, '') + ' - 分析报告');
                }
            }
        }
    },


    /* ============================================================
     * 交互二：记录类型变更回调
     *
     * 触发时机：用户切换 fk_record_type 下拉选项
     * 行为：
     *   - quiz（测评）→ 隐藏附件面板 + 禁用 AI 按钮
     *   - analysis / report  → 显示附件面板
     * ============================================================ */

    _onRecordTypeChanged(event) {
        // 兼容不同苍穹版本的事件参数格式
        const newValue = (event && event.value !== undefined) ? event.value : event;

        if (newValue === 'quiz') {
            // 测评类型：隐藏附件面板（不需要简历）
            this.$api.setVisible(false, 'attachmentpanelap1');
            // 测评不使用 AI 分析按钮
            this.$api.setEnable(false, 'btnAIAnalyze');
        } else {
            // 分析/报告类型：显示附件面板
            this.$api.setVisible(true, 'attachmentpanelap1');

            // 如果已有文件上传，恢复按钮可用
            const snapshot = this.$api.getModelValue('fk_filename_snapshot', 0);
            if (snapshot) {
                this.$api.setEnable(true, 'btnAIAnalyze');
            }
        }
    },


    /* ============================================================
     * 交互三：AI 分析按钮点击
     *
     * 触发时机：用户点击 btnAIAnalyze（🚀 开始AI分析）
     * 行为：
     *   1. 收集当前单据数据（类型、标题、附件、用户）
     *   2. 调用苍穹 Agent 助手 API 发起异步分析
     *   3. 显示加载状态
     *   4. 分析完成后刷新 TreeView 并展示报告
     * ============================================================ */

    'btnAIAnalyze.onClick'(event) {
        // 1. 收集单据数据
        const recordType = this.$api.getModelValue('fk_record_type');
        const title      = this.$api.getModelValue('fk_title');
        const userId     = this.$api.getModelValue('fk_user_id');

        // 2. 获取附件面板文件
        const files = this._getAttachmentFiles();

        // 3. 前置校验
        if (files.length === 0 && recordType !== 'quiz') {
            this.$api.showMessage('warning', '请先上传简历文件（支持 PDF、Word 格式）');
            return;
        }

        // 4. 显示加载状态
        this.$api.setEnable(false, 'btnAIAnalyze');
        this._showLoadingOverlay('AI 正在深度分析中，预计需要 30 秒 ~ 2 分钟...');

        // 5. 构建请求参数
        const agentInput = {
            recordType: recordType,
            title: title || '未命名分析报告',
            fileUrls: files.map(f => f.url || f.fileUrl || ''),
            fileName: files.length > 0 ? (files[0].fileName || files[0].name || '') : '',
            userId: userId,
            currentFid: this.$api.getModelValue('fid')
        };

        // 6. 调用苍穹 Agent 助手 API（异步）
        this._callAgentAsync(agentInput)
            .then(result => this._onAnalysisSuccess(result))
            .catch(error => this._onAnalysisError(error));
    },


    /* ============================================================
     * 交互四：导出 PDF 按钮（预留 UI）
     *
     * 触发时机：用户点击 btnExportPDF
     * 行为：暂时提示"即将上线"
     * ============================================================ */

    'btnExportPDF.onClick'(event) {
        this.$api.showMessage('info', '📄 PDF 导出功能开发中，敬请期待！');
    },


    /* ============================================================
     * 私有辅助方法
     * ============================================================ */

    /**
     * 从上传事件参数中提取文件列表。
     * 兼容苍穹不同版本的 params 结构。
     */
    _extractFiles(params) {
        if (!params) return [];
        if (Array.isArray(params.files)) return params.files;
        if (Array.isArray(params)) return params;
        // 兼容 { data: { files: [...] } } 结构
        if (params.data && Array.isArray(params.data.files)) return params.data.files;
        return [];
    },

    /**
     * 从附件面板控件获取当前已上传文件列表。
     * IMA 确认: this.$api.getControl('attachmentpanelap1') 获取附件面板对象
     */
    _getAttachmentFiles() {
        try {
            const panel = this.$api.getControl('attachmentpanelap1');
            if (panel && typeof panel.getFiles === 'function') {
                return panel.getFiles() || [];
            }
        } catch (e) {
            // 控件未找到或方法不可用
        }
        return [];
    },

    /**
     * 根据当前 fk_record_type 值同步附件面板显隐状态。
     */
    _syncAttachmentPanelState() {
        const currentType = this.$api.getModelValue('fk_record_type');
        if (currentType) {
            this._onRecordTypeChanged(currentType);
        }
    },

    /**
     * 调用苍穹 Agent 助手 API（模拟实现）。
     *
     * 在实际部署中，替换为以下任一方式：
     *   方式 A：苍穹助手侧边栏 API
     *     this.$api.callAgent({ agentCode: 'zhc_career_expert', input: ... })
     *   方式 B：直接调用 OpenAPI
     *     fetch('/kapi/v2/zhihuiqingchun/custom_agent_analyze', { ... })
     *
     * @param {Object} input - 智能体输入参数
     * @returns {Promise<Object>} 分析结果
     */
    async _callAgentAsync(input) {
        // ===== 方案 A：苍穹助手 SDK（推荐） =====
        // return this.$api.callAgent({
        //     agentCode: 'zhc_career_expert',
        //     input: input,
        //     timeout: 180000  // 3分钟超时
        // });

        // ===== 方案 B：直接 HTTP 调用（当前演示） =====
        const apiUrl = '/kapi/v2/zhihuiqingchun/custom_agent_analyze';

        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(input)
        });

        if (!response.ok) {
            throw new Error(`Agent API 返回错误: HTTP ${response.status}`);
        }

        const result = await response.json();

        if (!result.status || !result.success) {
            throw new Error(result.message || 'AI 分析失败');
        }

        return result.data || result;
    },

    /**
     * AI 分析成功回调。
     */
    _onAnalysisSuccess(result) {
        // 1. 隐藏加载遮罩
        this._hideLoadingOverlay();
        this.$api.setEnable(true, 'btnAIAnalyze');

        // 2. 刷新 TreeView 树节点
        try {
            const treeView = this.$api.getControl('historyTreeView');
            if (treeView && typeof treeView.refresh === 'function') {
                treeView.refresh();
            }
        } catch (e) {
            // TreeView 刷新失败不影响主流程
        }

        // 3. 提示用户
        const recordId = result.recordId || '';
        const discoveredCount = (result.discoveredSkills && result.discoveredSkills.length) || 0;

        let msg = '✅ AI 分析完成！报告已保存';
        if (recordId) msg += `，记录编号: ${recordId}`;
        if (discoveredCount > 0) msg += `\n🔍 图谱发现 ${discoveredCount} 个隐性潜在技能`;

        this.$api.showMessage('success', msg);

        // 4. 如果有发现的新技能，在页面上提示
        if (discoveredCount > 0) {
            console.log('[智绘青春] 图谱发现的潜在技能:',
                result.discoveredSkills.join(', '));
        }
    },

    /**
     * AI 分析失败回调。
     */
    _onAnalysisError(error) {
        this._hideLoadingOverlay();
        this.$api.setEnable(true, 'btnAIAnalyze');

        const errorMsg = (error && error.message) ? error.message : '未知错误';
        this.$api.showMessage('error', `❌ AI 分析失败: ${errorMsg}`);
        console.error('[智绘青春] AI 分析异常:', error);
    },

    /**
     * 显示全屏加载遮罩。
     */
    _showLoadingOverlay(message) {
        // 苍穹标准加载提示
        if (typeof this.$api.showLoading === 'function') {
            this.$api.showLoading(message);
        }
    },

    /**
     * 隐藏全屏加载遮罩。
     */
    _hideLoadingOverlay() {
        if (typeof this.$api.hideLoading === 'function') {
            this.$api.hideLoading();
        }
    }
};
