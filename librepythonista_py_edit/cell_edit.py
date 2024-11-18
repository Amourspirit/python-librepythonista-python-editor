#!/usr/bin/env python3
from __future__ import annotations
from typing import Any, List, Dict, cast
import socket
import struct
import sys
import json
import threading
from pathlib import Path
import argparse
import webview
import webview.menu as wm
import jedi  # noqa # type: ignore


# https://pywebview.flowrl.com/guide/api.html#webview-settings

webview.settings = {
    "ALLOW_DOWNLOADS": False,
    "ALLOW_FILE_URLS": True,
    "OPEN_EXTERNAL_LINKS_IN_BROWSER": False,
    "OPEN_DEVTOOLS_IN_DEBUG": False,
}

_WEB_VEW_ENDED = False
_IS_DEBUG = False
_IS_DARK_THEME = False


# region Args Parse
def _create_parser(name: str) -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description=name)


def _parser_args_add(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-i",
        "--process-id",
        help="Process Id that Invoked the subprocess",
        action="store",
        dest="process_id",
        default="",
    )
    parser.add_argument(
        "-d",
        "--debug",
        help="Debug mode",
        action="store",
        dest="debug_mode",
        default="no_debug",
    )
    parser.add_argument(
        "-p",
        "--port",
        help="Port number to connect to the server",
        action="store",
        dest="port_number",
        default=0,
    )


# endregion Args Parse


# region Runtime Args
class RuntimeArgs:
    def __init__(self):
        self.process_id = ""
        self.port = 0
        self.debug_mode = False

    def from_args(self, args: argparse.Namespace):
        self.process_id = str(args.process_id)
        self.port = int(args.port_number)
        debug_mode = str(args.debug_mode)
        self.debug_mode = debug_mode.lower() == "debug"


# endregion Runtime Args


class OutputCollector:
    _instances = {}
    _lock = threading.Lock()

    def __new__(cls, **kwargs):
        with cls._lock:
            key = kwargs.pop("key", "")
            if not key:
                raise ValueError("key is required")
            if key not in cls._instances:
                instance = super(OutputCollector, cls).__new__(cls)
                instance.__init__()
                cls._instances[key] = instance
            return cls._instances[key]

    def __init__(self, **kwargs):
        if not hasattr(self, "_logs"):
            self.lock = threading.Lock()
            self._logs: List[str] = []

    def write(self, message: str):
        with self.lock:
            self._logs.append(message)

    def flush(self):
        pass  # Required for file-like objects.

    def get_value(self) -> str:
        with self.lock:
            return "".join(self._logs)

    def get_logs(self, rstrip: bool = True) -> List[str]:
        if not rstrip:
            with self.lock:
                return self._logs
        with self.lock:
            return [line.rstrip() for line in self._logs]


class WindowConfig:
    def __init__(self):
        self.width = 0
        self.height = 0
        self.x = -1
        self.y = -1

    def from_json(self, json_str: str):
        try:
            data = json.loads(json_str)
            self.width = data.get("width", 0)
            self.height = data.get("height", 0)
            self.x = data.get("x", -1)
            self.y = data.get("y", -1)
        except Exception as e:
            sys.stderr.write(f"Error in from_json: {e}\n")

    def from_dict(self, data: Dict[str, int]):
        self.width = data.get("width", 0)
        self.height = data.get("height", 0)
        self.x = data.get("x", -1)
        self.y = data.get("y", -1)

    def to_json(self) -> str:
        data = {"width": self.width, "height": self.height, "x": self.x, "y": self.y}
        return json.dumps(data)

    def to_dict(self) -> Dict[str, int]:
        return {
            "width": self.width,
            "height": self.height,
            "x": self.x,
            "y": self.y,
        }

    def has_size(self) -> bool:
        return self.width > 0 and self.height > 0

    def has_position(self) -> bool:
        return self.x > -1 and self.y > -1

    def update_from_api(self, api: Api):
        try:
            if api.has_window():
                api.window_config.width = api._window.width
                api.window_config.height = api._window.height
                api.window_config.x = api._window.x
                api.window_config.y = api._window.y
        except Exception as e:
            sys.stderr.write(f"Error in update_from_api: {e}\n")


