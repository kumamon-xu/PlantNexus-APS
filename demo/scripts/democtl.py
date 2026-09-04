"""中文命令行入口：安全启动、检查和停止 CNC 仿真 Demo。"""

from __future__ import annotations

import argparse
from io import TextIOWrapper
import json
from pathlib import Path
import sys
from typing import Any


for stream in (sys.stdout, sys.stderr):
    if isinstance(stream, TextIOWrapper):
        stream.reconfigure(encoding="utf-8", errors="replace")


DEMO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = DEMO_ROOT.parent
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))
sys.path.insert(0, str(DEMO_ROOT / "backend"))

from plantnexus_demo.delivery import (  # noqa: E402
    DEFAULT_RUNTIME_ID,
    DeliveryController,
    DemoDeliveryError,
    run_browser_smoke,
)


_ERROR_MESSAGES = {
    "DELIVERY_API_REJECTED": "本地演示接口拒绝了请求",
    "DELIVERY_API_RESPONSE_INVALID": "本地演示接口返回格式不正确",
    "DELIVERY_API_UNAVAILABLE": "无法连接本地演示接口",
    "DELIVERY_BASELINE_NOT_APPROVED": "D17 正式基准或参数冻结状态无效",
    "DELIVERY_BROWSER_COMMAND_FAILED": "真实浏览器检查未能完成",
    "DELIVERY_BROWSER_OUTPUT_UNSAFE": "浏览器工具输出包含不应暴露的会话信息",
    "DELIVERY_BROWSER_RESULT_INVALID": "真实浏览器检查结果不符合约定",
    "DELIVERY_DEPENDENCY_MISSING": "缺少演示交付依赖",
    "DELIVERY_DEPENDENCY_UNUSABLE": "演示交付依赖不可用",
    "DELIVERY_DOCUMENT_INVALID": "演示交付证据文件无效",
    "DELIVERY_FINGERPRINT_MISMATCH": "演示交付证据指纹不匹配",
    "DELIVERY_FRONTEND_BUILD_MISSING": "中文前端生产构建不存在",
    "DELIVERY_JOB_TIMEOUT": "演示任务在限定时间内未完成",
    "DELIVERY_LOCKFILE_MISSING": "缺少锁文件或构建配置",
    "DELIVERY_NODE_VERSION_UNSUPPORTED": "Node.js 版本低于冻结要求",
    "DELIVERY_NOT_RUNNING": "演示服务尚未启动或启动状态已失效",
    "DELIVERY_NPM_VERSION_UNSUPPORTED": "npm 版本低于冻结要求",
    "DELIVERY_PORT_IN_USE": "演示端口已被占用",
    "DELIVERY_PROCESS_EXITED_EARLY": "演示进程在就绪前退出",
    "DELIVERY_PROCESS_IDENTITY_MISMATCH": "进程身份与启动记录不匹配，已拒绝停止",
    "DELIVERY_PROCESS_IDENTITY_UNAVAILABLE": "无法建立安全的进程身份记录",
    "DELIVERY_PROCESS_STOP_FAILED": "任务自有进程未能安全停止",
    "DELIVERY_PROCESS_STOP_TIMEOUT": "任务自有进程停止超时",
    "DELIVERY_PYTHON_VERSION_UNSUPPORTED": "Python 版本不是冻结的 3.12",
    "DELIVERY_RESET_COUNTS_INVALID": "重置结果与固定场景不一致",
    "DELIVERY_RESET_FAILED": "固定演示工厂重置失败",
    "DELIVERY_RESET_MANIFEST_MISSING": "重置后缺少场景清单",
    "DELIVERY_RESET_RESPONSE_INVALID": "重置受理结果格式不正确",
    "DELIVERY_RUNTIME_NOT_WRITABLE": "Demo runtime 目录不可写",
    "DELIVERY_RUNTIME_CONFLICT": "已有其他具名 runtime 正在运行",
    "DELIVERY_RUNTIME_ID_INVALID": "runtime 标识只能包含小写字母、数字和连字符",
    "DELIVERY_RUNTIME_PATH_ESCAPE": "runtime 路径越出 Demo 边界",
    "DELIVERY_SERVICE_START_TIMEOUT": "本地演示服务未在限定时间内就绪",
    "DELIVERY_SETUP_COMMAND_FAILED": "依赖安装或生产构建失败，请查看任务自有日志",
    "DELIVERY_STALE_STATE_PRESENT": "存在失效启动记录，请先执行 stop 并按 Runbook 排查",
    "DELIVERY_STATE_INVALID": "启动状态文件无效，已拒绝继续",
    "DELIVERY_STATE_PATH_ESCAPE": "启动状态路径越出 Demo 边界",
}


def _emit(document: dict[str, Any]) -> None:
    print(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True))


def _failure(error: DemoDeliveryError) -> dict[str, Any]:
    code = error.code
    message = _ERROR_MESSAGES.get(code)
    if code.startswith("D18_BROWSER_ASSERTION:"):
        message = "真实浏览器中的中文交付断言未通过"
    return {
        "status": "FAIL",
        "code": code,
        "field": error.field,
        "message_zh": message or "演示交付命令失败",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor", help="检查依赖、证据、端口与写权限")

    start = subparsers.add_parser("start", help="安装依赖、构建并启动本地演示")
    start.add_argument("--runtime-id", default=DEFAULT_RUNTIME_ID)
    start.add_argument("--skip-install", action="store_true")
    start.add_argument("--skip-build", action="store_true")

    subparsers.add_parser("stop", help="安全停止本次启动的前后端")
    subparsers.add_parser("status", help="查看进程身份与服务状态")
    subparsers.add_parser("health", help="检查前后端和数据库就绪状态")

    reset = subparsers.add_parser("reset", help="重置固定种子的演示工厂")
    reset.add_argument("--profile", choices=("smoke", "showcase"), default="showcase")
    reset.add_argument("--timeout", type=float, default=120.0)

    smoke = subparsers.add_parser("smoke", help="用真实 Chromium 检查中文演示首屏")
    smoke.add_argument("--headed", action="store_true")
    return parser


def _run(arguments: argparse.Namespace) -> dict[str, Any]:
    controller = DeliveryController()
    if arguments.command == "doctor":
        return controller.doctor(require_free_ports=True)
    if arguments.command == "start":
        return controller.start(
            runtime_id=arguments.runtime_id,
            install=not arguments.skip_install,
            build=not arguments.skip_build,
        )
    if arguments.command == "stop":
        return controller.stop()
    if arguments.command == "status":
        return controller.status()
    if arguments.command == "health":
        return controller.health()
    if arguments.command == "reset":
        if arguments.timeout <= 0:
            raise DemoDeliveryError("DELIVERY_JOB_TIMEOUT", field="timeout")
        return controller.reset(profile_name=arguments.profile, timeout=arguments.timeout)
    if arguments.command == "smoke":
        controller.health()
        return run_browser_smoke(headed=arguments.headed)
    raise DemoDeliveryError("DELIVERY_COMMAND_INVALID")


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        result = _run(arguments)
    except DemoDeliveryError as error:
        _emit(_failure(error))
        return 1
    except Exception:  # noqa: BLE001 - terminal output must not expose internal details
        _emit(
            {
                "status": "FAIL",
                "code": "DELIVERY_UNEXPECTED",
                "field": None,
                "message_zh": "演示交付命令发生未分类错误，已隐藏内部细节",
            }
        )
        return 1
    _emit(result)
    return 1 if result.get("status") in {"FAIL", "STALE"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
