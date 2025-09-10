/*
 * @作者           : KingFreeDom
 * @创建时间         : 2025-09-04 21:51:35
 * @最近一次编辑者      : KingFreeDom
 * @最近一次编辑时间     : 2025-09-04 21:51:35
 * @文件相对于项目的路径   : \AI_env2\static\js\history.js
 * @
 * @Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved. 
 */
document.addEventListener('DOMContentLoaded', function () {
    const projectsTableBody = document.getElementById('projectsTableBody');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const errorMessage = document.getElementById('errorMessage');
    const errorText = document.getElementById('errorText');

    async function fetchProjects() {
        try {
            loadingIndicator.style.display = 'block';
            errorMessage.classList.add('d-none');

            const response = await fetch('/api/projects');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const projects = await response.json();

            renderProjects(projects);
        } catch (error) {
            console.error('Error fetching projects:', error);
            errorText.textContent = '无法加载项目列表，请稍后重试。';
            errorMessage.classList.remove('d-none');
        } finally {
            loadingIndicator.style.display = 'none';
        }
    }

    function renderProjects(projects) {
        projectsTableBody.innerHTML = '';
        if (projects.length === 0) {
            projectsTableBody.innerHTML = '<tr><td colspan="8" class="text-center">没有找到任何项目。</td></tr>';
            return;
        }

        projects.forEach(project => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${project.project_code}</td>
                <td>${project.name}</td>
                <td>${project.description}</td>
                <td>${new Date(project.created_at).toLocaleString()}</td>
                <td><span class="badge bg-${getStatusColor(project.status)}">${project.status}</span></td>
                <td>${project.bid_count}</td>
                <td>${project.result_count}</td>
                <td>
                    <button class="btn btn-primary btn-sm" onclick="viewProjectDetails(${project.id})">
                        <i class="fas fa-eye me-1"></i>查看详情
                    </button>
                </td>
            `;
            projectsTableBody.appendChild(row);
        });
    }

    function getStatusColor(status) {
        switch (status) {
            case 'completed':
                return 'success';
            case 'processing':
                return 'info';
            case 'error':
            case 'completed_with_errors':
                return 'danger';
            default:
                return 'secondary';
        }
    }

    window.viewProjectDetails = async function (projectId) {
        const modalBody = document.getElementById('projectDetailsModalBody');
        const modal = new bootstrap.Modal(document.getElementById('projectDetailsModal'));

        modalBody.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div></div>';
        modal.show();

        try {
            // 并行获取评标总表和原始分析结果（为了价格分）
            const [evalTableResponse, resultsResponse] = await Promise.all([
                fetch(`/api/projects/${projectId}/evaluation-table`),
                fetch(`/api/projects/${projectId}/results`)
            ]);

            if (!evalTableResponse.ok || !resultsResponse.ok) {
                throw new Error('无法获取项目结果，请稍后重试');
            }

            const evaluationTable = await evalTableResponse.json();
            const results = await resultsResponse.json();
            
            let content = `<h5>项目ID: ${projectId}</h5>`;

            // --- 1. 渲染详细的评标汇总表 ---
            content += '<h6><i class="fas fa-table me-2"></i>评标汇总表</h6>';
            if (evaluationTable && evaluationTable.headers && evaluationTable.rows) {
                content += '<div class="table-responsive">';
                content += '<table class="table table-bordered table-striped table-hover">';
                // 渲染表头
                content += '<thead class="table-dark"><tr>';
                evaluationTable.headers.forEach(header => {
                    content += `<th>${header}</th>`;
                });
                content += '</tr></thead>';
                // 渲染数据行
                content += '<tbody>';
                evaluationTable.rows.forEach(row => {
                    content += '<tr>';
                    row.forEach(cell => {
                        // 对数字类型进行格式化，保留两位小数
                        const cellValue = (typeof cell === 'number') ? cell.toFixed(2) : cell;
                        content += `<td>${cellValue}</td>`;
                    });
                    content += '</tr>';
                });
                content += '</tbody></table>';
                content += '</div>';
            } else {
                content += '<div class="alert alert-warning">无法加载详细的评标汇总表。</div>';
            }

            // --- 2. 渲染价格分详情表 ---
            content += '<h6 class="mt-4"><i class="fas fa-dollar-sign me-2"></i>价格分详情</h6>';
            if (results && results.length > 0) {
                const priceData = results.map(r => ({
                    bidder_name: r.bidder_name,
                    extracted_price: r.extracted_price,
                    price_score: r.price_score
                })).sort((a, b) => {
                    if (!a.extracted_price || a.extracted_price <= 0) return 1;
                    if (!b.extracted_price || b.extracted_price <= 0) return -1;
                    return a.extracted_price - b.extracted_price;
                });

                content += '<div class="table-responsive">';
                content += '<table class="table table-bordered">';
                content += '<thead class="table-light"><tr><th>价格排名</th><th>投标方</th><th>投标报价 (元)</th><th>价格得分</th></tr></thead><tbody>';
                priceData.forEach((data, index) => {
                    const priceDisplay = data.extracted_price ? data.extracted_price.toLocaleString('zh-CN', { style: 'currency', currency: 'CNY' }) : 'N/A';
                    const priceScoreDisplay = data.price_score !== null ? data.price_score.toFixed(2) : 'N/A';
                    content += `<tr><td>${index + 1}</td><td>${data.bidder_name}</td><td>${priceDisplay}</td><td>${priceScoreDisplay}</td></tr>`;
                });
                content += '</tbody></table>';
                content += '</div>';
            } else {
                content += '<div class="alert alert-warning">没有找到价格分详细信息。</div>';
            }

            modalBody.innerHTML = content;

        } catch (error) {
            console.error('获取项目详情失败:', error);
            modalBody.innerHTML = `<div class="alert alert-danger">${error.message}</div>`;
        }
    };

    fetchProjects();
});