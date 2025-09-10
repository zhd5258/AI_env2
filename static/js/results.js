// 结果展示和表格渲染功能
document.addEventListener('DOMContentLoaded', function () {
    // 显示分析结果
    window.displayResults = async function (results) {
        const resultArea = document.getElementById('resultArea');
        if (!resultArea) {
            console.error('找不到结果区域');
            return;
        }

        // 清除进度显示
        document.getElementById('progressContainer').style.display = 'none';

        if (results.error) {
            resultArea.innerHTML = `<div class="alert alert-danger"><i class="fas fa-exclamation-circle me-2"></i>分析失败: ${results.error}</div>`;
            return;
        }

        const resultsArray = Array.isArray(results) ? results : [results];

        // 按总分排序(从高到低)作为默认排序
        resultsArray.sort((a, b) => {
            // 处理废标情况
            const scoreA = a.total_score === '废标' ? -1 : (a.total_score || 0);
            const scoreB = b.total_score === '废标' ? -1 : (b.total_score || 0);
            return scoreB - scoreA;
        });

        let html = '';

        // 添加视图切换按钮(汇总表, 详细视图, 图表视图)
        html += `
            <div class="mb-4 text-center">
                <div class="btn-group" role="group">
                    <button class="btn btn-primary" onclick="showSummaryTable()">
                        <i class="fas fa-table me-2"></i>汇总表
                    </button>
                    <button class="btn btn-outline-secondary" onclick="showDetailedView()">
                        <i class="fas fa-list me-2"></i>详细视图
                    </button>
                    <button class="btn btn-outline-success" onclick="showChartView()">
                        <i class="fas fa-chart-line me-2"></i>图表视图
                    </button>
                </div>
            </div>
        `;

        // 添加汇总表容器(按照评价.xlsx格式)
        html += `
            <div id="summaryTable" class="table-responsive mb-4" style="display: block;">
                <div class="card">
                    <div class="card-body">                        
                        <!-- 表格控制区域 -->
                        <div class="table-controls mb-3">
                            <div class="row">
                                <div class="col-md-4 mb-2">
                                    <div class="input-group">
                                        <span class="input-group-text"><i class="fas fa-search"></i></span>
                                        <input type="text" id="tableSearch" class="form-control" placeholder="搜索投标人...">
                                    </div>
                                </div>
                                <div class="col-md-4 mb-2">
                                    <div class="input-group">
                                        <span class="input-group-text"><i class="fas fa-filter"></i></span>
                                        <select id="scoreFilter" class="form-control">
                                            <option value="">所有投标人</option>
                                            <option value="valid">有效投标人</option>
                                            <option value="invalid">废标投标人</option>
                                        </select>
                                    </div>
                                </div>
                                <div class="col-md-4 mb-2">
                                    <div class="btn-group w-100" role="group">
                                        <button class="btn btn-outline-primary" onclick="refreshSummaryTable()">
                                            <i class="fas fa-sync-alt me-2"></i>刷新
                                        </button>
                                        <button class="btn btn-outline-secondary" onclick="showScoringRules()">
                                            <i class="fas fa-list me-2"></i>评分规则
                                        </button>
                                        <button class="btn btn-outline-success" onclick="exportTableToCSV()">
                                            <i class="fas fa-download me-2"></i>导出
                                        </button>
                                        <button class="btn btn-outline-warning" onclick="recalculatePriceScores(event)">
                                            <i class="fas fa-calculator me-2"></i>重新计算价格分
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="table-responsive">
                            <table class="table table-bordered table-hover data-table" id="resultsTable">
                                <thead class="table-primary">
                                    <tr>
                                        <th rowspan="2" style="vertical-align: middle; text-align: center;">
                                            排名
                                        </th>
                                        <th rowspan="2" style="vertical-align: middle; text-align: center;">
                                            投标人
                                        </th>
                                        <!-- 评分项表头将在这里动态插入 -->
                                        <th rowspan="2" style="vertical-align: middle; text-align: center; background-color: #fff3e0;" id="price-score-header">
                                            价格分(40分)
                                        </th>
                                        <th rowspan="2" style="vertical-align: middle; text-align: center;">
                                            总分
                                        </th>
                                    </tr>
                                    <tr>
                                        <!-- 二级表头将在这里动态插入 -->
                                    </tr>
                                </thead>
                                <tbody id="resultsTableBody">
                                </tbody>
                            </table>
                        </div>
                        <!-- 分页控件 -->
                        <div class="d-flex justify-content-center mt-3">
                            <nav>
                                <ul class="pagination" id="tablePagination">
                                    <!-- 分页按钮将在这里动态生成 -->
                                </ul>
                            </nav>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // 详细视图容器（包含原来的详细评分信息）
        html += `
            <div id="detailedView" style="display: none;">
                <div class="card">
                    <div class="card-body">
                        <h4 class="mb-4">详细视图</h4>
        `;

        resultsArray.forEach((result, index) => {
            // 根据排名设置徽章样式
            let rankBadge = '';
            switch (index + 1) {
                case 1:
                    rankBadge = 'rank-1';
                    break;
                case 2:
                    rankBadge = 'rank-2';
                    break;
                case 3:
                    rankBadge = 'rank-3';
                    break;
                default:
                    rankBadge = 'rank-other';
            }

            // 处理总分显示
            let totalScoreDisplay = 'N/A';
            if (result.total_score === '废标') {
                totalScoreDisplay = '<span class="badge bg-danger">废标</span>';
            } else if (result.total_score !== undefined) {
                totalScoreDisplay = result.total_score.toFixed(2);
            }

            html += `
                <div class="card bidder-card mb-4">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h5 class="mb-0">
                                <span class="score-badge ${rankBadge} me-3">${index + 1}</span>
                                投标人: ${result.bidder_name}
                            </h5>
                            <div class="text-end">
                                <div class="fs-6">总得分</div>
                                <div class="score-badge ${rankBadge} fs-5">${totalScoreDisplay}</div>
                            </div>
                        </div>
                        <h6 class="mt-4 mb-3"><i class="fas fa-list me-2"></i>详细评分及依据</h6>
                        <div class="accordion" id="accordion-${index}">
                            ${renderScoresTree(result.detailed_scores, `accordion-${index}`)}
                        </div>
                    </div>
                </div>
            `;
        });

        html += `
                    </div>
                </div>
            </div>
        `;

        // 图表视图容器
        html += `
            <div id="chartView" style="display: none;">
                <div class="card">
                    <div class="card-body">
                        <h4 class="mb-4">图表视图</h4>
                        
                        <!-- 图表控制区域 -->
                        <div class="row mb-4">
                            <div class="col-md-8">
                                <div class="btn-group" role="group">
                                    <button class="btn btn-outline-primary active" onclick="switchChartType('total')">
                                        <i class="fas fa-chart-bar me-2"></i>总分对比
                                    </button>
                                    <button class="btn btn-outline-primary" onclick="switchChartType('price')">
                                        <i class="fas fa-dollar-sign me-2"></i>价格分析
                                    </button>
                                    <button class="btn btn-outline-primary" onclick="switchChartType('detailed')">
                                        <i class="fas fa-chart-line me-2"></i>详细评分
                                    </button>
                                    <button class="btn btn-outline-primary" onclick="switchChartType('distribution')">
                                        <i class="fas fa-chart-pie me-2"></i>分布分析
                                    </button>
                                </div>
                            </div>
                            <div class="col-md-4 text-end">
                                <button class="btn btn-outline-success" onclick="exportCharts()">
                                    <i class="fas fa-download me-2"></i>导出图表
                                </button>
                            </div>
                        </div>

                        <!-- 总分对比图 -->
                        <div id="totalScoreChart" class="chart-container">
                            <div class="row">
                                <div class="col-md-8">
                                    <canvas id="scoreChart" height="100"></canvas>
                                </div>
                                <div class="col-md-4">
                                    <canvas id="scoreDistributionChart" height="100"></canvas>
                                </div>
                            </div>
                        </div>

                        <!-- 价格分析图 -->
                        <div id="priceAnalysisChart" class="chart-container" style="display: none;">
                            <div class="row">
                                <div class="col-md-7">
                                    <canvas id="priceChartCanvas" height="100"></canvas>
                                </div>
                                <div class="col-md-5">
                                    <div id="price-table-container"></div>
                                </div>
                            </div>
                        </div>

                        <!-- 详细评分对比图 -->
                        <div id="detailedScoreChart" class="chart-container" style="display: none;">
                            <div class="row">
                                <div class="col-12">
                                    <canvas id="detailedScoreChartCanvas" height="80"></canvas>
                                </div>
                            </div>
                        </div>

                        <!-- 分布分析图 -->
                        <div id="distributionAnalysisChart" class="chart-container" style="display: none;">
                            <div class="row">
                                <div class="col-md-6">
                                    <canvas id="scoreRangeChart" height="100"></canvas>
                                </div>
                                <div class="col-md-6">
                                    <canvas id="categoryScoreChart" height="100"></canvas>
                                </div>
                            </div>
                        </div>

                        <!-- 统计信息 -->
                        <div class="row mt-4">
                            <div class="col-12">
                                <div class="card">
                                    <div class="card-body">
                                        <h5 class="card-title"><i class="fas fa-info-circle me-2"></i>统计信息</h5>
                                        <div class="row" id="statisticsInfo">
                                            <!-- 统计信息将通过JavaScript动态填充 -->
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        resultArea.innerHTML = html;

        // 保存结果数据到全局变量，以便排序时使用
        window.resultsData = [...resultsArray];
        window.filteredResultsData = [...resultsArray]; // 用于过滤的数据

        // 保存结果数据到全局变量，以便排序时使用
        window.resultsData = [...resultsArray];
        window.filteredResultsData = [...resultsArray]; // 用于过滤的数据

        // 获取评分规则
        let scoringRules = [];
        try {
            const scoringRulesResponse = await fetch(`/api/projects/${window.currentProjectId}/scoring-rules`);
            if (scoringRulesResponse.ok) {
                scoringRules = await scoringRulesResponse.json();
                window.scoringRules = scoringRules;
            }
        } catch (error) {
            console.error('获取评分规则失败:', error);
        }

        // 构建并插入动态表头
        buildAndInsertHeaders(scoringRules);

        // 绑定排序事件处理程序
        bindSortEvents();

        // 绑定搜索和过滤事件
        bindSearchAndFilterEvents();

        // 默认显示汇总表（评标办法表格）
        showSummaryTable();

        // 初始化图表（但不显示）
        renderAllCharts(resultsArray);

        // 初始化排序状态
        window.currentSort = {
            column: 2, direction: 'desc' // 默认按总分降序排序
        };
        updateSortIcons();
    }

    // 调用所有图表渲染函数
    function renderAllCharts(data) {
        renderTotalScoreCharts(data);
        renderPriceAnalysisCharts(data);
        renderDetailedScoreChart(data);
        renderDistributionCharts(data);
        renderStatisticsInfo(data);
    }

    // 切换图表类型
    window.switchChartType = function (type) {
        // 隐藏所有图表容器
        document.getElementById('totalScoreChart').style.display = 'none';
        document.getElementById('priceAnalysisChart').style.display = 'none';
        document.getElementById('detailedScoreChart').style.display = 'none';
        document.getElementById('distributionAnalysisChart').style.display = 'none';

        // 更新按钮状态
        const buttons = document.querySelectorAll('#chartView .btn-group .btn');
        buttons.forEach(btn => {
            btn.classList.remove('active');
            btn.classList.add('btn-outline-primary');
        });
        
        const buttonMap = {
            'total': 0,
            'price': 1,
            'detailed': 2,
            'distribution': 3
        };
        const activeIndex = buttonMap[type];
        buttons[activeIndex].classList.add('active');
        buttons[activeIndex].classList.remove('btn-outline-primary');

        // 根据类型确定要显示的图表ID
        let chartId;
        switch(type) {
            case 'price':
                chartId = 'priceAnalysisChart';
                break;
            case 'detailed':
                chartId = 'detailedScoreChart';
                break;
            case 'distribution':
                chartId = 'distributionAnalysisChart';
                break;
            default:
                chartId = 'totalScoreChart';
        }
        
        // 显示对应的图表容器
        document.getElementById(chartId).style.display = 'block';
    };

    // 导出图表
    window.exportCharts = function () {
        const activeChartContainer = document.querySelector('#chartView .chart-container[style*="block"]');
        if (!activeChartContainer) {
            alert('没有可导出的图表');
            return;
        }

        // 获取当前显示的图表
        const canvas = activeChartContainer.querySelector('canvas');
        if (!canvas) {
            alert('图表数据不可用');
            return;
        }

        // 创建下载链接
        const link = document.createElement('a');
        link.download = '投标分析图表.png';
        link.href = canvas.toDataURL('image/png', 1.0);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    // 渲染统计信息
    function renderStatisticsInfo(data) {
        const statisticsInfo = document.getElementById('statisticsInfo');
        if (!statisticsInfo) return;

        const totalScores = data.map(result =>
            result.total_score === '废标' ? 0 : (result.total_score || 0)
        ).filter(score => score > 0);

        const validBidders = totalScores.length;
        const invalidBidders = data.length - validBidders;
        const averageScore = validBidders > 0 ? (totalScores.reduce((a, b) => a + b, 0) / validBidders).toFixed(2) : 0;
        const maxScore = validBidders > 0 ? Math.max(...totalScores).toFixed(2) : 0;
        const minScore = validBidders > 0 ? Math.min(...totalScores).toFixed(2) : 0;

        statisticsInfo.innerHTML = `
            <div class="col-md-3 mb-3"><div class="card text-center h-100"><div class="card-body"><h5 class="card-title text-primary">${data.length}</h5><p class="card-text">总投标人数</p></div></div></div>
            <div class="col-md-3 mb-3"><div class="card text-center h-100"><div class="card-body"><h5 class="card-title text-success">${validBidders}</h5><p class="card-text">有效投标人</p></div></div></div>
            <div class="col-md-3 mb-3"><div class="card text-center h-100"><div class="card-body"><h5 class="card-title text-danger">${invalidBidders}</h5><p class="card-text">废标投标人</p></div></div></div>
            <div class="col-md-3 mb-3"><div class="card text-center h-100"><div class="card-body"><h5 class="card-title text-info">${averageScore}</h5><p class="card-text">平均得分</p></div></div></div>
            <div class="col-md-3 mb-3"><div class="card text-center h-100"><div class="card-body"><h5 class="card-title text-warning">${maxScore}</h5><p class="card-text">最高得分</p></div></div></div>
            <div class="col-md-3 mb-3"><div class="card text-center h-100"><div class="card-body"><h5 class="card-title text-secondary">${minScore}</h5><p class="card-text">最低得分</p></div></div></div>
        `;
    }

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

    // 显示图-表视图
    window.showChartView = function () {
        document.getElementById('summaryTable').style.display = 'none';
        document.getElementById('detailedView').style.display = 'none';
        document.getElementById('chartView').style.display = 'block';

        // 更新按钮状态
        const buttons = document.querySelectorAll('#resultArea .btn-group .btn');
        buttons.forEach(btn => btn.classList.remove('btn-primary', 'btn-secondary', 'btn-success'));
        buttons[0].classList.add('btn-outline-primary');
        buttons[1].classList.add('btn-outline-secondary');
        buttons[2].classList.add('btn-success');
        
        // 默认显示总分图表
        switchChartType('total');
    };

    // 显示详细视图
    window.showDetailedView = function () {
        document.getElementById('summaryTable').style.display = 'none';
        document.getElementById('detailedView').style.display = 'block';
        document.getElementById('chartView').style.display = 'none';

        // 更新按钮状态
        const buttons = document.querySelectorAll('.btn-group .btn');
        buttons[0].classList.remove('btn-primary');
        buttons[0].classList.add('btn-outline-primary');
        buttons[1].classList.remove('btn-outline-secondary');
        buttons[1].classList.add('btn-secondary');
        buttons[2].classList.remove('btn-success');
        buttons[2].classList.add('btn-outline-success');
    };

    // 绑定搜索和过滤事件
    function bindSearchAndFilterEvents () {
        // 搜索功能
        const searchInput = document.getElementById('tableSearch');
        if (searchInput) {
            searchInput.addEventListener('input', function () {
                filterTable();
            });
        }

        // 过滤功能
        const filterSelect = document.getElementById('scoreFilter');
        if (filterSelect) {
            filterSelect.addEventListener('change', function () {
                filterTable();
            });
        }
    }

    // 过滤表格数据
    function filterTable () {
        const searchTerm = document.getElementById('tableSearch').value.toLowerCase();
        const filterValue = document.getElementById('scoreFilter').value;

        // 基于原始数据进行过滤
        let filteredData = [...window.resultsData];

        // 应用搜索过滤
        if (searchTerm) {
            filteredData = filteredData.filter(result =>
                result.bidder_name.toLowerCase().includes(searchTerm)
            );
        }

        // 应用状态过滤
        if (filterValue === 'valid') {
            filteredData = filteredData.filter(result =>
                result.total_score !== '废标'
            );
        } else if (filterValue === 'invalid') {
            filteredData = filteredData.filter(result =>
                result.total_score === '废标'
            );
        }

        // 更新过滤后的数据
        window.filteredResultsData = filteredData;

        // 重新渲染表格
        renderResultsTable();
    }

    // 绑定排序事件
    function bindSortEvents () {
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

    // 表格排序函数
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
                    comparison = valueA.localeCompare(valueB, 'zh-CN');
                    return window.currentSort.direction === 'asc' ? comparison : -comparison;
                    break;
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
        renderResultsTable();

        // 更新排序图标
        updateSortIcons();
    }

    // 更新排序图标
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

    // 简化投标方名称显示
    function simplifyBidderName (bidderName) {
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

// 重新渲染结果表格
function renderResultsTable () {
    const tableBody = document.getElementById('resultsTableBody');
    if (!tableBody) return;

    let html = '';
    const scoreUpdates = []; // 用于存储需要更新到后端的分数

    window.filteredResultsData.forEach((result, index) => {
        // 根据排名设置徽章样式
        let rankBadge = '';
        switch (index + 1) {
            case 1:
                rankBadge = 'rank-1';
                break;
            case 2:
                rankBadge = 'rank-2';
                break;
            case 3:
                rankBadge = 'rank-3';
                break;
            default:
                rankBadge = 'rank-other';
        }

        // 构建评分项单元格（根据动态表头顺序构建）
        let scoreCells = '';
        let totalScore = 0; // 计算总分
        
        if (window.scoringRules && result.detailed_scores) {
            // 创建一个映射以便快速查找评分
            const scoreMap = {};
            function buildScoreMap(scores) {
                if (Array.isArray(scores)) {
                    scores.forEach(score => {
                        if (score.criteria_name) {
                            scoreMap[score.criteria_name] = score;
                        }
                        if (score.children && score.children.length > 0) {
                            buildScoreMap(score.children);
                        }
                    });
                }
            }
            buildScoreMap(result.detailed_scores);

            // 根据动态表头顺序构建评分单元格
            function buildScoreCellsFromRules(rules) {
                rules.forEach(rule => {
                    // 检查是否为否决项规则
                    const isVeto = rule.is_veto || false;
                    if (!isVeto) {
                        if (rule.children && rule.children.length > 0) {
                            // 处理子项
                            rule.children.forEach(child => {
                                if (!child.is_veto) {
                                    const score = scoreMap[child.criteria_name];
                                    let scoreValue = 0; // 默认为0
                                        
                                    if (score && score.score !== undefined && score.score !== null) {
                                        scoreValue = score.score;
                                    }
                                    
                                    totalScore += scoreValue; // 累加到总分
                                    scoreCells += `<td>${scoreValue.toFixed(2)}</td>`;
                                }
                            });
                        } else {
                            // 处理叶子节点
                            const score = scoreMap[rule.criteria_name];
                            let scoreValue = 0; // 默认为0
                                
                            if (score && score.score !== undefined && score.score !== null) {
                                scoreValue = score.score;
                            }
                            
                            totalScore += scoreValue; // 累加到总分
                            scoreCells += `<td>${scoreValue.toFixed(2)}</td>`;
                        }
                    }
                });
            }

            buildScoreCellsFromRules(window.scoringRules);
        } else {
            // 如果没有评分规则或详细评分，需要根据window.scoringRules统计的数量填充空单元格
            // 先统计非否决项的数量
            let nonVetoCount = 0;
            if (window.scoringRules) {
                function countNonVetoRules(rules) {
                    rules.forEach(rule => {
                        const isVeto = rule.is_veto || false;
                        if (!isVeto) {
                            if (rule.children && rule.children.length > 0) {
                                rule.children.forEach(child => {
                                    if (!child.is_veto) {
                                        nonVetoCount++;
                                    }
                                });
                            } else {
                                nonVetoCount++;
                            }
                        }
                    });
                }
                countNonVetoRules(window.scoringRules);
            }
                
            // 填充评分项单元格
            for (let i = 0; i < nonVetoCount; i++) {
                scoreCells += '<td>0.00</td>';
            }
        }

        // 处理价格分（单独处理）
        let priceScoreValue = 0;
        if (result.price_score !== undefined && result.price_score !== null) {
            // 优先使用后端提供的price_score字段
            priceScoreValue = result.price_score;
        } else if (window.scoringRules && result.detailed_scores) {
            // 尝试从详细评分中获取价格分
            const scoreMap = {};
            function buildScoreMap(scores) {
                if (Array.isArray(scores)) {
                    scores.forEach(score => {
                        if (score.criteria_name) {
                            scoreMap[score.criteria_name] = score;
                        }
                        if (score.children && score.children.length > 0) {
                            buildScoreMap(score.children);
                        }
                    });
                }
            }
            buildScoreMap(result.detailed_scores);
            
            // 查找价格相关的评分项
            for (const [criteriaName, score] of Object.entries(scoreMap)) {
                if ((criteriaName.includes('价格') || criteriaName.includes('报价')) &&
                    score.score !== undefined && score.score !== null) {
                    priceScoreValue = score.score;
                    break;
                }
            }
        }

        totalScore += priceScoreValue; // 将价格分加入总分
        scoreCells += `<td class="table-info">${priceScoreValue.toFixed(2)}</td>`;

        // 处理总分显示
        let totalScoreDisplay = 'N/A';
        if (result.total_score === '废标') {
            totalScoreDisplay = '<span class="badge bg-danger">废标</span>';
        } else {
            // 始终使用前端计算的总分
            totalScoreDisplay = totalScore.toFixed(2);
        }

        // 如果计算出的分数与原始分数不同，则添加到待更新列表
        if (result.id && result.total_score !== totalScore) {
            scoreUpdates.push({ id: result.id, total_score: totalScore });
            result.total_score = totalScore; // 更新本地数据，防止重复发送
        }

        // 汇总表行（严格按照评标办法表格结构显示）
        html += `
                <tr class="align-middle" data-rank="${index + 1}" data-name="${result.bidder_name}" data-score="${(result.total_score !== undefined && result.total_score !== null) ? result.total_score : totalScore}">
                    <td><span class="score-badge ${rankBadge}">${index + 1}</span></td>
                    <td><strong>${simplifyBidderName(result.bidder_name)}</strong></td>
                    ${scoreCells}
                    <td><span class="score-badge ${rankBadge}">${totalScoreDisplay}</span></td>
                </tr>
            `;
    });

    tableBody.innerHTML = html;

    // 如果有需要更新的分数，则发送到后端
    if (scoreUpdates.length > 0) {
        updateScoresInBackend(scoreUpdates);
    }

    // 更新排序图标
    updateSortIcons();
}

// 将更新后的分数批量发送到后端
function updateScoresInBackend(updates) {
    // 使用 a.id 和 b.id 进行更稳定的排序
    updates.sort((a, b) => a.id - b.id);

    fetch('/api/analysis-results/bulk-update-scores', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(updates),
    })
    .then(response => {
        if (!response.ok) {
            console.error('向后端更新分数失败');
        }
        return response.json();
    })
    .then(data => {
        console.log('分数更新成功: ', data.message);
    })
    .catch(error => {
        console.error('更新分数时出错:', error);
    });
}

// 递归渲染评分树
function renderScoresTree (scores, parentId, level = 0) {
    let html = '';
    if (!scores) return html;

    scores.forEach((score, index) => {
        const itemId = `${parentId}-item-${level}-${index}`;
        const collapseId = `${parentId}-collapse-${level}-${index}`;
        const hasChildren = score.children && score.children.length > 0;

        // 检查是否为否决项规则
        const isVeto = score.is_veto || false;

        html += '<div class="accordion-item">';
        html += `
                <h2 class="accordion-header" id="${itemId}">
                    <button class="accordion-button ${hasChildren ? '' : 'collapsed'}" type="button" ${hasChildren ? `data-bs-toggle="collapse" data-bs-target="#${collapseId}"` : 'disabled'}>
                        <span class="flex-grow-1">${score.criteria_name} ${isVeto ? '<span class="badge bg-danger ms-2">否决项</span>' : ''}</span>
                        <span class="badge bg-primary rounded-pill me-2">${isVeto ? '不评分' : `${score.score ? score.score.toFixed(2) : 'N/A'} / ${score.max_score}`}</span>
                    </button>
                </h2>
            `;

        if (hasChildren) {
            html += `
                    <div id="${collapseId}" class="accordion-collapse collapse" aria-labelledby="${itemId}">
                        <div class="accordion-body">
                            ${renderScoresTree(score.children, collapseId, level + 1)}
                        </div>
                    </div>
                `;
        }

        html += '</div>';
    });

    return html;
}

// 显示评分规则
window.showScoringRules = async function () {
    // 从URL中获取project_id（简单实现，实际项目中可能需要更好的方式）
    const urlParams = new URLSearchParams(window.location.search);
    const projectId = urlParams.get('project_id') || 1; // 默认为1

    try {
        const response = await fetch(`/api/projects/${projectId}/scoring-rules`);
        const scoringRules = await response.json();

        if (scoringRules.error) {
            alert('获取评分规则失败: ' + scoringRules.error);
            return;
        }

        const modal = new bootstrap.Modal(document.getElementById('resultDetailsModal'));
        const modalTitle = document.getElementById('resultDetailsModalLabel');
        const modalBody = document.getElementById('modalBody');

        modalTitle.textContent = '评分规则';
        let tableHtml = `
                <div class="container-fluid">
                    <div class="row">
                        <div class="col-md-12">
                            <div class="table-responsive">
                                <table class="table table-hover">
                                    <thead class="table-dark">
                                        <tr>
                                            <th><i class="fas fa-layer-group me-2"></i>类别</th>
                                            <th><i class="fas fa-tasks me-2"></i>评分项</th>
                                            <th><i class="fas fa-star-half-alt me-2"></i>满分</th>
                                            <th><i class="fas fa-balance-scale me-2"></i>权重</th>
                                            <th><i class="fas fa-align-left me-2"></i>描述</th>
                                        </tr>
                                    </thead>
                                    <tbody>
            `;

        scoringRules.forEach(rule => {
            // 检查是否为否决项规则
            const isVeto = rule.is_veto || false;
            tableHtml += `
                    <tr>
                        <td>${rule.category || 'N/A'} ${isVeto ? '<span class="badge bg-danger ms-2">否决项</span>' : ''}</td>
                        <td>${rule.criteria_name || 'N/A'}</td>
                        <td>${isVeto ? '不评分' : (rule.max_score || 'N/A')}</td>
                        <td>${rule.weight || 'N/A'}</td>
                        <td>${rule.description || 'N/A'}</td>
                    </tr>
                `;
        });

        tableHtml += `
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            `;

        modalBody.innerHTML = tableHtml;
        modal.show();
    } catch (error) {
        console.error('Error:', error);
        alert('获取评分规则失败: ' + error.message);
    }
};

// 刷新汇总表
window.refreshSummaryTable = async function () {
    if (!window.currentProjectId) return;

    try {
        // 重新获取评分规则
        const scoringRulesResponse = await fetch(`/api/projects/${window.currentProjectId}/scoring-rules`);
        if (scoringRulesResponse.ok) {
            const scoringRules = await scoringRulesResponse.json();
            window.scoringRules = scoringRules;

            // 重新渲染汇总表
            renderResultsTable();

            // 更新表头
            updateTableHeaders();
        }
    } catch (error) {
        console.error('刷新评分规则失败:', error);
        alert('刷新评分规则失败: ' + error.message);
    }
};

// 更新表头
function updateTableHeaders () {
    // 清除现有的评分项列头
    const headerRow = document.querySelector('#resultsTable thead tr');
    if (headerRow) {
        // 保留前两列（排名、投标人）和最后一列（总分）
        const headers = headerRow.querySelectorAll('th');
        // 删除中间的评分项列（除了前两列和最后一列）
        for (let i = headers.length - 2; i > 1; i--) {
            if (headers[i]) {
                headers[i].remove();
            }
        }
    }

    // 重新插入评分项列头
    if (window.scoringRules) {
        let columnIndex = 3; // 从第3列开始（排名、投标人、总分之后）

        // 递归处理评分规则，包括父项和子项
        function buildColumnHeaders (rules) {
            rules.forEach(rule => {
                // 检查是否为否决项规则
                const isVeto = rule.is_veto || false;
                if (!isVeto) { // 只显示非否决项的评分项
                    if (rule.children && rule.children.length > 0) {
                        // 父项：显示父项名称和总分
                        const header = document.createElement('th');
                        header.style.cursor = 'pointer';
                        header.className = 'table-warning';
                        header.setAttribute('onclick', `sortTable(${columnIndex})`);
                        header.innerHTML = `
                                ${rule.criteria_name} <span id="sortIcon${columnIndex}"></span>
                                <div class="small text-white">${rule.max_score}分</div>
                            `;
                        headerRow.insertBefore(header, headerRow.querySelector('th:last-child'));
                        columnIndex++;

                        // 子项：递归处理子项
                        buildColumnHeaders(rule.children);
                    } else {
                        // 叶子节点：显示具体的评分项
                        const header = document.createElement('th');
                        header.style.cursor = 'pointer';
                        header.setAttribute('onclick', `sortTable(${columnIndex})`);
                        header.innerHTML = `
                                ${rule.criteria_name} <span id="sortIcon${columnIndex}"></span>
                                <div class="small text-white">${rule.max_score}分</div>
                            `;
                        headerRow.insertBefore(header, headerRow.querySelector('th:last-child'));
                        columnIndex++;
                    }
                }
            });
        }

        buildColumnHeaders(window.scoringRules);
    }
}

// 添加导出表格为CSV的功能
window.exportTableToCSV = function () {
    if (!window.resultsData || window.resultsData.length === 0) {
        alert('没有数据可导出');
        return;
    }

    // 创建CSV内容
    let csvContent = '\uFEFF'; // 添加BOM以支持中文

    // 创建表头
    let headers = ['排名', '投标人'];

    // 添加评分项列头
    if (window.scoringRules) {
        // 递归处理评分规则，包括父项和子项
        function buildCSVHeaders (rules) {
            rules.forEach(rule => {
                // 检查是否为否决项规则
                const isVeto = rule.is_veto || false;
                if (!isVeto) { // 只显示非否决项的评分项
                    if (rule.children && rule.children.length > 0) {
                        // 父项：添加父项名称
                        headers.push(rule.criteria_name);
                        // 子项：递归处理子项
                        buildCSVHeaders(rule.children);
                    } else {
                        // 叶子节点：添加具体的评分项名称
                        headers.push(rule.criteria_name);
                    }
                }
            });
        }

        buildCSVHeaders(window.scoringRules);
    }

    headers.push('总分');
    csvContent += headers.join(',') + '\n';

    // 添加数据行
    window.resultsData.forEach((result, index) => {
        let row = [index + 1, result.bidder_name];

        // 添加评分项数据
        if (window.scoringRules && result.detailed_scores) {
            // 创建一个映射以便快速查找评分
            const scoreMap = {};
            function buildScoreMap (scores) {
                if (Array.isArray(scores)) {
                    scores.forEach(score => {
                        if (score.criteria_name) {
                            scoreMap[score.criteria_name] = score;
                        }
                        if (score.children && score.children.length > 0) {
                            buildScoreMap(score.children);
                        }
                    });
                }
            }
            buildScoreMap(result.detailed_scores);

            // 递归处理评分规则，包括父项和子项
            function buildCSVScoreCells (rules) {
                rules.forEach(rule => {
                    // 检查是否为否决项规则
                    const isVeto = rule.is_veto || false;
                    if (!isVeto) { // 只显示非否决项的评分项
                        if (rule.children && rule.children.length > 0) {
                            // 父项：计算子项分数之和
                            let parentScore = 0;
                            rule.children.forEach(child => {
                                const childScore = scoreMap[child.criteria_name];
                                if (childScore && childScore.score) {
                                    parentScore += childScore.score;
                                }
                            });
                            row.push(parentScore.toFixed(2));

                            // 子项：递归处理子项
                            buildCSVScoreCells(rule.children);
                        } else {
                            // 叶子节点：显示具体的评分项分数
                            const score = scoreMap[rule.criteria_name];
                            if (score && score.score !== undefined && score.score !== null) {
                                row.push(score.score.toFixed(2));
                            } else {
                                row.push('0.00');
                            }
                        }
                    }
                });
            }

            buildCSVScoreCells(window.scoringRules);
        }

        // 添加总分（价格分不包含在内）
        let totalScoreDisplay = 'N/A';
        if (result.total_score === '废标') {
            totalScoreDisplay = '废标';
        } else if (result.total_score !== undefined) {
            totalScoreDisplay = result.total_score.toFixed(2);
        }
        row.push(totalScoreDisplay);

        csvContent += row.join(',') + '\n';
    });

    // 创建下载链接
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', '投标评分结果.csv');
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
};

// 显示单个评分项的详情
window.showScoreDetails = function (bidderName, index, score) {
    const modal = new bootstrap.Modal(document.getElementById('resultDetailsModal'));
    const modalTitle = document.getElementById('resultDetailsModalLabel');
    const modalBody = document.getElementById('modalBody');

    modalTitle.textContent = `评分详情 - ${bidderName} - ${score.criteria_name}`;
    // 检查是否为否决项规则
    const isVeto = score.is_veto || false;

    modalBody.innerHTML = `
            <div class="container-fluid">
                <div class="row">
                    <div class="col-md-12">
                        <div class="table-responsive">
                            <table class="table table-bordered">
                                <tr>
                                    <th class="table-primary"><i class="fas fa-tasks me-2"></i>评分项</th>
                                    <td>${score.criteria_name || 'N/A'} ${isVeto ? '<span class="badge bg-danger ms-2">否决项</span>' : ''}</td>
                                </tr>
                                <tr>
                                    <th class="table-primary"><i class="fas fa-star-half-alt me-2"></i>满分</th>
                                    <td>${isVeto ? '不评分' : (score.max_score || 'N/A')}</td>
                                </tr>
                                <tr>
                                    <th class="table-primary"><i class="fas fa-star me-2"></i>得分</th>
                                    <td>${isVeto ? '不评分' : (score.score ? score.score.toFixed(2) : 'N/A')}</td>
                                </tr>
                                <tr>
                                    <th class="table-primary"><i class="fas fa-comment me-2"></i>评分说明</th>
                                    <td>${score.reason || 'N/A'}</td>
                                </tr>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        `;

    modal.show();
};

// 显示所有评分项
window.showAllScores = function (bidderName, allScores) {
    const modal = new bootstrap.Modal(document.getElementById('resultDetailsModal'));
    const modalTitle = document.getElementById('resultDetailsModalLabel');
    const modalBody = document.getElementById('modalBody');

    modalTitle.textContent = `全部评分详情 - ${bidderName}`;
    let tableHtml = `
            <div class="container-fluid">
                <div class="row">
                    <div class="col-md-12">
                        <div class="table-responsive">
                            <table class="table table-hover">
                                <thead class="table-dark">
                                    <tr>
                                        <th><i class="fas fa-tasks me-2"></i>评分项</th>
                                        <th><i class="fas fa-star-half-alt me-2"></i>满分</th>
                                        <th><i class="fas fa-star me-2"></i>得分</th>
                                        <th><i class="fas fa-comment me-2"></i>评分说明</th>
                                    </tr>
                                </thead>
                                <tbody>
        `;

    allScores.forEach(score => {
        // 检查是否为否决项规则
        const isVeto = score.is_veto || false;
        tableHtml += `
                <tr>
                    <td>${score.criteria_name || 'N/A'} ${isVeto ? '<span class="badge bg-danger ms-2">否决项</span>' : ''}</td>
                    <td>${isVeto ? '不评分' : (score.max_score || 'N/A')}</td>
                    <td>${isVeto ? '不评分' : (score.score ? score.score.toFixed(2) : 'N/A')}</td>
                    <td>${score.reason || 'N/A'}</td>
                </tr>
            `;
    });

    tableHtml += `
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        `;

    modalBody.innerHTML = tableHtml;
    modal.show();
};

// 渲染价格分析图表和表格
function renderPriceAnalysisCharts(data) {
    const priceData = data.filter(d => d.extracted_price !== null && d.extracted_price > 0);

    if (priceData.length === 0) {
        document.getElementById('priceAnalysisChart').innerHTML = '<div class="alert alert-info">没有有效的报价信息可供分析。</div>';
        return;
    }

    // 1. 渲染价格表格
    priceData.sort((a, b) => a.extracted_price - b.extracted_price);
    const tableContainer = document.getElementById('price-table-container');
    let tableHtml = `
        <table class="table table-sm table-striped table-hover">
            <thead class="table-light">
                <tr>
                    <th>排名</th>
                    <th>投标人</th>
                    <th>投标报价 (元)</th>
                </tr>
            </thead>
            <tbody>
    `;
    priceData.forEach((result, index) => {
        tableHtml += `
            <tr>
                <td><span class="badge bg-secondary">${index + 1}</span></td>
                <td>${result.bidder_name}</td>
                <td><strong>${result.extracted_price.toLocaleString('zh-CN')}</strong></td>
            </tr>
        `;
    });
    tableHtml += `
            </tbody>
        </table>
    `;
    tableContainer.innerHTML = tableHtml;

    // 2. 渲染价格图表
    const chartCanvas = document.getElementById('priceChartCanvas').getContext('2d');
    const labels = priceData.map(d => d.bidder_name);
    const prices = priceData.map(d => d.extracted_price);

    if (window.priceChart instanceof Chart) {
        window.priceChart.destroy();
    }
    window.priceChart = new Chart(chartCanvas, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: '投标报价 (元)',
                data: prices,
                backgroundColor: 'rgba(255, 159, 64, 0.6)',
                borderColor: 'rgba(255, 159, 64, 1)',
                borderWidth: 1
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return value.toLocaleString('zh-CN') + ' 元';
                        }
                    }
                }
            },
            plugins: {
                legend: { display: false },
                title: { display: true, text: '各投标人报价对比' },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return '报价: ' + context.parsed.x.toLocaleString('zh-CN') + ' 元';
                        }
                    }
                }
            }
        }
    });
}

