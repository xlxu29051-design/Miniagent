# minimal-agent — 从零实现的最小可用 Agent

一个**不依赖任何 Agent 框架**（无 langgraph / openhands / openclaw 等）、完全用标准
Python 手写的最小可用 LLM Agent。核心 Agent Runtime、工具注册、输出解析、循环控制、
session 与 context 管理全部自行实现，只用一个官方 `openai` SDK 作为与「OpenAI 兼容」
LLM 服务通信的 HTTP 客户端。

```
agent/
  runtime.py     # 核心循环（接收输入 → 判断回复/调用工具 → 执行 → 继续/结束）
  parser.py      # 解析 LLM 输出：提取 thought / tool 调用 / final 答案
  session.py     # Session + SessionManager + context/memory/压缩
  llm.py         # OpenAI 兼容客户端 + 测试用 MockLLM
  trace.py       # 执行 trace / 日志
  tools/
    base.py      # Tool + ToolRegistry（名称/描述/参数 Schema + 校验）
    calculator.py  search.py(mock)  weather.py(mock)  todo.py(按 session 隔离)
cli.py           # 交互式多 session 命令行
demo.py          # 作业「两个窗口」场景的脚本化演示
tests/           # pytest 测试用例
conftest.py      # 让 pytest -v -s 打印每条用例的说明与真实输入/输出
```

## 运行方式

### 1. 安装依赖
```bash
pip install -r requirements.txt   # 只需要 openai
```

### 2. 配置真实 LLM API（任意 OpenAI 兼容服务）
```bash
cp .env.example .env    # 填入 key，然后 source .env
```
通过三个环境变量切换 provider：

| 变量 | 说明 | 例子 |
|------|------|------|
| `LLM_API_KEY` | 必填，API key | `sk-...` |
| `LLM_BASE_URL` | 选填，服务地址 | 阿里云百炼 `https://ws-....maas.aliyuncs.com/compatible-mode/v1` |
| `LLM_MODEL` | 选填，模型名 | `qwen3.7-plus` / `deepseek-chat` / `gpt-4o-mini` |

Windows PowerShell 下用 `$env:LLM_API_KEY="sk-..."` 逐个设置。

### 3. 交互式 CLI（多 session）
```bash
python cli.py
```
命令：`/new [name]` 新建并切换 session、`/switch <id|name>` 切换、`/sessions` 列表、
`/todos` 查看待办、`/remember <fact>` 写入长期记忆、`/trace` 开关 trace、`/quit` 退出。
其余输入直接发给当前 session 的 agent。未设置 key 时自动进入 MOCK 模式。

### 4. 脚本化演示（作业「两个窗口」场景）
```bash
source .env && python demo.py
```

### 5. 运行测试
```bash
python -m pytest -q         # 27 个用例，全部使用 MockLLM，无需联网
python -m pytest -v -s      # 详细模式：打印每条用例验证的功能 + 真实输入/输出
```

## 系统设计

### Agent 循环（`runtime.py`）
每收到一条用户消息，执行如下循环（最多 `max_turns` 轮，默认 8）：
1. **组装 context**：system prompt（角色 + 工具 Schema + 记忆 + 摘要）+ 最近历史；
2. **调用 LLM** 得到一条决策；
3. **解析**为 `thought` + （`tool 调用` 或 `final 答案`）；
4. `final` → 返回用户；`tool` → 执行工具、把 observation 追加进历史，继续循环；
5. 达到 `max_turns` 仍无最终答案 → 返回兜底提示（安全上界）。

### 工具注册与 Schema 驱动决策（`tools/`）
每个工具是一个 `Tool(name, description, parameters(JSON-Schema), func)`，注册进
`ToolRegistry`。工具的 Schema 会被渲染进 system prompt，**LLM 依据 Schema 自主决定**
调什么工具、传什么参数。调用前 `ToolRegistry` 做参数校验（必填项、未知参数），
运行期异常统一包装成 `ToolError`。已实现四个工具：
- `calculator`：基于 AST 的**安全**四则/函数运算（不使用 `eval`）；
- `search`：**mock** 搜索，结果确定性（便于测试复现）；
- `weather`：**mock** 天气，按城市名确定性生成；
- `todo`：**按 session 隔离**的待办列表（add / list / complete）。

