// 测试文件选择功能
function testFileSelection () {
    console.log("测试文件选择功能");

    // 创建一个模拟的文件对象
    const mockFile = new File(["content"], "test.pdf", { type: "application/pdf" });

    // 设置全局变量
    selectedTenderFile = mockFile;

    // 调用更新文件列表函数
    updateFileList();

    console.log("文件列表已更新");
}

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function () {
    console.log("页面加载完成");
});
