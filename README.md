# RepoPilot — Day 1

RepoPilot 是一个面向中小型 Python 仓库的代码研究 Agent。Day 1 版本只实现确定性、只读的最小闭环：

```text
Question → ScriptedModel → Tool Call → Registry → Observation
         ←───────────────────────────────────────────────┘
                         ↓
                    Final Answer
```

## 已实现

- `repopilot research <repo> "<question>"` CLI。
- 可替换的 Model 接口与离线 `ScriptedModel`。
- `list_files`、`search_text`、`read_file` 三个只读工具。
- Tool Registry；新增工具不需要修改 Agent Loop。
- 仓库根目录边界校验。
- 最大工具步数、总超时、重复调用熔断。
- 工具异常转为结构化 Observation。
- JSONL Trace。
- 自动化单元测试与成功/失败 Trace 示例。

## 快速运行

要求 Python 3.11+，无第三方运行时依赖。

```powershell
cd "D:\codex\output\repopilot"
python -m pip install -e .
repopilot research ./examples/demo_repo "登录逻辑在哪个文件？" --trace ./traces/success.jsonl
python ./examples/run_failure_demo.py
python -m unittest discover -s tests -v
```

不安装也可以运行：

```powershell
$env:PYTHONPATH="./src"
python -m repopilot research ./examples/demo_repo "登录逻辑在哪个文件？"
```

预期回答会引用 `app/auth.py` 及真实行号。默认模型是确定性的教学替身，不会调用远程 LLM。

## 目录

```text
src/repopilot/
├── agent/          # Model 接口、Agent Loop、停止条件
├── tools/          # Tool 定义、Registry、只读文件工具
├── harness/        # 仓库路径边界与 JSONL Trace
└── cli.py
tests/              # 机制级测试
examples/demo_repo/ # 可重复的演示仓库
traces/             # 成功与失败示例 Trace
```

## 设计边界

- Day 1 不接入真实 LLM、向量检索、写文件、Shell、Session、Reviewer 或 Multi-Agent。
- 总超时是协作式边界：会在每轮模型决策和工具执行之间检查；Day 4 再为可阻塞工具加入进程级超时。
- `ScriptedModel` 只为验证 Harness，不代表真实代码理解能力。
- `search_text` 是确定性的文本检索；AST、混合检索与 Evidence Ledger 属于 Day 2。

## 相关知识点

- Observe → Think → Act → Observe
- Tool Schema、Handler、Registry 与 Dispatch
- 模型提出动作，Harness 决定是否执行
- 结构化 Observation
- 最大步数、超时、重复调用熔断
- Repository Root 路径边界
- JSONL Trace 与可诊断性
- Model Double 与确定性测试