### LLM 输出解析（`parser.py`）
不依赖 provider 原生 function-calling，自行约定并解析 JSON 协议：
```json
{"thought": "...", "action": {"tool": "calculator", "args": {"expression": "2+2"}}}
{"thought": "...", "final": "给用户的最终答案"}
```
解析器对模型常见「不听话」有容错：能从 ```json 代码块、夹杂散文中**提取第一个配平的
JSON 对象**（正确处理字符串内的花括号），失败时抛 `ParseError`，循环会要求模型按格式
重试而不是直接崩溃。

### Session 管理（`session.py`）
`SessionManager` 用 id 索引多个 `Session`，彼此完全独立——用户 A 的窗口 1（查天气记待办）
与窗口 2（写周报记待办）各自持有**独立的历史、待办列表、工具注册表和记忆**，可随时切回
任一窗口继续，互不影响（见 `tests/test_session.py::test_sessions_are_isolated`）。

### Context 的有效管理 / memory 的召回时机与放置方式（作业重点）
- **放什么进 context**：
  - *工作记忆*：最近若干轮的完整对话消息（用户输入、Agent 的 thought+决策、工具 observation）——
    工具结果以 `Observation from <tool>: ...` 追加为一条消息，让模型在后续轮次「看到」结果。
  - *长期记忆（facts）*：通过 `/remember` 或代码写入 `session.facts` 的持久事实。
  - *摘要（summary）*：上下文过长时压缩得到的旧对话浓缩。
- **召回时机与放置方式**：记忆在**每一轮组装 prompt 时**（`Session.build_messages` →
  `system_prompt`）被召回，统一放进 **system 消息**的顶部——即
  `基础提示 + 工具 Schema + Remembered facts + Summary`，随后接最近的历史消息。
  这样「稳定、需长期生效」的信息（角色、工具、事实、摘要）始终位于上下文最前且不被裁剪，
  而易变的对话细节放在后面按预算保留。
- **最大轮次限制**：`SessionConfig.max_turns`（默认 8），防止工具循环失控。
- **追问**：因为历史留在 session 内，**纯对话追问**（“刚才那个数再乘 2”）和
  **带工具的追问**（“再帮我加一条待办并列出来”）都能基于既有状态继续
  （见 `tests/test_runtime.py::test_followup_remembers_state_with_tools`）。
- **基础压缩**：当历史消息数超过 `max_history_messages`（默认 20）时，`Session.compress`
  把较旧的消息交给 LLM 概括成要点（失败则回退为截断保留尾部），写入 `summary`，只在历史中
  保留最近 `keep_recent_messages` 条。复杂压缩（分层记忆、向量召回等）本作业不实现。

### 异常处理 & Trace
- **异常处理**：LLM 调用失败（`LLMError`）、输出解析失败（`ParseError`）、工具执行失败
  （`ToolError`）、未知工具、达到最大轮次——都被捕获并转成对用户友好的结果，循环永不崩溃。
  解析失败时还会把纠错提示回灌给模型重试。
- **Trace / 日志**：`Tracer` 把每一步（user / llm_request / thought / tool_call /
  tool_result / final / error / compact）记录为结构化事件，实时打印到 stderr，并可写入
  `logs/trace.jsonl`（JSONL，便于事后回放分析）。

## 测试用例（[d:/mycode/MiniAgent/tests/](cci:4://file://d:/mycode/MiniAgent/tests/:0:0-0:0)）
`python -m pytest -q`（或 `-v -s` 看详细）覆盖：
- **工具**：计算器正确性与拒绝任意代码、mock 搜索/天气的确定性、todo 生命周期、
  Schema 完整性、参数校验、todo 按 store 隔离；
- **解析器**：final / 工具调用 / 顶层工具 / 代码块与散文包裹 / 字符串内花括号 / 各类错误；
- **Session**：多 session 隔离、get_or_create、facts 去重与入 prompt、压缩、消息组装顺序；
- **Runtime（用 MockLLM，无需联网）**：直接回复、单工具、多工具链、解析错误恢复、
  未知工具处理、最大轮次兜底、带工具的追问记忆、LLM 报错的优雅降级。

