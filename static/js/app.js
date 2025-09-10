// DOM Elements
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const tenderFilesList = document.getElementById('tenderFiles');
const bidFilesList = document.getElementById('bidFiles');
const startAnalysisBtn = document.getElementById('startAnalysis');
const progressStatus = document.getElementById('progressStatus');
const progressBars = document.getElementById('progressBars');
const resultsDiv = document.getElementById('results');
const detailsModal = new bootstrap.Modal(document.getElementById('detailsModal'));
const detailsModalBody = document.getElementById('detailsModalBody');

// State Management
let tenderFile = null;
let bidFiles = [];
let projectId = null;
let pollingInterval = null;

// Prevent browser default file handling
window.addEventListener('dragover', e => e.preventDefault());
window.addEventListener('drop', e => e.preventDefault());

// File Upload Event Handlers
uploadArea.addEventListener('dragover', e => {
    e.preventDefault();
    uploadArea.style.borderColor = '#0d6efd';
});

uploadArea.addEventListener('dragleave', e => {
    e.preventDefault();
    uploadArea.style.borderColor = '#ccc';
});

uploadArea.addEventListener('drop', e => {
    e.preventDefault();
    uploadArea.style.borderColor = '#ccc';
    handleFiles(e.dataTransfer.files);
});

fileInput.addEventListener('change', e => {
    handleFiles(e.target.files);
});

// File Handling
function handleFiles (files) {
    const fileType = document.querySelector('input[name="fileType"]:checked').value;
    for (const file of files) {
        if (fileType === 'tender') {
            tenderFile = file;
            tenderFilesList.innerHTML = `
                <li class="list-group-item d-flex justify-content-between align-items-center">
                    ${file.name}
                    <span class="badge bg-primary rounded-pill">${formatFileSize(file.size)}</span>
                </li>`;
        } else {
            bidFiles.push(file);
            const listItem = document.createElement('li');
            listItem.className = 'list-group-item d-flex justify-content-between align-items-center';
            listItem.innerHTML = `
                ${file.name}
                <span class="badge bg-success rounded-pill">${formatFileSize(file.size)}</span>
            `;
            bidFilesList.appendChild(listItem);
        }
    }
    fileInput.value = '';
}

