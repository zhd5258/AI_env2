// 导出相关功能模块

/**
 * 导出表格为CSV格式
 */
window.exportTableToCSV = function () {
    const table = document.getElementById('resultsTable');
    if (!table) {
        console.error('找不到结果表格');
        return;
    }
    
    const rows = table.querySelectorAll('tr');
    const csv = [];

    rows.forEach(row => {
        const cells = row.querySelectorAll('th, td');
        const rowValues = Array.from(cells).map(cell => {
            // 处理包含HTML的内容，只提取文本
            const text = cell.textContent || cell.innerText || '';
            // 如果包含逗号或换行符，需要加引号
            if (text.includes(',') || text.includes('\n')) {
                return `"${text.replace(/"/g, '""')}"`;
            }
            return text;
        });
        csv.push(rowValues.join(','));
    });

    const csvString = csv.join('\n');
    const blob = new Blob(['\uFEFF' + csvString], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = '投标评分结果.csv';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
};

/**
 * 导出图表为图片
 */
window.exportCharts = function () {
    const activeChartContainer = document.querySelector('#chartView .chart-container[style*="block"]');
    if (!activeChartContainer) {
        alert('没有可导出的图表');
        return;
    }

    // 获取当前显示的图表
    const canvas = activeChartContainer.querySelector('canvas');
    if (!canvas) {
        alert('图表数据不可用');
        return;
    }

    // 创建下载链接
    const link = document.createElement('a');
    link.download = '投标分析图表.png';
    link.href = canvas.toDataURL('image/png', 1.0);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
};