// 渲染总分图表
function renderTotalScoreCharts(data) {
    // 总分对比图
    const scoreCtx = document.getElementById('scoreChart').getContext('2d');
    if (window.scoreChart) {
        window.scoreChart.destroy();
    }

    // 准备数据
    const bidderNames = data.map(result => result.bidder_name);
    const totalScores = data.map(result =>
        result.total_score === '废标' ? 0 : (result.total_score || 0)
    );

    window.scoreChart = new Chart(scoreCtx, {
        type: 'bar',
        data: {
            labels: bidderNames,
            datasets: [{
                label: '总分',
                data: totalScores,
                backgroundColor: [
                    'rgba(255, 99, 132, 0.7)',
                    'rgba(54, 162, 235, 0.7)',
                    'rgba(255, 206, 86, 0.7)',
                    'rgba(75, 192, 192, 0.7)',
                    'rgba(153, 102, 255, 0.7)',
                    'rgba(255, 159, 64, 0.7)'
                ],
                borderColor: [
                    'rgba(255, 99, 132, 1)',
                    'rgba(54, 162, 235, 1)',
                    'rgba(255, 206, 86, 1)',
                    'rgba(75, 192, 192, 1)',
                    'rgba(153, 102, 255, 1)',
                    'rgba(255, 159, 64, 1)'
                ],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: '各投标人总分对比'
                },
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100
                }
            }
        }
    });

    // 分数分布图
    const distributionCtx = document.getElementById('scoreDistributionChart').getContext('2d');
    if (window.distributionChart) {
        window.distributionChart.destroy();
    }

    // 计算分数分布
    const validScores = totalScores.filter(score => score > 0);
    const invalidCount = data.length - validScores.length;

    window.distributionChart = new Chart(distributionCtx, {
        type: 'doughnut',
        data: {
            labels: ['有效投标人', '废标投标人'],
            datasets: [{
                data: [validScores.length, invalidCount],
                backgroundColor: [
                    'rgba(75, 192, 192, 0.7)',
                    'rgba(255, 99, 132, 0.7)'
                ],
                borderColor: [
                    'rgba(75, 192, 192, 1)',
                    'rgba(255, 99, 132, 1)'
                ],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: '投标人状态分布'
                }
            }
        }
    });
}

