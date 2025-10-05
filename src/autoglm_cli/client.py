import websocket
import json
import time
import threading
from typing import Optional, Callable, Any


class AutoGLMClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.ws_url = "wss://autoglm-api.zhipuai.cn/openapi/v1/autoglm/developer"
        self.ws = None
        self.connected = False
        self.message_handler: Optional[Callable[[dict], None]] = None
        self.request_logger: Optional[Callable[[dict], None]] = None
        self.ws_thread = None

    def on_open(self, ws):
        self.connected = True

    def on_message(self, ws, message):
        try:
            data = json.loads(message)

            # Check for swipe actions and add direction info
            if (data.get("data", {}).get("data_type") == "data_agent" and
                data.get("data", {}).get("data_agent", {}).get("action") == "swipe"):
                data_agent = data["data"]["data_agent"]
                swipe_info = self.format_swipe_info(data_agent)
                if swipe_info:
                    data["swipe_direction_info"] = swipe_info

            if self.message_handler:
                self.message_handler(data)
        except json.JSONDecodeError:
            if self.message_handler:
                self.message_handler({"raw_message": message})

    def on_error(self, ws, error):
        if self.message_handler:
            self.message_handler({"error": str(error)})

    def on_close(self, ws, close_status_code, close_msg):
        self.connected = False

    def connect(self, message_handler: Optional[Callable[[dict], None]] = None, request_logger: Optional[Callable[[dict], None]] = None) -> bool:
        self.message_handler = message_handler
        self.request_logger = request_logger
        headers = {"Authorization": f"Bearer {self.api_key}"}

        self.ws = websocket.WebSocketApp(
            self.ws_url,
            header=headers,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )

        self.ws_thread = threading.Thread(target=self.ws.run_forever)
        self.ws_thread.daemon = True
        self.ws_thread.start()

        # Wait for connection
        timeout = 10
        while not self.connected and timeout > 0:
            time.sleep(0.5)
            timeout -= 0.5

        return self.connected

    def send_task(self, instruction: str, conversation_id: str = "") -> bool:
        payload = self.build_task_payload(instruction, conversation_id)
        return self.send_payload(payload)

    def build_task_payload(self, instruction: str, conversation_id: str = "") -> dict:
        return {
            "timestamp": int(time.time() * 1000),
            "conversation_id": conversation_id,
            "msg_type": "client_test",
            "msg_id": "",
            "data": {
                "biz_type": "test_agent",
                "instruction": instruction,
            },
        }

    def send_payload(self, payload: dict) -> bool:
        if not self.connected:
            return False

        # Log the request if logger is available
        if self.request_logger:
            self.request_logger(payload)

        self.ws.send(json.dumps(payload))
        return True

    def parse_swipe_direction(self, start2end: list) -> str:
        if len(start2end) != 4:
            return "未知方向"

        start_x, start_y, end_x, end_y = start2end
        dx = end_x - start_x
        dy = end_y - start_y

        # Calculate the primary direction based on larger displacement
        if abs(dx) > abs(dy):
            return "向右滑动" if dx > 0 else "向左滑动"
        else:
            return "向下滑动" if dy > 0 else "向上滑动"

    def format_swipe_info(self, data_agent: dict) -> str:
        if data_agent.get("action") != "swipe":
            return ""

        start2end = data_agent.get("start2end", [])
        if len(start2end) == 4:
            direction = self.parse_swipe_direction(start2end)
            return direction
        return "滑动操作"

    def close(self):
        self.connected = False
        if self.ws:
            self.ws.close()
        if self.ws_thread and self.ws_thread.is_alive():
            self.ws_thread.join(timeout=2)