class Api:
    def __init__(self, runtime_args: RuntimeArgs, sock: socket.socket):
        self._window = cast(webview.Window, None)
        self.runtime_args = runtime_args
        self.process_id = self.runtime_args.process_id
        self.port = self.runtime_args.port
        self.sock = sock
        self.resources: Dict[str, str] = {}
        self.info: Dict[str, str] = {}
        self.theme: Dict[str, Any] = {}
        self.module_source_code = ""
        self.window_config = WindowConfig()
        self.destroyed = False

    def set_window(self, window: webview.Window):
        self._window = window

    def destroy(self):
        global _WEB_VEW_ENDED
        try:
            if self._window:
                # Destroy the window in a separate thread
                # self.hide()
                data = {
                    "cmd": "destroyed",
                    "process_id": self.process_id,
                    "data": {
                        "window_config": self.window_config.to_dict(),
                        "logs": get_std_logs(self.runtime_args),
                    },
                }
                send_message(self.sock, data)
                self._window.destroy()
                self._window = cast(webview.Window, None)
                _WEB_VEW_ENDED = True
                self.destroyed = True
        except Exception as e:
            sys.stderr.write(f"Error in destroy {e}\n")

    def hide(self):
        try:
            if self._window:
                if not self._window.hidden:
                    sys.stdout.write("Hiding window\n")
                    self._window.hide()
                    sys.stdout.write("Window hidden'n")
                else:
                    sys.stdout.write("Window already hidden\n")
        except Exception as e:
            sys.stderr.write(f"Error in hide {e}\n")

    def show(self):
        try:
            if self._window:
                sys.stdout.write("Showing window\n")
                self._window.show()
                sys.stdout.write("Window shown\n")
        except Exception as e:
            sys.stderr.write(f"Error in show: {e}\n")

    def validate_code(self) -> None:
        try:
            if self._window:
                self._window.evaluate_js("validateCode();")
        except Exception as e:
            sys.stderr.write(f"Error in validate code: {e}\n")

    def validate_code_result(self, code):
        # Process the received code
        if _IS_DEBUG:
            sys.stdout.write(f"Code:\n{code}\n")
        request_data = {
            "cmd": "request_action",
            "process_id": self.process_id,
            "action": "validate_code",
            "params": {"code": code},
        }
        send_message(self.sock, request_data)
        sys.stdout.write("Sent code to server for validation\n")

    def insert_lp_function(self) -> None:
        request_data = {
            "cmd": "request_action",
            "process_id": self.process_id,
            "action": "insert_lp_function",
            "params": {},
        }
        send_message(self.sock, request_data)

    def insert_range(self) -> None:
        request_data = {
            "cmd": "request_action",
            "process_id": self.process_id,
            "action": "insert_range",
            "params": {},
        }
        send_message(self.sock, request_data)

    def get_autocomplete(self, code, line, column):
        try:
            # sys.stdout.write(f"{code}\n")
            # Combine the additional code with the editor code
            combined_code = self.module_source_code + "\n" + code

            # Adjust the line number for the cursor
            prepended_lines = self.module_source_code.count("\n") + 1
            adjusted_line = line + prepended_lines

            script = jedi.Script(combined_code, path="")
            completions = script.complete(adjusted_line, column)
            suggestions = [completion.name for completion in completions]
            return json.dumps(suggestions)
        except Exception:
            return json.dumps([])

    def has_window(self):
        return self._window is not None

    def receive_code(self, code):
        # Process the received code
        print("Received code from JavaScript")
        if _IS_DEBUG:
            print(f"Code:\n{code}")
        data = {
            "cmd": "code",
            "process_id": self.process_id,
            "data": {
                "code": code,
                "window_config": self.window_config.to_dict(),
            },
        }
        send_message(self.sock, data)
        print("Sent code to server")
        self.destroy()

    def set_code(self, code: str):
        try:
            if self._window:
                escaped_code = json.dumps(code)  # Escape the string for JavaScript
                # sys.stdout.write(f"{escaped_code}\n")
                self._window.evaluate_js(f"setCode({escaped_code})")
        except Exception as e:
            sys.stderr.write(f"Error in set_code: {e}\n")

    def insert_text_at_cursor(self, text: str):
        try:
            if self._window:
                js_code = f"insertTextAtCursor('{text}');"
                self._window.evaluate_js(js_code)
        except Exception as e:
            sys.stderr.write(f"Error in insert_text: {e}\n")

    def set_focus_on_editor(self):
        try:
            if self._window:
                js_code = "focusCodeMirror();"
                self._window.evaluate_js(js_code)
        except Exception as e:
            sys.stderr.write(f"Error in set_focus_on_editor: {e}\n")

    def handle_response(self, response: Dict[str, Any]) -> None:
        """
        Handles the response from the server and updates the UI.

        Args:
            response (Dict[str, Any]): The response from the server.
        """
        msg = response.get("message", "")
        status = response.get("status", "")
        try:
            # if msg == "got_resources":
            #     if status == "success":
            #         self.resources = cast(Dict[str, str], response.get("data", {}))

            if msg == "got_info":
                if status == "success":
                    data = cast(Dict[str, Dict[str, str]], response.get("data", {}))
                    self.info = data.get("info", {})
                    self.resources = data.get("resources", {})
                    self.theme = data.get("theme", {})
                    self.module_source_code = cast(
                        str, data.get("module_source_code", "")
                    )
                    self.window_config.from_dict(
                        cast(Dict[str, int], data.get("window_config", {}))
                    )

            elif msg == "validated_code":
                if status == "success":
                    self._window.evaluate_js(
                        f"alert('{self.resources.get('mbmsg001', 'Code is Valid')}')"
                    )
                else:
                    self._window.evaluate_js(
                        f"alert('{self.resources.get('log09', 'Error')}')"
                    )
            elif msg == "lp_fn_inserted":
                if status == "success":
                    data = cast(Dict[str, str], response.get("data", {}))
                    fn_str = data.get("function", "")
                    if fn_str:
                        # self._window.evaluate_js(f"alert('{fn_str}')")
                        self.insert_text_at_cursor(fn_str)
                    else:
                        self._window.evaluate_js(
                            "alert('Failed to insert LP function. No function returned.')"
                        )
            elif msg == "lp_rng_inserted":
                if status == "success":
                    data = cast(Dict[str, str], response.get("data", {}))
                    fn_str = data.get("range", "")
                    if fn_str:
                        # self._window.evaluate_js(f"alert('{fn_str}')")
                        self.insert_text_at_cursor(fn_str)
                    else:
                        self._window.evaluate_js(
                            "alert('Failed to insert range. No function returned.')"
                        )
            elif msg == "pass":
                pass
            else:
                sys.stderr.write(f"Unknown response: {response}\n")
        except Exception as e:
            sys.stderr.write(f"Error handling response: {e}\n")

    # region Window Events
    def on_resized(self, width: int, height: int) -> None:
        if _IS_DEBUG:
            sys.stdout.write(f"Resized: {width} x {height}\n")
        self.window_config.width = width
        self.window_config.height = height

    def on_moved(self, x: int, y: int) -> None:
        if _IS_DEBUG:
            sys.stdout.write(f"Moved: {x}, {y}\n")
        # On Ubuntu 24.04, the window position reports 0, 0 when moved
        # On Ubuntu 20.04, With LibreOffice and Embedded python it works.
        # On windows 10 the position is reported correctly
        self.window_config.x = x
        self.window_config.y = y

    # endregion Window Events


