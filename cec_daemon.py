import argparse
import asyncio
import logging
import subprocess
import sys
from aiohttp import web

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("cec-daemon")

# cec-clientが取得する論理アドレス（Playback Device = 4が一般的）
SELF_ADDR = 4
TV_ADDR = 0

class CECManager:
    def __init__(self):
        self.process = None

    def initialize(self):
        logger.info("Initializing cec-client in background...")
        try:
            self.process = subprocess.Popen(['cec-client', '-d', '1'],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
            logger.info("cec-client is running.")
        except FileNotFoundError:
            logger.error("'cec-client' not found. Run: sudo apt install cec-utils")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Failed to start cec-client: {e}")
            sys.exit(1)

    def _send_command(self, cmd_str):
        if self.process and self.process.poll() is None:
            self.process.stdin.write(f"{cmd_str}\n")
            self.process.stdin.flush()
            logger.info(f"Executed: {cmd_str}")
        else:
            logger.error("cec-client process is dead. Restarting...")
            self.initialize()
            self.process.stdin.write(f"{cmd_str}\n")
            self.process.stdin.flush()

    def _send_key(self, keycode):
        """USER_CONTROL_PRESSED + RELEASE を送信"""
        self._send_command(f"tx {SELF_ADDR:X}{TV_ADDR:X}:44:{keycode:02X}")
        self._send_command(f"tx {SELF_ADDR:X}{TV_ADDR:X}:45")

    # POST /power {"action": "on"|"off"}
    async def handle_power(self, request):
        data = await request.json()
        action = data.get("action", "on")
        if action == "on":
            self._send_command(f"on {TV_ADDR}")
        else:
            self._send_command(f"standby {TV_ADDR}")
        logger.info(f"power {action}")
        return web.Response(text="ok")

    # POST /channel {"channel": 8}
    async def handle_channel(self, request):
        data = await request.json()
        ch = data.get("channel")
        if ch is None:
            return web.Response(status=400, text="channel required")
        for digit in str(int(ch)):
            self._send_key(0x20 + int(digit))
            await asyncio.sleep(0.3)
        logger.info(f"channel {ch}")
        return web.Response(text="ok")

    # POST /key {"keycode": 65}
    async def handle_key(self, request):
        data = await request.json()
        keycode = data.get("keycode")
        if keycode is None:
            return web.Response(status=400, text="keycode required")
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

    # GET /tx?cmd=XX:YY:ZZ (後方互換)
    async def handle_tx(self, request):
        cmd = request.query.get('cmd')
        if not cmd:
            return web.Response(status=400, text="Missing 'cmd' parameter")
        self._send_command(f"tx {cmd}")
        return web.Response(text="ok")


def main():
    parser = argparse.ArgumentParser(description="CEC over HTTP Daemon")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()

    cec_manager = CECManager()
    cec_manager.initialize()

    app = web.Application()
    app.router.add_post('/power',      cec_manager.handle_power)
    app.router.add_post('/channel',    cec_manager.handle_channel)
    app.router.add_post('/key',        cec_manager.handle_key)
    app.router.add_post('/tv_off',     cec_manager.handle_tv_off)
    app.router.add_post('/input_tv',   cec_manager.handle_input_tv)
    app.router.add_post('/input_hdmi', cec_manager.handle_input_hdmi)
    app.router.add_get('/tx',          cec_manager.handle_tx)  # 後方互換

    logger.info(f"Listening on {args.host}:{args.port}")
    web.run_app(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
