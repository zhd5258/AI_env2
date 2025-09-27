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
    const resultDetailsModalElement = document.getElementById('resultDetailsModal');
    const resultDetailsModal = resultDetailsModalElement ? new bootstrap.Modal(resultDetailsModalElement) : null;
    const modalBody = document.getElementById('modalBody');
    const btnOpenSettings = document.getElementById('btnOpenSettings');
    // 修复模态框ID不匹配的问题,统一使用settingsModal元素并创建单一实例
    const settingsModalElement = document.getElementById('settingsModal');
    const settingsModal = settingsModalElement ? new bootstrap.Modal(settingsModalElement) : null;
    const cfgWorkers = document.getElementById('pdfPageMaxWorkers');
    const cfgPageTimeout = document.getElementById('pdfPageTimeoutSec');
    const cfgOverallMinTimeout = document.getElementById('pdfOverallMinTimeoutSec');
    const cfgAiAnalysisPageLimit = document.getElementById('aiAnalysisPageLimit');
    const cfgUseGpu = document.getElementById('useGpu');
    const btnSaveConfig = document.getElementById('saveSettings');
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
    if (btnOpenSettings && settingsModal) {
        btnOpenSettings.addEventListener('click', async () => {
            await loadRuntimeConfig();
            settingsModal.show();
        });
    }

    // 添加模态框隐藏事件监听器，确保正确清理背景
    if (settingsModalElement) {
        settingsModalElement.addEventListener('hidden.bs.modal', function () {
            // 清理modal-open类和backdrop元素
            document.body.classList.remove('modal-open');
            const backdrops = document.querySelectorAll('.modal-backdrop');
            backdrops.forEach(backdrop => backdrop.remove());
        });
    }

    async function loadRuntimeConfig () {
        try {
            // 优先按项目读取项目级默认；没有项目时回退全局默认
            let cfg = null;
            if (currentProjectId) {
                const projResp = await fetch(`/api/projects/${currentProjectId}/runtime-config`);
                if (projResp.ok) cfg = await projResp.json();
            }
            if (!cfg) {
                const resp = await fetch('/api/runtime-config');
                if (!resp.ok) throw new Error(`HTTP error! status: ${resp.status}`);
                cfg = await resp.json();
            }
            cfgWorkers.value = cfg.pdf_page_max_workers ?? '';
            cfgPageTimeout.value = cfg.pdf_page_timeout_sec ?? '';
            cfgOverallMinTimeout.value = cfg.pdf_overall_min_timeout_sec ?? '';
            cfgAiAnalysisPageLimit.value = cfg.ai_analysis_page_limit ?? '';
            // 加载OCR配置
            const ocrResp = await fetch('/api/ocr-config');
            if (ocrResp.ok) {
                const ocrCfg = await ocrResp.json();
                cfgUseGpu.checked = ocrCfg.use_gpu ?? false;
            }
            cfgFeedback.textContent = '';
        } catch (e) {
            console.error('加载配置失败:', e);
            cfgFeedback.textContent = '加载当前配置失败: ' + (e.message || e);
        }
    }

    // 将loadRuntimeConfig函数暴露到全局作用域，供其他脚本调用
    window.loadRuntimeConfig = loadRuntimeConfig;

    function numOrNull (v) {
        const n = parseInt(v, 10);
        return Number.isFinite(n) ? n : null;
    }

    if (btnSaveConfig) {
        btnSaveConfig.addEventListener('click', async () => {
            try {
                const payload = {
                    pdf_page_max_workers: numOrNull(cfgWorkers ? cfgWorkers.value : ''),
                    pdf_page_timeout_sec: numOrNull(cfgPageTimeout ? cfgPageTimeout.value : ''),
                    pdf_overall_min_timeout_sec: numOrNull(cfgOverallMinTimeout ? cfgOverallMinTimeout.value : ''),
                    ai_analysis_page_limit: numOrNull(cfgAiAnalysisPageLimit ? cfgAiAnalysisPageLimit.value : '')
                };
                // 保存到项目级别（若已创建项目），否则保存为全局默认
                const url = currentProjectId ? `/api/projects/${currentProjectId}/runtime-config` : '/api/runtime-config';
                const resp = await fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (!resp.ok) throw new Error('保存失败');
                const saved = await resp.json();

                // 保存OCR配置
                const ocrPayload = {
                    use_gpu: cfgUseGpu ? cfgUseGpu.checked : false
                };
                const ocrResp = await fetch('/api/ocr-config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(ocrPayload)
                });
                if (!ocrResp.ok) throw new Error('保存OCR配置失败');

                cfgFeedback.textContent = '保存成功';
                setTimeout(() => {
                    if (settingsModal) {
                        settingsModal.hide();
                        // 注意：背景清理工作已通过hidden.bs.modal事件监听器处理
                        // 清除配置反馈信息
                        cfgFeedback.textContent = '';
                        // 重置表单
                        if (document.getElementById('settingsForm')) {
                            document.getElementById('settingsForm').reset();
                        }
                    }
                }, 800);
            } catch (e) {
                cfgFeedback.textContent = '保存失败：' + (e.message || e);
            }
        });
    }

    function updateFileList () {
        if (!uploadedFiles.tender && uploadedFiles.bids.length === 0) {
            if (fileList) fileList.innerHTML = '<div class="text-muted"><i class="fas fa-info-circle me-2"></i>尚未选择任何文件</div>';
            return;
        }

        let html = '<h5 class="mb-3"><i class="fas fa-file-alt me-2"></i>已选择的文件：</h5>';
        
        // 如果有投标文件，添加批量操作工具栏
        if (uploadedFiles.bids.length > 0) {
            html += `
                <div class="batch-operations mb-3">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <label class="form-check-label">
                                <input type="checkbox" id="selectAllBids" class="form-check-input me-2">
                                全选投标文件
                            </label>
                        </div>
                        <div>
                            <button type="button" class="btn btn-outline-danger btn-sm" id="deleteSelectedBids" disabled>
                                <i class="fas fa-trash-alt me-1"></i>删除选中文件
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }
        
        html += '<div class="row">';
        if (uploadedFiles.tender) {
            html += createFileListItem(uploadedFiles.tender, '招标文件', 'primary', false);
        }
        uploadedFiles.bids.forEach((file, index) => {
            html += createFileListItem(file, `投标文件 #${index + 1}`, 'info', true, index);
        });
        html += '</div>';
        if (fileList) fileList.innerHTML = html;
        
        // 添加事件监听器
        setupBatchOperationListeners();
    }

    function createFileListItem (file, title, color, showCheckbox = false, fileIndex = null) {
        const checkboxHtml = showCheckbox ? 
            `<div class="form-check me-3">
                <input class="form-check-input bid-file-checkbox" type="checkbox" 
                       data-file-index="${fileIndex}" id="bidFile${fileIndex}">
            </div>` : '';
        
        return `
            <div class="col-md-6 mb-2">
                <div class="card border-start border-4 border-${color} h-100">
                    <div class="card-body">
                        <div class="d-flex align-items-start">
                            ${checkboxHtml}
                            <div class="flex-grow-1">
                                <h6 class="card-title text-${color}">
                                    <i class="fas fa-file-pdf me-2"></i>${title}
                                </h6>
                                <p class="card-text mb-1">${file.name}</p>
                                <small class="text-muted">${(file.size / 1024 / 1024).toFixed(2)} MB</small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    function setupBatchOperationListeners() {
        // 全选/取消全选
        const selectAllCheckbox = document.getElementById('selectAllBids');
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', function() {
                const bidCheckboxes = document.querySelectorAll('.bid-file-checkbox');
                bidCheckboxes.forEach(checkbox => {
                    checkbox.checked = this.checked;
                });
                updateDeleteButtonState();
            });
        }

        // 单个文件选择框变化
        const bidCheckboxes = document.querySelectorAll('.bid-file-checkbox');
        bidCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', function() {
                updateSelectAllState();
                updateDeleteButtonState();
            });
        });

        // 删除选中文件按钮
        const deleteButton = document.getElementById('deleteSelectedBids');
        if (deleteButton) {
            deleteButton.addEventListener('click', function() {
                const selectedIndexes = getSelectedFileIndexes();
                if (selectedIndexes.length > 0) {
                    const fileNames = selectedIndexes.map(index => uploadedFiles.bids[index].name).join('\n');
                    if (confirm(`确定要删除以下 ${selectedIndexes.length} 个文件吗？\n\n${fileNames}`)) {
                        deleteSelectedFiles(selectedIndexes);
                    }
                }
            });
        }
    }

    function updateSelectAllState() {
        const selectAllCheckbox = document.getElementById('selectAllBids');
        const bidCheckboxes = document.querySelectorAll('.bid-file-checkbox');
        
        if (selectAllCheckbox && bidCheckboxes.length > 0) {
            const checkedCount = Array.from(bidCheckboxes).filter(cb => cb.checked).length;
            selectAllCheckbox.checked = checkedCount === bidCheckboxes.length;
            selectAllCheckbox.indeterminate = checkedCount > 0 && checkedCount < bidCheckboxes.length;
        }
    }

    function updateDeleteButtonState() {
        const deleteButton = document.getElementById('deleteSelectedBids');
        const selectedCount = getSelectedFileIndexes().length;
        
        if (deleteButton) {
            deleteButton.disabled = selectedCount === 0;
            deleteButton.innerHTML = selectedCount > 0 ? 
                `<i class="fas fa-trash-alt me-1"></i>删除选中文件 (${selectedCount})` :
                '<i class="fas fa-trash-alt me-1"></i>删除选中文件';
        }
    }

    function getSelectedFileIndexes() {
        const selectedIndexes = [];
        const bidCheckboxes = document.querySelectorAll('.bid-file-checkbox:checked');
        bidCheckboxes.forEach(checkbox => {
            const index = parseInt(checkbox.getAttribute('data-file-index'));
            selectedIndexes.push(index);
        });
        return selectedIndexes.sort((a, b) => b - a); // 逆序，从后往前删除
    }

    function deleteSelectedFiles(selectedIndexes) {
        try {
            // 从后往前删除，避免索引混乱
            selectedIndexes.forEach(index => {
                if (index >= 0 && index < uploadedFiles.bids.length) {
                    uploadedFiles.bids.splice(index, 1);
                }
            });

            // 更新文件输入框（清空并重新设置剩余文件）
            const bidFilesInput = document.getElementById('bidFiles');
            if (bidFilesInput) {
                const dt = new DataTransfer();
                uploadedFiles.bids.forEach(file => {
                    dt.items.add(file);
                });
                bidFilesInput.files = dt.files;
            }

            // 更新文件列表显示
            updateFileList();

            // 显示成功消息
            const deletedCount = selectedIndexes.length;
            showNotification(`成功删除 ${deletedCount} 个投标文件`, 'success');

        } catch (error) {
            console.error('删除文件失败:', error);
            showNotification('删除文件失败: ' + error.message, 'error');
        }
    }

    function showNotification(message, type = 'info') {
        // 创建通知元素
        const notification = document.createElement('div');
        notification.className = `alert alert-${type === 'success' ? 'success' : type === 'error' ? 'danger' : 'info'} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 1050; min-width: 300px;';
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        document.body.appendChild(notification);

        // 3秒后自动移除
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 3000);
    }

    async function startAnalysis () {
        if (progressContainer) progressContainer.style.display = 'block';
        if (progressBar) progressBar.style.width = '0%';
        if (progressText) progressText.innerHTML = '<i class="fas fa-upload me-2"></i>正在上传文件...';
        if (detailedProgress) detailedProgress.innerHTML = '';
        if (resultArea) resultArea.innerHTML = '';

        const formData = new FormData();
        // 将文件添加到files字段中，以匹配后端init_upload接口的要求
        formData.append('files', uploadedFiles.tender);
        uploadedFiles.bids.forEach(file => formData.append('files', file));

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
            progressText.innerHTML = '<i class="fas fa-sync-alt fa-spin me-2"></i>正在启动分析...';

            // 直接以文件名作为投标方名称，立即启动分析
            const bidders = (initData.bidder_info || []).map(b => ({ id: b.id, confirmed_name: b.bidder_name }));
            const startResp = await fetch(`/api/projects/${currentProjectId}/start-analysis`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                // 修复：根据API要求，需要发送包含bidders字段的对象，并且字段名应为name而不是confirmed_name
                body: JSON.stringify({
                    bidders: bidders.map(b => ({
                        id: b.id,
                        name: b.confirmed_name
                    }))
                })
            });
            if (!startResp.ok) {
                const errorText = await startResp.text();
                throw new Error(`启动分析失败: ${startResp.status} ${startResp.statusText}\n${errorText}`);
            }

            // 启动轮询
            startPolling(currentProjectId);

        } catch (error) {
            console.error('初始化上传失败:', error);
            progressText.innerHTML = `<div class="alert alert-danger mb-0"><i class="fas fa-exclamation-circle me-2"></i>上传失败: ${error.message}</div>`;
        }
    }
    // 取消上传前的确认弹窗流程，改为分析完成后再确认名称

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

                // 弹出确认窗口，让用户确认投标人名称（分析完成后）
                await showConfirmBidderNamesModal(projectId);

                // 询问是否删除临时文件 - 暂时注释掉以便检查文本提取结果
                // await askToDeleteTempFiles(projectId);

                // 确认后显示结果
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

    async function showConfirmBidderNamesModal (projectId) {
        try {
            // 获取项目下的所有投标人信息
            const response = await fetch(`/api/projects/${projectId}/bidders`);
            if (!response.ok) {
                throw new Error(`获取投标人信息失败: ${response.statusText}`);
            }

            const bidders = await response.json();

            // 创建模态框HTML
            const modalHtml = `
            <div class="modal fade" id="confirmBidderNamesModal" tabindex="-1" aria-labelledby="confirmBidderNamesLabel">
              <div class="modal-dialog modal-lg">
                <div class="modal-content">
                  <div class="modal-header">
                    <h5 class="modal-title" id="confirmBidderNamesLabel">确认投标人名称</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                  </div>
                  <div class="modal-body">
                    <p>请确认以下投标人名称是否正确，如有需要可进行修改：</p>
                    <form id="bidderNamesForm">
                      ${bidders.map(bidder => `
                        <div class="mb-3">
                          <label for="bidderName${bidder.id}" class="form-label">${bidder.original_filename || '投标文件'}</label>
                          <input type="text" class="form-control" id="bidderName${bidder.id}" name="bidderName${bidder.id}" value="${bidder.bidder_name}" data-bidder-id="${bidder.id}">
                        </div>
                      `).join('')}
                    </form>
                  </div>
                  <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="button" class="btn btn-primary" id="saveBidderNamesBtn">保存并继续</button>
                  </div>
                </div>
              </div>
            </div>
            `;

            // 添加模态框到页面
            const modalElement = document.createElement('div');
            modalElement.innerHTML = modalHtml;
            document.body.appendChild(modalElement);

            // 显示模态框
            const modal = new bootstrap.Modal(document.getElementById('confirmBidderNamesModal'));
            modal.show();

            // 等待用户操作
            return new Promise((resolve) => {
                document.getElementById('saveBidderNamesBtn').addEventListener('click', async () => {
                    // 收集修改后的投标人名称
                    const formData = new FormData(document.getElementById('bidderNamesForm'));
                    const bidderUpdates = [];

                    bidders.forEach(bidder => {
                        const input = document.getElementById(`bidderName${bidder.id}`);
                        if (input && input.value !== bidder.bidder_name) {
                            bidderUpdates.push({
                                id: bidder.id,
                                confirmed_name: input.value
                            });
                        }
                    });

                    // 如果有修改，发送更新请求
                    if (bidderUpdates.length > 0) {
                        try {
                            // 逐个PATCH更新，不重新启动分析
                            for (const upd of bidderUpdates) {
                                const resp = await fetch(`/api/bids/${upd.id}/name`, {
                                    method: 'PATCH',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ new_name: upd.confirmed_name })
                                });
                                if (!resp.ok) {
                                    const errText = await resp.text();
                                    throw new Error(`更新投标人名称失败: ${resp.status} ${resp.statusText}\n${errText}`);
                                }
                            }
                            console.log('投标人名称批量更新成功');
                        } catch (error) {
                            console.error('更新投标人名称时出错:', error);
                            alert('更新投标人名称失败: ' + (error.message || error));
                        }
                    }

                    // 关闭模态框
                    modal.hide();
                    document.body.removeChild(modalElement);
                    resolve();
                });

                // 监听模态框关闭事件
                document.getElementById('confirmBidderNamesModal').addEventListener('hidden.bs.modal', function () {
                    document.body.removeChild(modalElement);
                    resolve();
                });
            });
        } catch (error) {
            console.error('显示确认投标人名称模态框时出错:', error);
        }
    }

    async function askToDeleteTempFiles (projectId) {
        // 创建确认删除临时文件的模态框
        const modalHtml = `
        <div class="modal fade" id="deleteTempFilesModal" tabindex="-1" aria-labelledby="deleteTempFilesLabel">
          <div class="modal-dialog">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title" id="deleteTempFilesLabel">删除临时文件</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
              </div>
              <div class="modal-body">
                <p>项目分析已完成。是否要删除上传的临时文件和生成的中间文件？</p>
                <div class="form-check">
                  <input class="form-check-input" type="checkbox" id="deleteUploads" checked>
                  <label class="form-check-label" for="deleteUploads">
                    删除上传的临时文件 (temp_uploads目录)
                  </label>
                </div>
                <div class="form-check">
                  <input class="form-check-input" type="checkbox" id="deleteCache" checked>
                  <label class="form-check-label" for="deleteCache">
                    删除生成的中间文件 (temp_pdf_cache目录)
                  </label>
                </div>
                <div class="form-check">
                  <input class="form-check-input" type="checkbox" id="deleteTempWord" checked>
                  <label class="form-check-label" for="deleteTempWord">
                    删除生成的文本文件 (temp_word目录)
                  </label>
                </div>
              </div>
              <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                <button type="button" class="btn btn-primary" id="confirmDeleteBtn">确认删除</button>
              </div>
            </div>
          </div>
        </div>
        `;

        // 添加模态框到页面
        const modalElement = document.createElement('div');
        modalElement.innerHTML = modalHtml;
        document.body.appendChild(modalElement);

        // 显示模态框
        const modal = new bootstrap.Modal(document.getElementById('deleteTempFilesModal'));
        modal.show();

        // 等待用户操作
        return new Promise((resolve) => {
            document.getElementById('confirmDeleteBtn').addEventListener('click', async () => {
                // 获取用户选择
                const deleteUploads = document.getElementById('deleteUploads').checked;
                const deleteCache = document.getElementById('deleteCache').checked;
                const deleteTempWord = document.getElementById('deleteTempWord').checked;

                // 发送删除请求
                try {
                    const response = await fetch(`/api/projects/${projectId}/cleanup`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            delete_uploads: deleteUploads,
                            delete_cache: deleteCache,
                            delete_temp_word: deleteTempWord
                        })
                    });

                    if (!response.ok) {
                        throw new Error(`清理临时文件失败: ${response.statusText}`);
                    }

                    console.log('临时文件清理完成');
                } catch (error) {
                    console.error('清理临时文件时出错:', error);
                    // 不中断流程，只是记录错误
                }

                // 关闭模态框
                modal.hide();
                document.body.removeChild(modalElement);
                resolve();
            });

            // 监听模态框关闭事件
            document.getElementById('deleteTempFilesModal').addEventListener('hidden.bs.modal', function () {
                document.body.removeChild(modalElement);
                resolve();
            });
        });
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

                // 绑定编辑按钮事件
                document.querySelectorAll('.edit-bidder-name').forEach(button => {
                    button.addEventListener('click', function () {
                        const bidId = this.getAttribute('data-bid');
                        const currentName = this.getAttribute('data-current-name');
                        showEditBidderNameModal(bidId, currentName);
                    });
                });
            })
            .catch(error => {
                console.error('获取动态汇总表数据失败:', error);
                resultArea.innerHTML = `<div class="alert alert-danger">获取动态汇总表数据失败: ${error.message}</div>`;
            });
    }

    function displaySimpleResults (results) {
        let html = '<div class="card"><div class="card-body"><h3 class="card-title">分析结果</h3><div class="table-responsive">';
        html += '<table class="table table-bordered table-hover"><thead class="table-light">';
        html += '<tr><th>排名</th><th>投标人</th><th>总得分</th><th>操作</th></tr></thead><tbody>';

        results.forEach((result, index) => {
            html += `<tr>
                <td>${index + 1}</td>
                <td>${result.bidder_name || 'N/A'}</td>
                <td>${result.total_score ? result.total_score.toFixed(2) : 'N/A'}</td>
                <td>
                    <button class="btn btn-sm btn-primary view-details" data-bid="${result.id}">
                        <i class="fas fa-eye"></i> 查看详情
                    </button>
                </td>
            </tr>`;
        });

        html += '</tbody></table></div></div></div>';
        resultArea.innerHTML = html;

        // 绑定查看详情按钮事件
        document.querySelectorAll('.view-details').forEach(button => {
            button.addEventListener('click', function () {
                const bidId = this.getAttribute('data-bid');
                showResultDetails(bidId);
            });
        });
    }

    async function showResultDetails (bidId) {
        try {
            const response = await fetch(`/api/bids/${bidId}/result`);
            if (!response.ok) {
                throw new Error(`获取详情失败: ${response.statusText}`);
            }

            const result = await response.json();
            displayResultDetails(result);
            if (resultDetailsModal) {
                resultDetailsModal.show();
            }
        } catch (error) {
            console.error('获取详情时出错:', error);
            alert('获取详情失败: ' + error.message);
        }
    }

    function displayResultDetails (result) {
        if (!modalBody) return;

        let html = '<h4>投标人: ' + (result.bidder_name || 'N/A') + '</h4>';
        html += '<h5>总得分: ' + (result.total_score ? result.total_score.toFixed(2) : 'N/A') + '</h5>';

        if (result.detailed_scores && Array.isArray(result.detailed_scores)) {
            html += '<h5>详细评分</h5>';
            html += '<div class="table-responsive"><table class="table table-bordered">';
            html += '<thead class="table-light"><tr><th>评分项</th><th>满分</th><th>得分</th><th>评分说明</th></tr></thead><tbody>';

            result.detailed_scores.forEach(score => {
                html += `<tr>
                    <td>${score.criteria_name || 'N/A'}</td>
                    <td>${score.max_score || 'N/A'}</td>
                    <td>${score.score ? score.score.toFixed(2) : 'N/A'}</td>
                    <td>${score.reason || 'N/A'}</td>
                </tr>`;
            });

            html += '</tbody></table></div>';
        }

        modalBody.innerHTML = html;
    }

    async function showEditBidderNameModal (bidId, currentName) {
        const modalHtml = `
        <div class="modal fade" id="editBidderNameModal" tabindex="-1" aria-labelledby="editBidderNameLabel">
          <div class="modal-dialog">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title" id="editBidderNameLabel">编辑投标人名称</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
              </div>
              <div class="modal-body">
                <form id="editBidderNameForm">
                  <div class="mb-3">
                    <label for="editBidderNameInput" class="form-label">投标人名称</label>
                    <input type="text" class="form-control" id="editBidderNameInput" required>
                    <input type="hidden" id="editBidderId">
                  </div>
                </form>
              </div>
              <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                <button type="button" class="btn btn-primary" id="saveEditBidderNameBtn">保存</button>
              </div>
            </div>
          </div>
        </div>
        `;

        // 添加模态框到页面
        const modalElement = document.createElement('div');
        modalElement.innerHTML = modalHtml;
        document.body.appendChild(modalElement);

        // 显示模态框
        const modal = new bootstrap.Modal(document.getElementById('editBidderNameModal'));
        modal.show();

        // 监听保存按钮点击事件
        document.getElementById('saveEditBidderNameBtn').addEventListener('click', async () => {
            const newName = document.getElementById('editBidderNameInput').value.trim();
            if (!newName) {
                alert('请输入新的投标方名称');
                return;
            }

            try {
                const response = await fetch(`/api/bids/${bidId}/name`, {
                    method: 'PATCH',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ new_name: newName })
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || '更新失败');
                }

                const result = await response.json();
                console.log('投标方名称更新成功:', result);

                // 更新页面上的显示
                const nameElement = document.querySelector(`.edit-bidder-name[data-bid="${bidId}"]`).previousElementSibling;
                if (nameElement) {
                    nameElement.textContent = newName.length > 5 ? newName.substring(0, 5) + '...' : newName;
                    nameElement.title = newName;
                }

                // 关闭模态框
                modal.hide();
                document.body.removeChild(modalElement);

                alert('投标方名称更新成功');
            } catch (error) {
                console.error('更新投标方名称时出错:', error);
                alert('更新失败: ' + error.message);
            }
        });

        // 监听模态框关闭事件
        document.getElementById('editBidderNameModal').addEventListener('hidden.bs.modal', function () {
            document.body.removeChild(modalElement);
        });
    }

    // 导出到Excel功能
    window.exportToExcel = async function (projectId) {
        try {
            const response = await fetch(`/api/projects/${projectId}/export-excel`, {
                method: 'GET',
            });

            if (!response.ok) {
                throw new Error(`导出失败: ${response.statusText}`);
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `评标结果_${projectId}.xlsx`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (error) {
            console.error('导出Excel时出错:', error);
            alert('导出失败: ' + error.message);
        }
    };

    // 导出到Word功能
    window.exportToWord = async function (projectId) {
        try {
            const response = await fetch(`/api/projects/${projectId}/export-word`, {
                method: 'GET',
            });

            if (!response.ok) {
                throw new Error(`导出失败: ${response.statusText}`);
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `评标结果_${projectId}.docx`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (error) {
            console.error('导出Word时出错:', error);
            alert('导出失败: ' + error.message);
        }
    };
});