def webview_ready(window: webview.Window):
    global _IS_DARK_THEME
    theme_js = f"applyTheme({str(_IS_DARK_THEME).lower()});"
    window.evaluate_js(theme_js)


def receive_all(sock: socket.socket, length: int) -> bytes:
    data = b""
    while len(data) < length:
        try:
            more = sock.recv(length - len(data))
        except ConnectionAbortedError as e:
            raise ConnectionAbortedError("Connection has been aborted") from e
        if not more:
            raise ConnectionResetError("Connection closed prematurely")
        data += more
    return data


def receive_messages(
    api: Api, sock: socket.socket, event: threading.Event, stop_event: threading.Event
) -> None:
    global _WEB_VEW_ENDED
    while not stop_event.is_set():
        try:
            # Receive the message length first
            raw_msg_len = receive_all(sock, 4)
            if not raw_msg_len:
                break
            msg_len = struct.unpack("!I", raw_msg_len)[0]

            # Receive the actual message
            data = receive_all(sock, msg_len)
            message = data.decode(encoding="utf-8")
            sys.stdout.write(f"Received from server: {message}\n")

            json_dict = cast(Dict[str, Any], json.loads(message))
            msg_cmd = json_dict.get("cmd")
            sys.stdout.write(f"Received from server with id: {msg_cmd}\n")

            if msg_cmd == "destroy":
                api.destroy()
            elif msg_cmd == "code":
                code = json_dict.get("data", "")
                api.set_code(code)
            elif msg_cmd == "general_message":
                msg = json_dict.get("data", "")
                sys.stdout.write(f"Received general message: {msg}\n")
            elif msg_cmd == "action_completed":
                response = json_dict.get("response_data", {})
                response_msg = response.get("message", "")
                api.handle_response(response)
                if response_msg == "got_info":
                    event.set()

            # elif message.startswith("action_completed:"):
            #     response = json.loads(message[len("action_completed:") :])
            #     api.handle_response(response)
            else:
                sys.stdout.write(f"Subprocess received: {message}\n")
        except (ConnectionResetError, struct.error, ConnectionAbortedError) as err:
            if _WEB_VEW_ENDED:
                sys.stdout.write("receive_messages() Webview ended\n")
            else:
                sys.stderr.write(f"receive_messages() Error receiving message: {err}\n")
                import traceback

                traceback.print_exc()
            break


