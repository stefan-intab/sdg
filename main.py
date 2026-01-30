import asyncio

from app import Brigde, AppConfig
from infra.logging_config import app_logger


async def main() -> None:
    bridge = Brigde(AppConfig())

    app_logger.info("Initializing SDG Bridge.")

    # Test: run for 10 seconds then stop
    runner = asyncio.create_task(bridge.run())
    
    await asyncio.sleep(1000)
    await bridge.stop()
    app_logger.info("SDG Bridge is shutting down.")
    await runner

if __name__ == "__main__":
    asyncio.run(main())
