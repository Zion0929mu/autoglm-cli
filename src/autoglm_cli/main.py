import json
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Optional

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax

from .client import AutoGLMClient

# Load environment variables from .env file
load_dotenv()


class ConfigManager:
    """Manage persisted configuration for Zion CLI."""

    def __init__(self) -> None:
        self._config_dir = Path(typer.get_app_dir("zion"))
        self._config_path = self._config_dir / "config.json"

    @property
    def config_dir(self) -> Path:
        self._config_dir.mkdir(parents=True, exist_ok=True)
        return self._config_dir

    @property
    def config_path(self) -> Path:
        return self.config_dir / "config.json"

    def load_api_key(self) -> Optional[str]:
        if not self.config_path.exists():
            return None
        try:
            with open(self.config_path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            api_key = data.get("api_key")
            if api_key and isinstance(api_key, str):
                return api_key.strip() or None
        except (OSError, json.JSONDecodeError):
            return None
        return None

    def save_api_key(self, api_key: str) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as fp:
            json.dump({"api_key": api_key}, fp, ensure_ascii=False, indent=2)

    def clear_api_key(self) -> None:
        try:
            if self.config_path.exists():
                self.config_path.unlink()
        except OSError:
            pass


config_manager = ConfigManager()
console = Console()
app = typer.Typer(help="AutoGLM API 命令行工具", invoke_without_command=True, no_args_is_help=False)
docs_app = typer.Typer(help="AutoGLM API 文档速查")


def ensure_api_key(
    provided_key: Optional[str] = None,
    *,
    reset: bool = False,
) -> str:
    """Retrieve an API key, prompting the user if needed."""

    if provided_key:
        sanitized = provided_key.strip()
        if sanitized:
            config_manager.save_api_key(sanitized)
            return sanitized

    env_key = os.environ.get("AUTOGLM_API_KEY")
    if env_key and not reset:
        return env_key.strip()

    if reset:
        config_manager.clear_api_key()
    else:
        stored = config_manager.load_api_key()
        if stored:
            return stored

    while True:
        api_key = typer.prompt("请输入 AutoGLM API 密钥", hide_input=True).strip()
        if api_key:
            config_manager.save_api_key(api_key)
            console.print(f"🔐 API 密钥已保存到 {config_manager.config_path}")
            return api_key
        console.print("❗ API 密钥不能为空，请重新输入。")


def render_section_title(title: str) -> None:
    console.rule(f"[bold cyan]{title}[/bold cyan]")


def render_quick_start_section() -> None:
    render_section_title("快速开始")
    console.print(
        Panel.fit(
            "[bold]Endpoint[/]: wss://autoglm-api.zhipuai.cn/openapi/v1/autoglm/developer\n"
            "[bold]Authorization[/]: Bearer <API_KEY>",
            title="连接信息",
            border_style="cyan",
        )
    )

    flow_table = Table(title="任务流程", show_header=True, header_style="bold magenta")
    flow_table.add_column("步骤", style="cyan", justify="center")
    flow_table.add_column("说明", style="white")
    flow_table.add_row("1", "建立到 AutoGLM 的 WebSocket 连接")
    flow_table.add_row("2", "发送包含任务指令的消息 (msg_type=client_test)")
    flow_table.add_row("3", "持续监听服务器返回的各类响应")
    console.print(flow_table)


def render_authentication_section() -> None:
    render_section_title("获取 API 密钥")
    console.print(
        Markdown(
            "1. 在 AutoGLM 应用中注册账号\n"
            "2. 进入 设置 → 开发者计划\n"
            "3. 申请密钥，等待邮件发送 API Key"
        )
    )


def render_request_section() -> None:
    render_section_title("请求格式")
    request_payload = {
        "timestamp": 1747885994523,
        "conversation_id": "",
        "msg_type": "client_test",
        "msg_id": "",
        "data": {
            "biz_type": "test_agent",
            "instruction": "your task instruction",
        },
    }
    console.print(
        Panel(
            Syntax(
                json.dumps(request_payload, ensure_ascii=False, indent=2),
                "json",
                theme="monokai",
                word_wrap=True,
            ),
            title="任务请求示例",
            border_style="magenta",
        )
    )


def render_response_section() -> None:
    render_section_title("常见响应类型")
    response_table = Table(show_header=True, header_style="bold magenta")
    response_table.add_column("msg_type", style="cyan")
    response_table.add_column("说明", style="white")
    response_table.add_row("server_init", "连接建立后的初始化信息 (biz_type=init_chat)")
    response_table.add_row("server_session", "虚拟机或会话状态更新 (biz_type=init_vm/init_session)")
    response_table.add_row("client_test", "服务器回显的任务指令与会话信息")
    response_table.add_row("server_task", "代理执行步骤、通知、人工接管等")
    console.print(response_table)

    response_examples = [
        ("server_init", {"msg_type": "server_init", "data": {"biz_type": "init_chat"}}),
        (
            "server_session",
            {
                "msg_type": "server_session",
                "data": {
                    "biz_type": "init_vm",
                    "vm_state": "vm_starting",
                    "vm_id": "...",
                    "uid": "...",
                },
            },
        ),
        (
            "client_test",
            {
                "msg_type": "client_test",
                "data": {
                    "instruction": "...",
                    "session_id": "...",
                    "metadata": "autoglm",
                    "conversation_id": "...",
                    "query_id": "...",
                },
            },
        ),
        (
            "server_task",
            {
                "msg_type": "server_task",
                "data": {
                    "data_type": "data_agent",
                    "biz_type": "agent_task",
                    "data_agent": {
                        "action": "launch",
                        "app_name": "AppName",
                        "package_name": "com.app.id",
                        "session_id": "...",
                        "request_id": "...",
                        "message": "result",
                        "round": 1,
                    },
                },
            },
        ),
    ]

    for title, example in response_examples:
        console.print(
            Panel(
                Syntax(
                    json.dumps(example, ensure_ascii=False, indent=2),
                    "json",
                    theme="monokai",
                    word_wrap=True,
                ),
                title=f"示例: {title}",
                border_style="green",
            )
        )

    action_table = Table(title="Agent 行为", show_header=True, header_style="bold magenta")
    action_table.add_column("action", style="cyan")
    action_table.add_column("说明", style="white")
    action_table.add_row("launch", "启动指定应用 (app_name, package_name)")
    action_table.add_row("tap", "点击屏幕坐标 (center_point)")
    action_table.add_row("type", "输入文本内容 (argument)")
    action_table.add_row("swipe", "执行滑动手势，start2end 指定方向")
    action_table.add_row("back", "执行返回操作")
    action_table.add_row("call_api", "调用内部 API 并返回结果")
    action_table.add_row("take_over", "需要人工干预，message 描述原因")
    action_table.add_row("finish", "任务完成，message 为最终结果")
    console.print(action_table)


def render_usage_rules_section() -> None:
    render_section_title("使用规则")
    console.print(
        Markdown(
            "- ⚠️ 仅限非商业用途\n"
            "- 允许个人使用但禁止转售或商用集成\n"
            "- 请遵守 AutoGLM 服务条款"
        )
    )


def render_manual_intervention_section() -> None:
    render_section_title("人工接管流程")
    console.print(
        Markdown(
            "当收到 `take_over` 动作时:\n"
            "1. 代理暂停自动化操作\n"
            "2. 用户需在 AutoGLM App 的云手机界面完成必要步骤\n"
            "3. 完成后返回命令行确认，任务将继续执行"
        )
    )


def render_monitoring_section() -> None:
    render_section_title("任务监控")
    console.print("可在 AutoGLM 应用 → 云手机 页面查看任务执行过程。")


def render_downloads_section() -> None:
    render_section_title("客户端下载")
    downloads = Table(show_header=True, header_style="bold magenta")
    downloads.add_column("平台", style="cyan")
    downloads.add_column("链接", style="white")
    downloads.add_row("Android", "autoglm_v2.0.06_office-release.apk (110.74MB)")
    downloads.add_row("iOS", "App Store 搜索 \"AutoGLM\"")
    console.print(downloads)


def render_cli_usage_section() -> None:
    render_section_title("Zion CLI 用法")
    usage_table = Table(show_header=True, header_style="bold magenta")
    usage_table.add_column("命令", style="cyan")
    usage_table.add_column("说明", style="white")
    usage_table.add_row("zion", "进入交互模式，适合持续对话")
    usage_table.add_row("zion task '指令'", "发送一次性任务并输出日志位置")
    usage_table.add_row("zion docs", "查看 API 速查指南")
    usage_table.add_row("zion docs responses", "查看常见响应及 agent 行为")
    usage_table.add_row("zion task --preview", "发送前打印请求 JSON")
    usage_table.add_row("zion task --log-dir ./logs", "自定义日志存储路径")
    usage_table.add_row("zion guide", "查看从零开始的完整使用流程")
    console.print(usage_table)
    console.print("交互模式内输入 :docs/:guide/:quickstart/:request/:responses/:manual/:rules 获取速查信息。")


def render_full_usage_guide() -> None:
    render_section_title("从零开始的使用流程")

    steps = [
        (
            "准备运行环境",
            "安装 Python 3.11+，并推荐使用 [uv](https://github.com/astral-sh/uv) 作为依赖管理工具。\n"
            "如果尚未安装 uv，可执行：\n\n"
            "```bash\n"
            "pip install uv\n"
            "```",
        ),
        (
            "下载程序本体",
            "你可以选择直接安装发布版或克隆源码：\n\n"
            "- 直接安装（推荐）：\n\n"
            "```bash\n"
            "pip install autoglm-cli\n"
            "# 或\n"
            "uv tool install autoglm-cli\n"
            "```\n\n"
            "安装完成后会自动注册 `zion` 命令。\n\n"
            "- 克隆源码自行安装：\n\n"
            "```bash\n"
            "git clone https://github.com/<your-org>/autoglm-cli.git\n"
            "cd autoglm-cli\n"
            "uv sync\n"
            "```\n\n"
            "如果无法访问 Git，可以从 GitHub Release 下载压缩包解压后执行 `uv sync`。",
        ),
        (
            "准备 API 密钥",
            "首次运行需要提供 AutoGLM API Key。建议提前在 AutoGLM App → 设置 → 开发者计划 申请，并将密钥保存到环境变量：\n\n"
            "```bash\n"
            "export AUTOGLM_API_KEY=\"your_api_key\"\n"
            "```\n\n"
            "也可以等到 CLI 提示时输入，程序会加密保存到 `~/.config/zion/config.json`。",
        ),
        (
            "快速验证安装",
            "运行以下命令查看可用子命令与选项：\n\n"
            "```bash\n"
            "uv run zion --help\n"
            "```",
        ),
        (
            "进入交互模式",
            "执行：\n\n"
            "```bash\n"
            "zion\n"
            "```\n\n"
            "如果是在项目目录通过 `uv sync` 安装的版本，可执行 `uv run zion`。随后即可像聊天一样输入任务指令，输入 `exit` 或 `Ctrl+C` 退出。交互模式下可以随时输入 `:guide`、`:docs` 等速查指令。",
        ),
        (
            "发送一次性任务",
            "若只需执行单条指令，可使用 task 子命令：\n\n"
            "```bash\n"
            "uv run zion task \"打开高德地图查询从望京到三里屯的通勤时间\"\n"
            "```\n\n"
            "常用参数：`--conversation-id` 续接历史对话、`--preview` 发送前预览请求、`--log-dir` 自定义日志目录。",
        ),
        (
            "查看速查文档",
            "需要回顾 API 细节时，可执行：\n\n"
            "```bash\n"
            "uv run zion docs\n"
            "uv run zion docs request\n"
            "uv run zion guide\n"
            "```\n\n"
            "这些命令与交互式指令 `:docs`、`:request`、`:guide` 等效果一致。",
        ),
        (
            "处理人工接管",
            "当服务器返回 `take_over` 行为时，CLI 会提示你在 AutoGLM App → 云手机 页面手动完成登录、验证码等操作。操作完成后回到命令行按回车继续，直到收到 `finish`。",
        ),
        (
            "查看与保存日志",
            "所有请求/响应会记录到 `~/.config/zion/logs/` 目录（或通过 `--log-dir` 指定的路径）。日志文件以时间戳命名，便于追溯调试。",
        ),
    ]

    for idx, (title, details) in enumerate(steps, start=1):
        console.print(
            Panel(
                Markdown(f"**步骤 {idx}: {title}**\n\n{details}"),
                border_style="cyan",
                title=f"步骤 {idx}",
            )
        )

    console.print("✅ 完成以上步骤后，即可稳定地通过 Zion 与 AutoGLM 交互。")


def render_docs_overview() -> None:
    render_quick_start_section()
    render_authentication_section()
    render_request_section()
    render_response_section()
    render_manual_intervention_section()
    render_usage_rules_section()
    render_downloads_section()
    render_monitoring_section()
    render_cli_usage_section()


def render_sections(*sections: Callable[[], None]) -> None:
    for section in sections:
        section()


CHEATSHEET_COMMANDS: Dict[str, Callable[[], None]] = {
    "docs": render_docs_overview,
    "help": render_docs_overview,
    "guide": render_full_usage_guide,
    "quickstart": lambda: render_sections(render_quick_start_section, render_authentication_section),
    "request": render_request_section,
    "responses": render_response_section,
    "manual": lambda: render_sections(render_manual_intervention_section, render_monitoring_section),
    "rules": lambda: render_sections(render_usage_rules_section, render_downloads_section),
    "commands": render_cli_usage_section,
}


def handle_inline_command(command: str) -> bool:
    handler = CHEATSHEET_COMMANDS.get(command)
    if handler:
        handler()
        return True
    return False


app.add_typer(docs_app, name="docs")


class AutoGLMLogger:
    def __init__(self, task_instruction: str, log_root: Optional[Path] = None):
        # Create logs directory
        if log_root is None:
            self.logs_dir = Path("logs")
        else:
            self.logs_dir = log_root
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Create log file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_instruction = "".join(c for c in task_instruction[:50] if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_instruction = safe_instruction.replace(' ', '_')

        self.log_file = self.logs_dir / f"{timestamp}_{safe_instruction}.json"

        # Initialize log data
        self.log_data = {
            "timestamp": datetime.now().isoformat(),
            "task_instruction": task_instruction,
            "messages": []
        }

        # Save initial log
        self._save_log()

    def log_request(self, message: dict):
        """Log outgoing request"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "request",
            "data": message
        }
        self.log_data["messages"].append(log_entry)
        self._save_log()

    def log_response(self, message: dict):
        """Log incoming response"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "response",
            "data": message
        }
        self.log_data["messages"].append(log_entry)
        self._save_log()

    def _save_log(self):
        """Save log data to file"""
        with open(self.log_file, 'w', encoding='utf-8') as f:
            json.dump(self.log_data, f, ensure_ascii=False, indent=2)


@docs_app.callback(invoke_without_command=True)
def docs_entry(ctx: typer.Context):
    """显示 AutoGLM API 速查概览"""
    if ctx.invoked_subcommand is None:
        render_docs_overview()


@docs_app.command("quickstart")
def docs_quickstart():
    """查看快速开始与认证步骤"""
    render_sections(render_quick_start_section, render_authentication_section)


@docs_app.command("request")
def docs_request():
    """查看请求格式示例"""
    render_request_section()


@docs_app.command("responses")
def docs_responses():
    """查看常见响应与行为"""
    render_response_section()


@docs_app.command("manual")
def docs_manual():
    """查看人工接管与监控说明"""
    render_sections(render_manual_intervention_section, render_monitoring_section)


@docs_app.command("guide")
def docs_guide():
    """查看完整的上手指南"""
    render_full_usage_guide()


@docs_app.command("rules")
def docs_rules():
    """查看使用规则与下载方式"""
    render_sections(render_usage_rules_section, render_downloads_section)


@docs_app.command("commands")
def docs_commands():
    """查看 Zion CLI 常用命令"""
    render_cli_usage_section()


def format_response(data: dict) -> str:
    """格式化 API 响应以供显示"""
    if "error" in data:
        return f"❌ 错误: {data['error']}"

    if "raw_message" in data:
        return f"📨 原始消息: {data['raw_message']}"

    msg_type = data.get("msg_type", "unknown")

    if msg_type == "server_init":
        return "✅ 已连接到 AutoGLM"

    elif msg_type == "server_session":
        session_data = data.get("data", {})
        biz_type = session_data.get("biz_type", "unknown")
        vm_state = session_data.get("vm_state", "unknown")
        vm_id = session_data.get("vm_id", "unknown")
        uid = session_data.get("uid", "")

        if biz_type == "init_vm":
            return f"🔧 虚拟机初始化中: {vm_state}"
        elif biz_type == "init_session":
            return f"🖥️  虚拟机 {vm_state} (ID: {vm_id[:12]}{'...' if len(vm_id) > 12 else ''})"
        else:
            return f"🖥️  虚拟机 {vm_state} (ID: {vm_id})"

    elif msg_type == "client_test":
        test_data = data.get("data", {})
        instruction = test_data.get("instruction", "")
        session_id = test_data.get("session_id", "")
        metadata = test_data.get("metadata", "")

        if session_id:
            return f"📋 任务: {instruction} (会话: {session_id[:16]}{'...' if len(session_id) > 16 else ''})"
        else:
            return f"📋 任务: {instruction}"

    elif msg_type == "server_task":
        task_data = data.get("data", {})
        biz_type = task_data.get("biz_type", "unknown")
        agent_data = task_data.get("data_agent", {})
        action = agent_data.get("action", "unknown")
        message = agent_data.get("message", "")
        round_num = agent_data.get("round", 1)

        # Handle special business types
        if biz_type == "take_over":
            return f"⏸️  第{round_num}轮: 需要手动操作 - {message}"
        elif biz_type == "notify_task":
            return f"📢 第{round_num}轮: 通知 - {message}"

        # Handle different action types
        if action == "launch":
            app_name = agent_data.get("app_name", "")
            package_name = agent_data.get("package_name", "")
            if package_name:
                return f"🚀 第{round_num}轮: 启动 {app_name} ({package_name})"
            else:
                return f"🚀 第{round_num}轮: 启动 {app_name}"
        elif action == "tap":
            center_point = agent_data.get("center_point", [0, 0])
            return f"👆 第{round_num}轮: 点击 {center_point}"
        elif action == "type":
            argument = agent_data.get("argument", "")
            return f"⌨️ 第{round_num}轮: 输入 '{argument}'"
        elif action == "swipe":
            # Check if we have direction info
            swipe_direction = data.get("swipe_direction_info", "")
            if swipe_direction:
                return f"👋 第{round_num}轮: {swipe_direction}"
            else:
                return f"👋 第{round_num}轮: 滑动手势"
        elif action == "back":
            return f"⬅️  第{round_num}轮: 返回导航"
        elif action == "call_api":
            # Truncate long API responses for readability
            display_msg = message[:100] + "..." if len(message) > 100 else message
            return f"🔗 第{round_num}轮: API 调用 - {display_msg}"
        elif action == "take_over":
            return f"⏸️  第{round_num}轮: 需要手动操作 - {message}"
        elif action == "finish":
            # Show full finish message - this is the final result users want to see
            return f"✅ 第{round_num}轮: {message}"
        else:
            return f"🔄 第{round_num}轮: {action} - {message}"

    return f"📨 {msg_type}: {json.dumps(data, ensure_ascii=False)}"


def run_task(
    instruction: str,
    api_key: str,
    *,
    conversation_id: str = "",
    log_root: Optional[Path] = None,
    echo_request: bool = False,
) -> bool:
    """Execute a single AutoGLM task."""

    logger = AutoGLMLogger(instruction, log_root=log_root)
    console.print(f"📝 日志记录到: {logger.log_file}")

    client = AutoGLMClient(api_key)
    take_over_requested = False
    task_completed = False

    def signal_handler(sig, frame):
        console.print("\n🛑 接收到中断信号，正在关闭连接...")
        client.close()
        sys.exit(0)

    previous_sigint = signal.getsignal(signal.SIGINT)
    previous_sigterm = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    def message_handler(data: dict):
        nonlocal take_over_requested, task_completed

        logger.log_response(data)

        response = format_response(data)
        console.print(response)

        if data.get("msg_type") == "server_task":
            agent_data = data.get("data", {}).get("data_agent", {})
            action = agent_data.get("action", "")
            if action == "finish":
                task_completed = True
            elif action == "take_over":
                take_over_requested = True

    console.print("🔗 正在连接 AutoGLM API...")

    if not client.connect(message_handler, logger.log_request):
        console.print("❌ 连接 AutoGLM API 失败")
        signal.signal(signal.SIGINT, previous_sigint)
        signal.signal(signal.SIGTERM, previous_sigterm)
        return False

    payload = client.build_task_payload(instruction, conversation_id)

    console.print(f"📤 发送任务: {instruction}")

    if echo_request:
        console.print("🧾 请求预览:")
        console.print(
            Syntax(
                json.dumps(payload, ensure_ascii=False, indent=2),
                "json",
                theme="monokai",
                word_wrap=True,
            )
        )

    if not client.send_payload(payload):
        console.print("❌ 发送任务失败")
        client.close()
        signal.signal(signal.SIGINT, previous_sigint)
        signal.signal(signal.SIGTERM, previous_sigterm)
        return False

    console.print("⏳ 等待响应中...")
    console.print("─" * 60)

    try:
        while not task_completed:
            time.sleep(1)

            if take_over_requested:
                console.print("\n📱 需要在手机上手动操作！")
                console.print("💡 请在 AutoGLM 应用中完成所需操作")
                console.print("⏭️  完成手动操作后请按 ENTER 键...")

                try:
                    input()
                    console.print("▶️  恢复自动化操作...")
                    console.print("─" * 60)
                    take_over_requested = False
                except KeyboardInterrupt:
                    console.print("\n🛑 任务被用户中断")
                    client.close()
                    signal.signal(signal.SIGINT, previous_sigint)
                    signal.signal(signal.SIGTERM, previous_sigterm)
                    return False
    except KeyboardInterrupt:
        console.print("\n🛑 任务被用户中断")
        client.close()
        signal.signal(signal.SIGINT, previous_sigint)
        signal.signal(signal.SIGTERM, previous_sigterm)
        return False

    client.close()
    signal.signal(signal.SIGINT, previous_sigint)
    signal.signal(signal.SIGTERM, previous_sigterm)
    console.print("─" * 60)
    console.print("✅ 任务完成")
    return True


def default_log_dir() -> Path:
    return config_manager.config_dir / "logs"


@app.command()
def task(
    instruction: str = typer.Argument(..., help="要发送的任务指令"),
    api_key: Optional[str] = typer.Option(None, envvar="AUTOGLM_API_KEY", help="AutoGLM API 密钥"),
    conversation_id: str = typer.Option("", help="对话ID（用于上下文）"),
    reset_api_key: bool = typer.Option(False, "--reset-key", help="重新输入并保存 API 密钥"),
    log_dir: Optional[Path] = typer.Option(None, "--log-dir", help="自定义日志目录"),
    preview: bool = typer.Option(False, "--preview/--no-preview", help="发送前打印请求 JSON"),
):
    """向 AutoGLM API 发送任务并监控响应"""

    key = ensure_api_key(api_key, reset=reset_api_key)
    success = run_task(
        instruction,
        key,
        conversation_id=conversation_id,
        log_root=log_dir or default_log_dir(),
        echo_request=preview,
    )
    if not success:
        raise typer.Exit(code=1)


@app.command()
def info():
    """显示 AutoGLM API 信息"""

    table = Table(title="AutoGLM API 信息")
    table.add_column("属性", style="cyan")
    table.add_column("值", style="white")

    table.add_row("端点", "wss://autoglm-api.zhipuai.cn/openapi/v1/autoglm/developer")
    table.add_row("认证", "Authorization 头中的 Bearer 令牌")
    table.add_row("消息类型", "client_test")
    table.add_row("业务类型", "test_agent")
    table.add_row("环境配置", "在 .env 文件中设置 AUTOGLM_API_KEY 或使用 --api-key")

    console.print(table)
    render_cli_usage_section()
    console.print("\n📚 想了解全部接口细节？执行 [bold]zion docs[/bold] 或在交互模式输入 :docs。")
    console.print("🛎️  收到 take_over 时，命令行会提示你在 AutoGLM App 完成必要操作后继续。")


@app.command()
def guide():
    """查看从安装到执行任务的完整流程"""
    render_full_usage_guide()
    console.print()
    render_cli_usage_section()


def interactive_loop(api_key: Optional[str] = None) -> None:
    console.print("[bold cyan]欢迎来到 Zion：AutoGLM 命令行助手[/bold cyan]")
    console.print("输入任务指令后按回车发送。输入 'exit' 或按 Ctrl+C 退出。\n")
    console.print("💡 支持的速查命令：:guide、:docs、:quickstart、:request、:responses、:manual、:rules、:commands\n")

    if api_key is None:
        api_key = ensure_api_key()
    log_dir = default_log_dir()

    while True:
        try:
            instruction = typer.prompt("请输入要执行的任务").strip()
        except typer.Abort:
            console.print("\n再见！")
            return
        except EOFError:
            console.print("\n再见！")
            return

        if instruction.startswith(":"):
            command = instruction[1:].strip().lower()
            if command in {"exit", "quit"}:
                console.print("👋 已退出 Zion。")
                return
            if handle_inline_command(command):
                continue
            console.print("❓ 未识别的命令，输入 :help 查看可用选项。")
            continue

        if not instruction:
            continue

        if instruction.lower() in {"exit", "quit", ":q"}:
            console.print("👋 已退出 Zion。")
            return

        run_task(instruction, api_key, log_root=log_dir)


@app.callback()
def main(
    ctx: typer.Context,
    reset_key: bool = typer.Option(False, "--reset-key", help="重新输入并保存 API 密钥"),
):
    if ctx.invoked_subcommand is None:
        api_key = ensure_api_key(reset=reset_key)
        interactive_loop(api_key)


if __name__ == "__main__":
    app()