// 渲染详细得分图表
function renderDetailedScoreChart(data) {
    if (!window.scoringRules || window.scoringRules.length === 0) {
        document.getElementById('detailedScoreChart').innerHTML = '<div class="alert alert-info">没有评分规则，无法生成详细评分图表。</div>';
        return;
    }

    const detailedCtx = document.getElementById('detailedScoreChartCanvas').getContext('2d');
    if (window.detailedScoreChart) {
        window.detailedScoreChart.destroy();
    }

    // 准备详细评分数据
    const topBidders = data.slice(0, 5); // 只显示前5名
    const bidderLabels = topBidders.map(result => result.bidder_name);

    // 为每个评分项创建数据集
    const datasets = [];
    const topLevelRules = window.scoringRules.filter(rule => !rule.is_veto);

    topLevelRules.forEach((rule, index) => {
        const scores = [];
        topBidders.forEach(result => {
            let categoryScore = 0;
            if (result.detailed_scores) {
                const scoreMap = {};
                function buildScoreMap(scores) {
                    if (Array.isArray(scores)) {
                        scores.forEach(score => {
                            if (score.criteria_name) scoreMap[score.criteria_name] = score;
                            if (score.children) buildScoreMap(score.children);
                        });
                    }
                }
                buildScoreMap(result.detailed_scores);
                
                const foundRule = scoreMap[rule.criteria_name];
                if(foundRule) categoryScore = foundRule.score || 0;
            }
            scores.push(categoryScore);
        });

        const color = `hsl(${index * 60 % 360}, 70%, 60%)`;
        datasets.push({
            label: rule.criteria_name,
            data: scores,
            backgroundColor: color.replace('hsl', 'hsla').replace(')', ', 0.7)'),
            borderColor: color,
            borderWidth: 1
        });
    });

    window.detailedScoreChart = new Chart(detailedCtx, {
        type: 'bar',
        data: {
            labels: bidderLabels,
            datasets: datasets
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: '前5名投标人各评分项对比'
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                x: {
                    stacked: true,
                },
                y: {
                    stacked: true,
                    beginAtZero: true
                }
            }
        }
    });
}

