import asyncio
import websockets
from websockets.asyncio.server import serve
import re
from datetime import datetime

message_parser = re.compile(r"(.+) - INFO - b'(.+)'")

async def send_after_delay(websocket, delay, message):
    await asyncio.sleep(delay)
    print("sending: {}...".format(message[:130]))
    await websocket.send(f"{message}")

async def echo(websocket):
    task_list = []
    while True:
        try:
            async for message in websocket:
                print("received:", message[:50])
                #await websocket.send(message)
                if message == "stop":
                    await websocket.close()
                    asyncio.get_event_loop().stop()
                    print("starting shutdown")
                    return
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
                                task = asyncio.create_task(send_after_delay(websocket, float(delay), text))
                                task_list.append(task)
                elif message == "heartbeat":
                    await websocket.send("ping")
                finished = []
                for task in task_list:
                    #await task
                    if task.done():
                        finished.append(True)
                    else:
                        finished.append(False)
                if len(finished) > 0:
                    if all(finished):
                        print("done serving")
                        await websocket.send("done")
        except Exception as e:
            print("websocket closed", e)
            asyncio.get_event_loop().stop()
            return

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