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
    const paginationControls = document.getElementById('paginationControls');

    let allProjects = [];
    let currentPage = 1;
    const projectsPerPage = 10;

    async function fetchProjects () {
        try {
            loadingIndicator.style.display = 'block';
            errorMessage.classList.add('d-none');

            const response = await fetch('/api/projects');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            allProjects = await response.json();

            // 初始显示第一页
            displayProjectsPage(1);
        } catch (error) {
            console.error('Error fetching projects:', error);
            errorText.textContent = '无法加载项目列表，请稍后重试。';
            errorMessage.classList.remove('d-none');
        } finally {
            loadingIndicator.style.display = 'none';
        }
    }

    function displayProjectsPage (page) {
        currentPage = page;
        const startIndex = (page - 1) * projectsPerPage;
        const endIndex = startIndex + projectsPerPage;
        const projectsToShow = allProjects.slice(startIndex, endIndex);

        renderProjects(projectsToShow);
        renderPaginationControls();
    }

    function renderPaginationControls () {
        const totalPages = Math.ceil(allProjects.length / projectsPerPage);
        if (totalPages <= 1) {
            paginationControls.innerHTML = '';
            return;
        }

        let paginationHTML = `
            <nav>
                <ul class="pagination justify-content-center">
        `;

        // Previous button
        paginationHTML += `
            <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="changePage(${currentPage - 1})">上一页</a>
            </li>
        `;

        // Page numbers
        for (let i = 1; i <= totalPages; i++) {
            if (i === currentPage) {
                paginationHTML += `
                    <li class="page-item active">
                        <span class="page-link">${i}</span>
                    </li>
                `;
            } else if (i === 1 || i === totalPages || (i >= currentPage - 2 && i <= currentPage + 2)) {
                paginationHTML += `
                    <li class="page-item">
                        <a class="page-link" href="#" onclick="changePage(${i})">${i}</a>
                    </li>
                `;
            } else if (i === currentPage - 3 || i === currentPage + 3) {
                paginationHTML += `
                    <li class="page-item disabled">
                        <span class="page-link">...</span>
                    </li>
                `;
            }
        }

        // Next button
        paginationHTML += `
            <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="changePage(${currentPage + 1})">下一页</a>
            </li>
        `;

        paginationHTML += `
                </ul>
            </nav>
        `;

        paginationControls.innerHTML = paginationHTML;
    }

    function renderProjects (projects) {
        projectsTableBody.innerHTML = '';
        if (projects.length === 0) {
            projectsTableBody.innerHTML = '<tr><td colspan="8" class="text-center">没有找到任何项目。</td></tr>';
            return;
        }

        projects.forEach(project => {
            // 计算用时信息
            let timeInfo = '';
            if (project.analysis_start_time) {
                if (project.analysis_end_time) {
                    // 分析已完成，计算总用时
                    const start = new Date(project.analysis_start_time);
                    const end = new Date(project.analysis_end_time);
                    const totalTime = (end - start) / 1000; // 转换为秒
                    const minutes = Math.floor(totalTime / 60);
                    const seconds = Math.floor(totalTime % 60);
                    timeInfo = `<span class="badge bg-success">总用时: ${minutes}分${seconds}秒</span>`;
                } else if (project.status === 'processing' || project.status === 'analyzing') {
                    // 分析进行中，显示"进行中"
                    timeInfo = '<span class="badge bg-info">分析中</span>';
                }
            }

            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${project.project_code}</td>
                <td>${project.name}</td>
                <td>${project.description}</td>
                <td>${new Date(project.created_at).toLocaleString()}</td>
                <td>
                    <span class="badge bg-${getStatusColor(project.status)}">${project.status}</span>
                    ${timeInfo}
                </td>
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

    function getStatusColor (status) {
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

    function simplifyName (name, maxLength = 10) {
        if (typeof name !== 'string' || name.length <= maxLength) {
            return { simplified: name, full: name };
        }
        return {
            simplified: name.substring(0, maxLength) + '...',
            full: name
        };
    }

    window.changePage = function (page) {
        displayProjectsPage(page);
    };

    window.viewProjectDetails = async function (projectId) {
        const modalBody = document.getElementById('projectDetailsModalBody');
        const modal = new bootstrap.Modal(document.getElementById('projectDetailsModal'));

        modalBody.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div></div>';
        modal.show();

        try {
            // 获取项目进度信息以获取用时数据
            const progressResponse = await fetch(`/api/projects/${projectId}/progress`);
            const progressData = await progressResponse.json();

            // 获取项目汇总数据
            const response = await fetch(`/api/projects/${projectId}/dynamic-summary`);

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || '无法获取项目结果，请稍后重试');
            }

            const summaryData = await response.json();

            let content = `<h5>项目ID: ${projectId}</h5>`;

            // 添加用时信息
            if (progressData.total_time !== null) {
                const minutes = Math.floor(progressData.total_time / 60);
                const seconds = Math.floor(progressData.total_time % 60);
                content += `<p><strong>总用时:</strong> ${minutes}分${seconds}秒</p>`;
            } else if (progressData.elapsed_time !== null) {
                const minutes = Math.floor(progressData.elapsed_time / 60);
                const seconds = Math.floor(progressData.elapsed_time % 60);
                content += `<p><strong>已用时:</strong> ${minutes}分${seconds}秒</p>`;
            }

            content += '<h6><i class="fas fa-table me-2"></i>评标汇总表</h6>';
            if (summaryData && summaryData.header_rows && summaryData.rows) {
                content += '<div class="table-responsive">';
                content += '<table class="table table-bordered table-striped table-hover">';

                // 渲染多层表头
                content += '<thead class="table-dark">';
                summaryData.header_rows.forEach(headerRowData => {
                    content += '<tr>';
                    headerRowData.forEach(headerCell => {
                        const colspan = headerCell.colspan ? `colspan="${headerCell.colspan}"` : '';
                        const rowspan = headerCell.rowspan ? `rowspan="${headerCell.rowspan}"` : '';

                        // 对子项名称进行简化
                        const isChildItem = !headerCell.colspan && !headerCell.rowspan;
                        const nameInfo = isChildItem ? simplifyName(headerCell.name) : { simplified: headerCell.name, full: headerCell.name };

                        const title = (nameInfo.simplified !== nameInfo.full) ? `title="${nameInfo.full}"` : '';

                        content += `<th ${colspan} ${rowspan} ${title}>${nameInfo.simplified}</th>`;
                    });
                    content += '</tr>';
                });
                content += '</thead>';

                // 渲染数据行
                content += '<tbody>';
                summaryData.rows.forEach(rowData => {
                    content += '<tr>';
                    content += `<td>${rowData.rank}</td>`;
                    content += `<td>${rowData.bidder_name}</td>`;

                    rowData.scores.forEach(score => {
                        const cellValue = (typeof score === 'number') ? score.toFixed(2) : (score === null ? 'N/A' : score);
                        content += `<td>${cellValue}</td>`;
                    });

                    const priceScore = (typeof rowData.price_score === 'number') ? rowData.price_score.toFixed(2) : 'N/A';
                    const totalScore = (typeof rowData.total_score === 'number') ? rowData.total_score.toFixed(2) : 'N/A';
                    content += `<td>${priceScore}</td>`;
                    content += `<td>${totalScore}</td>`;

                    content += '</tr>';
                });
                content += '</tbody></table>';
                content += '</div>';

                // 图表区：各投标方总分/价格分对比
                const labels = summaryData.rows.map(r => r.bidder_name);
                const totalScores = summaryData.rows.map(r => (typeof r.total_score === 'number' ? r.total_score : 0));
                const priceScores = summaryData.rows.map(r => (typeof r.price_score === 'number' ? r.price_score : 0));

                content += '<div class="mt-4">';
                content += '<h6><i class="fas fa-chart-bar me-2"></i>各投标方总分与价格分对比</h6>';
                content += '<div style="height: 320px;"><canvas id="summaryChart"></canvas></div>';
                content += '</div>';

                // 详细评分表：为每个投标方生成一行详细表
                const childHeaders = (summaryData.header_rows[1] || []).map(h => h.name);
                content += '<div class="mt-4">';
                content += '<h6><i class="fas fa-list-ul me-2"></i>各投标方详细评分</h6>';
                summaryData.rows.forEach(rowData => {
                    content += '<div class="card mb-3">';
                    content += `<div class="card-header"><strong>${rowData.bidder_name}</strong></div>`;
                    content += '<div class="card-body">';
                    content += '<div class="table-responsive">';
                    content += '<table class="table table-sm table-bordered">';
                    content += '<thead><tr>';
                    childHeaders.forEach(h => { content += `<th>${h}</th>`; });
                    content += '<th>价格分</th><th>总分</th>';
                    content += '</tr></thead>';
                    content += '<tbody><tr>';
                    (rowData.scores || []).forEach(score => {
                        const cellValue = (typeof score === 'number') ? score.toFixed(2) : (score === null ? 'N/A' : score);
                        content += `<td>${cellValue}</td>`;
                    });
                    const priceScore = (typeof rowData.price_score === 'number') ? rowData.price_score.toFixed(2) : 'N/A';
                    const totalScore = (typeof rowData.total_score === 'number') ? rowData.total_score.toFixed(2) : 'N/A';
                    content += `<td>${priceScore}</td><td>${totalScore}</td>`;
                    content += '</tr></tbody>';
                    content += '</table>';
                    content += '</div>';
                    content += '</div>';
                    content += '</div>';
                });
                content += '</div>';
            } else {
                content += `<div class="alert alert-warning">${summaryData.error || '无法加载详细的评标汇总表。'}</div>`;
            }

            modalBody.innerHTML = content;

            // 渲染图表（添加错误处理）
            if (summaryData && summaryData.rows) {
                const ctx = document.getElementById('summaryChart');
                if (ctx) {
                    // 检查Chart是否已定义
                    if (typeof Chart !== 'undefined') {
                        new Chart(ctx, {
                            type: 'bar',
                            data: {
                                labels: summaryData.rows.map(r => r.bidder_name),
                                datasets: [
                                    { label: '总分', data: summaryData.rows.map(r => (typeof r.total_score === 'number' ? r.total_score : 0)), backgroundColor: 'rgba(54, 162, 235, 0.6)' },
                                    { label: '价格分', data: summaryData.rows.map(r => (typeof r.price_score === 'number' ? r.price_score : 0)), backgroundColor: 'rgba(255, 159, 64, 0.6)' }
                                ]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                plugins: { legend: { position: 'top' } },
                                scales: { y: { beginAtZero: true } }
                            }
                        });
                    } else {
                        // 如果Chart未定义，显示错误消息
                        ctx.innerHTML = '<div class="alert alert-warning">图表库加载失败，无法显示图表。</div>';
                    }
                }
            }

        } catch (error) {
            console.error('获取项目详情失败:', error);
            modalBody.innerHTML = `<div class="alert alert-danger">${error.message}</div>`;
        }
    };

    fetchProjects();
});
