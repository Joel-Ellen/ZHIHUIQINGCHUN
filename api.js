/**
 * 智绘青春 - API调用模块
 * KG4Career智能职业规划系统 - 四组件架构驱动
 * 感知 → 推理 → 决策 → 行动
 */

// API配置 - 自动适配当前服务器地址
let API_BASE_URL = '/api';

// API调用函数
async function callAPI(endpoint, data) {
    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API调用失败:', error);
        return { success: false, error: error.message };
    }
}

/**
 * KG4Career智能体 - 简历深度分析
 * 
 * @param {Object} params - 分析参数
 * @param {Object} params.userInfo - 用户基本信息（姓名、学校，专业等）
 * @param {string} params.extractedText - 从简历文件中提取的原始文本内容
 * @param {Object} params.parsedData - AI解析后的结构化数据
 * @param {string} params.userId - 用户ID（可选）
 * @param {string} params.fileName - 上传的文件名
 * @param {string} params.fileType - 文件类型
 * @returns {Promise<Object>} 分析结果
 * 
 * 四组件架构说明：
 * 1. 感知模块：借助Few-shot抽取技术，从简历中构建10维度标准化画像
 * 2. 推理模块：运用Jaccard相似度算法量化岗位技能重叠程度
 * 3. 决策模块：LSH粗筛 + FAISS精排，输出综合匹配度
 * 4. 行动模块：RAG增强生成，输出可视化报告
 */
async function analyzeResume(params) {
    // 兼容旧格式参数
    let requestData;
    if (typeof params === 'object' && !Array.isArray(params) && (params.extractedText !== undefined || params.parsedData !== undefined)) {
        // 新格式：params包含完整数据
        requestData = {
            userInfo: params.userInfo || {},
            extractedText: params.extractedText || '',
            parsedData: params.parsedData || {},
            userId: params.userId || null,
            fileMeta: {
                name: params.fileName || '',
                type: params.fileType || ''
            },
            knowledgeGraph: {
                enabled: true,
                competencyPath: true,  // 专业-课程-技能关联路径用于低年级学生能力补全
                profileCompleteness: true  // 画像完整度与市场竞争力评分
            },
            modules: {
                perception: true,   // 感知模块：10维度画像构建
                reasoning: true,    // 推理模块：Jaccard相似度+职位层级
                decision: true,     // 决策模块：LSH+FAISS+图神经网络
                action: true        // 行动模块：RAG增强生成
            }
        };
    } else {
        // 旧格式兼容：第一个参数是userInfo，第二个是userId
        const userInfo = params || {};
        const userId = arguments[1] || null;
        requestData = {
            userInfo: userInfo,
            extractedText: '',
            parsedData: userInfo,
            userId: userId,
            fileMeta: {
                name: '',
                type: ''
            },
            knowledgeGraph: {
                enabled: true,
                competencyPath: true,
                profileCompleteness: true
            },
            modules: {
                perception: true,
                reasoning: true,
                decision: true,
                action: true
            }
        };
    }
    
    console.log('【KG4Career智能体】发送分析请求:', {
        userInfo: requestData.userInfo,
        hasExtractedText: !!requestData.extractedText,
        extractedTextLength: requestData.extractedText?.length || 0,
        hasParsedData: !!requestData.parsedData,
        fileName: requestData.fileMeta.name
    });
    
    return await callAPI('/analyze-resume', requestData);
}

// 生成职业报告
async function generateReport(userInfo, analysisResult, userId = null) {
    return await callAPI('/generate-report', { userInfo, analysisResult, userId });
}

// 问卷测评分析
async function analyzeQuiz(answers, questions, userId = null) {
    return await callAPI('/quiz-analysis', { answers, questions, userId });
}

// 健康检查
async function checkHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        return await response.json();
    } catch (error) {
        return { status: 'offline', error: error.message };
    }
}

// 用户注册
async function registerUser(username, email, password) {
    return await callAPI('/auth/register', { username, email, password });
}

// 用户登录
async function loginUser(username, password) {
    return await callAPI('/auth/login', { username, password });
}

// 文件上传
async function uploadFile(userId, file) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('user_id', userId);
    
    try {
        const response = await fetch(`${API_BASE_URL}/files/upload`, {
            method: 'POST',
            body: formData,
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('文件上传失败:', error);
        return { success: false, error: error.message };
    }
}

// 获取用户文件列表
async function getUserFiles(userId) {
    try {
        const response = await fetch(`${API_BASE_URL}/files/${userId}`);
        return await response.json();
    } catch (error) {
        console.error('获取文件列表失败:', error);
        return { success: false, error: error.message };
    }
}

// 获取用户历史记录
async function getUserHistory(userId) {
    try {
        const response = await fetch(`${API_BASE_URL}/history/${userId}`);
        return await response.json();
    } catch (error) {
        console.error('获取历史记录失败:', error);
        return { success: false, error: error.message };
    }
}

// 导出API模块
window.API = {
    // 用户管理
    registerUser,
    loginUser,
    uploadFile,
    getUserFiles,
    getUserHistory,
    
    // 职业分析 - KG4Career四组件架构
    analyzeResume,
    generateReport,
    analyzeQuiz,
    
    // 系统
    checkHealth,
    setBaseUrl: (url) => { API_BASE_URL = url; }
};
