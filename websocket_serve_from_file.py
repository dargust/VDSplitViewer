import asyncio
from websockets.asyncio.server import serve
import re
from datetime import datetime

message_parser = re.compile(r"(.+) - INFO - b'(.+)'")

async def send_after_delay(websocket, delay, message):
    await asyncio.sleep(delay)
    print("sending:",message)
    await websocket.send(f"{message}")

async def echo(websocket):
    async for message in websocket:
        print("received:", message)
        #await websocket.send(message)
        if message == "stop":
            await websocket.close()
            asyncio.get_event_loop().stop()
            break
        elif message == "serve":
            task_list = []
            file_name = "messages.log"
            print(f"serving messages from {file_name}")
            with open(file_name, "r") as file:
                lines = file.readlines()
                first_time = None
                for line in lines:
                    match = message_parser.match(line)
                    if match:
                        groups = match.groups()
                        delay = groups[0]
                        timestamp = datetime.strptime(delay, "%Y-%m-%d %H:%M:%S,%f").timestamp()
                        if first_time is None:
                            first_time = timestamp
                            delay = 0.0
                        else:
                            delay = (timestamp - first_time)
                        text = groups[1]
                        print(delay, text)
                        task = asyncio.create_task(send_after_delay(websocket, float(delay), text))
                        task_list.append(task)
            for task in task_list:
                await task
            await websocket.send("done")
            print("done serving")

async def main():
    async with serve(echo, "localhost", 8765) as server:
        try:
            await server.serve_forever()  # run forever
        except asyncio.CancelledError:
            print("websocket closed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("websocket closed")
    except RuntimeError as e:
        if str(e) == "Event loop stopped before Future completed.":
            print("server stopped")
        else:
            print(e)