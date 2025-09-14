document.addEventListener('DOMContentLoaded', function () {
    // DOM Elements
    const uploadForm = document.getElementById('uploadForm');
    const tenderFileInput = document.getElementById('tenderFile');
    const bidFilesInput = document.getElementById('bidFiles');
    const fileList = document.getElementById('fileList');
    const progressContainer = document.getElementById('progressContainer');
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    const detailedProgress = document.getElementById('detailedProgress');
    const resultArea = document.getElementById('resultArea');
    const resultDetailsModal = new bootstrap.Modal(document.getElementById('resultDetailsModal'));
    const modalBody = document.getElementById('modalBody');

    let uploadedFiles = {
        tender: null,
        bids: []
    };
    let currentProjectId = null;
    let pollInterval = null;

    // 添加WebSocket错误处理
    window.addEventListener('error', function(event) {
        // 检查是否为WebSocket相关错误
        if (event.message && event.message.includes('A listener indicated an asynchronous response by returning true, but the message channel closed before a response was received')) {
            // 这通常是浏览器扩展干扰导致的，不影响应用功能，静默处理
            console.warn('WebSocket连接被浏览器扩展干扰:', event.message);
            // 阻止错误冒泡
            event.stopImmediatePropagation();
            return false;
        }
    });

    // Event Listeners
    tenderFileInput.addEventListener('change', (e) => {
        uploadedFiles.tender = e.target.files[0];
        updateFileList();
    });

    bidFilesInput.addEventListener('change', (e) => {
        uploadedFiles.bids = Array.from(e.target.files);
        updateFileList();
    });

    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!uploadedFiles.tender || uploadedFiles.bids.length === 0) {
            alert('请选择招标文件和至少一个投标文件');
            return;
        }
        await startAnalysis();
    });

    function updateFileList() {
        if (!uploadedFiles.tender && uploadedFiles.bids.length === 0) {
            fileList.innerHTML = '<div class="text-muted"><i class="fas fa-info-circle me-2"></i>尚未选择任何文件</div>';
            return;
        }

        let html = '<h5 class="mb-3"><i class="fas fa-file-alt me-2"></i>已选择的文件：</h5><div class="row">';
        if (uploadedFiles.tender) {
            html += createFileListItem(uploadedFiles.tender, '招标文件', 'primary');
        }
        uploadedFiles.bids.forEach((file, index) => {
            html += createFileListItem(file, `投标文件 #${index + 1}`, 'info');
        });
        html += '</div>';
        fileList.innerHTML = html;
    }

    function createFileListItem(file, title, color) {
        return `
            <div class="col-md-6 mb-2">
                <div class="card border-start border-4 border-${color} h-100">
                    <div class="card-body">
                        <h6 class="card-title text-${color}">
                            <i class="fas fa-file-pdf me-2"></i>${title}
                        </h6>
                        <p class="card-text mb-1">${file.name}</p>
                        <small class="text-muted">${(file.size / 1024 / 1024).toFixed(2)} MB</small>
                    </div>
                </div>
            </div>
        `;
    }

    async function startAnalysis() {
        progressContainer.style.display = 'block';
        progressBar.style.width = '0%';
        progressText.innerHTML = '<i class="fas fa-upload me-2"></i>正在上传文件...';
        detailedProgress.innerHTML = '';
        resultArea.innerHTML = '';

        const formData = new FormData();
        formData.append('tender_file', uploadedFiles.tender);
        uploadedFiles.bids.forEach(file => formData.append('bid_files', file));

        try {
            const response = await fetch('/api/analyze-immediately', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`服务器错误: ${response.status} ${response.statusText}\n${errorText}`);
            }

            const result = await response.json();
            if (result.error) {
                throw new Error(result.error);
            }

            currentProjectId = result.project_id;
            startPolling(currentProjectId);

        } catch (error) {
            console.error('上传或分析启动失败:', error);
            progressText.innerHTML = `<div class="alert alert-danger mb-0"><i class="fas fa-exclamation-circle me-2"></i>上传失败: ${error.message}</div>`;
        }
    }

    function startPolling(projectId) {
        progressText.innerHTML = '<i class="fas fa-sync-alt fa-spin me-2"></i>正在初始化分析...';
        
        if (pollInterval) {
            clearInterval(pollInterval);
        }

        pollInterval = setInterval(() => pollProgress(projectId), 2000);
        pollProgress(projectId); // Initial poll
    }

    async function pollProgress(projectId) {
        try {
            const response = await fetch(`/api/projects/${projectId}/analysis-status`);
            if (!response.ok) {
                // If the server is just not ready, we don't want to kill the polling
                if (response.status === 404) {
                    console.warn("Analysis status not yet available, retrying...");
                    return;
                }
                throw new Error(`获取进度失败: ${response.statusText}`);
            }

            const data = await response.json();
            updateProgressDisplay(data);

            if (data.project_status === 'completed' || data.project_status === 'completed_with_errors') {
                clearInterval(pollInterval);
                progressText.innerHTML = '<i class="fas fa-check-circle me-2"></i>分析完成!';
                await fetchAndDisplayResults(projectId);
            }
        } catch (error) {
            console.error("轮询进度时出错:", error);
            // Don't stop polling on a network error, just log it and retry
        }
    }

    function updateProgressDisplay(data) {
        let overallProgress = 0;
        let totalBids = data.bids ? data.bids.length : 0;
        let completedBids = 0;

        detailedProgress.innerHTML = ''; // Clear previous entries

        if (data.bids) {
            data.bids.forEach(bid => {
                let bidProgress = bid.progress_total > 0 ? (bid.progress_completed / bid.progress_total * 100) : 0;
                if (bid.status === 'completed' || bid.status === 'error') {
                    completedBids++;
                }
                detailedProgress.innerHTML += createBidProgressItem(bid, bidProgress);
            });
        }
        
        if(totalBids > 0) {
            overallProgress = (completedBids / totalBids) * 100;
        }

        progressBar.style.width = `${overallProgress}%`;
        progressBar.setAttribute('aria-valuenow', overallProgress);
        progressText.textContent = `总体进度: ${data.project_status} (${completedBids}/${totalBids} 个文件完成)`;
    }

    function createBidProgressItem(bid, progress) {
        let statusIcon = '';
        let statusClass = '';
        switch (bid.status) {
            case 'completed':
                statusIcon = '<i class="fas fa-check-circle text-success me-2"></i>';
                statusClass = 'bg-success';
                break;
            case 'error':
                statusIcon = '<i class="fas fa-exclamation-circle text-danger me-2"></i>';
                statusClass = 'bg-danger';
                break;
            case 'processing':
                statusIcon = '<i class="fas fa-spinner fa-spin me-2"></i>';
                statusClass = 'progress-bar-striped progress-bar-animated';
                break;
            default:
                statusIcon = '<i class="fas fa-clock me-2"></i>';
                statusClass = 'bg-secondary';
        }

        return `
            <div class="mb-3">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <span>${statusIcon}${bid.bidder_name}</span>
                    <span>${progress.toFixed(1)}%</span>
                </div>
                <div class="progress" style="height: 20px;">
                    <div class="progress-bar ${statusClass}" role="progressbar" style="width: ${progress}%" aria-valuenow="${progress}" aria-valuemin="0" aria-valuemax="100">
                        ${bid.current_rule || ''}
                    </div>
                </div>
                ${bid.error_message ? `<div class="alert alert-danger mt-1 mb-0 py-1 small">${bid.error_message}</div>` : ''}
            </div>
        `;
    }

    async function fetchAndDisplayResults(projectId) {
        try {
            const [resultsResponse, rulesResponse] = await Promise.all([
                fetch(`/api/projects/${projectId}/results`),
                fetch(`/api/projects/${projectId}/scoring-rules`)
            ]);

            if (!resultsResponse.ok) {
                throw new Error(`获取分析结果失败: ${resultsResponse.statusText}`);
            }
            if (!rulesResponse.ok) {
                console.warn(`获取评分规则失败: ${rulesResponse.statusText}, 将显示简化版结果。`);
            }

            const results = await resultsResponse.json();
            const rules = rulesResponse.ok ? await rulesResponse.json() : [];

            displayResults(projectId, results, rules);

        } catch (error) {
            console.error("获取结果或规则时出错:", error);
            resultArea.innerHTML = `<div class="alert alert-danger">获取结果失败: ${error.message}</div>`;
        }
    }

    function truncateText(text, maxLength) {
        if (text.length > maxLength) {
            return text.substring(0, maxLength) + '...';
        }
        return text;
    }

    function displayResults(projectId, results, rules) {
        progressContainer.style.display = 'none';
        if (!results || results.length === 0) {
            resultArea.innerHTML = '<div class="alert alert-info">暂无分析结果</div>';
            return;
        }

        results.sort((a, b) => (b.total_score || 0) - (a.total_score || 0));

        const modelInfo = results[0].ai_model || '未知模型';

        if (!rules || rules.length === 0) {
            console.warn("未找到评分规则，将显示简化的结果表。");
            displaySimpleResults(results);
            return;
        }

        // 获取动态汇总表数据
        fetch(`/api/projects/${projectId}/dynamic-summary`)
            .then(response => response.json())
            .then(summaryData => {
                // 2. Build Header HTML
                let headerRow1 = '<tr>';
                headerRow1 += '<th rowspan="2">排名</th>';
                headerRow1 += '<th rowspan="2" class="sticky-col bidder-col">投标人</th>';
                
                // 构建表头第二行
                let headerRow2 = '<tr>';
                
                // 用于跟踪所有子项标题，以便在数据行中按顺序查找
                const allChildHeaders = [];
                
                if (summaryData && summaryData.scoring_items) {
                    // 遍历评分项构建多层表头
                    for (const [parentName, children] of Object.entries(summaryData.scoring_items)) {
                        if (children && children.length > 0) {
                            // 有子项的父项 - 合并列
                            headerRow1 += `<th colspan="${children.length}" title="${parentName}">${truncateText(parentName, 8)}</th>`;
                            
                            // 构建表头第二行 - 子项
                            children.forEach(child => {
                                const childName = child.name || 'N/A';
                                const maxScore = child.max_score || 0;
                                headerRow2 += `<th title="${childName}">${truncateText(childName, 8)}<br>(${maxScore}分)</th>`;
                                allChildHeaders.push(child.name);
                            });
                        } else {
                            // 没有子项的父项（如价格分）- 跨两行显示
                            headerRow1 += `<th rowspan="2" title="${parentName}">${truncateText(parentName, 8)}</th>`;
                            // 注意：这里不需要在第二行添加任何内容
                        }
                    }
                    
                    // 添加总分列
                    headerRow1 += '<th rowspan="2" title="总分">总分</th>';
                }
                
                headerRow1 += '</tr>';
                headerRow2 += '</tr>';

                // 3. Build Body HTML
                let tableRows = results.map((result, index) => {
                    let row = '<tr>';
                    row += `<td class="sticky-col"><span class="badge bg-primary rounded-pill">${index + 1}</span></td>`;
                    
                    const bidderName = result.bidder_name || 'N/A';
                    const truncatedName = bidderName.length > 5 ? bidderName.substring(0, 5) + '...' : bidderName;
                    row += `<td class="sticky-col bidder-col" title="${bidderName}">${truncatedName}</td>`;
                    
                    const scoresMap = new Map();
                    
                    // 正确处理detailed_scores，根据新规范处理数据结构
                    // detailed_scores是一个数组，每个元素包含Child_Item_Name、score、reason、Parent_Item_Name
                    let detailedScores = result.detailed_scores || [];
                    
                    // 处理数组格式的detailed_scores
                    if (Array.isArray(detailedScores)) {
                        // 新格式: 数组中的每个元素是一个包含Child_Item_Name、score、reason、Parent_Item_Name的字典
                        for (const item of detailedScores) {
                            // 使用Child_Item_Name作为键，score作为值
                            const childItemName = item.Child_Item_Name || item.criteria_name;
                            if (childItemName && item.score !== undefined) {
                                scoresMap.set(childItemName, item.score);
                            }
                        }
                    } 
                    // 处理旧的键值对字典结构（兼容性考虑）
                    else if (typeof detailedScores === 'object' && detailedScores !== null) {
                        // 旧格式: { '评分项名称': 分数, ... }
                        for (const [name, score] of Object.entries(detailedScores)) {
                            scoresMap.set(name, score);
                        }
                    }
                    
                    // 处理dynamic_scores
                    if (result.dynamic_scores && typeof result.dynamic_scores === 'object') {
                        for (const [name, score] of Object.entries(result.dynamic_scores)) {
                            if (typeof score === 'object' && score !== null && 'score' in score) {
                                scoresMap.set(name, score.score);
                            } else if (typeof score === 'number') {
                                scoresMap.set(name, score);
                            }
                        }
                    }
                    
                    // 确保正确处理价格分，无论它是否已经在detailed_scores中
                    if (result.price_score !== undefined && result.price_score !== null) {
                        scoresMap.set('价格分', result.price_score);
                    } else {
                        // 如果price_score为null或undefined，检查是否在detailed_scores中
                        if (Array.isArray(detailedScores)) {
                            // 在数组中查找价格评分项
                            for (const item of detailedScores) {
                                if (item.is_price_criteria || (item.Child_Item_Name && item.Child_Item_Name.includes('价格'))) {
                                    scoresMap.set('价格分', item.score);
                                    break;
                                }
                            }
                        } else if (typeof detailedScores === 'object' && detailedScores !== null) {
                            // 查找可能的价格评分项
                            for (const [name, score] of Object.entries(detailedScores)) {
                                if (name.includes('价格') || name.includes('Price')) {
                                    scoresMap.set('价格分', score);
                                    break;
                                }
                            }
                        }
                    }
                    
                    // 按顺序添加子项得分
                    allChildHeaders.forEach(childName => {
                        const score = scoresMap.get(childName);
                        row += `<td>${score !== undefined && score !== null ? parseFloat(score).toFixed(2) : '—'}</td>`;
                    });
                    
                    // 添加总分
                    const totalScore = result.total_score !== undefined && result.total_score !== null ? 
                        parseFloat(result.total_score).toFixed(2) : '—';
                    row += `<td><strong>${totalScore}</strong></td>`;

                    row += '</tr>';
                    return row;
                });

                resultArea.innerHTML = `
                    <div class="card">
                        <div class="card-header">
                            <div class="d-flex justify-content-between align-items-center">
                                <h3><i class="fas fa-poll me-2"></i>分析结果</h3>
                                <div class="d-flex gap-2">
                                    <button class="btn btn-primary" onclick="exportToExcel(${projectId})">
                                        <i class="fas fa-file-excel me-1"></i>导出Excel
                                    </button>
                                    <button class="btn btn-success" onclick="exportToWord(${projectId})">
                                        <i class="fas fa-file-word me-1"></i>导出Word
                                    </button>
                                </div>
                            </div>
                            <small class="text-muted">AI模型: ${modelInfo}</small>
                        </div>
                        <div class="card-body">
                            <div class="table-responsive">
                                <table class="table table-bordered table-hover">
                                    <thead class="table-dark align-middle text-center">
                                        ${headerRow1}
                                        ${headerRow2}
                                    </thead>
                                    <tbody class="text-center">
                                        ${tableRows}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                `;
            })
            .catch(error => {
                console.error("获取动态汇总表数据时出错:", error);
                resultArea.innerHTML = `<div class="alert alert-danger">获取动态汇总表数据失败: ${error.message}</div>`;
            });
    }

    function displaySimpleResults(results) {
        let tableRows = results.map((result, index) => `
            <tr>
                <td><span class="badge bg-primary rounded-pill">${index + 1}</span></td>
                <td>${result.bidder_name}</td>
                <td>${(result.total_score || 0).toFixed(2)}</td>
            </tr>
        `).join('');

        resultArea.innerHTML = `
            <div class="card">
                <div class="card-header"><h3><i class="fas fa-poll me-2"></i>分析结果</h3></div>
                <div class="card-body">
                    <div class="table-responsive">
                        <table class="table table-striped table-hover">
                            <thead class="table-dark">
                                <tr>
                                    <th>排名</th>
                                    <th>投标人</th>
                                    <th>总分</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${tableRows}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;
    }
});
