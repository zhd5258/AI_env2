// 全局变量
let currentProjectId = null;
let pollingActive = false;
let progressInterval = null;
let lastProgressData = null; // 保存最后一次进度数据
let selectedTenderFile = null;
let selectedBidFiles = [];
let startTime = null;

// 页面加载时获取轮询间隔配置
async function loadPollingConfig () {
    try {
        const response = await fetch('/api/runtime-config');
        if (response.ok) {
            const config = await response.json();
            window.pollingIntervalSec = config.polling_interval_sec || 3;
            console.log('轮询间隔配置已加载:', window.pollingIntervalSec + '秒');
        } else {
            console.warn('获取轮询配置失败，使用默认值3秒');
            window.pollingIntervalSec = 3;
        }
    } catch (error) {
        console.error('获取轮询配置出错:', error);
        window.pollingIntervalSec = 3;
    }
}

// 从localStorage恢复项目ID（如果存在）
function restoreProjectId () {
    const savedProjectId = localStorage.getItem('currentProjectId');
    if (savedProjectId) {
        currentProjectId = parseInt(savedProjectId);
        console.log('恢复项目ID:', currentProjectId);
    }
}

// 保存项目ID到localStorage
function saveProjectId (projectId) {
    localStorage.setItem('currentProjectId', projectId.toString());
}

// 清除保存的项目ID
function clearProjectId () {
    localStorage.removeItem('currentProjectId');
}

// 更新文件列表显示
function updateFileList () {
    const fileList = document.getElementById('fileList');
    if (!fileList) return;

    let html = '<ul>';

    if (selectedTenderFile) {
        html += `<li><strong>招标文件:</strong> ${selectedTenderFile.name}</li>`;
    }

    if (selectedBidFiles.length > 0) {
        html += '<li><strong>投标文件:</strong><ul>';
        selectedBidFiles.forEach(file => {
            html += `<li>${file.name}</li>`;
        });
        html += '</ul></li>';
    }

    html += '</ul>';
    fileList.innerHTML = html;
}

// 清除之前的结果显示
function clearPreviousResults () {
    // 隐藏结果区域
    const resultDiv = document.getElementById('result');
    if (resultDiv) {
        resultDiv.style.display = 'none';
        resultDiv.innerHTML = ''; // 清空结果内容
        resultDiv.className = 'result'; // 重置类名
    }

    // 隐藏进度区域
    const progressSection = document.getElementById('progressSection');
    if (progressSection) {
        progressSection.style.display = 'none';
    }

    // 显示上传表单
    const uploadSection = document.querySelector('.upload-section');
    if (uploadSection) {
        uploadSection.style.display = 'block';
    }

    // 清除保存的项目ID
    clearProjectId();

    // 停止任何正在进行的轮询
    stopProgressPolling();

    // 重置项目ID变量
    currentProjectId = null;

    // 清除项目ID显示
    const projectIdElement = document.getElementById('projectId');
    if (projectIdElement) {
        projectIdElement.textContent = '-';
    }
}

