// 表格相关功能模块

/**
 * 构建并插入动态表头
 * @param {Array} scoringRules - 评分规则数组
 */
function buildAndInsertHeaders(scoringRules) {
    // 清除现有动态表头
    clearDynamicHeaders();

    // 创建并插入一级和二级表头
    if (scoringRules && scoringRules.length > 0) {
        const topLevelHeaders = [];
        const secondLevelHeaders = [];
        let columnIndex = 2; // 从第3列开始（排名、投标人之后）

        // 递归处理评分规则，构建表头
        function buildHeaders(rules) {
            rules.forEach(rule => {
                // 检查是否为否决项规则
                const isVeto = rule.is_veto || false;
                if (!isVeto) {  // 只显示非否决项的评分项
                    if (rule.children && rule.children.length > 0) {
                        // 过滤出非否决项的子项
                        const validChildren = rule.children.filter(child => !child.is_veto);
                        
                        if (validChildren.length > 0) {
                            // 父项：计算子项数量
                            const childCount = validChildren.length;
                            
                            // 添加一级表头（父项）
                            topLevelHeaders.push({
                                html: `
                                    <th colspan="${childCount}" style="text-align: center; background-color: ${getCategoryColor(rule.category)}">
                                        ${simplifyCriteriaName(rule.criteria_name)}（${rule.max_score}分）
                                    </th>
                                `,
                                position: columnIndex
                            });

                            // 递归处理子项
                            validChildren.forEach(child => {
                                // 添加二级表头（子项）
                                secondLevelHeaders.push({
                                    html: `
                                        <th style="cursor: pointer; text-align: center;" onclick="sortTable(${columnIndex})">
                                            ${simplifyCriteriaName(child.criteria_name)}<br><small>(${child.max_score}分)</small>
                                            <span id="sortIcon${columnIndex}"></span>
                                        </th>
                                    `,
                                    position: columnIndex
                                });
                                columnIndex++;
                            });
                        }
                    } else {
                        // 叶子节点（无子项的评分项）
                        // 添加一级表头（单列表头），并设置rowspan=2
                        topLevelHeaders.push({
                            html: `
                                <th rowspan="2" style="cursor: pointer; text-align: center; vertical-align: middle; background-color: ${getCategoryColor(rule.category)}" onclick="sortTable(${columnIndex})">
                                    ${simplifyCriteriaName(rule.criteria_name)}（${rule.max_score}分）
                                    <span id="sortIcon${columnIndex}"></span>
                                </th>
                            `,
                            position: columnIndex
                        });
                        columnIndex++;
                    }
                }
            });
        }

        // 构建表头
        buildHeaders(scoringRules);

        // 插入一级表头（在价格分列之前插入）
        const priceScoreHeader = document.getElementById('price-score-header');
        if (priceScoreHeader) {
            // 按照列位置排序插入
            topLevelHeaders
                .sort((a, b) => a.position - b.position)
                .forEach(header => {
                    priceScoreHeader.insertAdjacentHTML('beforebegin', header.html);
                });
        }

        // 插入二级表头
        const secondHeaderRow = document.querySelector('#resultsTable thead tr:nth-child(2)');
        if (secondHeaderRow) {
            // 按照列位置排序插入
            secondLevelHeaders
                .sort((a, b) => a.position - b.position)
                .forEach(header => {
                    secondHeaderRow.insertAdjacentHTML('beforeend', header.html);
                });
        }
    }
}

/**
 * 清除现有的动态表头
 */
function clearDynamicHeaders() {
    const headerRow = document.querySelector('#resultsTable thead tr');
    const secondHeaderRow = document.querySelector('#resultsTable thead tr:nth-child(2)');
    
    if (headerRow) {
        // 保留前两列（排名、投标人）和最后两列（价格分、总分）
        // 从后往前删除，避免索引变化问题
        const headers = Array.from(headerRow.querySelectorAll('th'));
        for (let i = headers.length - 1; i >= 0; i--) {
            // 保留前两列（排名、投标人）和最后两列（价格分、总分）
            if (i >= 2 && i < headers.length - 2) {
                headers[i].remove();
            }
        }
    }

    if (secondHeaderRow) {
        // 清除所有动态插入的二级表头，但保留空的<tr>元素
        secondHeaderRow.innerHTML = '';
    }
}

