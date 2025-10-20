// 全局变量
let currentProjectId = null;
let pollingActive = false;
let progressInterval = null;
let lastProgressData = null; // 保存最后一次进度数据

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

        // 检查项目状态
        if (data.project_status === 'completed' || data.project_status === 'completed_with_errors' ||
            data.processing_status === 'completed' || data.processing_status === 'completed_with_errors') {
            // 分析完成，直接获取结果，不再显示价格分计算提示
            // 获取结果
            const progressTextAfter = document.getElementById('progressText');
            if (progressTextAfter) {
                progressTextAfter.innerHTML = '处理完成，正在获取结果...';
            }
            await new Promise(resolve => setTimeout(resolve, 300));

            // 首先尝试获取动态汇总数据
            try {
                const summaryResponse = await fetch(`/api/projects/${projectId}/dynamic-summary`);
                if (summaryResponse.ok) {
                    const summaryData = await summaryResponse.json();
                    displaySummary(summaryData);
                    pollingActive = false;
                    return; // 结束轮询
                }
            } catch (summaryError) {
                console.warn('获取动态汇总数据失败，回退到分析结果:', summaryError);
            }

            // 如果获取动态汇总数据失败，获取分析结果
            const resultResponse = await fetch(`/api/projects/${projectId}/results`);
            const resultData = await resultResponse.json();
            displayResults(resultData);
            pollingActive = false;
            return; // 结束轮询
        }

        // 2秒后再次检查
        await new Promise(resolve => setTimeout(resolve, 2000));

        // 检查是否应该继续轮询
        if (shouldContinuePolling()) {
            await pollAnalysisStatus(projectId); // 继续轮询
        } else {
            pollingActive = false;
        }
    } catch (error) {
        console.error('Error:', error);
        alert('分析过程中发生错误: ' + error.message);
        pollingActive = false;
    }
}

// 检查是否应该继续轮询
function shouldContinuePolling () {
    // 检查是否在正确的页面（动态进度界面）
    const progressSection = document.getElementById('progressSection');

    // 只有在进度界面显示时才继续轮询
    return progressSection &&
        progressSection.style.display !== 'none' &&
        document.visibilityState !== 'hidden';
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
    if (progressSection && progressSection.style.display !== 'none' && currentProjectId) {
        pollingActive = true;
        // 使用定时器而不是递归调用
        if (progressInterval) {
            clearInterval(progressInterval);
        }
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
                                    } else {
                                        const resultResponse = await fetch(`/api/projects/${currentProjectId}/results`);
                                        const resultData = await resultResponse.json();
                                        displayResults(resultData);
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
        }, 2000); // 每2秒轮询一次
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
    // 如果页面加载时进度界面是显示的，则启动轮询
    const progressSection = document.getElementById('progressSection');
    if (progressSection && progressSection.style.display !== 'none' && currentProjectId) {
        startProgressPolling();
    }
});

// 更新进度显示 - 实现每个投标文件的动态进展
function updateProgress (data) {
    // 确保详细进度容器存在
    let detailedProgressContainer = document.getElementById('detailedProgressContainer');
    const progressBar = document.getElementById('progressFill'); // 在index.html中是progressFill
    const progressText = document.getElementById('progressText');

    if (!detailedProgressContainer) {
        // 创建详细进度显示区域
        const progressContainer = document.getElementById('progressSection');
        if (progressContainer) {
            detailedProgressContainer = document.createElement('div');
            detailedProgressContainer.id = 'detailedProgressContainer';
            detailedProgressContainer.className = 'mt-3';
            progressContainer.appendChild(detailedProgressContainer);
        }
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

    // 构建汇总结果显示
    let html = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">项目汇总结果 - ${summaryData.project_name || '未知项目'}</h3>
                </div>
                <div class="card-body">
                    <div class="table-responsive">
                        <table class="table table-bordered table-hover">
                            <thead class="table-light">
                                <tr>
                                    <th>投标人</th>
                                    <th>投标总价</th>
                                    <th>评标基准价</th>
                                    <th>价格得分</th>
                                    <th>技术得分</th>
                                    <th>总分</th>
                                    <th>排名</th>
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
            bid_price: null, // 动态汇总数据中没有这个字段
            benchmark_price: null, // 动态汇总数据中没有这个字段
            price_score: row.price_score,
            technical_score: null, // 动态汇总数据中没有这个字段
            total_score: row.total_score,
            rank: row.rank
        }));
    } else if (summaryData.summary) {
        // 普通汇总数据格式
        summaryItems = summaryData.summary;
    }

    if (summaryItems && summaryItems.length > 0) {
        summaryItems.forEach((item, index) => {
            // 如果没有排名，根据排序位置生成排名
            const rank = item.rank || (index + 1);

            html += `
                    <tr>
                        <td>${item.bidder_name || 'N/A'}</td>
                        <td>${item.bid_price ? item.bid_price.toFixed(2) : 'N/A'}</td>
                        <td>${item.benchmark_price ? item.benchmark_price.toFixed(2) : 'N/A'}</td>
                        <td>${item.price_score ? item.price_score.toFixed(2) : 'N/A'}</td>
                        <td>${item.technical_score ? item.technical_score.toFixed(2) : 'N/A'}</td>
                        <td>${item.total_score ? item.total_score.toFixed(2) : 'N/A'}</td>
                        <td>${rank}</td>
                    </tr>
                `;
        });
    } else {
        html += '<tr><td colspan="7">无汇总数据</td></tr>';
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
