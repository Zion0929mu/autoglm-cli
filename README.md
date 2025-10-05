# AutoGLM CLI

AutoGLM API 的命令行工具，用于发送自动化任务并监控手机应用操作。

安装后可以直接运行 `zion` 进入交互式会话，体验类似 Claude Code 的即时指令输入。

## 配置

首次运行 `zion` 会提示输入 AutoGLM API 密钥，并将其保存在本地配置目录中（例如 `~/.config/zion/config.json`）。

你也可以通过环境变量或 `.env` 文件预先设置：

```bash
export AUTOGLM_API_KEY="your_api_key"
```

```env
AUTOGLM_API_KEY=your_api_key
```

## 从零开始的完整流程

1. **安装依赖工具**：确保系统具备 Python 3.11+，推荐安装 [uv](https://github.com/astral-sh/uv) 以管理依赖。

   ```bash
   pip install uv
   ```

2. **获取并安装项目**：克隆仓库后在项目根目录执行安装。

   ```bash
   git clone https://github.com/<your-org>/autoglm-cli.git
   cd autoglm-cli
   uv sync
   ```

3. **准备 API 密钥**：在 AutoGLM App → 设置 → 开发者计划 申请密钥，可通过环境变量或 `.env` 文件提前配置，或等待 CLI 首次运行时输入。

   ```bash
   export AUTOGLM_API_KEY="your_api_key"
   ```

4. **快速检查安装**：运行帮助命令确认 `zion` 可用。

   ```bash
   uv run zion --help
   ```

5. **进入交互模式**：

   ```bash
   uv run zion
   ```

   像聊天一样输入任务指令即可。交互模式支持 `:guide`、`:docs`、`:request` 等速查命令，输入 `exit` 或按 `Ctrl+C` 退出。

6. **发送一次性任务**：

   ```bash
   uv run zion task "打开高德地图查询从望京到三里屯的通勤时间"
   ```

   常用参数包括 `--conversation-id` 续接上下文、`--preview` 预览请求体、`--log-dir` 自定义日志目录。

7. **查看速查文档与完整指南**：

   ```bash
   uv run zion guide
   uv run zion docs
   uv run zion docs request
   ```

8. **处理人工接管**：若收到 `take_over` 提示，请在 AutoGLM App → 云手机 页面完成所需操作并回到终端确认。

9. **查看日志**：所有会话日志默认保存在 `~/.config/zion/logs/`（或使用 `--log-dir` 指定的目录），便于事后排查。

完成以上步骤后，即可稳定地通过 Zion 与 AutoGLM 交互。

## 常用命令速览

```bash
# 进入交互模式
uv run zion

# 直接发送一次性任务
uv run zion task "打开高德地图查询从望京到三里屯的通勤时间"

# 携带对话 ID
uv run zion task "搜索附近的咖啡店" --conversation-id "your_conversation_id"

# 在发送前打印请求 JSON
uv run zion task "测试语音助手" --preview

# 指定日志目录
uv run zion task "测试小程序" --log-dir ./my-logs

# 查看完整指南
uv run zion guide
```

## 速查指南

安装后的 `zion` CLI 同时内置了 AutoGLM API 速查文档：

```bash
# 查看完整速查信息
uv run zion docs

# 仅查看请求格式
uv run zion docs request

# 查看常见响应与 agent 行为
uv run zion docs responses

# 查看人工接管与监控说明
uv run zion docs manual
```

在交互模式中，可以直接输入内联指令调出同样的内容：

```
:guide       # 从安装到任务执行的完整流程
:docs         # 完整速查
:quickstart   # 接入流程与认证
:request      # 请求 JSON 模板
:responses    # 响应类型与动作说明
:manual       # take_over 操作指引
:rules        # 使用规范与客户端下载
:commands     # Zion 常用命令
```

## AutoGLM API 摘要

- **终端地址**：`wss://autoglm-api.zhipuai.cn/openapi/v1/autoglm/developer`
- **认证方式**：在 `Authorization` 请求头中携带 `Bearer <API_KEY>`
- **任务请求格式**：

  ```json
  {
    "timestamp": 1747885994523,
    "conversation_id": "",
    "msg_type": "client_test",
    "msg_id": "",
    "data": {
      "biz_type": "test_agent",
      "instruction": "your task instruction"
    }
  }
  ```

- **常见响应**：
  - `server_init`：连接建立后的初始化消息（`biz_type=init_chat`）
  - `server_session`：虚拟机启动/会话准备状态（`biz_type=init_vm | init_session`）
  - `client_test`：任务回显（包含 `instruction`、`session_id` 等）
  - `server_task`：代理执行动作、通知或人工接管指令
- **Agent 动作类型**：`launch`、`tap`、`type`、`swipe`、`back`、`call_api`、`take_over`、`finish`
- **人工接管**：当收到 `take_over` 时，Zion 会提示你暂停等待。请在 AutoGLM App → 云手机 页面完成所需操作后按回车继续。
- **使用规则**：仅限非商业用途，禁止转售或商用集成，需遵守 AutoGLM 服务条款。
- **客户端下载**：Android 版本 `autoglm_v2.0.06_office-release.apk (110.74MB)`，iOS 在 App Store 搜索 “AutoGLM”。