def send_message(sock: socket.socket, message: Dict[str, Any]) -> None:
    # Prefix each message with a 4-byte length (network byte order)
    try:
        json_message = json.dumps(message)
        message_bytes = json_message.encode(encoding="utf-8")
        message_length = struct.pack("!I", len(message_bytes))
        sock.sendall(message_length + message_bytes)
    except Exception as e:
        sys.stderr.write(f"Error sending message: {e}\n")


# region Menu
class Menu:
    def __init__(self, api: Api):
        self.api = api

    def get_menu(self):
        items = [
            wm.Menu(
                self.api.resources.get("mnuCode", "Code"),
                [
                    wm.MenuAction(
                        cast(str, self.api.resources.get("mnuValidate", "Validate")),
                        self.api.validate_code,
                    ),  # type: ignore
                ],
            ),
            wm.Menu(
                self.api.resources.get("mnuInsert", "Insert"),
                [
                    wm.MenuAction(
                        cast(
                            str,
                            self.api.resources.get("mnuAutoLpFn", "Insert Lp Function"),
                        ),
                        self.api.insert_lp_function,
                    ),  # type: ignore
                    wm.MenuAction(
                        cast(
                            str,
                            self.api.resources.get("mnuSelectRng", "Select Range"),
                        ),
                        self.api.insert_range,
                    ),  # type: ignore
                ],
            ),
        ]
        return items


# endregion Menu


def get_std_logs(runtime_args: RuntimeArgs) -> Dict[str, str]:
    if runtime_args.process_id and runtime_args.port > 0:
        stdout_collector = OutputCollector(key="stdout")
        stderr_collector = OutputCollector(key="stderr")
        return {
            "stdout": stdout_collector.get_logs(),
            "stderr": stderr_collector.get_logs(),
        }
    return {}


# region Main


