// 排序相关功能模块

// 初始化排序状态
window.currentSort = { column: 2, direction: 'desc' };

/**
 * 表格排序函数
 * @param {number} columnIndex - 要排序的列索引
 */
window.sortTable = function (columnIndex) {
    if (!window.filteredResultsData) return;

    // 切换排序方向
    if (window.currentSort.column === columnIndex) {
        window.currentSort.direction = window.currentSort.direction === 'asc' ? 'desc' : 'asc';
    } else {
        window.currentSort.column = columnIndex;
        // 总分默认降序，其他默认升序
        window.currentSort.direction = (columnIndex === 2 || (window.scoringRules && columnIndex >= 3 && columnIndex < 3 + window.scoringRules.length)) ? 'desc' : 'asc';
    }

    // 根据列索引排序
    window.filteredResultsData.sort((a, b) => {
        let valueA, valueB;

        switch (columnIndex) {
            case 0: // 排名
                // 按原始排名排序
                const indexA = window.filteredResultsData.indexOf(a);
                const indexB = window.filteredResultsData.indexOf(b);
                valueA = indexA;
                valueB = indexB;
                break;
            case 1: // 投标人名称
                valueA = a.bidder_name;
                valueB = b.bidder_name;
                const comparison = valueA.localeCompare(valueB, 'zh-CN');
                return window.currentSort.direction === 'asc' ? comparison : -comparison;
            case 2: // 总分
                valueA = a.total_score === '废标' ? -1 : (a.total_score || 0);
                valueB = b.total_score === '废标' ? -1 : (b.total_score || 0);
                break;
            default:
                // 评分项列 - 需要根据列索引找到对应的规则
                if (window.scoringRules && columnIndex >= 3) {
                    // 计算实际的评分项索引（扣除前两列：排名和投标人）
                    let targetRuleIndex = columnIndex - 2; // 减去排名和投标人列
                    
                    // 查找对应评分规则
                    let currentRuleIndex = 1; // 从1开始计数
                    let targetRule = null;

                    function findRuleByIndex(rules) {
                        for (const rule of rules) {
                            const isVeto = rule.is_veto || false;
                            if (!isVeto) {
                                if (rule.children && rule.children.length > 0) {
                                    // 处理子项
                                    for (const child of rule.children) {
                                        if (!child.is_veto) {
                                            if (currentRuleIndex === targetRuleIndex) {
                                                targetRule = child;
                                                return true;
                                            }
                                            currentRuleIndex++;
                                        }
                                    }
                                } else {
                                    // 叶子节点
                                    if (currentRuleIndex === targetRuleIndex) {
                                        targetRule = rule;
                                        return true;
                                    }
                                    currentRuleIndex++;
                                }
                            }
                        }
                        return false;
                    }

                    if (findRuleByIndex(window.scoringRules) && targetRule) {
                        // 创建一个映射以便快速查找评分
                        const scoreMapA = {};
                        const scoreMapB = {};

                        function buildScoreMap(scores, scoreMap) {
                            if (Array.isArray(scores)) {
                                scores.forEach(score => {
                                    if (score.criteria_name) {
                                        scoreMap[score.criteria_name] = score;
                                    }
                                    if (score.children && score.children.length > 0) {
                                        buildScoreMap(score.children, scoreMap);
                                    }
                                });
                            }
                        }

                        buildScoreMap(a.detailed_scores, scoreMapA);
                        buildScoreMap(b.detailed_scores, scoreMapB);

                        const scoreA = scoreMapA[targetRule.criteria_name];
                        const scoreB = scoreMapB[targetRule.criteria_name];
                        valueA = scoreA ? (scoreA.score || 0) : 0;
                        valueB = scoreB ? (scoreB.score || 0) : 0;
                    } else {
                        valueA = 0;
                        valueB = 0;
                    }
                } else {
                    return 0;
                }
        }

        if (valueA < valueB) {
            return window.currentSort.direction === 'asc' ? -1 : 1;
        }
        if (valueA > valueB) {
            return window.currentSort.direction === 'asc' ? 1 : -1;
        }
        return 0;
    });

    // 重新渲染表格
    if (typeof renderResultsTable === 'function') {
        renderResultsTable();
    }

    // 更新排序图标
    updateSortIcons();
};

/**
 * 更新排序图标
 */
function updateSortIcons() {
    // 清除所有排序图标
    const allIcons = document.querySelectorAll('[id^="sortIcon"]');
    allIcons.forEach(icon => {
        icon.innerHTML = '';
    });

    // 检查window.currentSort是否存在
    if (!window.currentSort) {
        window.currentSort = { column: 2, direction: 'desc' };
    }

    // 设置当前排序列的图标
    const currentIconElement = document.getElementById(`sortIcon${window.currentSort.column}`);
    if (currentIconElement) {
        currentIconElement.innerHTML = window.currentSort.direction === 'asc'
            ? '<i class="fas fa-sort-up"></i>'
            : '<i class="fas fa-sort-down"></i>';
    }
}

// 绑定排序事件
function bindSortEvents() {
    // 确保DOM已经更新后再绑定事件
    setTimeout(() => {
        const header0 = document.getElementById('sort-header-0');
        const header1 = document.getElementById('sort-header-1');
        const header2 = document.getElementById('sort-header-2');

        if (header0) header0.addEventListener('click', () => sortTable(0));
        if (header1) header1.addEventListener('click', () => sortTable(1));
        if (header2) header2.addEventListener('click', () => sortTable(2));
    }, 0);
}

// 导出函数供其他模块使用
window.updateSortIcons = updateSortIcons;
window.bindSortEvents = bindSortEvents;