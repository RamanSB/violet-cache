import asyncio
import os
from random import random
import threading
import time


async def foo():
    start_time_ns = time.time_ns()
    print(
        f"Enterring foo, process ID {os.getpid()} & {threading.current_thread().name}"
    )
    await asyncio.sleep(5)
    print(f"foo() completed in {(time.time_ns() - start_time_ns)/1e9}s")


async def bar():
    import aiofiles

    start_time_ns = time.time_ns()
    print(
        f"Enterring bar, process ID {os.getpid()} & {threading.current_thread().name}"
    )

    # Open and read a file asynchronously
    async with aiofiles.open("app/data/errors/gmail-403-qpm.json", mode="r") as f:
        content = await f.read()
        print(f"bar() file content read.")

    print(f"bar() completed in {(time.time_ns() - start_time_ns)/1e9}s")


async def do_work(x: int):
    start_time = time.time()
    print(
        f"do_work({x}) | PID: {os.getpid()} | Thread: {threading.current_thread().name}"
    )
    await asyncio.sleep(x)
    print(f"do_work({x}) completed in {time.time() - start_time}s")


async def main():
    print("main()")
    print("===== DRILL #1 =====")
    # await asyncio.gather(*[foo(), bar()])
    print("\n\n===== DRILL #2 =====")
    # n = 10
    # print(f"{n} do_work() invocations (all called in sequence (1 after the other)")
    # for _ in range(n):
    #     await do_work(1)
    # print(f"{n} do_work() invocations at the same time.")
    # await asyncio.gather(*[do_work(1) for _ in range(n)])
    print("\n\n===== DRILL #3 =====")
    await asyncio.gather(metronome(), blocker())


async def metronome():
    print("Tik")
    await asyncio.sleep(1)
    print("Tok")


async def blocker():
    # Block the main thread (I believe this is like blocking the event loop)?
    time.sleep(300)


if __name__ == "__main__":
    asyncio.run(main())
