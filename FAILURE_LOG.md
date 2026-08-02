# Failure Log

## Day 1

### 仓库外路径读取

- 场景：模型请求 `read_file` 读取 `../../secret.txt`。
- 预期：Repository Boundary 拒绝访问，Registry 将异常转为失败 Observation，Agent Loop 保持运行并记录 Trace。
- 验证入口：`python examples/run_failure_demo.py`。
- Trace：`traces/failure.jsonl`。

### 当前限制

- 总超时尚不能中断已经阻塞的第三方函数；当前三个内置工具均为本地只读短操作。
- `ScriptedModel` 只覆盖确定性研究流程，不衡量真实模型推理质量。
