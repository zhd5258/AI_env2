1、上传的文件应保存在临时文件目录下，项目分析结束时弹出提示框，询问是否删除临时文件。
2、temp_pdf_cache目录下生成的中间文件在项目结束时弹出提示框，询问是否删除临时文件。
3、既然项目生成了temp_word下的文本文件，是否不再需要生成temp_pdf_cache下的JSON文件？评估后作出修改或优化
4、投标人名称的确认流程存在错误，正确的流程是在分析前以投标文件的文件名代替，全部投标文件分析完成后，使用AI分析得到的每个投保人的名称更新替换，并在前端弹出窗口确认，并根据确认后的名称更新已经存储的数据库的相关字段值，并更新前端的表格内容。
5、运行时存在大量错误：

5.1、 Traceback (most recent call last):
  File "/media/kr/软件/user/PythonProject/AI_env2/main.py", line 476, in analysis_task
    analyzer = IntelligentBidAnalyzer(
  File "/media/kr/软件/user/PythonProject/AI_env2/modules/intelligent_bid_analyzer.py", line 28, in __init__
    self.price_manager = PriceManager()
NameError: name 'PriceManager' is not defined

5.2、main.js:71  POST http://127.0.0.1:8000/api/upload 404 (Not Found)

（匿名） @ main.js:71
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
main.js:97  GET http://127.0.0.1:8000/api/projects/undefined/analysis-status 422 (Unprocessable Entity)
pollAnalysisProgress @ main.js:97
await in pollAnalysisProgress
（匿名） @ main.js:83
app.js:382  GET http://127.0.0.1:8000/api/projects/40/results 404 (Not Found)
fetchAndDisplayResults @ app.js:382
pollProgress @ app.js:308
await in pollProgress
（匿名） @ app.js:286
setInterval
startPolling @ app.js:286
（匿名） @ app.js:268
app.js:399 获取结果或规则时出错: Error: 获取分析结果失败: Not Found
    at fetchAndDisplayResults (app.js:387:23)
    at async pollProgress (app.js:308:17)
fetchAndDisplayResults @ app.js:399
await in fetchAndDisplayResults
pollProgress @ app.js:308
await in pollProgress
（匿名） @ app.js:286
setInterval
startPolling @ app.js:286
（匿名） @ app.js:268
