// 轮询分析进度
async function pollAnalysisStatus (projectId) {
    try {
        const response = await fetch(`/api/projects/${projectId}/progress`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('Polling data:', data);

        // 更新进度显示
        updateProgress(data);

        // 检查项目状态
        if (data.project_status === 'completed' || data.project_status === 'completed_with_errors' ||
            data.processing_status === 'completed' || data.processing_status === 'completed_with_errors') {
            // 分析完成，获取结果
            progressText.innerHTML = '处理完成，正在获取结果...';
            await new Promise(resolve => setTimeout(resolve, 300));

            // 首先尝试获取动态汇总数据
            try {
                const summaryResponse = await fetch(`/api/projects/${projectId}/dynamic-summary`);
                if (summaryResponse.ok) {
                    const summaryData = await summaryResponse.json();
                    displaySummary(summaryData);
                    return; // 结束轮询
                }
            } catch (summaryError) {
                console.warn('获取动态汇总数据失败，回退到分析结果:', summaryError);
            }

            // 如果获取动态汇总数据失败，获取分析结果
            const resultResponse = await fetch(`/api/projects/${projectId}/results`);
            const resultData = await resultResponse.json();
            displayResults(resultData);
            return; // 结束轮询
        }

        // 1秒后再次检查
        await new Promise(resolve => setTimeout(resolve, 1000));
        await pollAnalysisStatus(projectId); // 继续轮询
    } catch (error) {
        console.error('Error:', error);
        alert('分析过程中发生错误: ' + error.message);
    }
}

// 更新进度显示 - 实现每个投标文件的动态进展
function updateProgress (data) {
    // 确保详细进度容器存在
    if (!detailedProgressContainer) {
        // 创建详细进度显示区域
        const progressContainer = progressBar.parentElement;
        detailedProgressContainer = document.createElement('div');
        detailedProgressContainer.id = 'detailedProgressContainer';
        detailedProgressContainer.className = 'mt-3';
        progressContainer.parentNode.insertBefore(detailedProgressContainer, progressContainer.nextSibling);
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
    progressBar.style.width = `${overallProgress}%`;
    progressBar.setAttribute('aria-valuenow', overallProgress);

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

    progressText.textContent = `总体进度: ${data.processing_status} (${completedBids}/${totalBids} 个文件完成)${phaseInfo}`;

    // 显示每个投标文件的详细进度
    if (data.document_statuses) {
        let detailedHtml = '<div class="row">';

        data.document_statuses.forEach((bid, index) => {
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
                    <div class="col-md-6 col-lg-4 mb-4">
                        <div class="card h-100">
                            <div class="card-header bg-primary text-white">
                                <h6 class="mb-0">${displayTitle}</h6>
                            </div>
                            <div class="card-body">
                                <div class="d-flex justify-content-between align-items-center mb-2">
                                    <span class="fw-bold ${statusClass}">${statusText}</span>
                                    <span class="fw-bold">${bidProgress.toFixed(1)}%</span>
                                </div>
                                <div class="progress mb-3" style="height: 20px;">
                                    <div class="progress-bar ${statusBgClass}" 
                                         role="progressbar" 
                                         style="width: ${bidProgress}%;" 
                                         aria-valuenow="${bidProgress}" 
                                         aria-valuemin="0" 
                                         aria-valuemax="100">
                                    </div>
                                </div>
                                <div class="small text-muted mb-2">
                                    规则进度: ${bid.progress_completed || 0}/${bid.progress_total || 0}
                                </div>
                                ${bid.current_rule ? `<div class="small mb-2"><strong>当前规则:</strong> ${bid.current_rule}</div>` : ''}
                                ${bid.error_message ? `<div class="small text-danger"><strong>错误:</strong> ${bid.error_message}</div>` : ''}
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
    progressBar.parentElement.style.display = 'none';
    progressText.textContent = '';

    // 隐藏详细进度显示
    if (detailedProgressContainer) {
        detailedProgressContainer.style.display = 'none';
    }

    // 错误检查
    if (summaryData.error) {
        resultArea.innerHTML = `
                <div class="alert alert-danger">
                    汇总失败: ${summaryData.error}
                </div>
            `;
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
    if (summaryData.summary && summaryData.summary.length > 0) {
        summaryData.summary.forEach((item, index) => {
            html += `
                    <tr>
                        <td>${item.bidder_name || 'N/A'}</td>
                        <td>${item.bid_price ? item.bid_price.toFixed(2) : 'N/A'}</td>
                        <td>${item.benchmark_price ? item.benchmark_price.toFixed(2) : 'N/A'}</td>
                        <td>${item.price_score ? item.price_score.toFixed(2) : 'N/A'}</td>
                        <td>${item.technical_score ? item.technical_score.toFixed(2) : 'N/A'}</td>
                        <td>${item.total_score ? item.total_score.toFixed(2) : 'N/A'}</td>
                        <td>${item.rank || 'N/A'}</td>
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

    resultArea.innerHTML = html;
}

// 分析结果显示
function displayResults (results) {
    progressBar.parentElement.style.display = 'none';
    progressText.textContent = '';

    // 隐藏详细进度显示
    if (detailedProgressContainer) {
        detailedProgressContainer.style.display = 'none';
    }

    // 错误检查
    if (results.error) {
        resultArea.innerHTML = `
                <div class="alert alert-danger">
                    分析失败: ${results.error}
                </div>
            `;
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
    resultArea.innerHTML = html;
}
