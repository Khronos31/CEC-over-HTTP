"""CEC over HTTP — cec-client(libcec)をHTTP REST APIとして公開する常駐デーモン。

⚠️ このリポジトリは Khronos31/home-assistant-cec-control へ移行する。
このデーモンは、そちらの `daemon/`（HAカスタム統合 `cec_control` のリモート側トランスポート）
として作り直される。新規の作業はこのリポジトリではなく移行先で行うこと。

⚠️ READMEは実装と食い違ったまま（存在しない `GET /power_on` / `GET /standby` を記載し、
実装説明も「起動時にlibcecを初期化」と誤っている）。実際のAPIは下のルーティング定義が正本。
移行時に書き直すため、ここでは直していない。
"""
import argparse
import asyncio
import logging
import re
import subprocess
import sys

from aiohttp import web

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("cec-daemon")

# cec-clientが取得する論理アドレス（Playback Device = 4が一般的）
SELF_ADDR = 4
TV_ADDR = 0

# /tx が受け付ける生CECコマンド: "4F:82:10:00" のような : 区切りの16進バイト列のみ。
# cec-clientのstdinへ行単位で流し込むため、改行や任意の文字列を通すと別コマンドを
# 注入できてしまう。ここで形を縛る。
_TX_CMD_RE = re.compile(r"^[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2})*$")


class CECUnavailable(RuntimeError):
    """cec-clientが起動できない／死んでいて復帰もできない。HTTP 503に対応する。"""


class CECManager:
    def __init__(self):
        self.process = None

    def initialize(self):
        """cec-clientを起動する。失敗時はCECUnavailableを送出する（プロセスは落とさない）。"""
        logger.info("Initializing cec-client in background...")
        try:
            self.process = subprocess.Popen(['cec-client', '-d', '1'],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError as e:
            self.process = None
            raise CECUnavailable("'cec-client' not found. Run: sudo apt install cec-utils") from e
        except OSError as e:
            self.process = None
            raise CECUnavailable(f"Failed to start cec-client: {e}") from e
        logger.info("cec-client is running.")

    def _write(self, cmd_str):
        self.process.stdin.write(f"{cmd_str}\n")
        self.process.stdin.flush()

    def _send_command(self, cmd_str):
        if self.process is None or self.process.poll() is not None:
            logger.error("cec-client process is dead. Restarting...")
            self.initialize()
        try:
            self._write(cmd_str)
        except (BrokenPipeError, ValueError, OSError):
            # poll()とwrite()の隙間で死んだ場合。一度だけ再起動して再送する。
            logger.error("Write to cec-client failed. Restarting once and retrying...")
            self.initialize()
            try:
                self._write(cmd_str)
            except OSError as e:
                raise CECUnavailable(f"cec-client is not writable: {e}") from e
        logger.info(f"Executed: {cmd_str}")

    def _send_key(self, keycode):
        """USER_CONTROL_PRESSED + RELEASE を送信"""
        self._send_command(f"tx {SELF_ADDR:X}{TV_ADDR:X}:44:{keycode:02X}")
        self._send_command(f"tx {SELF_ADDR:X}{TV_ADDR:X}:45")

    # POST /power {"action": "on"|"off"}
    async def handle_power(self, request):
        data = await _read_json(request)
        action = data.get("action", "on")
        if action not in ("on", "off"):
            raise web.HTTPBadRequest(text="action must be 'on' or 'off'")
        if action == "on":
            self._send_command(f"on {TV_ADDR}")
        else:
            self._send_command(f"standby {TV_ADDR}")
        logger.info(f"power {action}")
        return web.Response(text="ok")

    # POST /channel {"channel": 8}
    async def handle_channel(self, request):
        data = await _read_json(request)
        ch = _require_int(data, "channel", minimum=0, maximum=9999)
        for digit in str(ch):
            self._send_key(0x20 + int(digit))
            await asyncio.sleep(0.3)
        logger.info(f"channel {ch}")
        return web.Response(text="ok")

    # POST /key {"keycode": 65}
    async def handle_key(self, request):
        data = await _read_json(request)
        keycode = _require_int(data, "keycode", minimum=0, maximum=0xFF)
        self._send_key(keycode)
        logger.info(f"key 0x{keycode:02X}")
        return web.Response(text="ok")

    # POST /tv_off
    async def handle_tv_off(self, request):
        self._send_command("as")
        await asyncio.sleep(0.5)
        self._send_command(f"standby {TV_ADDR}")
        logger.info("tv_off (as → standby)")
        return web.Response(text="ok")

    # POST /input_tv
    async def handle_input_tv(self, request):
        # TV内蔵チューナーに切替（TV自身をActive Sourceにする）
        self._send_command(f"tx {SELF_ADDR:X}{TV_ADDR:X}:82:00:00")
        logger.info("input_tv")
        return web.Response(text="ok")

    # POST /input_hdmi
    async def handle_input_hdmi(self, request):
        self._send_command("as")
        logger.info("input_hdmi (as)")
        return web.Response(text="ok")

    # GET /tx?cmd=XX:YY:ZZ (このデーモン独自。cec-bridgeには無い)
    async def handle_tx(self, request):
        cmd = request.query.get('cmd')
        if not cmd:
            raise web.HTTPBadRequest(text="Missing 'cmd' parameter")
        if not _TX_CMD_RE.match(cmd):
            raise web.HTTPBadRequest(text="cmd must be colon-separated hex bytes, e.g. 4F:82:10:00")
        self._send_command(f"tx {cmd}")
        return web.Response(text="ok")


async def _read_json(request):
    try:
        data = await request.json()
    except ValueError as e:
        raise web.HTTPBadRequest(text=f"invalid JSON body: {e}") from e
    if not isinstance(data, dict):
        raise web.HTTPBadRequest(text="JSON body must be an object")
    return data


def _require_int(data, key, *, minimum, maximum):
    value = data.get(key)
    if value is None:
        raise web.HTTPBadRequest(text=f"{key} required")
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise web.HTTPBadRequest(text=f"{key} must be an integer")
    try:
        value = int(value)
    except ValueError:
        raise web.HTTPBadRequest(text=f"{key} must be an integer") from None
    if not minimum <= value <= maximum:
        raise web.HTTPBadRequest(text=f"{key} must be between {minimum} and {maximum}")
    return value


@web.middleware
async def cec_unavailable_middleware(request, handler):
    """cec-clientが使えない状態を503で返す。cec-bridgeが「TVがバス上に居ない」を
    503で返すのと同じ位置づけ（=こちらの都合で今は撃てない、リクエストは正しい）。"""
    try:
        return await handler(request)
    except CECUnavailable as e:
        logger.error(f"CEC unavailable: {e}")
        return web.Response(status=503, text=str(e))


def main():
    parser = argparse.ArgumentParser(description="CEC over HTTP Daemon")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()

    cec_manager = CECManager()
    try:
        cec_manager.initialize()
    except CECUnavailable as e:
        logger.error(str(e))
        sys.exit(1)

    app = web.Application(middlewares=[cec_unavailable_middleware])
    app.router.add_post('/power',      cec_manager.handle_power)
    app.router.add_post('/channel',    cec_manager.handle_channel)
    app.router.add_post('/key',        cec_manager.handle_key)
    app.router.add_post('/tv_off',     cec_manager.handle_tv_off)
    app.router.add_post('/input_tv',   cec_manager.handle_input_tv)
    app.router.add_post('/input_hdmi', cec_manager.handle_input_hdmi)
    app.router.add_get('/tx',          cec_manager.handle_tx)

    logger.info(f"Listening on {args.host}:{args.port}")
    web.run_app(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
