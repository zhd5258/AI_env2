document.addEventListener('DOMContentLoaded', function () {
    // 获取DOM元素
    const uploadForm = document.getElementById('uploadForm');
    const fileList = document.getElementById('fileList');
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    const resultArea = document.getElementById('resultArea');
    const progressContainer = document.getElementById('progressContainer');

    // 用于存储上传的文件信息
    let uploadedFiles = {
        tender: null,
        bids: []
    };

    // 监听招标文件上传
    document.getElementById('tenderFile').addEventListener('change', function (e) {
        const file = e.target.files[0];
        if (file) {
            uploadedFiles.tender = file;
            updateFileList();
        }
    });

    // 监听投标文件上传
    document.getElementById('bidFiles').addEventListener('change', function (e) {
        const files = Array.from(e.target.files);
        uploadedFiles.bids = files;
        updateFileList();
    });

    // 更新文件列表显示
    function updateFileList () {
        if (!uploadedFiles.tender && uploadedFiles.bids.length === 0) {
            fileList.innerHTML = '<div class="text-muted"><i class="fas fa-info-circle me-2"></i>尚未选择任何文件</div>';
            return;
        }

        let html = '<h5 class="mb-3"><i class="fas fa-file-alt me-2"></i>已选择的文件：</h5><div class="row">';
        if (uploadedFiles.tender) {
            html += `
                <div class="col-md-6 mb-2">
                    <div class="card border-start border-4 border-primary h-100">
                        <div class="card-body">
                            <h6 class="card-title text-primary">
                                <i class="fas fa-file-pdf me-2"></i>招标文件
                            </h6>
                            <p class="card-text mb-1">${uploadedFiles.tender.name}</p>
                            <small class="text-muted">${(uploadedFiles.tender.size / 1024 / 1024).toFixed(2)} MB</small>
                        </div>
                    </div>
                </div>
            `;
        }
        if (uploadedFiles.bids.length > 0) {
            uploadedFiles.bids.forEach((file, index) => {
                html += `
                    <div class="col-md-6 mb-2">
                        <div class="card border-start border-4 border-info h-100">
                            <div class="card-body">
                                <h6 class="card-title text-info">
                                    <i class="fas fa-file-invoice me-2"></i>投标文件 #${index + 1}
                                </h6>
                                <p class="card-text mb-1">${file.name}</p>
                                <small class="text-muted">${(file.size / 1024 / 1024).toFixed(2)} MB</small>
                            </div>
                        </div>
                    </div>
                `;
            });
        }
        html += '</div>';
        fileList.innerHTML = html;
    }

    // 处理表单提交
    uploadForm.addEventListener('submit', async function (e) {
        e.preventDefault();

        if (!uploadedFiles.tender || uploadedFiles.bids.length === 0) {
            alert('请选择招标文件和至少一个投标文件');
            return;
        }

        try {
            // 显示进度容器
            progressContainer.style.display = 'block';
            progressBar.style.width = '0%';
            progressText.innerHTML = '<i class="fas fa-upload me-2"></i>正在上传文件...';
            // 清空详细进度区域
            document.getElementById('detailedProgress').innerHTML = '';

            // 创建表单数据
            const formData = new FormData();
            formData.append('tender_file', uploadedFiles.tender);
            uploadedFiles.bids.forEach((file, index) => {
                formData.append('bid_files', file);
            });

            // 上传文件
            const response = await fetch('/api/analyze-immediately', {
                method: 'POST',
                body: formData
            });

            // 检查响应状态
            if (!response.ok) {
                const errorText = await response.text();
                console.error('Server error response:', errorText);
                throw new Error(`服务器错误: ${response.status} ${response.statusText}\n${errorText}`);
            }

            const result = await response.json();

            if (result.error) {
                throw new Error(result.error);
            }

            // 保存项目ID以便后续使用
            window.currentProjectId = result.project_id;

            // 开始轮询获取进度
            startPolling(result.project_id);

        } catch (error) {
            console.error('Error:', error);
            alert('上传失败: ' + error.message);
            progressContainer.style.display = 'none';
            progressText.textContent = '';
        }
    });

    // 开始轮询获取进度
    function startPolling (projectId) {
        console.log("开始轮询项目进度，项目ID:", projectId);

        // 立即显示进度容器
        progressContainer.style.display = 'block';

        // 初始化进度显示
        progressText.innerHTML = '<i class="fas fa-sync-alt fa-spin me-2"></i>正在初始化分析...';
        progressBar.style.width = '0%';
        progressBar.setAttribute('aria-valuenow', 0);

        // 清空详细进度区域
        if (document.getElementById('detailedProgress')) {
            document.getElementById('detailedProgress').innerHTML = '<div class="text-center"><i class="fas fa-spinner fa-spin me-2"></i>正在加载详细进度...</div>';
        }

        // 立即执行一次轮询
        pollProgress(projectId);

        // 设置定时器，每1.5秒轮询一次（比原来更频繁）
        const pollInterval = setInterval(() => {
            pollProgress(projectId);
        }, 1500);

        // 保存定时器ID，以便在分析完成时清除
        window.pollInterval = pollInterval;
    }

    // 轮询进度函数
    async function pollProgress (projectId) {
        try {
            const response = await fetch(`/api/projects/${projectId}/analysis-status`);
            if (!response.ok) {
                throw new Error(`获取进度失败: ${response.statusText}`);
            }

            const data = await response.json();
            console.log("轮询获取到进度数据:", data);

            // 更新进度显示
            updateProgressFromStatus(data);

            // 检查是否完成
            if (data.project_status === 'completed' || data.project_status === 'completed_with_errors') {
                console.log("分析完成，停止轮询");
                clearInterval(window.pollInterval);

                // 延迟1秒后显示结果，确保最后一次进度更新完成
                setTimeout(() => {
                    fetchAndDisplayResults(projectId);
                }, 1000);
            }

        } catch (error) {
            console.error("轮询进度时出错:", error);
            progressText.innerHTML = `<div class="alert alert-danger mb-0"><i class="fas fa-exclamation-circle me-2"></i>获取进度失败: ${error.message}</div>`;

            // 出错时停止轮询
            if (window.pollInterval) {
                clearInterval(window.pollInterval);
            }
        }
    }

    // 根据状态API的数据更新进度
    function updateProgressFromStatus (data) {
        console.log("Update progress from status called with data:", data);

        // 检查数据有效性
        if (!data || !data.bids) {
            console.warn("Invalid progress data received:", data);
            return;
        }

        let totalCompleted = 0;
        let totalRules = 0;
        let currentRule = '正在处理...';
        let processingCount = 0;
        let completedCount = 0;
        let errorCount = 0;

        // 计算总体进度和状态
        data.bids.forEach(bid => {
            totalCompleted += bid.progress_completed || 0;
            totalRules += bid.progress_total || 0;

            // 更新当前正在进行的规则
            if (bid.status === 'processing' && bid.current_rule) {
                currentRule = bid.current_rule;
                processingCount++;
            } else if (bid.status === 'completed') {
                completedCount++;
            } else if (bid.status === 'error') {
                errorCount++;
            }
        });

        // 计算总体进度百分比
        let overallProgress = totalRules > 0 ? (totalCompleted / totalRules) * 100 : 0;

        // 根据项目状态更新进度信息
        if (data.project_status === 'completed' || data.project_status === 'completed_with_errors') {
            overallProgress = 100;
            currentRule = data.project_status === 'completed' ? "分析完成" : "分析完成（存在错误）";
        } else if (processingCount === 0 && completedCount === 0 && errorCount === 0) {
            currentRule = "准备中...";
        }

        // 更新总体进度条
        progressBar.style.width = `${overallProgress}%`;
        progressBar.setAttribute('aria-valuenow', overallProgress);

        // 更新进度文本，增加更多状态信息
        let statusInfo = '';
        if (data.project_status === 'completed') {
            statusInfo = '<span class="text-success"><i class="fas fa-check-circle me-2"></i>分析已完成</span>';
        } else if (data.project_status === 'completed_with_errors') {
            statusInfo = '<span class="text-warning"><i class="fas fa-exclamation-triangle me-2"></i>分析完成（存在错误）</span>';
        } else if (errorCount > 0) {
            statusInfo = `<span class="text-danger"><i class="fas fa-exclamation-circle me-2"></i>出现错误 (${errorCount})</span>`;
        } else if (processingCount > 0) {
            statusInfo = `<span class="text-primary"><i class="fas fa-cog fa-spin me-2"></i>正在分析 (${processingCount})</span>`;
        } else {
            statusInfo = '<span class="text-info"><i class="fas fa-clock me-2"></i>等待处理</span>';
        }

        progressText.innerHTML = `
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <strong>分析进度:</strong> ${currentRule}
                </div>
                <div>
                    ${statusInfo}
                </div>
            </div>
            <div class="mt-2">
                <strong>总体进度:</strong> ${overallProgress.toFixed(1)}% (${totalCompleted}/${totalRules})
            </div>
        `;

        // 显示详细进度信息
        displayDetailedProgress(data);
    }

    // 显示每个投标文件的详细进度
    function displayDetailedProgress (data) {
        console.log("Displaying detailed progress with data:", data);

        // 检查数据有效性
        if (!data.bids || data.bids.length === 0) {
            document.getElementById('detailedProgress').innerHTML = '<div class="alert alert-info">暂无投标文件信息</div>';
            return;
        }

        let html = `
            <div class="card mt-4">
                <div class="card-header">
                    <h5 class="mb-0"><i class="fas fa-tasks me-2"></i>详细进度</h5>
                </div>
                <div class="card-body">
                    <div class="row">
        `;

        // 按状态排序：处理中 > 错误 > 已完成 > 其他
        const sortedBids = [...data.bids].sort((a, b) => {
            const statusOrder = {
                'processing': 1,
                'error': 2,
                'completed': 3
            };

            const orderA = statusOrder[a.status] || 4;
            const orderB = statusOrder[b.status] || 4;

            if (orderA !== orderB) {
                return orderA - orderB;
            }

            // 如果状态相同，按名称排序
            return a.bidder_name.localeCompare(b.bidder_name);
        });

        sortedBids.forEach(bid => {
            let progress = 0;
            if (bid.progress_total && bid.progress_total > 0) {
                progress = (bid.progress_completed / bid.progress_total) * 100;
            }

            // 确定状态样式
            let statusClass = '';
            let statusIcon = '';
            let statusText = '';
            let progressClass = '';

            switch (bid.status) {
                case 'completed':
                    statusClass = 'status-completed';
                    statusIcon = '<i class="fas fa-check-circle me-2"></i>';
                    statusText = '已完成';
                    progressClass = 'bg-success';
                    break;
                case 'error':
                    statusClass = 'status-error';
                    statusIcon = '<i class="fas fa-exclamation-circle me-2"></i>';
                    statusText = '错误';
                    progressClass = 'bg-danger';
                    break;
                case 'processing':
                    statusClass = 'status-processing';
                    statusIcon = '<i class="fas fa-cog fa-spin me-2"></i>';
                    statusText = '处理中';
                    progressClass = 'progress-bar-striped progress-bar-animated bg-primary';
                    break;
                default:
                    statusClass = 'bg-secondary';
                    statusIcon = '<i class="fas fa-question-circle me-2"></i>';
                    statusText = bid.status || '未知';
                    progressClass = 'bg-secondary';
            }

            // 处理部分分析结果
            let partialResultsHtml = '';
            if (bid.partial_analysis_results) {
                try {
                    // 确保partial_analysis_results是有效的JSON字符串
                    let partialResults = [];
                    if (typeof bid.partial_analysis_results === 'string' && bid.partial_analysis_results.trim() !== '') {
                        partialResults = JSON.parse(bid.partial_analysis_results);
                    } else if (Array.isArray(bid.partial_analysis_results)) {
                        partialResults = bid.partial_analysis_results;
                    }

                    if (Array.isArray(partialResults) && partialResults.length > 0) {
                        partialResultsHtml = `
                            <div class="mt-3">
                                <h6 class="mb-2"><i class="fas fa-list me-2"></i>已分析项 (${bid.progress_completed}/${bid.progress_total}):</h6>
                                <div class="table-responsive">
                                    <table class="table table-sm table-striped">
                                        <thead>
                                            <tr>
                                                <th>评分项</th>
                                                <th>得分</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            ${partialResults.map(score =>
                            `<tr>
                                                    <td>${score.criteria_name}</td>
                                                    <td>${score.score}/${score.max_score}</td>
                                                </tr>`
                        ).join('')}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        `;
                    }
                } catch (e) {
                    console.error('解析部分分析结果时出错:', e);
                    console.error('部分分析结果内容:', bid.partial_analysis_results);
                    partialResultsHtml = `<div class="alert alert-warning mt-2">部分分析结果解析失败</div>`;
                }
            }

            html += `
                <div class="col-lg-6 mb-4">
                    <div class="card detail-progress-card h-100">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h5 class="card-title mb-0">
                                    <i class="fas fa-file-contract me-2"></i>${bid.bidder_name}
                                </h5>
                                <span class="status-badge ${statusClass}">${statusIcon}${statusText}</span>
                            </div>
                            
                            <div class="mb-2">
                                <div class="d-flex justify-content-between">
                                    <small class="text-muted">进度</small>
                                    <small class="text-muted">${progress.toFixed(1)}% (${bid.progress_completed}/${bid.progress_total})</small>
                                </div>
                                <div class="progress" style="height: 15px;">
                                    <div class="progress-bar ${progressClass}" 
                                         role="progressbar" 
                                         style="width: ${progress}%"
                                         aria-valuenow="${progress}" 
                                         aria-valuemin="0" 
                                         aria-valuemax="100">
                                    </div>
                                </div>
                            </div>
                            
                            <div class="mt-2 mb-1">
                                <small class="text-muted"><i class="fas fa-tasks me-2"></i>当前任务:</small>
                                <div class="fw-bold">${bid.detailed_progress_info || bid.current_rule || '准备中...'}</div>
                            </div>
                            
                            ${bid.error_message ? `
                                <div class="alert alert-danger mb-2 py-2">
                                    <i class="fas fa-exclamation-triangle me-2"></i>
                                    <strong>错误:</strong> ${bid.error_message}
                                    ${bid.error_message.includes('处理失败') ?
                        `<button class="btn btn-sm btn-outline-light ms-2" onclick="showFailedPages('${bid.bidder_name}', ${bid.id})">
                                            <i class="fas fa-info-circle me-1"></i>查看详情
                                        </button>` : ''}
                                </div>
                            ` : ''}
                            
                            <!-- 显示部分分析结果 -->
// 简化版的main.js，用于保持向后兼容性
document.addEventListener('DOMContentLoaded', function () {
    // 监听分析完成事件
    window.addEventListener('analysisCompleted', function (event) {
        const projectId = event.detail.projectId;
        fetchAndDisplayResults(projectId);
    });

    // 监听结果准备就绪事件
    window.addEventListener('resultsReady', function (event) {
        const results = event.detail.results;
        if (typeof displayResults !== 'undefined') {
            displayResults(results);
        }
    });

    // 获取并显示最终结果
    async function fetchAndDisplayResults(projectId) {
        try {
            const response = await fetch(`/api/projects/${projectId}/results`);
            if (!response.ok) {
                if (response.status === 404) {
                    // 分析可能失败或没有生成结果
                    const resultArea = document.getElementById('resultArea');
                    resultArea.innerHTML = `
                        <div class="alert alert-warning">
                            <h4><i class="fas fa-exclamation-triangle me-2"></i>分析完成但未生成结果</h4>
                            <p>分析过程已完成，但可能由于某些错误未能生成最终结果。</p>
                            <p>请检查分析日志或重新尝试分析。</p>
                        </div>
                    `;
                    return;
                }
                throw new Error(`获取结果失败: ${response.statusText}`);
            }
            const results = await response.json();
            if (typeof displayResults !== 'undefined') {
                displayResults(results);
            }
        } catch (error) {
            console.error("获取结果时出错:", error);
            const resultArea = document.getElementById('resultArea');
            resultArea.innerHTML = `<div class="alert alert-danger"><i class="fas fa-exclamation-circle me-2"></i>获取结果时出错: ${error.message}</div>`;
        }
    }

    // 确保全局函数可用
    window.fetchAndDisplayResults = fetchAndDisplayResults;
});
                        
<div>
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
                                        <button class="btn btn-outline-warning" onclick="recalculatePriceScores()">
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
                                            <i class="fas fa-medal me-2"></i>排名
                                        </th>
                                        <th rowspan="2" style="vertical-align: middle; text-align: center;">
                                            <i class="fas fa-user me-2"></i>投标人
                                        </th>
                                        <th colspan="3" style="text-align: center; background-color: #e3f2fd;">商务部分（总分18分）</th>
                                        <th colspan="3" style="text-align: center; background-color: #f3e5f5;">服务部分（总分10分）</th>
                                        <th colspan="6" style="text-align: center; background-color: #e8f5e8;">技术部分（总分32分）</th>
                                        <th rowspan="2" style="vertical-align: middle; text-align: center; background-color: #fff3e0;">
                                            <i class="fas fa-dollar-sign me-2"></i>价格分（40分）
                                        </th>
                                        <th rowspan="2" style="vertical-align: middle; text-align: center;">
                                            <i class="fas fa-star me-2"></i>总分
                                        </th>
                                    </tr>
                                    <tr>
                                        <!-- 商务部分 -->
                                        <th style="text-align: center; background-color: #e3f2fd;">标书的完整性<br /><small>(5分)</small></th>
                                        <th style="text-align: center; background-color: #e3f2fd;">业绩<br /><small>(5分)</small></th>
                                        <th style="text-align: center; background-color: #e3f2fd;">供货能力<br /><small>(3分)</small></th>
                                        <!-- 服务部分 -->
                                        <th style="text-align: center; background-color: #f3e5f5;">售后服务方案等服务内容<br /><small>(5分)</small></th>
                                        <th style="text-align: center; background-color: #f3e5f5;">高于投标文件要求的服务<br /><small>(2分)</small></th>
                                        <th style="text-align: center; background-color: #f3e5f5;">服务保障体系<br /><small>(3分)</small></th>
                                        <!-- 技术部分 -->
                                        <th style="text-align: center; background-color: #e8f5e8;">品牌形象<br /><small>(2分)</small></th>
                                        <th style="text-align: center; background-color: #e8f5e8;">技术先进，成熟、合理<br /><small>(3分)</small></th>
                                        <th style="text-align: center; background-color: #e8f5e8;">设备稳定性强<br /><small>(2分)</small></th>
                                        <th style="text-align: center; background-color: #e8f5e8;">节能环保方案<br /><small>(5分)</small></th>
                                        <th style="text-align: center; background-color: #e8f5e8;">主要部件采用推荐品牌<br /><small>(5分)</small></th>
                                        <th style="text-align: center; background-color: #e8f5e8;">投标产品技术性能指标<br /><small>(15分)</small></th>
                                    </tr>
                                </thead>
                                <tbody id="resultsTableBody">
                        </tbody>
                    </table>
                </div>
            </div>
        `;

        // 保存结果数据到全局变量，以便排序时使用
        window.resultsData = [...resultsArray];
        window.filteredResultsData = [...resultsArray]; // 用于过滤的数据

        // 获取评分规则并构建表格列
        try {
            const scoringRulesResponse = await fetch(`/api/projects/${window.currentProjectId}/scoring-rules`);
            if (scoringRulesResponse.ok) {
                const scoringRules = await scoringRulesResponse.json();
                window.scoringRules = scoringRules;

                // 构建评分项列头（严格按照评标办法表格结构）
                let columnHeaders = '';
                let columnIndex = 3; // 从第3列开始（排名、投标人、总分之后）

                // 递归处理评分规则，包括父项和子项
                function buildColumnHeaders (rules, parentIndex = 0) {
                    rules.forEach((rule, index) => {
                        // 检查是否为否决项规则
                        const isVeto = rule.is_veto || false;
                        if (!isVeto) {  // 只显示非否决项的评分项
                            if (rule.children && rule.children.length > 0) {
                                // 父项：显示简化的父项名称，保留分数
                                const simplifiedName = rule.criteria_name.replace(/（.*?）/g, '').replace(/\(.*?\)/g, '');
                                columnHeaders += `
                                    <th style="cursor: pointer;" onclick="sortTable(${columnIndex})" class="table-warning">
                                        ${simplifiedName} <span id="sortIcon${columnIndex}"></span>
                                        <div class="small text-white">${rule.max_score}分</div>
                                    </th>
                                `;
                                columnIndex++;

                                // 子项：递归处理子项
                                buildColumnHeaders(rule.children, columnIndex);
                            } else {
                                // 叶子节点：显示简化的评分项名称，保留分数
                                const simplifiedName = rule.criteria_name.replace(/（.*?）/g, '').replace(/\(.*?\)/g, '');
                                columnHeaders += `
                                    <th style="cursor: pointer;" onclick="sortTable(${columnIndex})">
                                        ${simplifiedName} <span id="sortIcon${columnIndex}"></span>
                                        <div class="small text-white">${rule.max_score}分</div>
                                    </th>
                                `;
                                columnIndex++;
                            }
                        }
                    });
                }

                buildColumnHeaders(scoringRules);

                // 插入评分项列头到表格
                const headerRow = document.querySelector('#resultsTable thead tr');
                if (headerRow) {
                    // 在总分列前插入评分项列
                    const totalScoreHeader = headerRow.querySelector('th:last-child');
                    totalScoreHeader.insertAdjacentHTML('beforebegin', columnHeaders);
                }
            }
        } catch (error) {
            console.error('获取评分规则失败:', error);
        }

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

            // 构建评分项单元格（严格按照评标办法表格结构）
            let scoreCells = '';
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
                function buildScoreCells (rules) {
                    rules.forEach(rule => {
                        // 检查是否为否决项规则
                        const isVeto = rule.is_veto || false;
                        if (!isVeto) {  // 只显示非否决项的评分项
                            if (rule.children && rule.children.length > 0) {
                                // 父项：计算子项分数之和
                                let parentScore = 0;
                                rule.children.forEach(child => {
                                    const childScore = scoreMap[child.criteria_name];
                                    if (childScore && childScore.score) {
                                        parentScore += childScore.score;
                                    }
                                });
                                scoreCells += `<td class="table-warning"><strong>${parentScore.toFixed(2)}</strong></td>`;

                                // 子项：递归处理子项
                                buildScoreCells(rule.children);
                            } else {
                                // 叶子节点：显示具体的评分项分数
                                const score = scoreMap[rule.criteria_name];
                                let scoreValue = '0.00';
                                let cellClass = '';

                                if (score) {
                                    if (score.score !== undefined && score.score !== null) {
                                        scoreValue = score.score.toFixed(2);
                                        // 如果是价格分，特殊标记
                                        if (rule.criteria_name.includes('价格') || rule.criteria_name.includes('报价')) {
                                            cellClass = 'table-info';
                                        }
                                    }
                                }

                                scoreCells += `<td class="${cellClass}">${scoreValue}</td>`;
                            }
                        }
                    });
                }

                buildScoreCells(window.scoringRules);
            }

            // 处理总分显示
            let totalScoreDisplay = 'N/A';
            if (result.total_score === '废标') {
                totalScoreDisplay = '<span class="badge bg-danger">废标</span>';
            } else if (result.total_score !== undefined) {
                totalScoreDisplay = result.total_score.toFixed(2);
            }

            // 汇总表行（严格按照评标办法表格结构显示）
            html += `
                <tr class="align-middle" data-rank="${index + 1}" data-name="${result.bidder_name}" data-score="${result.total_score}">
                    <td><span class="score-badge ${rankBadge}">${index + 1}</span></td>
                    <td><strong>${result.bidder_name}</strong></td>
                    ${scoreCells}
                    <td><span class="score-badge ${rankBadge}">${totalScoreDisplay}</span></td>
                </tr>
            `;
        });

        html += `
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
        `;

        // 详细视图容器（包含原来的详细评分信息）
        html += `
            <div id="detailedView" style="display: none;">
                <div class="card">
                    <div class="card-body">
                        <h4 class="mb-4"><i class="fas fa-list me-2"></i>详细评分视图</h4>
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
                        <h4 class="mb-4"><i class="fas fa-chart-line me-2"></i>评分图表分析</h4>
                        
                        <!-- 图表控制区域 -->
                        <div class="row mb-4">
                            <div class="col-md-6">
                                <div class="btn-group" role="group">
                                    <button class="btn btn-outline-primary active" onclick="switchChartType('total')">
                                        <i class="fas fa-chart-bar me-2"></i>总分对比
                                    </button>
                                    <button class="btn btn-outline-primary" onclick="switchChartType('detailed')">
                                        <i class="fas fa-chart-line me-2"></i>详细评分
                                    </button>
                                    <button class="btn btn-outline-primary" onclick="switchChartType('distribution')">
                                        <i class="fas fa-chart-pie me-2"></i>分布分析
                                    </button>
                                </div>
                            </div>
                            <div class="col-md-6 text-end">
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

        // 绑定排序事件处理程序
        bindSortEvents();

        // 绑定搜索和过滤事件
        bindSearchAndFilterEvents();

        // 默认显示汇总表（评标办法表格）
        showSummaryTable();

        // 初始化排序状态
        window.currentSort = { column: 2, direction: 'desc' }; // 默认按总分降序排序
        updateSortIcons();
    }

    // 显示汇总表
    window.showSummaryTable = function () {
        // 隐藏其他视图
        document.getElementById('detailedView').style.display = 'none';
        document.getElementById('chartView').style.display = 'none';

        // 显示汇总表
        const summaryTable = document.getElementById('summaryTable');
        if (summaryTable) {
            summaryTable.style.display = 'block';
        }

        // 更新按钮状态
        const buttons = document.querySelectorAll('.btn-group .btn');
        buttons[0].classList.remove('btn-outline-primary');
        buttons[0].classList.add('btn-primary');
        buttons[1].classList.remove('btn-secondary');
        buttons[1].classList.add('btn-outline-secondary');
        buttons[2].classList.remove('btn-success');
        buttons[2].classList.add('btn-outline-success');

        // 重新渲染表格数据
        renderResultsTable();
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

    // 显示图表视图
    window.showChartView = function () {
        document.getElementById('summaryTable').style.display = 'none';
        document.getElementById('detailedView').style.display = 'none';
        document.getElementById('chartView').style.display = 'block';

        // 更新按钮状态
        const buttons = document.querySelectorAll('.btn-group .btn');
        buttons[0].classList.remove('btn-primary');
        buttons[0].classList.add('btn-outline-primary');
        buttons[1].classList.remove('btn-secondary');
        buttons[1].classList.add('btn-outline-secondary');
        buttons[2].classList.remove('btn-outline-success');
        buttons[2].classList.add('btn-success');

        // 渲染图表
        renderCharts();
    };

    // 渲染图表
    function renderCharts () {
        // 确保有数据
        if (!window.resultsData || window.resultsData.length === 0) {
            return;
        }

        // 渲染总分对比图
        renderTotalScoreChart();

        // 渲染统计信息
        renderStatisticsInfo();
    }

    // 渲染总分对比图
    function renderTotalScoreChart () {
        // 总分对比图
        const scoreCtx = document.getElementById('scoreChart').getContext('2d');
        if (window.scoreChart) {
            window.scoreChart.destroy();
        }

        // 准备数据
        const bidderNames = window.resultsData.map(result => result.bidder_name);
        const totalScores = window.resultsData.map(result =>
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
        const invalidCount = window.resultsData.length - validScores.length;

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

    // 渲染详细评分对比图
    function renderDetailedScoreChart () {
        if (!window.scoringRules || window.scoringRules.length === 0) {
            return;
        }

        const detailedCtx = document.getElementById('detailedScoreChartCanvas').getContext('2d');
        if (window.detailedScoreChart) {
            window.detailedScoreChart.destroy();
        }

        // 准备详细评分数据
        const topBidders = window.resultsData.slice(0, 5); // 只显示前5名
        const bidderLabels = topBidders.map(result => result.bidder_name);

        // 为每个评分项创建数据集
        const datasets = [];
        window.scoringRules.forEach((rule, index) => {
            // 检查是否为否决项规则
            const isVeto = rule.is_veto || false;
            if (!isVeto) {  // 只显示非否决项的评分项
                const scores = [];
                topBidders.forEach(result => {
                    if (result.detailed_scores) {
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

                        const score = scoreMap[rule.criteria_name];
                        scores.push(score ? (score.score || 0) : 0);
                    } else {
                        scores.push(0);
                    }
                });

                // 生成随机颜色
                const color = `hsl(${index * 60 % 360}, 70%, 60%)`;
                datasets.push({
                    label: rule.criteria_name,
                    data: scores,
                    backgroundColor: `rgba(${parseInt(color.slice(4))}, 0.7)`,
                    borderColor: color,
                    borderWidth: 1
                });
            }
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
                        text: '前5名投标人详细评分对比'
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

    // 渲染分布分析图
    function renderDistributionAnalysisChart () {
        // 分数区间分布图
        const scoreRangeCtx = document.getElementById('scoreRangeChart').getContext('2d');
        if (window.scoreRangeChart) {
            window.scoreRangeChart.destroy();
        }

        const totalScores = window.resultsData.map(result =>
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
            ranges.forEach(range => {
                if (score >= range.min && score <= range.max) {
                    range.count++;
                }
            });
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
                    borderColor: [
                        'rgba(75, 192, 192, 1)',
                        'rgba(54, 162, 235, 1)',
                        'rgba(255, 206, 86, 1)',
                        'rgba(255, 99, 132, 1)',
                        'rgba(153, 102, 255, 1)'
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
                const isVeto = rule.is_veto || false;
                if (!isVeto) {
                    const category = rule.category || '其他';
                    if (!categories[category]) {
                        categories[category] = { total: 0, count: 0 };
                    }
                    categories[category].total += rule.max_score || 0;
                    categories[category].count++;
                }
            });

            const categoryLabels = Object.keys(categories);
            const categoryData = categoryLabels.map(category => categories[category].total);

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
                        borderColor: [
                            'rgba(255, 99, 132, 1)',
                            'rgba(54, 162, 235, 1)',
                            'rgba(255, 206, 86, 1)',
                            'rgba(75, 192, 192, 1)',
                            'rgba(153, 102, 255, 1)'
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

    // 渲染统计信息
    function renderStatisticsInfo () {
        const statisticsInfo = document.getElementById('statisticsInfo');
        if (!statisticsInfo) return;

        const totalScores = window.resultsData.map(result =>
            result.total_score === '废标' ? 0 : (result.total_score || 0)
        ).filter(score => score > 0);

        const validBidders = totalScores.length;
        const invalidBidders = window.resultsData.length - validBidders;
        const averageScore = validBidders > 0 ? (totalScores.reduce((a, b) => a + b, 0) / validBidders).toFixed(2) : 0;
        const maxScore = validBidders > 0 ? Math.max(...totalScores).toFixed(2) : 0;
        const minScore = validBidders > 0 ? Math.min(...totalScores).toFixed(2) : 0;

        statisticsInfo.innerHTML = `
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h5 class="card-title text-primary">${window.resultsData.length}</h5>
                        <p class="card-text">总投标人数</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h5 class="card-title text-success">${validBidders}</h5>
                        <p class="card-text">有效投标人</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h5 class="card-title text-danger">${invalidBidders}</h5>
                        <p class="card-text">废标投标人</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h5 class="card-title text-info">${averageScore}</h5>
                        <p class="card-text">平均得分</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h5 class="card-title text-warning">${maxScore}</h5>
                        <p class="card-text">最高得分</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h5 class="card-title text-secondary">${minScore}</h5>
                        <p class="card-text">最低得分</p>
                    </div>
                </div>
            </div>
        `;
    }

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
                    valueA = a.bidder_name.toLowerCase();
                    valueB = b.bidder_name.toLowerCase();
                    break;
                case 2: // 总分
                    valueA = a.total_score === '废标' ? -1 : (a.total_score || 0);
                    valueB = b.total_score === '废标' ? -1 : (b.total_score || 0);
                    break;
                default:
                    // 评分项列 - 需要根据层级结构找到对应的规则
                    if (window.scoringRules && columnIndex >= 3) {
                        // 递归查找对应列索引的规则
                        let currentIndex = 3;
                        let targetRule = null;

                        function findRuleByIndex (rules) {
                            for (const rule of rules) {
                                const isVeto = rule.is_veto || false;
                                if (!isVeto) {
                                    if (currentIndex === columnIndex) {
                                        targetRule = rule;
                                        return true;
                                    }
                                    currentIndex++;

                                    if (rule.children && rule.children.length > 0) {
                                        if (findRuleByIndex(rule.children)) {
                                            return true;
                                        }
                                    }
                                }
                            }
                            return false;
                        }

                        if (findRuleByIndex(window.scoringRules) && targetRule) {
                            // 创建一个映射以便快速查找评分
                            const scoreMapA = {};
                            const scoreMapB = {};

                            function buildScoreMap (scores, scoreMap) {
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

                            if (targetRule.children && targetRule.children.length > 0) {
                                // 父项：计算子项分数之和
                                let scoreA = 0, scoreB = 0;
                                targetRule.children.forEach(child => {
                                    const childScoreA = scoreMapA[child.criteria_name];
                                    const childScoreB = scoreMapB[child.criteria_name];
                                    if (childScoreA && childScoreA.score) scoreA += childScoreA.score;
                                    if (childScoreB && childScoreB.score) scoreB += childScoreB.score;
                                });
                                valueA = scoreA;
                                valueB = scoreB;
                            } else {
                                // 叶子节点
                                const scoreA = scoreMapA[targetRule.criteria_name];
                                const scoreB = scoreMapB[targetRule.criteria_name];
                                valueA = scoreA ? (scoreA.score || 0) : 0;
                                valueB = scoreB ? (scoreB.score || 0) : 0;
                            }
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
    function updateSortIcons () {
        // 清除所有排序图标
        // 先清除已知的列图标
        for (let i = 0; i < 3; i++) {
            const iconElement = document.getElementById(`sortIcon${i}`);
            if (iconElement) {
                iconElement.innerHTML = '';
            }
        }

        // 清除动态生成的列图标
        if (window.scoringRules) {
            let columnIndex = 3;

            function clearColumnIcons (rules) {
                rules.forEach(rule => {
                    const isVeto = rule.is_veto || false;
                    if (!isVeto) {
                        const iconElement = document.getElementById(`sortIcon${columnIndex}`);
                        if (iconElement) {
                            iconElement.innerHTML = '';
                        }
                        columnIndex++;

                        if (rule.children && rule.children.length > 0) {
                            clearColumnIcons(rule.children);
                        }
                    }
                });
            }

            clearColumnIcons(window.scoringRules);
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

        // 移除常见的后缀和无关信息
        let simplified = bidderName
            .replace(/\(盖单位章\).*$/, '')  // 移除"(盖单位章)"及之后的内容
            .replace(/法定代表人.*$/, '')     // 移除"法定代表人"及之后的内容
            .replace(/单位负责人.*$/, '')     // 移除"单位负责人"及之后的内容
            .replace(/授权代表.*$/, '')       // 移除"授权代表"及之后的内容
            .replace(/签字.*$/, '')           // 移除"签字"及之后的内容
            .replace(/\d{4}\s*年.*$/, '')     // 移除日期及之后的内容
            .replace(/第\s*\d+\s*页.*$/, '')  // 移除页码及之后的内容
            .replace(/共\s*\d+\s*页.*$/, '')  // 移除总页数及之后的内容
            .trim();

        // 如果名称太长，截取前20个字符
        if (simplified.length > 20) {
            simplified = simplified.substring(0, 20) + '...';
        }

        return simplified;
    }

    // 重新渲染结果表格
    function renderResultsTable () {
        const tableBody = document.getElementById('resultsTableBody');
        if (!tableBody) return;

        let html = '';
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

            // 构建评分项单元格
            let scoreCells = '';
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
                function buildScoreCells (rules) {
                    rules.forEach(rule => {
                        // 检查是否为否决项规则
                        const isVeto = rule.is_veto || false;
                        if (!isVeto) {  // 只显示非否决项的评分项
                            if (rule.children && rule.children.length > 0) {
                                // 父项：计算子项分数之和
                                let parentScore = 0;
                                rule.children.forEach(child => {
                                    const childScore = scoreMap[child.criteria_name];
                                    if (childScore && childScore.score) {
                                        parentScore += childScore.score;
                                    }
                                });
                                scoreCells += `<td class="table-warning"><strong>${parentScore.toFixed(2)}</strong></td>`;

                                // 子项：递归处理子项
                                buildScoreCells(rule.children);
                            } else {
                                // 叶子节点：显示具体的评分项分数
                                const score = scoreMap[rule.criteria_name];
                                let scoreValue = '0.00';
                                let cellClass = '';

                                if (score) {
                                    if (score.score !== undefined && score.score !== null) {
                                        scoreValue = score.score.toFixed(2);
                                        // 如果是价格分，特殊标记
                                        if (rule.criteria_name.includes('价格') || rule.criteria_name.includes('报价')) {
                                            cellClass = 'table-info';
                                        }
                                    }
                                }

                                scoreCells += `<td class="${cellClass}">${scoreValue}</td>`;
                            }
                        }
                    });
                }

                buildScoreCells(window.scoringRules);
            }

            // 处理总分显示
            let totalScoreDisplay = 'N/A';
            if (result.total_score === '废标') {
                totalScoreDisplay = '<span class="badge bg-danger">废标</span>';
            } else if (result.total_score !== undefined) {
                totalScoreDisplay = result.total_score.toFixed(2);
            }

            // 简化投标方名称显示
            const simplifiedBidderName = simplifyBidderName(result.bidder_name);

            // 汇总表行（显示排名、投标人、评分项得分和总分）
            html += `
                <tr class="align-middle" data-rank="${index + 1}" data-name="${result.bidder_name}" data-score="${result.total_score}">
                    <td><span class="score-badge ${rankBadge}">${index + 1}</span></td>
                    <td><strong title="${result.bidder_name}">${simplifiedBidderName}</strong></td>
                    ${scoreCells}
                    <td><span class="score-badge ${rankBadge}">${totalScoreDisplay}</span></td>
                </tr>
            `;
        });

        tableBody.innerHTML = html;

        // 更新排序图标
        updateSortIcons();
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
                html += `<div id="${collapseId}" class="accordion-collapse collapse show" data-bs-parent="#${parentId}">`;
                html += '<div class="accordion-body">';
                // 递归调用
                html += renderScoresTree(score.children, itemId, level + 1);
                html += '</div></div>';
            } else {
                // 对于叶子节点，可以在展开的内容中显示评分理由
                html += `<div id="${collapseId}" class="accordion-collapse collapse" data-bs-parent="#${parentId}">`;
                if (isVeto) {
                    html += `<div class="accordion-body"><strong>说明:</strong> ${score.reason || '此为否决项规则，违反则否决投标'}</div>`;
                } else {
                    html += `<div class="accordion-body"><strong>评分理由:</strong> ${score.reason || '无'}</div>`;
                }
                html += '</div>';
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
                    if (!isVeto) {  // 只显示非否决项的评分项
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
                    if (!isVeto) {  // 只显示非否决项的评分项
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
                        if (!isVeto) {  // 只显示非否决项的评分项
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

            // 添加总分
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

    // 显示失败页面信息
    window.showFailedPages = async function (bidderName, bidId) {
        try {
            // 获取项目ID（从全局变量或其他方式）
            const projectId = window.currentProjectId; // 需要在开始分析时设置这个变量

            if (!projectId) {
                alert('项目ID未找到');
                return;
            }

            const response = await fetch(`/api/projects/${projectId}/bid-documents/${bidId}/failed-pages`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const failedPagesData = await response.json();

            // 创建模态框显示失败页面信息
            displayFailedPages(bidderName, failedPagesData);
        } catch (error) {
            console.error('获取失败页面信息时出错:', error);
            alert(`获取失败页面信息时出错: ${error.message}`);
        }
    }

    // 显示失败页面详情
    function displayFailedPages (bidderName, failedPagesData) {
        // 创建模态框内容
        let modalContent = `
            <div class="modal-header bg-danger text-white">
                <h5 class="modal-title"><i class="fas fa-exclamation-triangle me-2"></i>${bidderName} - PDF处理失败页面详情</h5>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
                <p>共 ${failedPagesData.length} 个页面处理失败：</p>
                <div class="table-responsive">
                    <table class="table table-striped">
                        <thead class="table-dark">
                            <tr>
                                <th>页码</th>
                                <th>失败原因</th>
                                <th>错误类型</th>
                            </tr>
                        </thead>
                        <tbody>
        `;

        failedPagesData.forEach(page => {
            modalContent += `
                <tr>
                    <td>${page.page_number}</td>
                    <td>${page.reason}</td>
                    <td>${page.error_type || page.method || '未知'}</td>
                </tr>
            `;
        });

        modalContent += `
                        </tbody>
                    </table>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
            </div>
        `;

        // 创建或更新模态框
        let modalElement = document.getElementById('failedPagesModal');
        if (!modalElement) {
            modalElement = document.createElement('div');
            modalElement.className = 'modal fade';
            modalElement.id = 'failedPagesModal';
            modalElement.tabIndex = '-1';
            modalElement.setAttribute('aria-hidden', 'true');
            document.body.appendChild(modalElement);
        }

        modalElement.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    ${modalContent}
                </div>
            </div>
        `;

        // 显示模态框
        const modal = new bootstrap.Modal(modalElement);
        modal.show();
    }


    // 切换图表类型
    window.switchChartType = function (type) {
        // 隐藏所有图表容器
        document.getElementById('totalScoreChart').style.display = 'none';
        document.getElementById('detailedScoreChart').style.display = 'none';
        document.getElementById('distributionAnalysisChart').style.display = 'none';

        // 更新按钮状态
        const buttons = document.querySelectorAll('#chartView .btn-group .btn');
        buttons.forEach(btn => {
            btn.classList.remove('active');
            btn.classList.add('btn-outline-primary');
        });

        // 显示对应的图表容器并更新按钮状态
        switch (type) {
            case 'total':
                document.getElementById('totalScoreChart').style.display = 'block';
                buttons[0].classList.add('active');
                buttons[0].classList.remove('btn-outline-primary');
                renderTotalScoreChart();
                break;
            case 'detailed':
                document.getElementById('detailedScoreChart').style.display = 'block';
                buttons[1].classList.add('active');
                buttons[1].classList.remove('btn-outline-primary');
                renderDetailedScoreChart();
                break;
            case 'distribution':
                document.getElementById('distributionAnalysisChart').style.display = 'block';
                buttons[2].classList.add('active');
                buttons[2].classList.remove('btn-outline-primary');
                renderDistributionAnalysisChart();
                break;
        }
    };

    // 导出图表
    window.exportCharts = function () {
        const activeChart = document.querySelector('#chartView .chart-container[style*="block"]');
        if (!activeChart) {
            alert('没有可导出的图表');
            return;
        }

        // 获取当前显示的图表
        const canvas = activeChart.querySelector('canvas');
        if (!canvas) {
            alert('图表数据不可用');
            return;
        }

        // 创建下载链接
        const link = document.createElement('a');
        link.download = '评分图表.png';
        link.href = canvas.toDataURL();
        link.click();
    };

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
            await fetchAndDisplayResults(window.currentProjectId);

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

});
