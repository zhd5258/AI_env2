/*
 * @作者           : KingFreeDom
 * @创建时间         : 2025-10-03 14:35:26
 * @最近一次编辑者      : KingFreeDom
 * @最近一次编辑时间     : 2025-10-03 14:35:29
 * @文件相对于项目的路径   : \AI_env2\public\js\main.js
 * 
 * Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved. 
 */
// 主JavaScript文件

// 文件上传功能
document.addEventListener('DOMContentLoaded', function () {
    console.log('AI_env2应用已加载');

    // 可以在这里添加更多的前端交互逻辑
});

// 通用的API调用函数
async function callAPI (endpoint, options = {}) {
    try {
        const response = await fetch(`/api${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error('API调用失败:', error);
        throw error;
    }
}
