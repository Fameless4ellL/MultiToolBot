from Bot.app import *


class Timer:
    def __init__(self, timeout, callback):
        self._timeout = timeout
        self._callback = callback
        self._task = asyncio.ensure_future(self._job())

    async def _job(self):
        await asyncio.sleep(self._timeout)
        await self._callback()

    def cancel(self):
        self._task.cancel()
        print('timer stopped!')


async def timeout_callback():
    await asyncio.sleep(0.1)
    print('Beep!')
    await timer_is_done()