// Utility Functions
function formatFileSize (bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Analysis Control
startAnalysisBtn.addEventListener('click', async () => {
    if (!tenderFile || bidFiles.length === 0) {
        alert('请至少选择一个招标文件和一个投标文件');
        return;
    }

    startAnalysisBtn.disabled = true;
    updateStatus('正在上传文件并初始化分析...', 'info');
    clearResults();

    const formData = new FormData();
    formData.append('tender_file', tenderFile);
    bidFiles.forEach(file => formData.append('bid_files', file));

    try {
        const response = await fetch('/api/analyze-immediately', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const data = await response.json();
            projectId = data.project_id;
            startProgressPolling();
        } else {
            const errorText = await response.text();
            updateStatus(`启动分析时出错: ${errorText}`, 'danger');
            startAnalysisBtn.disabled = false;
        }
    } catch (error) {
        // 检查是否为浏览器扩展引起的错误
        if (error.message.includes('message channel closed')) {
            console.warn('可能由浏览器扩展引起的连接错误，这通常不会影响功能:', error);
            // 继续执行，因为这类错误通常不会影响实际功能
            return;
        }
        
        updateStatus(`错误: ${error.message}`, 'danger');
        startAnalysisBtn.disabled = false;
    }
});

// Progress Polling
function startProgressPolling () {
    // Clear any existing polling interval
    if (pollingInterval) {
        clearInterval(pollingInterval);
    }

    // Start polling for progress updates
    pollingInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/projects/${projectId}/analysis-status`);
            if (response.ok) {
                const data = await response.json();
                updateProgressDisplay(data);

                // Check if project is completed
                if (data.project_status === 'completed' || data.project_status === 'completed_with_errors') {
                    clearInterval(pollingInterval);
                    startAnalysisBtn.disabled = false;
                    fetchResults();
                }
            } else {
                console.error('获取进度时出错:', response.status);
            }
        } catch (error) {
            console.error('轮询进度时出错:', error);
        }
    }, 2000); // Poll every 2 seconds
}

function updateProgressDisplay (data) {
    // Update overall status
    let statusClass = 'info';
    let statusMessage = '';

    switch (data.project_status) {
        case 'processing':
            statusMessage = '正在进行分析...';
            break;
        case 'completed':
            statusClass = 'success';
            statusMessage = '分析已完成！';
            break;
        case 'completed_with_errors':
            statusClass = 'warning';
            statusMessage = '分析完成，但有一些错误。';
            break;
        default:
            statusMessage = `状态: ${data.project_status}`;
    }

    updateStatus(statusMessage, statusClass);

    // Update individual progress bars
    progressBars.innerHTML = '';
    if (data.bids) {
        data.bids.forEach(bid => {
            const progress = bid.progress_total > 0
                ? (bid.progress_completed / bid.progress_total * 100).toFixed(1)
                : 0;

            const progressBar = document.createElement('div');
            progressBar.className = 'mb-3';
            progressBar.innerHTML = `
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <span>${bid.bidder_name}</span>
                    <span>${progress}%</span>
                </div>
                <div class="progress" style="height: 20px;">
                    <div class="progress-bar ${getProgressBarClass(bid.status)}" 
                         role="progressbar" 
                         style="width: ${progress}%"
                         aria-valuenow="${progress}" 
                         aria-valuemin="0" 
                         aria-valuemax="100">
                        ${bid.current_rule || ''}
                    </div>
                </div>
                ${bid.error_message ? `
                    <div class="alert alert-danger mt-1 mb-0 py-1 small">
                        ${bid.error_message}
                        ${bid.error_message.includes('处理失败') ? `<button class="btn btn-sm btn-outline-primary ms-2" onclick="showFailedPages('${bid.bidder_name}', ${bid.id})">查看失败页面</button>` : ''}
                    </div>
                ` : ''}
            `;
            progressBars.appendChild(progressBar);
        });
    }
}

function getProgressBarClass (status) {
    switch (status) {
        case 'completed': return 'bg-success';
        case 'error': return 'bg-danger';
        case 'processing': return 'progress-bar-striped progress-bar-animated';
        default: return 'bg-secondary';
    }
}

// Results Handling
async function fetchResults () {
    try {
        const response = await fetch(`/api/projects/${projectId}/results`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const results = await response.json();
        displayResults(results);
    } catch (error) {
        updateStatus(`获取结果时出错: ${error.message}`, 'danger');
    }
}

function displayResults (results) {
    if (!results || results.length === 0) {
        resultsDiv.innerHTML = '<div class="alert alert-info">暂无分析结果</div>';
        return;
    }

    const modelInfo = results[0].ai_model || '未知模型';
    results.sort((a, b) => b.total_score - a.total_score);

    resultsDiv.innerHTML = `
        <div class="alert alert-info mb-3">使用的AI模型: ${modelInfo}</div>
        <div class="table-responsive">
            <table class="table table-striped table-hover">
                <thead class="table-dark">
                    <tr>
                        <th>排名</th>
                        <th>投标人</th>
                        <th>总分</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>
                    ${results.map((result, index) => `
                        <tr>
                            <td>${index + 1}</td>
                            <td>${result.bidder_name}</td>
                            <td>${result.total_score.toFixed(2)}</td>
                            <td>
                                <button class="btn btn-sm btn-info" 
                                        onclick='showDetails(${JSON.stringify(result.detailed_scores)})'>
                                    查看详情
                                </button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
}

function showDetails (details) {
    if (typeof details === 'string') {
        details = JSON.parse(details);
    }

    detailsModalBody.innerHTML = details.map(item => `
        <tr>
            <td>${item.criteria_name}</td>
            <td>${item.score.toFixed(2)}</td>
            <td>${item.max_score}</td>
            <td>${item.reason}</td>
        </tr>
    `).join('');

    detailsModal.show();
}

// Show failed pages information
async function showFailedPages (bidderName, bidId) {
    try {
        // Get project ID from global variable
        if (!projectId) {
            alert('项目ID未找到');
            return;
        }

        const response = await fetch(`/api/projects/${projectId}/bid-documents/${bidId}/failed-pages`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const failedPagesData = await response.json();

        // Display the failed pages data in a modal
        displayFailedPages(bidderName, failedPagesData);
    } catch (error) {
        console.error('获取失败页面信息时出错:', error);
        alert(`获取失败页面信息时出错: ${error.message}`);
    }
}

function displayFailedPages (bidderName, failedPagesData) {
    // Create modal content
    let modalContent = `
        <div class="modal-header">
            <h5 class="modal-title">${bidderName} - PDF处理失败页面详情</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
        </div>
        <div class="modal-body">
            <p>共 ${failedPagesData.length} 个页面处理失败：</p>
            <div class="table-responsive">
                <table class="table table-striped">
                    <thead>
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

    // Create or update modal
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

    // Show modal
    const modal = new bootstrap.Modal(modalElement);
    modal.show();
}

// Utility Functions
function updateStatus (message, type = 'info') {
    progressStatus.style.display = 'block';
    progressStatus.className = `alert alert-${type}`;
    progressStatus.textContent = message;
}

function clearResults () {
    resultsDiv.innerHTML = '';
    progressBars.innerHTML = '';
}
