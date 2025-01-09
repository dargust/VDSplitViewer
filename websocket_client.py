import asyncio
from websockets.asyncio.client import connect

async def wait_for_all_serves(websocket):
    message = ""
    while message[:4] != "done":
        message = await websocket.recv()
        print(message)
    await websocket.send("stop")

async def test():
    async with connect("ws://localhost:8765", ping_interval=None) as websocket:
        await websocket.send(input("Enter message: "))
        task = asyncio.create_task(wait_for_all_serves(websocket))
        await task

if __name__ == "__main__":
    asyncio.run(test())