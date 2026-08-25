# 任务书证据归档说明

本目录用于保存任务 3.5 的脱敏验收材料，不放置真实简历、API Key 或未经脱敏的日志。

建议的截图文件名：

1. `01-environment.png`：Python、虚拟环境和主要依赖版本；
2. `02-run.png`：命令行运行及完成提示；
3. `03-report.png`：报告评分、完整度、硬门槛和证据匹配；
4. `04-api-log.png`：`agent.log` 中的模型调用成功和工具调用记录；
5. `05-tests.png`：`pytest` 测试通过结果；
6. `06-bailian-console.png`（可选）：阿里云百炼调用记录，需隐藏账号和密钥。

关键代码片段可从以下文件截取：

- `app.py`：程序入口；
- `services/analyzer.py`：Agent 编排和模型调用；
- `tools/parse_document_tool.py`：文档工具；
- `services/normalization.py`：结构归一化、项目维度修正和引文校验；
- `services/scorer.py`：评分公式；
- `services/reporter.py`：报告生成。

运行产物默认位于 `workspace/output/`，日志位于 `workspace/logs/`。这些目录被 `.gitignore` 忽略，提交前应仅复制脱敏后的摘要或截图到本目录。
