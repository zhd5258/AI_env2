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
            // 调用新的动态汇总API
            const response = await fetch(`/api/projects/${projectId}/dynamic-summary`);

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || '无法获取项目结果，请稍后重试');
            }

            const summaryData = await response.json();
            
            let content = `<h5>项目ID: ${projectId}</h5>`;

            // --- 渲染动态生成的评标汇总表 ---
            content += '<h6><i class="fas fa-table me-2"></i>评标汇总表</h6>';
            if (summaryData && summaryData.headers && summaryData.rows) {
                content += '<div class="table-responsive">';
                content += '<table class="table table-bordered table-striped table-hover">';
                
                // 渲染表头
                content += '<thead class="table-dark"><tr>';
                summaryData.headers.forEach(header => {
                    content += `<th>${header}</th>`;
                });
                content += '</tr></thead>';
                
                // 渲染数据行
                content += '<tbody>';
                summaryData.rows.forEach(rowData => {
                    content += '<tr>';
                    // 排名和投标人名称
                    content += `<td>${rowData.rank}</td>`;
                    content += `<td>${rowData.bidder_name}</td>`;
                    
                    // 各评分项得分
                    rowData.scores.forEach(score => {
                        const cellValue = (typeof score === 'number') ? score.toFixed(2) : (score === null ? 'N/A' : score);
                        content += `<td>${cellValue}</td>`;
                    });
                    
                    // 价格分和总分
                    const priceScore = (typeof rowData.price_score === 'number') ? rowData.price_score.toFixed(2) : 'N/A';
                    const totalScore = (typeof rowData.total_score === 'number') ? rowData.total_score.toFixed(2) : 'N/A';
                    content += `<td>${priceScore}</td>`;
                    content += `<td>${totalScore}</td>`;

                    content += '</tr>';
                });
                content += '</tbody></table>';
                content += '</div>';
            } else {
                content += `<div class="alert alert-warning">${summaryData.error || '无法加载详细的评标汇总表。'}</div>`;
            }

            modalBody.innerHTML = content;

        } catch (error) {
            console.error('获取项目详情失败:', error);
            modalBody.innerHTML = `<div class="alert alert-danger">${error.message}</div>`;
        }
    };

    fetchProjects();
});