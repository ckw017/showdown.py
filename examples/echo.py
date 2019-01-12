import showdown
import logging

logging.basicConfig(level=logging.INFO)
with open('./examples/data/login.txt', 'rt') as f:
    username, password = f.read().splitlines()


class EchoClient(showdown.Client):
    async def on_private_message(self, pm):
        if pm.recipient == self:
            await pm.reply(pm.content)

EchoClient(name=username, password=password).start()
