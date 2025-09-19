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
    const btnOpenSettings = document.getElementById('btnOpenSettings');
    const runtimeConfigModal = new bootstrap.Modal(document.getElementById('runtimeConfigModal'));
    const cfgWorkers = document.getElementById('cfg_page_workers');
    const cfgPageTimeout = document.getElementById('cfg_page_timeout');
    const cfgOverallMinTimeout = document.getElementById('cfg_overall_min_timeout');
    const btnSaveConfig = document.getElementById('btnSaveConfig');
    const cfgFeedback = document.getElementById('cfg_feedback');

    let uploadedFiles = {
        tender: null,
        bids: []
    };
    let currentProjectId = null;
    let pollInterval = null;

    // 添加WebSocket错误处理
    window.addEventListener('error', function (event) {
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

    // 打开系统设置
    btnOpenSettings.addEventListener('click', async () => {
        await loadRuntimeConfig();
        const modalElement = document.getElementById('runtimeConfigModal');
        const modal = new bootstrap.Modal(modalElement);
        modal.show();
    });

    async function loadRuntimeConfig () {
        try {
            const resp = await fetch('/api/runtime-config');
            if (!resp.ok) throw new Error(`HTTP error! status: ${resp.status}`);
            const cfg = await resp.json();
            cfgWorkers.value = cfg.pdf_page_max_workers ?? '';
            cfgPageTimeout.value = cfg.pdf_page_timeout_sec ?? '';
            cfgOverallMinTimeout.value = cfg.pdf_overall_min_timeout_sec ?? '';
            cfgFeedback.textContent = '';
        } catch (e) {
            console.error('加载配置失败:', e);
            cfgFeedback.textContent = '加载当前配置失败: ' + (e.message || e);
        }
    }

    btnSaveConfig.addEventListener('click', async () => {
        try {
            const payload = {
                pdf_page_max_workers: numOrNull(cfgWorkers.value),
                pdf_page_timeout_sec: numOrNull(cfgPageTimeout.value),
                pdf_overall_min_timeout_sec: numOrNull(cfgOverallMinTimeout.value)
            };
            const resp = await fetch('/api/runtime-config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (!resp.ok) throw new Error('保存失败');
            const saved = await resp.json();
            cfgFeedback.textContent = '保存成功：' + JSON.stringify(saved);
            setTimeout(() => runtimeConfigModal.hide(), 800);
        } catch (e) {
            cfgFeedback.textContent = '保存失败：' + (e.message || e);
        }
    });

    function numOrNull (v) {
        const n = parseInt(v, 10);
        return Number.isFinite(n) ? n : null;
    }

    function updateFileList () {
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

    function createFileListItem (file, title, color) {
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

    async function startAnalysis () {
        progressContainer.style.display = 'block';
        progressBar.style.width = '0%';
        progressText.innerHTML = '<i class="fas fa-upload me-2"></i>正在上传文件...';
        detailedProgress.innerHTML = '';
        resultArea.innerHTML = '';

        const formData = new FormData();
        formData.append('tender_file', uploadedFiles.tender);
        uploadedFiles.bids.forEach(file => formData.append('bid_files', file));

        try {
            // 第一步：初始化上传，返回候选投标人名称
            const response = await fetch('/api/init-upload', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`服务器错误: ${response.status} ${response.statusText}\n${errorText}`);
            }

            const initData = await response.json();
            if (initData.error) {
                throw new Error(initData.error);
            }

            currentProjectId = initData.project_id;
            progressText.innerHTML = '<i class="fas fa-user-edit me-2"></i>请确认各投标方名称后开始分析';

            // 打开确认投标方名称的模态框
            await showConfirmBiddersModal(initData);

        } catch (error) {
            console.error('初始化上传失败:', error);
            progressText.innerHTML = `<div class="alert alert-danger mb-0"><i class="fas fa-exclamation-circle me-2"></i>上传失败: ${error.message}</div>`;
        }
    }

    async function showConfirmBiddersModal (initData) {
        const modalHtml = `
        <div class="modal fade" id="confirmBiddersModal" tabindex="-1" aria-labelledby="confirmBiddersLabel" aria-hidden="true">
          <div class="modal-dialog modal-lg">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title" id="confirmBiddersLabel"><i class="fas fa-users me-2"></i>确认投标方名称</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
              </div>
              <div class="modal-body">
                <div class="table-responsive">
                  <table class="table table-striped align-middle">
                    <thead class="table-dark">
                      <tr>
                        <th style="width: 120px;">文件名</th>
                        <th>建议名称</th>
                        <th>确认名称</th>
                      </tr>
                    </thead>
                    <tbody>
                      ${initData.bidders.map(b => `
                        <tr>
                          <td title="${b.file_name}">${(b.file_name || '').slice(0, 20)}${(b.file_name || '').length > 20 ? '...' : ''}</td>
                          <td>${b.suggested_name || ''}</td>
                          <td>
                            <input type="text" class="form-control bidder-input" data-bid-id="${b.id}" value="${b.suggested_name || ''}">
                          </td>
                        </tr>`).join('')}
                    </tbody>
                  </table>
                </div>
                <div class="small text-muted">请核对并修改不规范的公司名称（需包含"公司/有限/股份/集团"等关键词）。</div>
              </div>
              <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                <button type="button" class="btn btn-primary" id="btnConfirmBidders"><i class="fas fa-play me-1"></i>开始分析</button>
              </div>
            </div>
          </div>
        </div>`;

        document.body.insertAdjacentHTML('beforeend', modalHtml);
        const modalElement = document.getElementById('confirmBiddersModal');
        const modal = new bootstrap.Modal(modalElement);
        modal.show();

        document.getElementById('btnConfirmBidders').addEventListener('click', async () => {
            try {
                const inputs = Array.from(document.querySelectorAll('.bidder-input'));
                const bidders = inputs.map(inp => ({ id: parseInt(inp.getAttribute('data-bid-id'), 10), confirmed_name: inp.value.trim() }));

                // 简单校验
                const companyKeywords = ['公司', '有限', '股份', '集团', '厂', '院', '所', '中心'];
                for (const b of bidders) {
                    if (!b.confirmed_name || b.confirmed_name.length < 2 || !companyKeywords.some(k => b.confirmed_name.includes(k))) {
                        alert('名称无效，请检查：' + (b.confirmed_name || '空'));
                        return;
                    }
                }

                const resp = await fetch(`/api/projects/${currentProjectId}/start-analysis`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ bidders })
                });
                if (!resp.ok) {
                    const err = await resp.text();
                    throw new Error(err || '启动分析失败');
                }

                modal.hide();
                // 启动轮询
                startPolling(currentProjectId);
            } catch (e) {
                alert('启动分析失败：' + (e.message || e));
            }
        });

        modalElement.addEventListener('hidden.bs.modal', function () {
            document.body.removeChild(modalElement);
        });
    }

    function startPolling (projectId) {
        progressText.innerHTML = '<i class="fas fa-sync-alt fa-spin me-2"></i>正在初始化分析...';

        if (pollInterval) {
            clearInterval(pollInterval);
        }

        pollInterval = setInterval(() => pollProgress(projectId), 2000);
        pollProgress(projectId); // Initial poll
    }

    async function pollProgress (projectId) {
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

    function updateProgressDisplay (data) {
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

        if (totalBids > 0) {
            overallProgress = (completedBids / totalBids) * 100;
        }

        progressBar.style.width = `${overallProgress}%`;
        progressBar.setAttribute('aria-valuenow', overallProgress);
        progressText.textContent = `总体进度: ${data.project_status} (${completedBids}/${totalBids} 个文件完成)`;
    }

    function createBidProgressItem (bid, progress) {
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

    async function fetchAndDisplayResults (projectId) {
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

    function truncateText (text, maxLength) {
        if (text.length > maxLength) {
            return text.substring(0, maxLength) + '...';
        }
        return text;
    }

    function displayResults (projectId, results, rules) {
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
                // 2. Build Header HTML (双层表头)
                let headerTop = '<tr>';
                let headerBottom = '<tr>';
                headerTop += '<th rowspan="2">排名</th>';
                headerTop += '<th rowspan="2" class="sticky-col bidder-col">投标人</th>';

                // 用于跟踪所有子项标题，以便在数据行中按顺序查找
                const allChildHeaders = [];

                if (summaryData && summaryData.scoring_items) {
                    for (const [parentName, children] of Object.entries(summaryData.scoring_items)) {
                        if (children && children.length > 0) {
                            // 顶层父项列合并
                            headerTop += `<th colspan="${children.length}" class="text-center">${parentName}</th>`;
                            // 第二行子项列
                            children.forEach(child => {
                                const childName = child.name || 'N/A';
                                const maxScore = child.max_score || 0;
                                headerBottom += `<th title="${childName}">${truncateText(childName, 8)}<br>(${maxScore}分)</th>`;
                                allChildHeaders.push(childName);
                            });
                        }
                    }

                    // 价格分与总分列
                    headerTop += '<th rowspan="2" title="价格分">价格分</th>';
                    headerTop += '<th rowspan="2" title="总分">总分</th>';
                }

                headerTop += '</tr>';
                headerBottom += '</tr>';

                // 3. Build Body HTML
                let tableRows = results.map((result, index) => {
                    let row = '<tr>';
                    row += `<td class="sticky-col"><span class="badge bg-primary rounded-pill">${index + 1}</span></td>`;

                    const bidderName = result.bidder_name || 'N/A';
                    const truncatedName = bidderName.length > 5 ? bidderName.substring(0, 5) + '...' : bidderName;
                    // 添加可编辑的投标方名称单元格
                    row += `<td class="sticky-col bidder-col" title="${bidderName}">
                                <span class="bidder-name-text">${truncatedName}</span>
                                <button class="btn btn-sm btn-outline-primary edit-bidder-name ms-2" data-bid="${result.id}" data-current-name="${bidderName}">
                                    <i class="fas fa-edit"></i>
                                </button>
                            </td>`;

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

                    // 按顺序添加子项得分
                    allChildHeaders.forEach(childName => {
                        const score = scoresMap.get(childName);
                        row += `<td>${score !== undefined && score !== null ? parseFloat(score).toFixed(2) : '—'}</td>`;
                    });

                    // 添加价格分
                    const priceScore = result.price_score !== undefined && result.price_score !== null ?
                        parseFloat(result.price_score).toFixed(2) : '—';
                    row += `<td>${priceScore}</td>`;

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
                                        ${headerTop}
                                        ${headerBottom}
                                    </thead>
                                    <tbody class="text-center">
                                        ${tableRows}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                `;

                // 添加事件监听器用于编辑投标方名称
                document.querySelectorAll('.edit-bidder-name').forEach(button => {
                    button.addEventListener('click', function () {
                        const bidId = this.getAttribute('data-bid');
                        const currentName = this.getAttribute('data-current-name');
                        editBidderName(bidId, currentName);
                    });
                });
            })
            .catch(error => {
                console.error("获取动态汇总表数据时出错:", error);
                resultArea.innerHTML = `<div class="alert alert-danger">获取动态汇总表数据失败: ${error.message}</div>`;
            });
    }

    function displaySimpleResults (results) {
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

// 编辑投标方名称函数
async function editBidderName (bidId, currentName) {
    // 创建模态框HTML
    const modalHtml = `
        <div class="modal fade" id="editBidderNameModal" tabindex="-1" aria-labelledby="editBidderNameModalLabel" aria-hidden="true">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="editBidderNameModalLabel">编辑投标方名称</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <form id="editBidderNameForm">
                            <div class="mb-3">
                                <label for="newBidderName" class="form-label">新的投标方名称</label>
                                <input type="text" class="form-control" id="newBidderName" value="${currentName}" required>
                                <div class="form-text">请输入有效的公司名称，必须包含"公司"、"有限"、"股份"、"集团"等关键词。</div>
                            </div>
                            <div id="editNameFeedback" class="small text-danger"></div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                        <button type="button" class="btn btn-primary" id="saveBidderNameBtn">保存</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    // 添加模态框到页面
    document.body.insertAdjacentHTML('beforeend', modalHtml);

    // 显示模态框
    const modalElement = document.getElementById('editBidderNameModal');
    const modal = new bootstrap.Modal(modalElement);
    modal.show();

    // 保存按钮事件监听器
    document.getElementById('saveBidderNameBtn').addEventListener('click', async function () {
        const newName = document.getElementById('newBidderName').value.trim();
        const feedbackElement = document.getElementById('editNameFeedback');

        // 简单验证
        if (newName.length < 2) {
            feedbackElement.textContent = '名称长度不能少于2个字符';
            return;
        }

        // 检查是否包含公司关键词
        const companyKeywords = ['公司', '有限', '股份', '集团', '厂', '院', '所', '中心'];
        if (!companyKeywords.some(keyword => newName.includes(keyword))) {
            feedbackElement.textContent = '名称必须包含公司关键词，如"公司"、"有限"、"股份"、"集团"等';
            return;
        }

        try {
            // 发送请求更新投标方名称
            const response = await fetch(`/api/bids/${bidId}/name`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ new_name: newName })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || '更新失败');
            }

            const result = await response.json();
            
            // 更新表格中的显示
            const nameElements = document.querySelectorAll(`.edit-bidder-name[data-bid="${bidId}"]`);
            nameElements.forEach(element => {
                const nameSpan = element.closest('td').querySelector('.bidder-name-text');
                if (nameSpan) {
                    const truncatedName = newName.length > 10 ? newName.substring(0, 10) + '...' : newName;
                    nameSpan.textContent = truncatedName;
                    nameSpan.setAttribute('title', newName);
                    // 更新按钮的data-current-name属性
                    element.setAttribute('data-current-name', newName);
                }
            });

            // 关闭模态框
            modal.hide();
            
            // 显示成功消息
            alert('投标方名称更新成功');
        } catch (error) {
            console.error('更新投标方名称失败:', error);
            feedbackElement.textContent = '更新失败: ' + (error.message || '未知错误');
        }
    });

    // 模态框关闭后移除DOM元素
    modalElement.addEventListener('hidden.bs.modal', function () {
        document.body.removeChild(modalElement);
    });
}
