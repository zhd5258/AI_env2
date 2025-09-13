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
                    </div>
                </div>
            </div>
        `;

        // 统计信息将通过JavaScript动态填充
        resultArea.innerHTML = html;

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
        if (typeof buildAndInsertHeaders === 'function') {
            buildAndInsertHeaders(scoringRules);
        }

        // 绑定排序事件处理程序
        if (typeof bindSortEvents === 'function') {
            bindSortEvents();
        }

        // 绑定搜索和过滤事件
        if (typeof bindSearchAndFilterEvents === 'function') {
            bindSearchAndFilterEvents();
        }

        // 默认显示汇总表（评标办法表格）
        showSummaryTable();

        // 初始化图表（但不显示）
        if (typeof renderAllCharts === 'function') {
            renderAllCharts(resultsArray);
        }
    }

    // 递归渲染评分树
    function renderScoresTree(scores, parentId, level = 0) {
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
        if (typeof switchChartType === 'function') {
            switchChartType('total');
        }
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

    // 显示汇总表
    window.showSummaryTable = function () {
        const summaryTable = document.getElementById('summaryTable');
        const detailedView = document.getElementById('detailedView');
        const chartView = document.getElementById('chartView');
        
        if (summaryTable) summaryTable.style.display = 'block';
        if (detailedView) detailedView.style.display = 'none';
        if (chartView) chartView.style.display = 'none';

        // 更新按钮状态
        const buttons = document.querySelectorAll('#resultArea .btn-group .btn');
        if (buttons.length >= 3) {
            buttons[0].className = 'btn btn-primary';  // 汇总表按钮设为激活状态
            buttons[1].className = 'btn btn-outline-secondary';  // 详细视图按钮设为非激活状态
            buttons[2].className = 'btn btn-outline-success';   // 图表视图按钮设为非激活状态
        }
    };

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
                if (typeof renderResultsTable === 'function') {
                    renderResultsTable();
                }

                // 更新表头
                if (typeof buildAndInsertHeaders === 'function') {
                    buildAndInsertHeaders(scoringRules);
                }
            }
        } catch (error) {
            console.error('刷新评分规则失败:', error);
            alert('刷新评分规则失败: ' + error.message);
        }
    };
});
