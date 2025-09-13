// 搜索和过滤功能模块

/**
 * 绑定搜索和过滤事件
 */
function bindSearchAndFilterEvents() {
    // 搜索功能
    const searchInput = document.getElementById('tableSearch');
    if (searchInput) {
        searchInput.addEventListener('input', function () {
            filterTable();
        });
    }

    // 过滤功能
    const filterSelect = document.getElementById('scoreFilter');
    if (filterSelect) {
        filterSelect.addEventListener('change', function () {
            filterTable();
        });
    }
}

/**
 * 过滤表格数据
 */
function filterTable() {
    const searchTerm = document.getElementById('tableSearch').value.toLowerCase();
    const filterValue = document.getElementById('scoreFilter').value;

    // 基于原始数据进行过滤
    let filteredData = [...window.resultsData];

    // 应用搜索过滤
    if (searchTerm) {
        filteredData = filteredData.filter(result =>
            result.bidder_name.toLowerCase().includes(searchTerm)
        );
    }

    // 应用状态过滤
    if (filterValue === 'valid') {
        filteredData = filteredData.filter(result =>
            result.total_score !== '废标'
        );
    } else if (filterValue === 'invalid') {
        filteredData = filteredData.filter(result =>
            result.total_score === '废标'
        );
    }

    // 更新过滤后的数据
    window.filteredResultsData = filteredData;

    // 重新渲染表格
    if (typeof renderResultsTable === 'function') {
        renderResultsTable();
    }
}

// 导出函数供其他模块使用
window.bindSearchAndFilterEvents = bindSearchAndFilterEvents;
window.filterTable = filterTable;