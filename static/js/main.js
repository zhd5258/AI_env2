document.addEventListener('DOMContentLoaded', function () {
    // 获取DOM元素
    const uploadForm = document.getElementById('uploadForm');
    const fileList = document.getElementById('fileList');
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    const resultArea = document.getElementById('resultArea');

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
    function updateFileList () {
        let html = '<h4>已选择的文件：</h4><ul class="list-group">';
        if (uploadedFiles.tender) {
            html += `<li class="list-group-item">招标文件: ${uploadedFiles.tender.name}</li>`;
        }
        if (uploadedFiles.bids.length > 0) {
            html += '<li class="list-group-item">投标文件：<ul class="list-group">';
            uploadedFiles.bids.forEach(file => {
                html += `<li class="list-group-item">${file.name}</li>`;
            });
            html += '</ul></li>';
        }
        html += '</ul>';
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
            // 显示进度条
            progressBar.parentElement.style.display = 'block';
            progressBar.style.width = '0%';
            progressText.textContent = '正在上传文件...';

            // 创建表单数据
            const formData = new FormData();
            formData.append('tender_file', uploadedFiles.tender);
            uploadedFiles.bids.forEach((file, index) => {
                formData.append('bid_files', file);
            });

            // 上传文件
            const response = await fetch('/api/init-upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.error) {
                throw new Error(result.error);
            }

            // 开始轮询分析进度
            await pollAnalysisProgress(result.project_id);

        } catch (error) {
            console.error('Error:', error);
            alert('上传失败: ' + error.message);
            progressBar.parentElement.style.display = 'none';
            progressText.textContent = '';
        }
    });

    // 轮询分析进度
    async function pollAnalysisProgress (projectId) {
        try {
            while (true) {
                const response = await fetch(`/api/projects/${projectId}/analysis-status`);
                const data = await response.json();

                if (data.error) {
                    throw new Error(data.error);
                }

                // 更新进度条
                let progress = 0;
                let currentRule = '正在处理...';

                // 处理可能的多种状态格式
                if (data.bids && data.bids.length > 0) {
                    // 计算总体进度
                    let totalCompleted = 0;
                    let totalRules = 0;

                    data.bids.forEach(bid => {
                        totalCompleted += bid.progress_completed || 0;
                        totalRules += bid.progress_total || 0;
                        // 使用最后一个bid的当前规则作为显示
                        if (bid.current_rule) {
                            currentRule = bid.current_rule;
                        }
                    });

                    if (totalRules > 0) {
                        progress = (totalCompleted / totalRules) * 100;
                    }
                }

                progressBar.style.width = `${progress}%`;
                progressBar.setAttribute('aria-valuenow', progress);
                progressText.textContent = currentRule;

                // 检查项目状态
                if (data.project_status === 'completed' || data.project_status === 'completed_with_errors') {
                    // 获取分析结果
                    const resultResponse = await fetch(`/api/projects/${projectId}/results`);
                    const resultData = await resultResponse.json();
                    displayResults(resultData);
                    break;
                }

                // 等待1秒再次查询
                await new Promise(resolve => setTimeout(resolve, 1000));
            }
        } catch (error) {
            console.error('Error:', error);
            progressText.textContent = '分析失败: ' + error.message;
            progressBar.parentElement.style.display = 'none';
        }
    }

    // 显示分析结果
    function displayResults (results) {
        progressBar.parentElement.style.display = 'none';
        progressText.textContent = '';

        // 检查是否有错误
        if (results.error) {
            resultArea.innerHTML = `
                <div class="alert alert-danger">
                    分析失败: ${results.error}
                </div>
            `;
            return;
        }

        // 确保results是数组格式
        const resultsArray = Array.isArray(results) ? results : [results];

        let html = '<div class="card"><div class="card-body"><h3 class="card-title">分析结果</h3>';

        resultsArray.forEach((result, index) => {
            html += `
                <div class="result-item mb-4">
                    <h4>投标人: ${result.bidder_name}</h4>
                    <div class="result-summary">
                        <div class="row">
                            <div class="col-md-6">
                                <h5>总得分: ${result.total_score ? result.total_score.toFixed(2) : 'N/A'}</h5>
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
                            <td>${score.criteria_name || 'N/A'}</td>
                            <td>${score.max_score || 'N/A'}</td>
                            <td>${score.score ? score.score.toFixed(2) : 'N/A'}</td>
                            <td>${score.reason || 'N/A'}</td>
                        </tr>
                    `;
                });
            } else {
                html += '<tr><td colspan="4">暂无详细评分数据</td></tr>';
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
});
