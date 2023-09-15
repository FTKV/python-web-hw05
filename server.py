import aiohttp
import aiofile
import aiopath
import asyncio
import logging
import websockets
import names
from websockets import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosedOK
import platform
from datetime import datetime
from main import (
    handle_data,
    handle_parameters,
    get_exchange_rates,
    json_view,
    DATETIME_FORMAT,
)


BASE_DIR = aiopath.Path()
STORAGE_FILE = "logs/log.txt"


logger = logging.getLogger()
stream_handler = logging.StreamHandler()
logger.addHandler(stream_handler)
logger.setLevel(logging.INFO)


class Server:
    clients = set()

    async def register(self, ws: WebSocketServerProtocol):
        ws.name = names.get_full_name()
        self.clients.add(ws)
        logger.info(f"{ws.remote_address} connects")

    async def unregister(self, ws: WebSocketServerProtocol):
        self.clients.remove(ws)
        logger.info(f"{ws.remote_address} disconnects")

    async def send_to_clients(self, message: str):
        if self.clients:
            [await client.send(message) for client in self.clients]

    async def ws_handler(self, ws: WebSocketServerProtocol):
        await self.register(ws)
        try:
            await self.distrubute(ws)
        except ConnectionClosedOK:
            pass
        finally:
            await self.unregister(ws)

    async def distrubute(self, ws: WebSocketServerProtocol):
        async for message in ws:
            if message.casefold().startswith("exchange"):
                ws.name, message = await self.currency_exchange(message)
            await self.send_to_clients(f"{ws.name}: {message}")

    async def currency_exchange(self, message):
        await self.log_to_file(message)
        name = "Privatbank currency exchange"
        try:
            n, *additional_currencies = handle_parameters(*message.split())
        except ValueError as error:
            logger.error(f"ValueError: {str(error)}")
            return name, str(error)
        currency_list = ["EUR", "USD"]
        if additional_currencies:
            for currency in additional_currencies:
                currency_list.append(currency.upper())
        if platform.system() == "Windows":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        try:
            data = await get_exchange_rates(n)
        except aiohttp.ClientConnectorError as error:
            logger.error(f"Connection error: {str(error)}")
            return name, str(error)
        except aiohttp.client_exceptions.ContentTypeError:
            logger.error(f"Content error: {str(error)}")
            return name, str(error)
        result = handle_data(data, currency_list)
        result = json_view(result)
        result = "\n" + result + "\n"
        return name, result

    async def log_to_file(self, message):
        storage_file = BASE_DIR.joinpath(STORAGE_FILE)
        if await storage_file.exists():
            mode = "a"
        else:
            await storage_file.parent.mkdir(parents=True, exist_ok=True)
            mode = "w"

        async with aiofile.async_open(storage_file, mode, encoding="utf-8") as afp:
            await afp.write(f"{datetime.now().strftime(DATETIME_FORMAT)}: {message}\n")


async def main():
    server = Server()
    async with websockets.serve(server.ws_handler, "localhost", 8080):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bye")
