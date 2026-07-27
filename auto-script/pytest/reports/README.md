# reports 目录

pytest 运行完成后 pytest-html 报告自动生成到本目录：

- 默认报告文件：`report.html`（由 `pytest.ini` 的 `addopts --html=reports/report.html` 触发）
- 每次运行会覆盖同名文件；如需保留历史，请在命令行指定带时间戳的文件名，例如：

```bash
pytest --html=reports/report_%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%.html --self-contained-html
```

本目录建议加入 `.gitignore`（避免报告入库污染仓库）：
```
reports/*.html
reports/logs/
```