/**
 * 根据评分项类别获取背景颜色
 * @param {string} category - 评分项类别
 * @returns {string} - 对应的背景颜色
 */
function getCategoryColor(category) {
    switch (category) {
        case '商务部分':
            return '#e3f2fd'; // 浅蓝
        case '服务部分':
            return '#f3e5f5'; // 浅紫
        case '技术部分':
            return '#e8f5e8'; // 浅绿
        default:
            return '#ffffff'; // 白色
    }
}

/**
 * 简化评分项名称
 * @param {string} name - 原始评分项名称
 * @returns {string} - 简化后的名称
 */
function simplifyCriteriaName(name) {
    if (!name) return '';
    
    // 移除括号内的内容
    return name.replace(/（.*?）/g, '').replace(/\(.*?\)/g, '');
}

/**
 * 简化投标方名称显示
 * @param {string} bidderName - 原始投标方名称
 * @returns {string} - 简化后的名称
 */
function simplifyBidderName(bidderName) {
    if (!bidderName) return '未知';

    // 尝试从投标文件封面提取公司名称
    // 匹配"投标人（或投标方或者投标单位等等类似的）：XXXX公司"格式
    const coverPattern = /(投标人|投标方|投标单位|报价人|报价单位).*?[：:]\s*([^：:\r\n\u3000]+公司)/i;
    const coverMatch = bidderName.match(coverPattern);
    if (coverMatch && coverMatch[2]) {
        return coverMatch[2].trim();
    }

    // 更智能地提取公司名称
    let simplified = bidderName
        // 移除常见的后缀和无关信息
        .replace(/\s*\(盖单位章\).*$/i, '') // 移除"(盖单位章)"及之后的内容
        .replace(/\s*法定代表人.*$/i, '') // 移除"法定代表人"及之后的内容
        .replace(/\s*单位负责人.*$/i, '') // 移除"单位负责人"及之后的内容
        .replace(/\s*授权代表.*$/i, '') // 移除"授权代表"及之后的内容
        .replace(/\s*签字.*$/i, '') // 移除"签字"及之后的内容
        .replace(/\s*\d{4}\s*年.*$/i, '') // 移除日期及之后的内容
        .replace(/\s*第\s*\d+\s*页.*$/i, '') // 移除页码及之后的内容
        .replace(/\s*共\s*\d+\s*页.*$/i, '') // 移除总页数及之后的内容
        .replace(/\s*招杯编号.*$/i, '') // 移除"招杯编号"及之后的内容
        .replace(/\s*MSZB.*$/i, '') // 移除"MSZB"编号及之后的内容
        .replace(/\s*\(正本\).*$/i, '') // 移除"(正本)"及之后的内容
        .replace(/\s*中车眉山车辆有限公司.*$/i, '') // 移除特定公司名称
        .replace(/\s*[A-Za-z\s\.,]+$/, '') // 移除末尾的英文内容
        .trim();

    // 如果还有英文内容，尝试提取中文部分
    const chineseMatch = simplified.match(/[\u4e00-\u9fa5]+/g);
    if (chineseMatch && chineseMatch.length > 0) {
        // 取最长的中文段作为公司名称
        simplified = chineseMatch.reduce((longest, current) =>
            current.length > longest.length ? current : longest, '');
    }

    // 如果名称太长，截取前20个字符
    if (simplified.length > 20) {
        simplified = simplified.substring(0, 20) + '...';
    }

    // 如果处理后名称为空，返回原始名称的前20个字符
    if (!simplified) {
        simplified = bidderName.substring(0, 20);
    }

    return simplified;
}

// 导出函数供其他模块使用
window.buildAndInsertHeaders = buildAndInsertHeaders;
window.clearDynamicHeaders = clearDynamicHeaders;
window.simplifyBidderName = simplifyBidderName;