// 渲染分布图表
function renderDistributionCharts(data) {
    // 分数区间分布图
    const scoreRangeCtx = document.getElementById('scoreRangeChart').getContext('2d');
    if (window.scoreRangeChart) {
        window.scoreRangeChart.destroy();
    }

    const totalScores = data.map(result =>
        result.total_score === '废标' ? 0 : (result.total_score || 0)
    ).filter(score => score > 0);

    // 计算分数区间分布
    const ranges = [
        { label: '90-100分', min: 90, max: 100, count: 0 },
        { label: '80-89分', min: 80, max: 89, count: 0 },
        { label: '70-79分', min: 70, max: 79, count: 0 },
        { label: '60-69分', min: 60, max: 69, count: 0 },
        { label: '60分以下', min: 0, max: 59, count: 0 }
    ];

    totalScores.forEach(score => {
        for(const range of ranges){
            if (score >= range.min && score <= range.max) {
                range.count++;
                break;
            }
        }
    });

    window.scoreRangeChart = new Chart(scoreRangeCtx, {
        type: 'pie',
        data: {
            labels: ranges.map(r => r.label),
            datasets: [{
                data: ranges.map(r => r.count),
                backgroundColor: [
                    'rgba(75, 192, 192, 0.7)',
                    'rgba(54, 162, 235, 0.7)',
                    'rgba(255, 206, 86, 0.7)',
                    'rgba(255, 99, 132, 0.7)',
                    'rgba(153, 102, 255, 0.7)'
                ],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: '分数区间分布'
                }
            }
        }
    });

    // 分类评分对比图
    const categoryScoreCtx = document.getElementById('categoryScoreChart').getContext('2d');
    if (window.categoryScoreChart) {
        window.categoryScoreChart.destroy();
    }

    if (window.scoringRules && window.scoringRules.length > 0) {
        const categories = {};
        window.scoringRules.forEach(rule => {
            if (!rule.is_veto) {
                const category = rule.category || '其他';
                if (!categories[category]) {
                    categories[category] = 0;
                }
                categories[category] += rule.max_score || 0;
            }
        });

        const categoryLabels = Object.keys(categories);
        const categoryData = Object.values(categories);

        window.categoryScoreChart = new Chart(categoryScoreCtx, {
            type: 'doughnut',
            data: {
                labels: categoryLabels,
                datasets: [{
                    data: categoryData,
                    backgroundColor: [
                        'rgba(255, 99, 132, 0.7)',
                        'rgba(54, 162, 235, 0.7)',
                        'rgba(255, 206, 86, 0.7)',
                        'rgba(75, 192, 192, 0.7)',
                        'rgba(153, 102, 255, 0.7)'
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: '评分分类权重分布'
                    }
                }
            }
        });
    }
}

// 重新计算价格分
window.recalculatePriceScores = async function () {
    if (!window.currentProjectId) {
        alert('项目ID未找到');
        return;
    }


    // 确认对话框
    if (!confirm('确定要重新计算价格分吗？这将根据评标规则重新计算所有投标方的价格分，并更新总分和排名。')) {
        return;
    }

    try {
        // 显示加载状态
        const button = event.target;
        const originalText = button.innerHTML;
        button.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>计算中...';
        button.disabled = true;

        const response = await fetch(`/api/projects/${window.currentProjectId}/recalculate-price-scores`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || '重新计算价格分失败');
        }

        // 显示成功消息
        alert(`价格分重新计算完成！\n更新了 ${result.updated_count} 个投标方的价格分。\n\n价格分详情：\n${Object.entries(result.price_scores).map(([bidder, score]) => `${bidder}: ${score}分`).join('\n')}`);

        // 重新获取并显示结果
        const resultsResponse = await fetch(`/api/projects/${window.currentProjectId}/results`);
        if (resultsResponse.ok) {
            const results = await resultsResponse.json();
            displayResults(results);
        }

    } catch (error) {
        console.error('重新计算价格分时出错:', error);
        alert('重新计算价格分失败: ' + error.message);
    } finally {
        // 恢复按钮状态
        const button = event.target;
        button.innerHTML = '<i class="fas fa-calculator me-2"></i>重新计算价格分';
        button.disabled = false;
    }
};

// 获取价格分的辅助函数
function getPriceScore (detailedScores) {
    if (!detailedScores) return 0;

    // 创建一个映射以便快速查找评分
    const scoreMap = {};
    function buildScoreMap (scores) {
        if (Array.isArray(scores)) {
            scores.forEach(score => {
                if (score.criteria_name) {
                    scoreMap[score.criteria_name] = score;
                }
                if (score.children && score.children.length > 0) {
                    buildScoreMap(score.children);
                }
            });
        }
    }
    buildScoreMap(detailedScores);

    // 查找价格相关的评分项
    for (const [criteriaName, score] of Object.entries(scoreMap)) {
        if ((criteriaName.includes('价格') || criteriaName.includes('报价')) &&
            score.score !== undefined && score.score !== null) {
            return score.score;
        }
    }
    
    return 0;
}
});
