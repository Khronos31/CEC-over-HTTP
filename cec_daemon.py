import argparse
import asyncio
import logging
import subprocess
import sys
from aiohttp import web

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("cec-daemon")

class CECManager:
    def __init__(self):
        self.process = None

    def initialize(self):
        logger.info("Initializing cec-client in background...")
        try:
            # cec-client をバックグラウンドで起動し、標準入力を開いたままにする
            # -d 1 : ログ出力を最小限にする
            self.process = subprocess.Popen(['cec-client', '-d', '1'],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1 # 行バッファリング
            )
            logger.info("cec-client is running and ready to receive commands.")
        except FileNotFoundError:
            logger.error("Error: 'cec-client' command not found. Please run 'sudo apt install cec-utils'.")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Failed to start cec-client: {e}")
            sys.exit(1)

    def _send_command(self, cmd_str):
        """開いたままの cec-client プロセスにコマンドを流し込む"""
        if self.process and self.process.poll() is None:
            self.process.stdin.write(f"{cmd_str}\n")
            self.process.stdin.flush()
            logger.info(f"Executed: {cmd_str}")
        else:
            logger.error("cec-client process is dead. Attempting to restart...")
            self.initialize()
            self.process.stdin.write(f"{cmd_str}\n")
            self.process.stdin.flush()

    async def handle_tx(self, request):
        cmd = request.query.get('cmd')
        if not cmd:
            return web.Response(text="Missing 'cmd' parameter", status=400)
        
        try:
            # 例: "tx 1F:82:10:00" を流し込む
            self._send_command(f"tx {cmd}")
            return web.Response(text="OK")
        except Exception as e:
            logger.error(f"TX failed: {e}")
            return web.Response(text=str(e), status=500)

    async def handle_power_on(self, request):
        try:
            # テレビ(アドレス0)をONにする
            self._send_command("on 0")
            return web.Response(text="OK")
        except Exception as e:
            logger.error(f"Power ON failed: {e}")
            return web.Response(text=str(e), status=500)

    async def handle_standby(self, request):
        try:
            # テレビ(アドレス0)をスタンバイにする
            self._send_command("standby 0")
            return web.Response(text="OK")
        except Exception as e:
            logger.error(f"Standby failed: {e}")
            return web.Response(text=str(e), status=500)

def main():
    parser = argparse.ArgumentParser(description="CEC over HTTP Daemon (Subprocess Edition)")
    parser.add_argument("--port", type=int, default=8080, help="Listen port (default: 8080)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Listen host (default: 0.0.0.0)")
    args = parser.parse_args()

    cec_manager = CECManager()
    cec_manager.initialize()

    app = web.Application()
    app.router.add_get('/tx', cec_manager.handle_tx)
    app.router.add_get('/power_on', cec_manager.handle_power_on)
    app.router.add_get('/standby', cec_manager.handle_standby)

    logger.info(f"Starting server on {args.host}:{args.port}")
    web.run_app(app, host=args.host, port=args.port)

if __name__ == "__main__":
    main()
