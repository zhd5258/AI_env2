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
    function updateFileList() {
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
            // 检查是否为浏览器扩展引起的错误
            if (error.message.includes('message channel closed')) {
                console.warn('可能由浏览器扩展引起的连接错误，这通常不会影响功能:', error);
                // 继续执行，因为这类错误通常不会影响实际功能
                return;
            }
            
            console.error('Error:', error);
            alert('上传失败: ' + error.message);
            progressContainer.style.display = 'none';
            progressText.textContent = '';
        }
    });

    // 开始轮询获取进度
    function startPolling (projectId) {
        // 减少控制台日志输出，只在开发时启用
        // console.log("开始轮询项目进度，项目ID:", projectId);

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
    async function pollProgress(projectId) {
        try {
            const response = await fetch(`/api/projects/${projectId}/analysis-status`);
            if (!response.ok) {
                throw new Error(`获取进度失败: ${response.statusText}`);
            }

            const data = await response.json();
            // 减少控制台日志输出，只在开发时启用
            // console.log("轮询获取到进度数据:", data);

            // 更新进度显示
            updateProgressFromStatus(data);

            // 检查是否完成
            if (data.project_status === 'completed' || data.project_status === 'completed_with_errors') {
                console.log("分析完成，停止轮询");
                clearInterval(window.pollInterval);

                // 延迟1秒后显示结果，确保最后一次进度更新完成
                setTimeout(() => {
                    if (typeof displayResults !== 'undefined') {
                        fetchAndDisplayResults(projectId);
                    } else {
                        // 如果displayResults函数不在当前作用域，则触发一个自定义事件
                        window.dispatchEvent(new CustomEvent('analysisCompleted', { detail: { projectId } }));
                    }
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
    function updateProgressFromStatus(data) {
        // 减少控制台日志输出，只在开发时启用
        // console.log("Update progress from status called with data:", data);

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
    function displayDetailedProgress(data) {
        // 减少控制台日志输出，只在开发时启用
        // console.log("Displaying detailed progress with data:", data);

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
                            ${partialResultsHtml}
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

        // 确保详细进度区域存在并更新内容
        let detailArea = document.getElementById('detailedProgress');
        if (detailArea) {
            detailArea.innerHTML = html;
        }
    }

    // 获取并显示最终结果
    async function fetchAndDisplayResults(projectId) {
        try {
            const response = await fetch(`/api/projects/${projectId}/results`);
            if (!response.ok) {
                if (response.status === 404) {
                    // 分析可能失败或没有生成结果
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
            } else {
                // 如果displayResults函数不在当前作用域，则触发一个自定义事件
                window.dispatchEvent(new CustomEvent('resultsReady', { detail: { results } }));
            }
        } catch (error) {
            console.error("获取结果时出错:", error);
            resultArea.innerHTML = `<div class="alert alert-danger"><i class="fas fa-exclamation-circle me-2"></i>获取结果时出错: ${error.message}</div>`;
        }
    }

    // 将部分函数暴露到全局作用域
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
    function displayFailedPages(bidderName, failedPagesData) {
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
});