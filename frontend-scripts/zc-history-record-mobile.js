/**
 * 智绘青春 - 移动端 H5 历史记录页面脚本
 * 绑定页面: zc_history_record_mobile
 *
 * 功能清单:
 *   交互一：附件上传完成 → 自动启用 "发送AI分析" 按钮 + 写入文件名
 *   交互二：记录类型切换 → quiz 隐藏附件面板
 *   交互三：悬浮按钮（FAB）→ 跳转新增页面
 *   交互四：移动端底部按钮 → 发送 AI 异步分析
 *
 * 移动端适配要点（IMA 确认）：
 *   - 附件面板标识 attachmentpanelap1 必须与 PC 端保持一致（数据联动）
 *   - 底部固定按钮通过 移动端工具栏 + 底部tab栏控件方案 实现
 *   - 悬浮按钮通过 悬浮按钮控件 + 控件方案预置样式 实现
 *   - BOS V6.0.1+ 自动生成移动端自适应布局
 *
 * @author 智绘青春
 * @since 2026-06-06
 */

export default {

    /* ============================================================
     * 生命周期：页面初始化
     * ============================================================ */

    didMount() {
        // 1. 初始状态：禁用发送按钮
        this.$api.setEnable(false, 'btnSendAI');

        // 2. 附件上传完成事件（标识与PC端一致，IMA确认必须保持相同）
        this.$api.on('attachmentpanelap1.afterUpload', this._onMobileAttachmentUploaded.bind(this));

        // 3. 记录类型变更事件
        this.$api.on('fk_record_type.onValueChange', this._onMobileRecordTypeChanged.bind(this));

        // 4. 初始化时同步附件面板状态
        this._syncMobileAttachmentState();

        // 5. 移动端特有：监听页面可见性恢复（从后台切回时刷新状态）
        this._setupMobileVisibilityHandler();
    },


    /* ============================================================
     * 交互一：移动端附件上传完成
     *
     * 移动端特有行为（IMA 确认）：
     *   - 支持调用 App 原生拍照、相册、文件选择
     *   - 图片附件支持缩略图展示
     *   - 底层使用 H5 <input onchange> 实现
     * ============================================================ */

    _onMobileAttachmentUploaded(context, params) {
        // 启用发送按钮
        this.$api.setEnable(true, 'btnSendAI');

        // 提取文件名写入分录
        const files = this._extractMobileFiles(params);
        if (files.length > 0) {
            const firstName = files[0].fileName || files[0].name || '';
            if (firstName) {
                this.$api.setModelValue('fk_filename_snapshot', firstName, 0);

                // 自动填充标题
                const currentTitle = this.$api.getModelValue('fk_title');
                if (!currentTitle || currentTitle.trim() === '') {
                    const cleanName = firstName.replace(/\.(pdf|docx|doc|jpg|png)$/i, '');
                    this.$api.setModelValue('fk_title', cleanName + ' - 分析报告');
                }
            }
        }

        // 移动端特有：上传完成后给出轻提示
        this._showMobileToast('文件上传成功，可以开始 AI 分析');
    },


    /* ============================================================
     * 交互二：记录类型变更（移动端）
     * ============================================================ */

    _onMobileRecordTypeChanged(event) {
        const newValue = (event && event.value !== undefined) ? event.value : event;

        if (newValue === 'quiz') {
            // 测评：隐藏附件面板
            this.$api.setVisible(false, 'attachmentpanelap1');
            this.$api.setEnable(false, 'btnSendAI');
        } else {
            this.$api.setVisible(true, 'attachmentpanelap1');
            const snapshot = this.$api.getModelValue('fk_filename_snapshot', 0);
            if (snapshot) {
                this.$api.setEnable(true, 'btnSendAI');
            }
        }
    },


    /* ============================================================
     * 交互三：悬浮按钮（FAB）点击 → 跳转新增页面
     *
     * IMA 确认：移动端支持 "标准悬浮按钮" 和 "含标题悬浮按钮" 控件方案
     * ============================================================ */

    'fabNew.onClick'(event) {
        // 跳转到新增页面
        // 苍穹移动端页面跳转方式
        if (typeof this.$api.navigateTo === 'function') {
            this.$api.navigateTo({
                formId: 'zc_history_record_mobile_form',
                mode: 'new'
            });
        }
    },


    /* ============================================================
     * 交互四：底部固定按钮 → 发送 AI 异步分析
     *
     * IMA 确认：底部固定按钮通过 工具栏控件 + 底部tab栏控件方案 实现
     * ============================================================ */

    'btnSendAI.onClick'(event) {
        // 1. 收集数据
        const recordType = this.$api.getModelValue('fk_record_type');
        const title      = this.$api.getModelValue('fk_title');
        const userId     = this.$api.getModelValue('fk_user_id');
        const files      = this._getMobileAttachmentFiles();

        // 2. 前置校验
        if (files.length === 0 && recordType !== 'quiz') {
            this._showMobileToast('请先上传简历文件');
            return;
        }

        // 3. 显示加载状态
        this.$api.setEnable(false, 'btnSendAI');
        this._showMobileToast('🚀 AI 正在分析中...');

        // 4. 构建请求
        const agentInput = {
            recordType: recordType,
            title: title || '未命名分析报告',
            fileUrls: files.map(f => f.url || f.fileUrl || ''),
            fileName: files.length > 0 ? (files[0].fileName || files[0].name || '') : '',
            userId: userId
        };

        // 5. 调用 Agent API
        this._callMobileAgentAsync(agentInput)
            .then(result => this._onMobileAnalysisSuccess(result))
            .catch(error => this._onMobileAnalysisError(error));
    },


    /* ============================================================
     * 私有辅助方法
     * ============================================================ */

    /**
     * 从移动端上传事件提取文件列表。
     * 兼容移动端特有参数结构（Camera/Gallery/File 三种来源）。
     */
    _extractMobileFiles(params) {
        if (!params) return [];
        if (Array.isArray(params.files)) return params.files;
        if (Array.isArray(params)) return params;
        if (params.data && Array.isArray(params.data.files)) return params.data.files;
        return [];
    },

    /**
     * 从移动端附件面板获取文件列表。
     */
    _getMobileAttachmentFiles() {
        try {
            const panel = this.$api.getControl('attachmentpanelap1');
            if (panel && typeof panel.getFiles === 'function') {
                return panel.getFiles() || [];
            }
        } catch (e) {
            // 忽略
        }
        return [];
    },

    /**
     * 同步移动端附件面板状态。
     */
    _syncMobileAttachmentState() {
        const currentType = this.$api.getModelValue('fk_record_type');
        if (currentType) {
            this._onMobileRecordTypeChanged(currentType);
        }
    },

    /**
     * 移动端可见性变化处理（App 切后台再回来时）。
     */
    _setupMobileVisibilityHandler() {
        // 监听页面可见性 API
        if (typeof document !== 'undefined') {
            document.addEventListener('visibilitychange', () => {
                if (!document.hidden) {
                    // 页面恢复可见：刷新附件状态
                    this._syncMobileAttachmentState();
                }
            });
        }
    },

    /**
     * 移动端轻提示（Toast）。
     * 替代 PC 端 this.$api.showMessage()，更适合移动体验。
     */
    _showMobileToast(message) {
        // 优先使用苍穹移动端 Toast API
        if (typeof this.$api.showToast === 'function') {
            this.$api.showToast({ message: message, duration: 2000 });
        } else if (typeof this.$api.showMessage === 'function') {
            // 回退到标准消息提示
            this.$api.showMessage('info', message);
        }
    },

    /**
     * 移动端调用 Agent API（异步）。
     */
    async _callMobileAgentAsync(input) {
        const apiUrl = '/kapi/v2/zhihuiqingchun/custom_agent_analyze';

        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(input)
        });

        if (!response.ok) {
            throw new Error(`Agent API 返回错误: HTTP ${response.status}`);
        }

        const result = await response.json();
        if (!result.status && !result.success) {
            throw new Error(result.message || 'AI 分析失败');
        }
        return result.data || result;
    },

    /**
     * 移动端分析成功回调。
     */
    _onMobileAnalysisSuccess(result) {
        this.$api.setEnable(true, 'btnSendAI');

        const discoveredCount = (result.discoveredSkills && result.discoveredSkills.length) || 0;
        let msg = '✅ 分析完成！';
        if (discoveredCount > 0) msg += ` 发现 ${discoveredCount} 个潜在技能`;

        this._showMobileToast(msg);

        // 移动端：自动跳转到详情页查看报告
        const recordId = result.recordId;
        if (recordId && typeof this.$api.navigateTo === 'function') {
            // 延迟跳转，让用户看到成功提示
            setTimeout(() => {
                this.$api.navigateTo({
                    formId: 'zc_history_record_mobile_form',
                    mode: 'view',
                    pkId: recordId
                });
            }, 1500);
        }
    },

    /**
     * 移动端分析失败回调。
     */
    _onMobileAnalysisError(error) {
        this.$api.setEnable(true, 'btnSendAI');
        const errorMsg = (error && error.message) ? error.message : '未知错误';
        this._showMobileToast('❌ 分析失败: ' + errorMsg);
        console.error('[智绘青春·移动端] AI 分析异常:', error);
    }
};