def main():
    global _WEB_VEW_ENDED, _IS_DEBUG, _IS_DARK_THEME
    _WEB_VEW_ENDED = False

    parser = _create_parser("main")
    _parser_args_add(parser)

    runtime_args = RuntimeArgs()
    runtime_args.from_args(parser.parse_args())

    process_id = runtime_args.process_id
    _IS_DEBUG = runtime_args.debug_mode

    # Create OutputCollector instances
    if runtime_args.process_id and runtime_args.port > 0:
        stdout_collector = OutputCollector(key="stdout")
        stderr_collector = OutputCollector(key="stderr")
        # Save original stdout and stderr
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        # Redirect stdout and stderr
        sys.stdout = stdout_collector
        sys.stderr = stderr_collector

    def on_loaded():
        nonlocal process_id, client_socket

        sys.stdout.write("Webview is ready\n")
        try:
            data = {
                "cmd": "webview_ready",
                "process_id": process_id,
                "data": "webview_ready",
            }
            send_message(client_socket, data)
            sys.stdout.write("Sent 'webview_ready' to main process\n")
        except Exception as e:
            sys.stderr.write(f"Error sending 'webview_ready': {e}\n")

    try:
        if not runtime_args.process_id or runtime_args.port <= 0:
            sys.stdout.write(
                "Usage: python shell_edit.py --process-id <process_id> --port <port>\n"
            )
            sys.exit(1)

        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(("localhost", runtime_args.port))

        # Send a message to the main process
        data = {
            "cmd": "general_message",
            "process_id": process_id,
            "data": "Hello from subprocess!",
        }
        send_message(client_socket, data)

        api = Api(runtime_args=runtime_args, sock=client_socket)
        root = Path(__file__).parent
        html_file = Path(root, "html/index.html")
        sys.stdout.write(f"html_file: {html_file}: Exists: {html_file.exists()}\n")

        # Create an event to wait for the menu data
        response_event = threading.Event()
        stop_event = threading.Event()

        # Start a thread to receive messages from the server
        t1 = threading.Thread(
            target=receive_messages,
            args=(api, client_socket, response_event, stop_event),
            daemon=False,
        )
        t1.start()

        # Request menu data from the server
        request_data = {
            "cmd": "request_action",
            "process_id": process_id,
            "action": "get_info",
            "params": {},
        }
        send_message(client_socket, request_data)
        sys.stdout.write("Requested menu data from server\n")

        # Wait for the menu data to be received
        response_event.wait(timeout=10)  # Wait for up to 10 seconds

        if api.resources:
            sys.stdout.write(f"Received menu data: {api.resources}\n")
        else:
            sys.stderr.write("Failed to receive menu data within the timeout period\n")

        if api.info:
            sys.stdout.write(f"Received info data: {api.info}\n")
        else:
            sys.stderr.write("Failed to receive info data within the timeout period\n")

        if api.theme:
            sys.stdout.write(f"Received theme data: {api.theme}\n")
        else:
            sys.stderr.write("Failed to receive theme data within the timeout period\n")

        # if api.module_source_code:
        #     sys.stdout.write(f"Received Module Source Code: {api.module_source_code}\n")

        _IS_DARK_THEME = bool(api.theme.get("is_doc_dark", False))

        sys.stdout.write("Creating window\n")
        title = api.resources.get("title10", "Python Code")
        cell = api.info.get("cell", "")
        if cell:
            title = f"{title} - {cell}"
        if api.window_config.has_size():
            width = api.window_config.width
            height = api.window_config.height
        else:
            width = 800
            height = 600

        if api.window_config.has_position():
            x = api.window_config.x
            y = api.window_config.y
        else:
            x = None
            y = None
        window = webview.create_window(
            title=title,
            url=html_file.as_uri(),
            width=width,
            height=height,
            x=x,
            y=y,
            js_api=api,
        )

        window.events.loaded += on_loaded
        window.events.moved += api.on_moved
        window.events.resized += api.on_resized

        api.set_window(window)
        # theme_js = f"applyTheme({_IS_DARK_THEME});"
        # window.evaluate_js(theme_js)
        sys.stdout.write("Window created\n")
        # if sys.platform == "win32":
        #     gui_type = "cef"
        # elif sys.platform == "linux":
        #     gui_type = "qt"
        # else:
        #     gui_type = None

        sys.stdout.write("Starting Webview\n")
        mnu = Menu(api)
        webview.start(
            webview_ready,
            (window,),
            gui=None,
            menu=mnu.get_menu(),
            debug=False,
        )  # setting gui is causing crash in LibreOffice
        sys.stdout.write("Ended Webview\n")

        # Collect logs from stdout and stderr

        # Prepare data to send to server
        if not api.destroyed:
            data = {
                "cmd": "logs",
                "process_id": process_id,
                "data": {"logs": get_std_logs(runtime_args)},
            }
            # Send logs to server
            send_message(client_socket, data)

        data = {
            "cmd": "exit",
            "process_id": process_id,
            "data": {"window_config": api.window_config.to_dict()},
        }

        send_message(client_socket, data)

        _WEB_VEW_ENDED = True
        stop_event.set()
        if t1.is_alive():
            t1.join(timeout=1)
        client_socket.close()

    except Exception as e:
        sys.stderr.write(f"Error in main {e}\n")
    finally:
        # Restore original stdout and stderr
        if runtime_args.process_id and runtime_args.port > 0:
            sys.stdout = original_stdout
            sys.stderr = original_stderr


# endregion Main

if __name__ == "__main__":
    main()
