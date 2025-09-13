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

    let uploadedFiles = { tender: null, bids: [] };
    let currentProjectId = null;
    let pollInterval = null;
    let priceChartInstance = null;

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
                        <h6 class="card-title text-${color}"><i class="fas fa-file-pdf me-2"></i>${title}</h6>
                        <p class="card-text mb-1">${file.name}</p>
                        <small class="text-muted">${(file.size / 1024 / 1024).toFixed(2)} MB</small>
                    </div>
                </div>
            </div>`;
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
            const response = await fetch('/api/analyze-immediately', { method: 'POST', body: formData });
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`服务器错误: ${response.status} ${response.statusText}\n${errorText}`);
            }
            const result = await response.json();
            if (result.error) throw new Error(result.error);
            currentProjectId = result.project_id;
            startPolling(currentProjectId);
        } catch (error) {
            console.error('上传或分析启动失败:', error);
            progressText.innerHTML = `<div class="alert alert-danger mb-0"><i class="fas fa-exclamation-circle me-2"></i>上传失败: ${error.message}</div>`;
        }
    }

    function startPolling(projectId) {
        progressText.innerHTML = '<i class="fas fa-sync-alt fa-spin me-2"></i>正在初始化分析...';
        if (pollInterval) clearInterval(pollInterval);
        pollInterval = setInterval(() => pollProgress(projectId), 2000);
        pollProgress(projectId);
    }

    async function pollProgress(projectId) {
        try {
            const response = await fetch(`/api/projects/${projectId}/analysis-status`);
            if (!response.ok) {
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
        }
    }

    function updateProgressDisplay(data) {
        let totalBids = data.bids ? data.bids.length : 0;
        let completedBids = 0;
        detailedProgress.innerHTML = '';
        if (data.bids) {
            data.bids.forEach(bid => {
                if (bid.status === 'completed' || bid.status === 'error') completedBids++;
                detailedProgress.innerHTML += createBidProgressItem(bid);
            });
        }
        let overallProgress = totalBids > 0 ? (completedBids / totalBids) * 100 : 0;
        progressBar.style.width = `${overallProgress}%`;
        progressBar.setAttribute('aria-valuenow', overallProgress);
        progressText.textContent = `总体进度: ${data.project_status} (${completedBids}/${totalBids} 个文件完成)`;
    }

    function createBidProgressItem(bid) {
        let progress = bid.progress_total > 0 ? (bid.progress_completed / bid.progress_total * 100) : (bid.status === 'completed' ? 100 : 0);
        let statusIcon, statusClass;
        switch (bid.status) {
            case 'completed': statusIcon = '<i class="fas fa-check-circle text-success me-2"></i>'; statusClass = 'bg-success'; break;
            case 'error': statusIcon = '<i class="fas fa-exclamation-circle text-danger me-2"></i>'; statusClass = 'bg-danger'; break;
            case 'processing': statusIcon = '<i class="fas fa-spinner fa-spin me-2"></i>'; statusClass = 'progress-bar-striped progress-bar-animated'; break;
            default: statusIcon = '<i class="fas fa-clock me-2"></i>'; statusClass = 'bg-secondary';
        }
        return `
            <div class="mb-3">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <span>${statusIcon}${bid.bidder_name}</span>
                    <span>${progress.toFixed(1)}%</span>
                </div>
                <div class="progress" style="height: 20px;">
                    <div class="progress-bar ${statusClass}" role="progressbar" style="width: ${progress}%">${bid.current_rule || ''}</div>
                </div>
                ${bid.error_message ? `<div class="alert alert-danger mt-1 mb-0 py-1 small">${bid.error_message}</div>` : ''}
            </div>`;
    }

    async function fetchAndDisplayResults(projectId) {
        try {
            const [resultsResponse, rulesResponse] = await Promise.all([
                fetch(`/api/projects/${projectId}/results`),
                fetch(`/api/projects/${projectId}/scoring-rules`)
            ]);
            if (!resultsResponse.ok) throw new Error(`获取分析结果失败: ${resultsResponse.statusText}`);
            const results = await resultsResponse.json();
            const rules = rulesResponse.ok ? await rulesResponse.json() : [];
            displayResults(projectId, results, rules);
        } catch (error) {
            console.error("获取结果或规则时出错:", error);
            resultArea.innerHTML = `<div class="alert alert-danger">获取结果失败: ${error.message}</div>`;
        }
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
            displaySimpleResults(results);
            return;
        }

        const groupedRules = rules.reduce((acc, rule) => {
            const parent = rule.category || '未分类';
            if (!acc[parent]) {
                const parentRule = rules.find(r => r.criteria_name === parent && r.category === parent);
                acc[parent] = { children: [], parent_score: parentRule ? parentRule.max_score : 0 };
            }
            if (rule.category !== rule.criteria_name) {
                acc[parent].children.push({ name: rule.criteria_name, max_score: rule.max_score });
            }
            return acc;
        }, {});

        for (const category in groupedRules) {
            if (groupedRules[category].children.length === 0) {
                const rule = rules.find(r => r.category === category && r.criteria_name === category);
                if (rule) groupedRules[category].children.push({ name: rule.criteria_name, max_score: rule.max_score });
            }
        }

        let headerRow1 = '<tr><th rowspan="2" class="sticky-col">排名</th><th rowspan="2" class="sticky-col bidder-col">投标人</th><th rowspan="2">总分</th>';
        let headerRow2 = '<tr>';
        const allChildHeaders = [];

        for (const category in groupedRules) {
            const group = groupedRules[category];
            if (group.children.length > 0) {
                if (group.children.length === 1 && group.children[0].name === category) {
                    const child = group.children[0];
                    headerRow1 += `<th rowspan="2" title="${child.name}">${truncateText(child.name)} (${child.max_score}分)</th>`;
                    allChildHeaders.push(child.name);
                } else {
                    headerRow1 += `<th colspan="${group.children.length}">${category} (${group.parent_score}分)</th>`;
                    group.children.forEach(child => {
                        headerRow2 += `<th title="${child.name}">${truncateText(child.name)} (${child.max_score}分)</th>`;
                        allChildHeaders.push(child.name);
                    });
                }
            }
        }
        headerRow1 += '</tr>';
        headerRow2 += '</tr>';

        let tableRows = results.map((result, index) => {
            let row = `<tr><td class="sticky-col"><span class="badge bg-primary rounded-pill">${index + 1}</span></td>`;
            row += `<td class="sticky-col bidder-col" title="${result.bidder_name}">${truncateText(result.bidder_name)}</td>`;
            row += `<td><strong>${(result.total_score || 0).toFixed(2)}</strong></td>`;
            const scoresMap = buildScoresMap(result, rules);
            allChildHeaders.forEach(childName => {
                const score = scoresMap.get(childName);
                row += `<td>${score !== undefined && score !== null ? parseFloat(score).toFixed(2) : '—'}</td>`;
            });
            row += '</tr>';
            return row;
        }).join('');

        resultArea.innerHTML = `
            <div class="card">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <div><h3><i class="fas fa-poll me-2"></i>分析结果</h3><p class="text-muted mb-0">AI模型: ${modelInfo}</p></div>
                    <div>
                        <button id="analysisBtn" class="btn btn-info"><i class="fas fa-chart-bar me-2"></i>图表与详细分析</button>
                        <a href="/api/projects/${projectId}/download-results" class="btn btn-success ms-2"><i class="fas fa-file-excel me-2"></i>下载Excel报告</a>
                    </div>
                </div>
                <div class="card-body">
                    <div class="table-responsive">
                        <table class="table table-striped table-hover table-bordered summary-table">
                            <thead class="table-dark align-middle text-center">${headerRow1}${headerRow2}</thead>
                            <tbody class="text-center">${tableRows}</tbody>
                        </table>
                    </div>
                </div>
            </div>`;
        
        document.getElementById('analysisBtn').addEventListener('click', () => displayDetailedAnalysis(results, rules));
    }

    function displayDetailedAnalysis(results, rules) {
        renderPriceChart(results);
        const viewToggle = document.getElementById('viewToggle');
        viewToggle.addEventListener('change', (e) => renderDetailedTable(e.target.value, results, rules));
        renderDetailedTable('child', results, rules);
        resultDetailsModal.show();
    }

    function renderPriceChart(results) {
        const ctx = document.getElementById('priceChart').getContext('2d');
        const labels = results.map(r => truncateText(r.bidder_name, 10));
        const prices = results.map(r => r.extracted_price || 0);
        const priceScores = results.map(r => r.price_score || 0);

        if (priceChartInstance) priceChartInstance.destroy();
        
        priceChartInstance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: '投标报价 (元)',
                        data: prices,
                        backgroundColor: 'rgba(54, 162, 235, 0.6)',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 1,
                        yAxisID: 'y-price',
                    },
                    {
                        label: '价格得分',
                        data: priceScores,
                        backgroundColor: 'rgba(255, 99, 132, 0.6)',
                        borderColor: 'rgba(255, 99, 132, 1)',
                        borderWidth: 1,
                        yAxisID: 'y-score',
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    'y-price': {
                        type: 'linear',
                        position: 'left',
                        title: { display: true, text: '投标报价 (元)' }
                    },
                    'y-score': {
                        type: 'linear',
                        position: 'right',
                        title: { display: true, text: '价格得分' },
                        grid: { drawOnChartArea: false }
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            title: (tooltipItems) => results[tooltipItems[0].dataIndex].bidder_name
                        }
                    }
                }
            }
        });
    }

    function renderDetailedTable(viewType, results, rules) {
        const container = document.getElementById('detailedTableContainer');
        let tableHtml = '<table class="table table-sm table-striped table-bordered">';
        
        const childToParentMap = rules.reduce((map, rule) => {
            if (rule.category !== rule.criteria_name) map[rule.criteria_name] = rule.category;
            return map;
        }, {});

        if (viewType === 'child') {
            tableHtml += `
                <thead class="table-light">
                    <tr><th>投标人</th><th>评分大项</th><th>评分子项</th><th>得分</th></tr>
                </thead><tbody>`;
            results.forEach(result => {
                const scoresMap = buildScoresMap(result, rules);
                scoresMap.forEach((score, name) => {
                    const parent = childToParentMap[name] || '直接评分项';
                    tableHtml += `<tr><td>${truncateText(result.bidder_name)}</td><td>${parent}</td><td>${name}</td><td>${score.toFixed(2)}</td></tr>`;
                });
            });
        } else { // parent view
            tableHtml += `
                <thead class="table-light">
                    <tr><th>投标人</th><th>评分大项</th><th>汇总得分</th></tr>
                </thead><tbody>`;
            results.forEach(result => {
                const parentScores = {};
                const scoresMap = buildScoresMap(result, rules);
                scoresMap.forEach((score, name) => {
                    const parent = childToParentMap[name] || name; // If no parent, it's a parent itself
                    if (!parentScores[parent]) parentScores[parent] = 0;
                    parentScores[parent] += score;
                });
                for (const [parent, score] of Object.entries(parentScores)) {
                    tableHtml += `<tr><td>${truncateText(result.bidder_name)}</td><td>${parent}</td><td>${score.toFixed(2)}</td></tr>`;
                }
            });
        }
        
        tableHtml += '</tbody></table>';
        container.innerHTML = tableHtml;
    }

    function buildScoresMap(result, rules) {
        const scoresMap = new Map();
        if (result.detailed_scores) {
            for (const [name, score] of Object.entries(result.detailed_scores)) {
                scoresMap.set(name, score);
            }
        }
        if (result.price_score !== null && result.price_score !== undefined) {
            const priceRule = rules.find(r => r.is_price_criteria || (r.category && r.category.includes('价格')));
            const priceRuleName = priceRule ? priceRule.criteria_name : '价格分';
            scoresMap.set(priceRuleName, result.price_score);
        }
        return scoresMap;
    }

    function truncateText(text, length = 5) {
        if (!text) return 'N/A';
        return text.length > length ? text.substring(0, length) + '...' : text;
    }

    function displaySimpleResults(results) {
        let tableRows = results.map((result, index) => `
            <tr>
                <td><span class="badge bg-primary rounded-pill">${index + 1}</span></td>
                <td>${result.bidder_name}</td>
                <td>${(result.total_score || 0).toFixed(2)}</td>
            </tr>`).join('');
        resultArea.innerHTML = `
            <div class="card">
                <div class="card-header"><h3><i class="fas fa-poll me-2"></i>分析结果</h3></div>
                <div class="card-body">
                    <div class="table-responsive">
                        <table class="table table-striped table-hover">
                            <thead class="table-dark"><tr><th>排名</th><th>投标人</th><th>总分</th></tr></thead>
                            <tbody>${tableRows}</tbody>
                        </table>
                    </div>
                </div>
            </div>`;
    }
});