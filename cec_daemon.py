import argparse
import asyncio
import logging
import sys
from aiohttp import web

try:
    import cec
except ImportError:
    print("Error: 'python-cec' library not found. Please install it with 'pip install python-cec' or 'sudo apt install python3-cec'.")
    sys.exit(1)

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("cec-daemon")

class CECManager:
    def __init__(self):
        self.tv = None

    def initialize(self):
        logger.info("Initializing HDMI-CEC...")
        try:
            # Initialize CEC with default configuration
            cec.init()
            # Get TV device (logical address 0)
            self.tv = cec.Device(0)
            logger.info("CEC initialized. TV device ready.")
        except Exception as e:
            logger.error(f"Failed to initialize CEC: {e}")
            sys.exit(1)

    async def handle_tx(self, request):
        cmd = request.query.get('cmd')
        if not cmd:
            return web.Response(text="Missing 'cmd' parameter", status=400)
        
        try:
            logger.info(f"Transmitting raw command: {cmd}")
            # cec.transmit takes a TransmitCommand object
            # TransmitCommand.from_string exists in python-cec to parse "1F:82:10:00"
            command = cec.TransmitCommand.from_string(cmd)
            cec.transmit(command)
            return web.Response(text="OK")
        except Exception as e:
            logger.error(f"TX failed: {e}")
            return web.Response(text=str(e), status=500)

    async def handle_power_on(self, request):
        try:
            logger.info("Powering on TV...")
            self.tv.power_on()
            return web.Response(text="OK")
        except Exception as e:
            logger.error(f"Power ON failed: {e}")
            return web.Response(text=str(e), status=500)

    async def handle_standby(self, request):
        try:
            logger.info("Putting TV in standby...")
            self.tv.standby()
            return web.Response(text="OK")
        except Exception as e:
            logger.error(f"Standby failed: {e}")
            return web.Response(text=str(e), status=500)

def main():
    parser = argparse.ArgumentParser(description="CEC over HTTP Daemon")
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
