// static/js/charts.js

// 存放Chart实例，方便管理
const charts = {};

/**
 * 渲染所有图表
 * @param {Array} data - 分析结果数据
 */
export function renderAllCharts(data) {
    renderTotalScoreCharts(data);
    renderPriceAnalysisCharts(data);
}

/**
 * 切换显示的图表视图
 * @param {string} type - 图表类型 ('total', 'price')
 */
export function switchChartView(type) {
    document.getElementById('totalScoreChart').style.display = 'none';
    document.getElementById('priceAnalysisChart').style.display = 'none';

    const chartId = type === 'price' ? 'priceAnalysisChart' : 'totalScoreChart';
    document.getElementById(chartId).style.display = 'block';
}

/**
 * 导出当前可见的图表为PNG图片
 */
export function exportCharts() {
    const activeChartContainer = document.querySelector('#chartView .chart-container[style*="block"]');
    if (!activeChartContainer) {
        alert('没有可导出的图表');
        return;
    }

    const canvas = activeChartContainer.querySelector('canvas');
    if (!canvas) {
        alert('图表数据不可用');
        return;
    }

    const link = document.createElement('a');
    link.download = '投标分析图表.png';
    link.href = canvas.toDataURL('image/png', 1.0);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// --- Private Helper Functions ---

/**
 * 渲染总分相关的图表（条形图和分布图）
 * @param {Array} data - 分析结果数据
 */
function renderTotalScoreCharts(data) {
    // 1. 总分对比条形图
    const scoreCtx = document.getElementById('scoreChart').getContext('2d');
    if (charts.scoreChart) {
        charts.scoreChart.destroy();
    }

    const bidderNames = data.map(result => result.bidder_name);
    const totalScores = data.map(result =>
        result.total_score === '废标' ? 0 : (result.total_score || 0)
    );

    charts.scoreChart = new Chart(scoreCtx, {
        type: 'bar',
        data: {
            labels: bidderNames,
            datasets: [{
                label: '总分',
                data: totalScores,
                backgroundColor: 'rgba(54, 162, 235, 0.7)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: { display: true, text: '各投标人总分对比' },
                legend: { display: false }
            },
            scales: { y: { beginAtZero: true, max: 100 } }
        }
    });

    // 2. 投标人状态分布饼图
    const distributionCtx = document.getElementById('scoreDistributionChart').getContext('2d');
    if (charts.distributionChart) {
        charts.distributionChart.destroy();
    }

    const validScores = totalScores.filter(score => score > 0);
    const invalidCount = data.length - validScores.length;

    charts.distributionChart = new Chart(distributionCtx, {
        type: 'doughnut',
        data: {
            labels: ['有效投标人', '废标投标人'],
            datasets: [{
                data: [validScores.length, invalidCount],
                backgroundColor: ['rgba(75, 192, 192, 0.7)', 'rgba(255, 99, 132, 0.7)'],
                borderColor: ['rgba(75, 192, 192, 1)', 'rgba(255, 99, 132, 1)'],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: { display: true, text: '投标人状态分布' }
            }
        }
    });
}

/**
 * 渲染价格分析相关的图表和表格
 * @param {Array} data - 分析结果数据
 */
function renderPriceAnalysisCharts(data) {
    const priceData = data.filter(d => d.extracted_price !== null && d.extracted_price > 0);

    const container = document.getElementById('priceAnalysisChart');
    if (priceData.length === 0) {
        container.innerHTML = '<div class="alert alert-info">没有有效的报价信息可供分析。</div>';
        return;
    }

    // 确保容器内容被重置
    container.innerHTML = `
        <div class="row">
            <div class="col-md-7">
                <canvas id="priceChartCanvas" height="100"></canvas>
            </div>
            <div class="col-md-5">
                <div id="price-table-container"></div>
            </div>
        </div>
    `;

    // 1. 渲染价格表格
    priceData.sort((a, b) => a.extracted_price - b.extracted_price);
    const tableContainer = document.getElementById('price-table-container');
    let tableHtml = `
        <table class="table table-sm table-striped table-hover">
            <thead class="table-light">
                <tr><th>排名</th><th>投标人</th><th>投标报价 (元)</th></tr>
            </thead>
            <tbody>
                ${priceData.map((result, index) => `
                    <tr>
                        <td><span class="badge bg-secondary">${index + 1}</span></td>
                        <td>${result.bidder_name}</td>
                        <td><strong>${result.extracted_price.toLocaleString('zh-CN')}</strong></td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
    tableContainer.innerHTML = tableHtml;

    // 2. 渲染价格图表
    const chartCanvas = document.getElementById('priceChartCanvas').getContext('2d');
    if (charts.priceChart) {
        charts.priceChart.destroy();
    }
    charts.priceChart = new Chart(chartCanvas, {
        type: 'bar',
        data: {
            labels: priceData.map(d => d.bidder_name),
            datasets: [{
                label: '投标报价 (元)',
                data: priceData.map(d => d.extracted_price),
                backgroundColor: 'rgba(255, 159, 64, 0.6)',
                borderColor: 'rgba(255, 159, 64, 1)',
                borderWidth: 1
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: { callback: value => value.toLocaleString('zh-CN') + ' 元' }
                }
            },
            plugins: {
                legend: { display: false },
                title: { display: true, text: '各投标人报价对比' },
                tooltip: {
                    callbacks: {
                        label: context => '报价: ' + context.parsed.x.toLocaleString('zh-CN') + ' 元'
                    }
                }
            }
        }
    });
}
