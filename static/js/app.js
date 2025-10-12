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

    // 延迟初始化Bootstrap模态框，确保Bootstrap已经加载
    let resultDetailsModal, runtimeConfigModal;

    // 等待Bootstrap加载完成后再初始化模态框
    function initBootstrapModals () {
        if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
            resultDetailsModal = new bootstrap.Modal(document.getElementById('resultDetailsModal'));
            runtimeConfigModal = new bootstrap.Modal(document.getElementById('runtimeConfigModal'));
        } else {
            // 如果Bootstrap还没有加载完成，稍后再尝试
            setTimeout(initBootstrapModals, 100);
        }
    }

    // 开始初始化模态框
    initBootstrapModals();

    const btnOpenSettings = document.getElementById('btnOpenSettings');
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
        // 确保Bootstrap已经加载
        if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
            const modal = new bootstrap.Modal(modalElement);
            modal.show();
        } else {
            // 如果Bootstrap还没有加载完成，等待一下再显示
            setTimeout(() => {
                if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                    const modal = new bootstrap.Modal(modalElement);
                    modal.show();
                }
            }, 200);
        }
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
        `;

        initData.bidders.forEach((bidder, index) => {
            modalHtml += `
                      <tr>
                        <td>${bidder.filename}</td>
                        <td>${bidder.suggested_name}</td>
                        <td>
                          <input type="text" class="form-control bidder-name-input" 
                                 data-index="${index}" 
                                 value="${bidder.suggested_name}">
                        </td>
                      </tr>
            `;
        });

        modalHtml += `
                    </tbody>
                  </table>
                </div>
              </div>
              <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                <button type="button" class="btn btn-primary" id="confirmBiddersBtn">
                  <i class="fas fa-check me-2"></i>确认并开始分析
                </button>
              </div>
            </div>
          </div>
        </div>
        `;

        // 添加模态框到页面
        document.body.insertAdjacentHTML('beforeend', modalHtml);

        // 等待Bootstrap加载完成后再显示模态框
        function showConfirmModal () {
            if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                const modalElement = document.getElementById('confirmBiddersModal');
                const modal = new bootstrap.Modal(modalElement);
                modal.show();

                // 添加确认按钮事件监听器
                document.getElementById('confirmBiddersBtn').addEventListener('click', async () => {
                    const bidders = [];
                    document.querySelectorAll('.bidder-name-input').forEach((input, index) => {
                        bidders.push({
                            filename: initData.bidders[index].filename,
                            name: input.value
                        });
                    });

                    // 关闭模态框
                    modal.hide();

                    // 开始分析
                    await startAnalysisWithConfirmedNames(bidders);
                });

                // 模态框关闭后清理
                modalElement.addEventListener('hidden.bs.modal', function () {
                    document.body.removeChild(modalElement);
                });
            } else {
                // 如果Bootstrap还没有加载完成，稍后再尝试
                setTimeout(showConfirmModal, 100);
            }
        }

        showConfirmModal();
    }

    async function startAnalysisWithConfirmedNames (bidders) {
        progressText.innerHTML = '<i class="fas fa-sync-alt fa-spin me-2"></i>正在初始化分析...';

        try {
            const resp = await fetch(`/api/projects/${currentProjectId}/start-analysis`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ bidders })
            });
            if (!resp.ok) {
                const err = await resp.text();
                throw new Error(err || '启动分析失败');
            }

            // 启动轮询
            startPolling(currentProjectId);
        } catch (e) {
            alert('启动分析失败：' + (e.message || e));
        }
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
            const response = await fetch(`/api/projects/${projectId}/progress`);
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
        // 过滤掉招标文件，只计算投标文件的进度
        let bidDocuments = [];
        if (data.document_statuses) {
            bidDocuments = data.document_statuses.filter(doc =>
                doc.file_path && !doc.file_path.includes('tender') && !doc.file_path.includes('招标')
            );
        }
        let totalBids = bidDocuments.length;
        let completedBids = 0;

        detailedProgress.innerHTML = ''; // Clear previous entries

        if (bidDocuments) {
            bidDocuments.forEach(bid => {
                let bidProgress = bid.progress_total > 0 ? (bid.progress_completed / bid.progress_total * 100) : 0;
                if (bid.processing_status === 'completed') {
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

        // 显示更详细的处理阶段信息
        let phaseInfo = '';
        if (bidDocuments && bidDocuments.length > 0) {
            const phases = bidDocuments.map(doc => doc.processing_phase).filter(phase => phase);
            if (phases.length > 0) {
                // 统计各阶段的文件数量
                const phaseCounts = {};
                phases.forEach(phase => {
                    phaseCounts[phase] = (phaseCounts[phase] || 0) + 1;
                });

                // 构建阶段信息字符串
                const phaseTexts = Object.entries(phaseCounts).map(([phase, count]) => `${phase}: ${count}个`);
                phaseInfo = ` (${phaseTexts.join(', ')})`;
            }
        }

        progressText.textContent = `总体进度: ${data.processing_status} (${completedBids}/${totalBids} 个文件完成)${phaseInfo}`;
    }

    function createBidProgressItem (bid, progress) {
        let statusIcon = '';
        let statusClass = '';
        let statusText = '';

        // 根据处理阶段显示不同的状态
        if (bid.processing_phase) {
            statusText = bid.processing_phase;
        } else {
            switch (bid.processing_status) {
                case 'completed':
                    statusIcon = '<i class="fas fa-check-circle text-success me-2"></i>';
                    statusClass = 'bg-success';
                    statusText = '分析完成';
                    break;
                case 'error':
                    statusIcon = '<i class="fas fa-exclamation-circle text-danger me-2"></i>';
                    statusClass = 'bg-danger';
                    statusText = '处理出错';
                    break;
                case 'processing':
                    statusIcon = '<i class="fas fa-spinner fa-spin me-2"></i>';
                    statusClass = 'progress-bar-striped progress-bar-animated bg-info';
                    statusText = '处理中';
                    break;
                default:
                    statusIcon = '<i class="fas fa-clock me-2"></i>';
                    statusClass = 'bg-secondary';
                    statusText = '等待处理';
            }
        }

        // 如果有当前规则信息，显示在进度条上
        if (bid.current_rule && bid.processing_status === 'processing') {
            statusText = bid.current_rule;
        }

        // 处理警告状态
        let warningAlert = '';
        if (bid.error_message && bid.processing_status === 'completed') {
            warningAlert = `<div class="alert alert-warning mt-1 mb-0 py-1 small">${bid.error_message}</div>`;
        }

        return `
            <div class="mb-3">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <span>${statusIcon}${bid.bidder_name}</span>
                    <span>${progress.toFixed(1)}%</span>
                </div>
                <div class="progress" style="height: 20px; width: 100%;">
                    <div class="progress-bar ${statusClass}" role="progressbar" style="width: ${progress}%; transition: width 0.3s ease;" aria-valuenow="${progress}" aria-valuemin="0" aria-valuemax="100">
                        ${statusText}
                    </div>
                </div>
                ${bid.error_message && bid.processing_status === 'error' ? `<div class="alert alert-danger mt-1 mb-0 py-1 small">${bid.error_message}</div>` : ''}
                ${warningAlert}
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
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(summaryData => {
                // 如果获取动态汇总数据失败，尝试获取普通汇总数据
                if (summaryData.error) {
                    console.warn('动态汇总数据获取失败，尝试获取普通汇总数据');
                    return fetch(`/api/projects/${projectId}/summary`)
                        .then(response => response.json())
                        .then(fallbackData => {
                            // 如果普通汇总数据也失败，构造兼容的数据格式
                            if (fallbackData.error) {
                                console.warn('普通汇总数据获取失败，尝试构造兼容格式');
                                return fetch(`/api/projects/${projectId}/results`)
                                    .then(response => response.json())
                                    .then(resultsData => {
                                        return {
                                            summary: resultsData.results || [],
                                            project_name: resultsData.project_name || '未知项目'
                                        };
                                    });
                            }
                            return fallbackData;
                        });
                }
                return summaryData;
            })
            .then(summaryData => {
                // 2. Build Header HTML (双层表头)
                let headerTop = '<tr>';
                let headerBottom = '<tr>';
                headerTop += '<th rowspan="2">排名</th>';
                headerTop += '<th rowspan="2" class="sticky-col bidder-col">投标人</th>';

                // 用于跟踪所有子项标题，以便在数据行中按顺序查找
                const allChildHeaders = [];

                // 使用动态生成的表头数据
                if (summaryData && summaryData.header_rows) {
                    // 第一行表头（父项）
                    const headerTopRow = summaryData.header_rows[0] || [];
                    // 第二行表头（子项）
                    const headerBottomRow = summaryData.header_rows[1] || [];

                    // 处理第一行表头
                    headerTopRow.forEach(headerCell => {
                        const colspan = headerCell.colspan ? `colspan="${headerCell.colspan}"` : '';
                        const rowspan = headerCell.rowspan ? `rowspan="${headerCell.rowspan}"` : '';
                        headerTop += `<th ${colspan} ${rowspan} class="text-center">${headerCell.name}</th>`;
                    });

                    // 处理第二行表头
                    headerBottomRow.forEach(headerCell => {
                        headerBottom += `<th>${headerCell.name}</th>`;
                        allChildHeaders.push(headerCell.name);
                    });
                } else if (summaryData && summaryData.scoring_items) {
                    // 降级到旧的处理方式
                    for (const [parentName, children] of Object.entries(summaryData.scoring_items)) {
                        if (children && children.length > 0) {
                            // 顶层父项列合并（只显示父项名称，不显示分值）
                            headerTop += `<th colspan="${children.length}" class="text-center">${parentName}</th>`;
                            // 第二行子项列
                            children.forEach(child => {
                                const childName = child.name || 'N/A';
                                // 只显示子项名称，不添加分值（因为名称中已经包含了分值）
                                headerBottom += `<th title="${childName}">${truncateText(childName, 8)}</th>`;
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

                    // 如果没有找到评分数据，尝试从其他字段获取
                    if (scoresMap.size === 0 && result.scores) {
                        // 处理后端返回的scores数组
                        if (Array.isArray(result.scores)) {
                            result.scores.forEach((score, index) => {
                                const childHeader = allChildHeaders[index];
                                if (childHeader && score !== undefined && score !== null) {
                                    scoresMap.set(childHeader, typeof score === 'number' ? score : parseFloat(score) || 0);
                                }
                            });
                        }
                    }

                    // 按顺序添加子项得分
                    allChildHeaders.forEach(childName => {
                        const score = scoresMap.get(childName);
                        const displayScore = score !== undefined ? score.toFixed(2) : 'N/A';
                        row += `<td>${displayScore}</td>`;
                    });

                    // 添加价格分和总分
                    const priceScore = result.price_score !== undefined ? result.price_score.toFixed(2) : 'N/A';
                    const totalScore = result.total_score !== undefined ? result.total_score.toFixed(2) : 'N/A';
                    row += `<td>${priceScore}</td>`;
                    row += `<td>${totalScore}</td>`;

                    row += '</tr>';
                    return row;
                });

                // 4. Build Complete HTML
                let html = `
                    <div class="card">
                        <div class="card-header">
                            <h3 class="card-title">
                                <i class="fas fa-chart-bar me-2"></i>评标结果汇总表
                                <small class="text-muted ms-2">(AI模型: ${modelInfo})</small>
                            </h3>
                            <div class="card-tools">
                                <button class="btn btn-sm btn-outline-primary me-2" id="exportExcelBtn">
                                    <i class="fas fa-file-excel me-1"></i>导出Excel
                                </button>
                                <button class="btn btn-sm btn-outline-info" id="viewDetailsBtn">
                                    <i class="fas fa-info-circle me-1"></i>查看详情
                                </button>
                            </div>
                        </div>
                        <div class="card-body">
                            <div class="table-responsive">
                                <table class="table table-bordered table-hover summary-table">
                                    <thead class="table-dark">
                                        ${headerTop}
                                        ${headerBottom}
                                    </thead>
                                    <tbody>
                                        ${tableRows.join('')}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                `;

                resultArea.innerHTML = html;

                // 添加事件监听器
                document.getElementById('exportExcelBtn').addEventListener('click', () => exportToExcel(results, summaryData));
                document.getElementById('viewDetailsBtn').addEventListener('click', () => showResultDetails(results, rules));

                // 添加编辑投标方名称按钮的事件监听器
                document.querySelectorAll('.edit-bidder-name').forEach(button => {
                    button.addEventListener('click', function () {
                        const bidId = this.getAttribute('data-bid');
                        const currentName = this.getAttribute('data-current-name');
                        editBidderName(bidId, currentName);
                    });
                });
            })
            .catch(error => {
                console.error('获取动态汇总数据失败:', error);
                resultArea.innerHTML = `<div class="alert alert-danger">获取动态汇总数据失败: ${error.message}</div>`;
            });
    }

    function displaySimpleResults (results) {
        let html = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title"><i class="fas fa-chart-bar me-2"></i>评标结果</h3>
                </div>
                <div class="card-body">
                    <div class="table-responsive">
                        <table class="table table-bordered table-hover">
                            <thead class="table-dark">
                                <tr>
                                    <th>排名</th>
                                    <th>投标人</th>
                                    <th>总分</th>
                                    <th>操作</th>
                                </tr>
                            </thead>
                            <tbody>
        `;

        results.forEach((result, index) => {
            html += `
                <tr>
                    <td>${index + 1}</td>
                    <td>${result.bidder_name || 'N/A'}</td>
                    <td>${result.total_score ? result.total_score.toFixed(2) : 'N/A'}</td>
                    <td>
                        <button class="btn btn-sm btn-outline-primary view-details-btn" data-result='${JSON.stringify(result)}'>
                            <i class="fas fa-eye me-1"></i>查看详情
                        </button>
                    </td>
                </tr>
            `;
        });

        html += `
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;

        resultArea.innerHTML = html;

        // 添加查看详情按钮事件监听器
        document.querySelectorAll('.view-details-btn').forEach(button => {
            button.addEventListener('click', function () {
                const result = JSON.parse(this.getAttribute('data-result'));
                showSimpleResultDetails(result);
            });
        });
    }

    function showSimpleResultDetails (result) {
        const modalHtml = `
            <div class="modal fade" id="simpleResultDetailsModal" tabindex="-1" aria-labelledby="simpleResultDetailsLabel" aria-hidden="true">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="simpleResultDetailsLabel">评标详情 - ${result.bidder_name}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <div class="mb-3">
                                <h6>总分: ${result.total_score ? result.total_score.toFixed(2) : 'N/A'}</h6>
                            </div>
                            <div class="table-responsive">
                                <table class="table table-bordered">
                                    <thead class="table-light">
                                        <tr>
                                            <th>评分项</th>
                                            <th>得分</th>
                                            <th>说明</th>
                                        </tr>
                                    </thead>
                                    <tbody>
        `;

        // 处理详细评分
        const detailedScores = Array.isArray(result.detailed_scores) ? result.detailed_scores : [];
        if (detailedScores.length > 0) {
            detailedScores.forEach(score => {
                modalHtml += `
                    <tr>
                        <td>${score.criteria_name || score.Child_Item_Name || 'N/A'}</td>
                        <td>${score.score ? score.score.toFixed(2) : 'N/A'}</td>
                        <td>${score.reason || 'N/A'}</td>
                    </tr>
                `;
            });
        } else {
            modalHtml += '<tr><td colspan="3">无详细评分数据</td></tr>';
        }

        modalHtml += `
                                    </tbody>
                                </table>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // 添加模态框到页面
        document.body.insertAdjacentHTML('beforeend', modalHtml);

        // 显示模态框
        const modalElement = document.getElementById('simpleResultDetailsModal');
        const modal = new bootstrap.Modal(modalElement);
        modal.show();

        // 模态框关闭后清理
        modalElement.addEventListener('hidden.bs.modal', function () {
            document.body.removeChild(modalElement);
        });
    }

    async function exportToExcel (results, summaryData) {
        try {
            const response = await fetch('/export-results', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ results, summary_data: summaryData })
            });

            if (!response.ok) {
                throw new Error('导出失败');
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `评标结果_${new Date().toISOString().slice(0, 10)}.xlsx`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        } catch (error) {
            console.error('导出Excel失败:', error);
            alert('导出Excel失败: ' + (error.message || error));
        }
    }

    function showResultDetails (results, rules) {
        // 获取第一个结果作为示例数据
        const resultData = results[0];

        // 更新模态框内容
        renderPriceChart(resultData);
        renderDetailedScores(resultData);

        // 显示模态框
        function showModal () {
            if (typeof bootstrap !== 'undefined' && bootstrap.Modal && resultDetailsModal) {
                resultDetailsModal.show();
            } else {
                // 如果Bootstrap还没有加载完成，稍后再尝试
                setTimeout(showModal, 100);
            }
        }

        showModal();
    }

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

    function renderPriceChart (resultData) {
        const ctx = document.getElementById('priceChart');
        if (!ctx) return;

        // 清除之前的图表实例
        if (window.priceChartInstance) {
            window.priceChartInstance.destroy();
        }

        // 准备数据
        const labels = ['基准价', '投标价', '价格分'];
        const data = [
            resultData.benchmark_price || 0,
            resultData.bid_price || 0,
            resultData.price_score || 0
        ];

        // 创建新图表
        window.priceChartInstance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: '价格相关信息',
                    data: data,
                    backgroundColor: [
                        'rgba(54, 162, 235, 0.6)',
                        'rgba(255, 99, 132, 0.6)',
                        'rgba(75, 192, 192, 0.6)'
                    ],
                    borderColor: [
                        'rgba(54, 162, 235, 1)',
                        'rgba(255, 99, 132, 1)',
                        'rgba(75, 192, 192, 1)'
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }

    function renderDetailedScores (resultData) {
        const detailedScoresContainer = document.getElementById('detailedScoresContainer');
        if (!detailedScoresContainer) return;

        // 清空容器
        detailedScoresContainer.innerHTML = '';

        // 处理详细评分数据
        const detailedScores = resultData.detailed_scores || [];
        if (detailedScores.length === 0) {
            detailedScoresContainer.innerHTML = '<p class="text-muted">暂无详细评分数据</p>';
            return;
        }

        // 创建评分项卡片
        detailedScores.forEach(score => {
            const card = document.createElement('div');
            card.className = 'col-md-6 mb-3';
            card.innerHTML = `
                <div class="card h-100">
                    <div class="card-body">
                        <h6 class="card-title">${score.criteria_name || score.Child_Item_Name || '未知评分项'}</h6>
                        <p class="card-text">
                            <strong>得分:</strong> ${score.score ? score.score.toFixed(2) : 'N/A'}<br>
                            <strong>说明:</strong> ${score.reason || '无说明'}
                        </p>
                    </div>
                </div>
            `;
            detailedScoresContainer.appendChild(card);
        });
    }
});
