# Trace Walkthrough

`traces/success.jsonl` 展示一次完整研究循环：

1. `run.start`：记录问题和 Run ID。
2. `model.request`：Harness 请求下一步决策。
3. `tool.request(list_files)` / `tool.result`：观察仓库文件。
4. `tool.request(search_text)` / `tool.result`：定位 `login` 的真实路径和行号。
5. `tool.request(read_file)` / `tool.result`：读取命中位置附近的代码。
6. `model.final`：根据 Observation 生成最终回答。
7. `loop.stop(final_answer)`：记录正常停止原因。

`traces/failure.jsonl` 展示权限失败仍可诊断：

1. 模型请求 `read_file("../../secret.txt")`。
2. Repository Boundary 抛出 `PermissionError`。
3. Registry 把异常转换为 `ok: false` 的 Observation。
4. Harness 记录完整 `tool.result`，循环没有崩溃。

Trace 是审计证据，不是可恢复 Session；Day 4 才引入 Session Store。

