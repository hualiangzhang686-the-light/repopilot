# Day 1 Design Decisions

## 一个循环

Agent Loop 只处理四件事：请求模型决策、识别最终答案、把 Tool Call 交给 Registry、将 Observation 放回历史。路径解析、文件读取和 Trace 序列化不进入循环。

## Typed Tool，而不是 Bash-only

Day 1 使用 `list_files`、`search_text`、`read_file` 三个窄接口。这样能独立验证参数、权限和错误，也不会提前开放任意 Shell。Bash-only 更灵活，但其命令权限与结果解析留到后续沙箱阶段。

## ScriptedModel，而不是真实 API

离线 Model Double 让完整循环、停止条件和 Trace 可以确定性回归。它验证的是 Harness 机制，不是模型推理质量；真实 Provider 留到最终交付阶段接入。

## Harness 统一 Trace

工具自身不写审计日志。Harness 在模型请求、工具请求、工具结果和停止边界统一记录，因此未知工具、权限拒绝和异常也不会漏记。

## Day 1 安全边界

只开放仓库内读取；绝对路径、`..` 和符号链接最终都必须解析到 Repository Root 内。写入、执行和外部操作没有注册，因此不是“默认拒绝后仍可绕过”，而是根本不存在对应能力。