// 文件选择事件处理
document.addEventListener('DOMContentLoaded', function () {
    // 加载轮询配置
    loadPollingConfig();

    const tenderFileInput = document.getElementById('tender_file');
    const bidFilesInput = document.getElementById('bid_files');

    if (tenderFileInput) {
        tenderFileInput.addEventListener('change', function (e) {
            selectedTenderFile = e.target.files[0];
            updateFileList();
            clearPreviousResults();
        });
    }

    if (bidFilesInput) {
        bidFilesInput.addEventListener('change', function (e) {
            selectedBidFiles = [];
            if (e.target.files.length > 0) {
                for (let i = 0; i < e.target.files.length; i++) {
                    selectedBidFiles.push(e.target.files[i]);
                }
            }
            updateFileList();
            clearPreviousResults();
        });
    }

    // 表单提交处理
    const uploadForm = document.getElementById('uploadForm');
    if (uploadForm) {
        uploadForm.addEventListener('submit', async function (e) {
            e.preventDefault();

            // 检查是否有文件被选中
            if (!selectedTenderFile && selectedBidFiles.length === 0) {
                alert('请至少选择一个文件');
                return;
            }

            // 停止任何正在进行的轮询
            stopProgressPolling();

            const formData = new FormData();
            if (selectedTenderFile) {
                formData.append('tender_file', selectedTenderFile);
            }

            selectedBidFiles.forEach(file => {
                formData.append('bid_files', file);
            });

            const resultDiv = document.getElementById('result');
            const progressSection = document.getElementById('progressSection');
            const fileListSection = document.getElementById('fileListSection');
            if (resultDiv) resultDiv.style.display = 'none';

            // 隐藏上传表单和文件列表，显示进度界面
            const uploadSection = document.querySelector('.upload-section');
            if (uploadSection) uploadSection.style.display = 'none';
            if (fileListSection) fileListSection.style.display = 'none';
            if (progressSection) progressSection.style.display = 'block';

            // 隐藏符合性审查按钮
            const complianceBtn = document.getElementById('complianceReviewBtn');
            if (complianceBtn) {
                complianceBtn.style.display = 'none';
            }

            // 重置用时显示和开始时间
            const timeDisplay = document.getElementById('timeDisplay');
            if (timeDisplay) {
                timeDisplay.className = 'time-display processing';
                document.getElementById('elapsedTime').textContent = '0';
            }
            startTime = new Date(); // 重置开始时间

            try {
                const response = await fetch('/api/init-upload', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (response.ok) {
                    // 上传成功，更新项目ID
                    currentProjectId = data.project_id;
                    document.getElementById('projectId').textContent = currentProjectId;

                    // 保存项目ID到localStorage
                    saveProjectId(currentProjectId);

                    // 确保进度界面显示
                    if (progressSection) {
                        progressSection.style.display = 'block';
                    }

                    // 现在开始轮询进度
                    startProgressPolling();
                } else {
                    // 特别处理413错误（文件大小超出限制）
                    if (response.status === 413) {
                        if (resultDiv) {
                            resultDiv.className = 'result error';
                            if (data.error && data.error.includes('招标文件大小超出限制')) {
                                resultDiv.innerHTML = `<h3>上传失败!</h3><p>招标文件大小超出限制，请检查系统设置中的单个文件大小限制。</p>`;
                            } else if (data.error && data.error.includes('投标文件大小超出限制')) {
                                resultDiv.innerHTML = `<h3>上传失败!</h3><p>投标文件大小超出限制，请检查系统设置中的单个文件大小限制。</p>`;
                            } else if (data.error && data.error.includes('文件大小超出限制')) {
                                resultDiv.innerHTML = `<h3>上传失败!</h3><p>文件大小超出限制，请检查系统设置中的单个文件大小限制。</p>`;
                            } else {
                                resultDiv.innerHTML = `<h3>上传失败!</h3><p>${data.error || '文件大小超出限制'}</p>`;
                            }
                            resultDiv.style.display = 'block';
                        }
                    } else {
                        if (resultDiv) {
                            resultDiv.className = 'result error';
                            resultDiv.innerHTML = `<h3>上传失败!</h3><p>${data.error}</p>`;
                            resultDiv.style.display = 'block';
                        }
                    }

                    // 恢复上传表单
                    if (uploadSection) uploadSection.style.display = 'block';
                    if (progressSection) progressSection.style.display = 'none';
                }
            } catch (error) {
                if (resultDiv) {
                    resultDiv.className = 'result error';
                    resultDiv.innerHTML = `<h3>请求失败!</h3><p>${error.message}</p>`;
                    resultDiv.style.display = 'block';
                }

                // 恢复上传表单
                if (uploadSection) uploadSection.style.display = 'block';
                if (progressSection) progressSection.style.display = 'none';
            }
        });
    }
});

// 轮询分析进度
async function pollAnalysisStatus (projectId) {
    // 设置当前项目ID
    currentProjectId = projectId;

    // 检查是否应该继续轮询
    if (!shouldContinuePolling()) {
        pollingActive = false;
        return;
    }

    try {
        const response = await fetch(`/api/projects/${projectId}/progress`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('Polling data:', data);

        // 保存进度数据
        lastProgressData = data;

        // 更新进度显示
        updateProgress(data);

        // 检查项目状态 - 增加更严格的检查
        const projectStatus = data.project_status || data.processing_status;
        const isCompleted = projectStatus === 'completed' || projectStatus === 'completed_with_errors';

        // 额外检查：确保所有投标文件都已完成
        let allBidsCompleted = true;
        if (data.document_statuses) {
            for (const doc of data.document_statuses) {
                if (doc.processing_status !== 'completed' && doc.processing_status !== 'error') {
                    allBidsCompleted = false;
                    break;
                }
            }
        }

        if (isCompleted || (projectStatus === 'processing' && allBidsCompleted)) {
            // 即使项目状态显示为完成，也要确保所有投标文件状态都已更新
            console.log('项目已完成或所有投标文件已完成，准备获取结果...');

            // 显示处理完成提示
            const progressTextAfter = document.getElementById('progressText');
            if (progressTextAfter) {
                progressTextAfter.innerHTML = '处理完成，正在获取结果...';
            }

            // 短暂延迟后获取结果
            await new Promise(resolve => setTimeout(resolve, 500));

            // 首先尝试获取动态汇总数据
            try {
                const summaryResponse = await fetch(`/api/projects/${projectId}/dynamic-summary`);
                if (summaryResponse.ok) {
                    const summaryData = await summaryResponse.json();
                    displaySummary(summaryData);
                    pollingActive = false;
                    // 清除保存的项目ID
                    clearProjectId();
                    return; // 结束轮询
                }
            } catch (summaryError) {
                console.warn('获取动态汇总数据失败，回退到分析结果:', summaryError);
            }

            // 如果获取动态汇总数据失败，获取分析结果
            try {
                const resultResponse = await fetch(`/api/projects/${projectId}/results`);
                const resultData = await resultResponse.json();
                displayResults(resultData);
                pollingActive = false;
                // 清除保存的项目ID
                clearProjectId();
                return; // 结束轮询
            } catch (resultError) {
                console.error('获取分析结果失败:', resultError);
                // 如果获取结果失败，继续轮询而不是终止
                console.log('获取结果失败，继续轮询...');
            }
        }

        // 如果项目未完成，继续轮询
        if (!isCompleted) {
            // 2秒后再次检查
            await new Promise(resolve => setTimeout(resolve, 2000));

            // 检查是否应该继续轮询
            if (shouldContinuePolling()) {
                await pollAnalysisStatus(projectId); // 继续轮询
            } else {
                pollingActive = false;
            }
        } else {
            // 项目已完成但结果获取失败，停止轮询
            pollingActive = false;
        }
    } catch (error) {
        console.error('轮询过程中出错:', error);
        // 出错时继续轮询而不是立即停止
        await new Promise(resolve => setTimeout(resolve, 5000)); // 等待5秒后重试
        if (shouldContinuePolling()) {
            await pollAnalysisStatus(projectId); // 继续轮询
        } else {
            pollingActive = false;
        }
    }
}

// 检查是否应该继续轮询
function shouldContinuePolling () {
    // 检查是否在正确的页面（动态进度界面）
    const progressSection = document.getElementById('progressSection');

    // 增加额外的检查：确保currentProjectId存在且有效
    if (!currentProjectId) {
        return false;
    }

    // 检查页面可见性
    if (document.visibilityState === 'hidden') {
        return false;
    }

    // 如果进度界面存在且显示，则继续轮询
    if (progressSection && progressSection.style.display !== 'none') {
        return true;
    }

    // 如果进度界面不存在但当前页面是首页（index.html），且有项目ID，也继续轮询
    // 这样可以处理页面切换后返回的情况
    if (window.location.pathname === '/' || window.location.pathname === '/index.html') {
        return true;
    }

    // 其他情况不继续轮询
    return false;
}

// 停止轮询进度
function stopProgressPolling () {
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }
    pollingActive = false;
}

// 开始轮询进度
function startProgressPolling () {
    // 先停止现有的轮询
    if (typeof stopProgressPolling === 'function' && window.stopProgressPolling !== stopProgressPolling) {
        stopProgressPolling();
    } else if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
        pollingActive = false;
    }

    // 检查是否应该启动轮询
    const progressSection = document.getElementById('progressSection');
    // 修改条件判断，确保在有currentProjectId时启动轮询，而不依赖progressSection的显示状态
    if (currentProjectId) {
        pollingActive = true;
        // 使用定时器而不是递归调用
        if (progressInterval) {
            clearInterval(progressInterval);
        }
        // 获取轮询间隔配置，默认3秒
        const pollingInterval = window.pollingIntervalSec || 3;
        progressInterval = setInterval(() => {
            if (currentProjectId && shouldContinuePolling()) {
                fetch(`/api/projects/${currentProjectId}/progress`)
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP error! status: ${response.status}`);
                        }
                        return response.json();
                    })
                    .then(data => {
                        console.log('Polling data:', data);
                        lastProgressData = data;
                        updateProgress(data);

                        // 检查项目是否完成
                        if (data.project_status === 'completed' || data.project_status === 'completed_with_errors' ||
                            data.processing_status === 'completed' || data.processing_status === 'completed_with_errors') {
                            // 停止轮询
                            stopProgressPolling();

                            // 显示结果
                            const progressTextAfter = document.getElementById('progressText');
                            if (progressTextAfter) {
                                progressTextAfter.innerHTML = '处理完成，正在获取结果...';
                            }

                            setTimeout(async function () {
                                try {
                                    const summaryResponse = await fetch(`/api/projects/${currentProjectId}/dynamic-summary`);
                                    if (summaryResponse.ok) {
                                        const summaryData = await summaryResponse.json();
                                        displaySummary(summaryData);
                                        // 清除保存的项目ID
                                        clearProjectId();
                                    } else {
                                        const resultResponse = await fetch(`/api/projects/${currentProjectId}/results`);
                                        const resultData = await resultResponse.json();
                                        displayResults(resultData);
                                        // 清除保存的项目ID
                                        clearProjectId();
                                    }
                                } catch (error) {
                                    console.error('获取结果失败:', error);
                                }
                            }, 300);
                        }
                    })
                    .catch(error => {
                        console.error('轮询进度时出错:', error);
                    });
            } else {
                stopProgressPolling();
            }
        }, pollingInterval * 1000); // 使用配置的轮询间隔
    }
}

// 页面可见性变化处理
document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible') {
        // 页面变为可见时，如果在进度页面且有项目ID，则恢复轮询
        const progressSection = document.getElementById('progressSection');
        if (progressSection && progressSection.style.display !== 'none' && currentProjectId) {
            startProgressPolling();
        }
    } else {
        // 页面隐藏时停止轮询
        stopProgressPolling();
    }
});

// 页面加载完成后检查是否需要启动轮询
document.addEventListener('DOMContentLoaded', function () {
    // 恢复项目ID
    restoreProjectId();

    // 如果页面加载时进度界面是显示的，则启动轮询
    const progressSection = document.getElementById('progressSection');
    if (progressSection && progressSection.style.display !== 'none' && currentProjectId) {
        startProgressPolling();
    } else if (currentProjectId) {
        // 如果有保存的项目ID但进度界面未显示，检查项目状态并恢复轮询
        checkAndRestoreProgress(currentProjectId);
    }
});

// 检查项目状态并恢复进度显示和轮询
async function checkAndRestoreProgress(projectId) {
    try {
        const response = await fetch(`/api/projects/${projectId}/progress`);
        if (!response.ok) {
            console.warn('获取项目进度失败，清除保存的项目ID');
            clearProjectId();
            return;
        }

        const data = await response.json();
        const projectStatus = data.project_status || data.processing_status;
        
        // 检查项目是否真的在进行中（通过检查最后更新时间）
        const lastUpdateTime = data.last_update_time || data.updated_at;
        const now = new Date().getTime();
        const timeSinceUpdate = lastUpdateTime ? (now - new Date(lastUpdateTime).getTime()) : Infinity;
        const maxStaleTime = 30 * 60 * 1000; // 30分钟
        
        // 如果项目状态是processing或analyzing，恢复进度显示和轮询
        if (projectStatus === 'processing' || projectStatus === 'analyzing') {
            // 如果项目超过30分钟没有更新，认为已卡住，允许用户取消
            if (timeSinceUpdate > maxStaleTime) {
                console.warn('项目可能已卡住（超过30分钟未更新），提供取消选项');
                // 显示进度界面但添加警告和取消按钮
                showProgressWithCancelOption(projectId, data, true);
                return;
            }
            
            console.log('检测到进行中的项目，恢复进度显示和轮询');
            
            // 显示进度界面
            const progressSection = document.getElementById('progressSection');
            const uploadSection = document.querySelector('.upload-section');
            const fileListSection = document.getElementById('fileListSection');
            
            if (progressSection) {
                progressSection.style.display = 'block';
            }
            if (uploadSection) {
                uploadSection.style.display = 'none';
            }
            if (fileListSection) {
                fileListSection.style.display = 'none';
            }
            
            // 更新项目ID显示
            const projectIdElement = document.getElementById('projectId');
            if (projectIdElement) {
                projectIdElement.textContent = projectId;
            }
            
            // 更新进度显示
            updateProgress(data);
            
            // 确保显示取消按钮
            showCancelButton();
            
            // 启动轮询
            startProgressPolling();
        } else if (projectStatus === 'completed' || projectStatus === 'completed_with_errors') {
            // 如果项目已完成，显示结果
            console.log('项目已完成，显示结果');
            const progressSection = document.getElementById('progressSection');
            if (progressSection) {
                progressSection.style.display = 'block';
            }
            updateProgress(data);
            
            // 隐藏取消按钮
            hideCancelButton();
            
            // 尝试获取结果
            try {
                const summaryResponse = await fetch(`/api/projects/${projectId}/dynamic-summary`);
                if (summaryResponse.ok) {
                    const summaryData = await summaryResponse.json();
                    displaySummary(summaryData);
                } else {
                    const resultResponse = await fetch(`/api/projects/${projectId}/results`);
                    if (resultResponse.ok) {
                        const resultData = await resultResponse.json();
                        displayResults(resultData);
                    }
                }
            } catch (error) {
                console.error('获取结果失败:', error);
            }
        } else {
            // 项目状态不是进行中或已完成，清除保存的项目ID
            console.log('项目状态不是进行中或已完成，清除保存的项目ID');
            clearProjectId();
        }
    } catch (error) {
        console.error('检查项目状态时出错:', error);
        clearProjectId();
    }
}

// 显示带取消选项的进度界面
function showProgressWithCancelOption(projectId, data, isStale) {
    const progressSection = document.getElementById('progressSection');
    const uploadSection = document.querySelector('.upload-section');
    const fileListSection = document.getElementById('fileListSection');
    
    if (progressSection) {
        progressSection.style.display = 'block';
    }
    if (uploadSection) {
        uploadSection.style.display = 'none';
    }
    if (fileListSection) {
        fileListSection.style.display = 'none';
    }
    
    // 更新项目ID显示
    const projectIdElement = document.getElementById('projectId');
    if (projectIdElement) {
        projectIdElement.textContent = projectId;
    }
    
    // 更新进度显示
    updateProgress(data);
    
    // 显示警告和取消按钮
    if (isStale) {
        showStaleWarning();
    }
    showCancelButton();
}

// 显示项目可能已卡住的警告
function showStaleWarning() {
    const progressSection = document.getElementById('progressSection');
    if (!progressSection) return;
    
    // 检查是否已有警告
    let warningDiv = document.getElementById('staleWarning');
    if (!warningDiv) {
        warningDiv = document.createElement('div');
        warningDiv.id = 'staleWarning';
        warningDiv.className = 'alert alert-warning';
        warningDiv.style.marginTop = '10px';
        warningDiv.innerHTML = `
            <strong>警告：</strong>该项目可能已卡住（超过30分钟未更新）。
            <button class="btn btn-sm btn-danger ms-2" onclick="cancelCurrentProject()">取消当前项目</button>
        `;
        progressSection.insertBefore(warningDiv, progressSection.firstChild);
    }
    warningDiv.style.display = 'block';
}

// 隐藏项目卡住警告
function hideStaleWarning() {
    const warningDiv = document.getElementById('staleWarning');
    if (warningDiv) {
        warningDiv.style.display = 'none';
    }
}

// 显示取消按钮
function showCancelButton() {
    const progressSection = document.getElementById('progressSection');
    if (!progressSection) return;
    
    // 检查是否已有取消按钮
    let cancelBtn = document.getElementById('cancelProjectBtn');
    if (!cancelBtn) {
        cancelBtn = document.createElement('button');
        cancelBtn.id = 'cancelProjectBtn';
        cancelBtn.className = 'btn btn-danger mt-3';
        cancelBtn.textContent = '取消当前项目，重新开始';
        cancelBtn.onclick = cancelCurrentProject;
        
        // 找到进度文本区域，在它后面插入按钮
        const progressText = document.getElementById('progressText');
        if (progressText && progressText.parentNode) {
            progressText.parentNode.appendChild(cancelBtn);
        } else {
            progressSection.appendChild(cancelBtn);
        }
    }
    cancelBtn.style.display = 'block';
}

// 隐藏取消按钮
function hideCancelButton() {
    const cancelBtn = document.getElementById('cancelProjectBtn');
    if (cancelBtn) {
        cancelBtn.style.display = 'none';
    }
}

// 取消当前项目
function cancelCurrentProject() {
    if (!confirm('确定要取消当前项目吗？这将清除当前进度并允许您重新开始。')) {
        return;
    }
    
    // 停止轮询
    stopProgressPolling();
    
    // 清除项目ID
    clearProjectId();
    currentProjectId = null;
    
    // 隐藏进度界面
    const progressSection = document.getElementById('progressSection');
    if (progressSection) {
        progressSection.style.display = 'none';
    }
    
    // 显示上传表单
    const uploadSection = document.querySelector('.upload-section');
    if (uploadSection) {
        uploadSection.style.display = 'block';
    }
    
    const fileListSection = document.getElementById('fileListSection');
    if (fileListSection) {
        fileListSection.style.display = 'block';
    }
    
    // 隐藏警告和取消按钮
    hideStaleWarning();
    hideCancelButton();
    
    // 清除项目ID显示
    const projectIdElement = document.getElementById('projectId');
    if (projectIdElement) {
        projectIdElement.textContent = '-';
    }
    
    // 清除结果显示
    clearPreviousResults();
    
    console.log('已取消当前项目，可以重新开始');
}

// 更新进度显示 - 实现每个投标文件的动态进展
function updateProgress (data) {
    // 确保详细进度容器存在
    let detailedProgressContainer = document.getElementById('detailedProgress');
    const progressBar = document.getElementById('progressFill'); // 在index.html中是progressFill
    const progressText = document.getElementById('progressText');
    
    // 检查项目状态，如果是进行中状态，显示取消按钮
    const projectStatus = data.project_status || data.processing_status;
    if (projectStatus === 'processing' || projectStatus === 'analyzing') {
        showCancelButton();
    } else {
        hideCancelButton();
        hideStaleWarning();
    }

    // 更新总体进度
    let overallProgress = 0;
    let totalBids = data.document_statuses ? data.document_statuses.length : 0;
    let completedBids = 0;

    if (data.document_statuses) {
        data.document_statuses.forEach(bid => {
            if (bid.processing_status === 'completed') {
                completedBids++;
            }
        });
    }

    if (totalBids > 0) {
        overallProgress = (completedBids / totalBids) * 100;
    }

    // 更新总体进度条
    if (progressBar) {
        // 确保进度条宽度正确设置
        progressBar.style.width = `${overallProgress}%`;
        progressBar.setAttribute('aria-valuenow', overallProgress);
    }

    // 显示总体进度文本
    let phaseInfo = '';
    if (data.document_statuses && data.document_statuses.length > 0) {
        const phases = data.document_statuses.map(doc => doc.processing_phase).filter(phase => phase);
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

    if (progressText) {
        progressText.textContent = `总体进度: ${data.processing_status} (${completedBids}/${totalBids} 个文件完成)${phaseInfo}`;
    }

    // 更新用时显示
    const timeDisplay = document.getElementById('timeDisplay');
    const elapsedTimeElement = document.getElementById('elapsedTime');

    if (data.total_time !== null) {
        // 分析已完成，显示总用时
        if (timeDisplay) {
            timeDisplay.className = 'time-display completed';
        }
        const minutes = Math.floor(data.total_time / 60);
        const seconds = Math.floor(data.total_time % 60);
        if (elapsedTimeElement) {
            elapsedTimeElement.textContent = `${minutes}分${seconds}秒`;
        }
    } else if (data.elapsed_time !== null) {
        // 分析进行中，显示已用时
        if (timeDisplay) {
            timeDisplay.className = 'time-display processing';
        }
        const minutes = Math.floor(data.elapsed_time / 60);
        const seconds = Math.floor(data.elapsed_time % 60);
        if (elapsedTimeElement) {
            elapsedTimeElement.textContent = `${minutes}分${seconds}秒`;
        }
    }

    // 显示每个投标文件的详细进度
    // 过滤掉招标文件，只显示投标文件的进度
    if (data.document_statuses && detailedProgressContainer) {
        // 过滤掉招标文件，只保留投标文件
        const bidDocuments = data.document_statuses.filter(doc =>
            doc.file_path && !doc.file_path.includes('tender') && !doc.file_path.includes('招标')
        );

        let detailedHtml = '<div class="row">';

        bidDocuments.forEach((bid, index) => {
            // 计算单个文件的进度
            let bidProgress = 0;
            if (bid.progress_total > 0) {
                bidProgress = (bid.progress_completed / bid.progress_total) * 100;
            } else if (bid.processing_status === 'completed') {
                bidProgress = 100;
            }

            // 确定状态文本和样式
            let statusText = '';
            let statusClass = '';
            let statusBgClass = '';

            if (bid.processing_phase) {
                statusText = bid.processing_phase;
            } else {
                switch (bid.processing_status) {
                    case 'completed':
                        statusText = '分析完成';
                        statusClass = 'text-success';
                        statusBgClass = 'bg-success';
                        break;
                    case 'error':
                        statusText = '处理出错';
                        statusClass = 'text-danger';
                        statusBgClass = 'bg-danger';
                        break;
                    case 'processing':
                        statusText = bid.current_rule || '处理中';
                        statusClass = 'text-info';
                        statusBgClass = 'bg-info';
                        break;
                    default:
                        statusText = '等待处理';
                        statusClass = 'text-secondary';
                        statusBgClass = 'bg-secondary';
                }
            }

            // 获取文件名（用于在投标人名称未解析成功时显示）
            let fileName = '未知文件';
            if (bid.file_path) {
                const pathParts = bid.file_path.split('\\');
                fileName = pathParts[pathParts.length - 1].replace('.pdf', '');
            }

            // 使用投标人名称或文件名作为标题
            const displayTitle = (bid.bidder_name && bid.bidder_name !== '未知投标人' && bid.bidder_name.trim() !== '')
                ? bid.bidder_name
                : fileName;

            // 构建单个文件的进度框架
            detailedHtml += `
                    <div class="col-xl-3 col-lg-4 col-md-6 col-sm-12 mb-4">
                        <div class="card h-100 progress-card">
                            <div class="card-header text-white py-2" style="display: flex; align-items: center;">
                                <h6 class="mb-0 text-truncate" style="font-size: 0.9rem;" title="${displayTitle}">${displayTitle}</h6>
                            </div>
                            <div class="card-body py-2">
                                <div class="d-flex justify-content-between align-items-center mb-2">
                                    <span class="fw-bold ${statusClass}" style="font-size: 0.8rem;">${statusText}</span>
                                    <span class="fw-bold" style="font-size: 0.8rem;">${bidProgress.toFixed(1)}%</span>
                                </div>
                                <div class="progress progress-sm mb-2" style="width: 100%;">
                                    <div class="progress-bar ${statusBgClass}" 
                                         role="progressbar" 
                                         style="width: ${bidProgress}%; transition: width 0.3s ease;" 
                                         aria-valuenow="${bidProgress}" 
                                         aria-valuemin="0" 
                                         aria-valuemax="100">
                                    </div>
                                </div>
                                <div class="small text-muted mb-1" style="font-size: 0.75rem;">
                                    规则进度: ${bid.progress_completed || 0}/${bid.progress_total || 0}
                                </div>
                                ${bid.current_rule ? `<div class="small mb-1" style="font-size: 0.75rem;"><strong>当前规则:</strong> <span class="text-primary">${bid.current_rule}</span></div>` : ''}
                                ${bid.error_message ? `<div class="small text-danger" style="font-size: 0.75rem;"><strong>错误:</strong> ${bid.error_message}</div>` : ''}
                            </div>
                        </div>
                    </div>
                `;
        });

        detailedHtml += '</div>';
        detailedProgressContainer.innerHTML = detailedHtml;
    }
}

// 汇总结果显示
function displaySummary (summaryData) {
    const progressSection = document.getElementById('progressSection');
    const progressText = document.getElementById('progressText');
    const detailedProgressContainer = document.getElementById('detailedProgressContainer');
    const resultArea = document.getElementById('result');

    if (progressSection) {
        progressSection.style.display = 'none';
    }
    if (progressText) {
        progressText.textContent = '';
    }

    // 隐藏详细进度显示
    if (detailedProgressContainer) {
        detailedProgressContainer.style.display = 'none';
    }

    // 错误检查
    if (summaryData.error) {
        if (resultArea) {
            resultArea.innerHTML = `
                <div class="alert alert-danger">
                    汇总失败: ${summaryData.error}
                </div>
            `;
            resultArea.style.display = 'block';
        }
        return;
    }

    // 构建汇总结果显示 - 支持动态表头
    let html = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">项目汇总结果 - ${summaryData.project_name || '未知项目'}</h3>
                </div>
                <div class="card-body">
                    <div class="table-responsive" style="max-height: 600px; overflow: auto;">
                        <table class="table table-bordered table-hover">
                            <thead class="table-light">
    `;

    // 检查是否有动态表头数据
    if (summaryData.header_rows && summaryData.rows) {
        // 使用动态表头
        html += '<tr>';
        // 第一行表头
        summaryData.header_rows[0].forEach(headerCell => {
            const colspan = headerCell.colspan ? `colspan="${headerCell.colspan}"` : '';
            const rowspan = headerCell.rowspan ? `rowspan="${headerCell.rowspan}"` : '';
            html += `<th ${colspan} ${rowspan}>${headerCell.name}</th>`;
        });
        html += '</tr>';

        // 第二行表头（如果有）
        if (summaryData.header_rows.length > 1) {
            html += '<tr>';
            summaryData.header_rows[1].forEach(headerCell => {
                html += `<th>${headerCell.name}</th>`;
            });
            html += '</tr>';
        }

        html += '</thead><tbody>';

        // 渲染数据行
        summaryData.rows.forEach(rowData => {
            html += '<tr>';
            html += `<td>${rowData.rank}</td>`;
            html += `<td>${rowData.bidder_name}</td>`;

            // 渲染子项得分
            rowData.scores.forEach(score => {
                const cellValue = (typeof score === 'number') ? score.toFixed(2) : (score === null ? 'N/A' : score);
                html += `<td>${cellValue}</td>`;
            });

            // 渲染价格分和总分
            const priceScore = (typeof rowData.price_score === 'number') ? rowData.price_score.toFixed(2) : 'N/A';
            const totalScore = (typeof rowData.total_score === 'number') ? rowData.total_score.toFixed(2) : 'N/A';
            html += `<td>${priceScore}</td>`;
            html += `<td>${totalScore}</td>`;
            html += '</tr>';
        });
    } else {
        // 回退到旧的显示方式
        html += `
                            <tr>
                                <th>排名</th>
                                <th>投标人</th>
                                <th>价格得分</th>
                                <th>总分</th>
                            </tr>
                        </thead>
                        <tbody>
        `;

        // 处理汇总数据
        let summaryItems = [];

        // 检查是否是动态汇总数据格式
        if (summaryData.rows) {
            // 动态汇总数据格式
            summaryItems = summaryData.rows.map(row => ({
                bidder_name: row.bidder_name,
                price_score: row.price_score,
                total_score: row.total_score,
                rank: row.rank
            }));
        } else if (summaryData.summary) {
            // 普通汇总数据格式
            summaryItems = summaryData.summary;
        }

        if (summaryItems && summaryItems.length > 0) {
            // 按总分降序排列
            summaryItems.sort((a, b) => (b.total_score || 0) - (a.total_score || 0));

            summaryItems.forEach((item, index) => {
                // 如果没有排名，根据排序位置生成排名
                const rank = item.rank || (index + 1);

                const priceScore = (typeof item.price_score === 'number') ? item.price_score.toFixed(2) : 'N/A';
                const totalScore = (typeof item.total_score === 'number') ? item.total_score.toFixed(2) : 'N/A';

                html += `
                    <tr>
                        <td>${rank}</td>
                        <td>${item.bidder_name || 'N/A'}</td>
                        <td>${priceScore}</td>
                        <td>${totalScore}</td>
                    </tr>
                `;
            });
        } else {
            html += '<tr><td colspan="4">无汇总数据</td></tr>';
        }
    }

    html += `
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;

    if (resultArea) {
        resultArea.innerHTML = html;
        resultArea.style.display = 'block';
    }
}

// 分析结果显示
function displayResults (results) {
    const progressSection = document.getElementById('progressSection');
    const progressText = document.getElementById('progressText');
    const detailedProgressContainer = document.getElementById('detailedProgressContainer');
    const resultArea = document.getElementById('result');

    if (progressSection) {
        progressSection.style.display = 'none';
    }
    if (progressText) {
        progressText.textContent = '';
    }

    // 隐藏详细进度显示
    if (detailedProgressContainer) {
        detailedProgressContainer.style.display = 'none';
    }

    // 错误检查
    if (results.error) {
        if (resultArea) {
            resultArea.innerHTML = `
                <div class="alert alert-danger">
                    分析失败: ${results.error}
                </div>
            `;
            resultArea.style.display = 'block';
        }
        return;
    }

    // results可能是数组也可能是单个对象
    const resultsArray = Array.isArray(results) ? results : [results];

    let html = '<div class="card"><div class="card-body"><h3 class="card-title">分析结果</h3>';

    resultsArray.forEach((result, index) => {
        html += `
                <div class="result-item mb-4">
                    <h4>投标人: ${result.bidder_name}</h4>
                    <div class="result-summary">
                        <div class="row">
                            <div class="col-md-6">
                                <h5>总分: ${result.total_score ? result.total_score.toFixed(2) : 'N/A'}</h5>
                            </div>
                        </div>
                    </div>

                    <h5>详细评分</h5>
                    <div class="table-responsive">
                        <table class="table table-bordered table-hover">
                            <thead class="table-light">
                                <tr>
                                    <th>评分项</th>
                                    <th>满分</th>
                                    <th>得分</th>
                                    <th>评分说明</th>
                                </tr>
                            </thead>
                            <tbody>
            `;

        // 处理详细评分
        const detailedScores = Array.isArray(result.detailed_scores) ? result.detailed_scores : [];
        if (detailedScores.length > 0) {
            detailedScores.forEach(score => {
                html += `
                        <tr>
                            <td>${score.criteria_name || score.Child_Item_Name || 'N/A'}</td>
                            <td>${score.max_score || 'N/A'}</td>
                            <td>${score.score ? score.score.toFixed(2) : 'N/A'}</td>
                            <td>${score.reason || 'N/A'}</td>
                        </tr>
                    `;
            });
        } else {
            html += '<tr><td colspan="4">无详细评分数据</td></tr>';
        }

        html += `
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
    });

    html += '</div></div>';

    if (resultArea) {
        resultArea.innerHTML = html;
        resultArea.style.display = 'block';
    }
}

// 导出函数供其他脚本使用
window.currentProjectId = currentProjectId;
window.startProgressPolling = startProgressPolling;
window.stopProgressPolling = stopProgressPolling;
window.updateProgress = updateProgress;
window.displaySummary = displaySummary;
window.displayResults = displayResults;
window.saveProjectId = saveProjectId;
window.restoreProjectId = restoreProjectId;
window.clearProjectId = clearProjectId;
window.loadPollingConfig = loadPollingConfig;
