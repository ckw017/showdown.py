import showdown
import logging

logging.basicConfig(level=logging.INFO)
with open('./tests/data/login.txt', 'rt') as f:
    username, password = f.read().splitlines()


class EchoClient(showdown.Client):
    async def on_login(self):
        await self.join('monotype')
        await self.set_avatar('caitlin')

    async def on_query_response(self, query_response):
        print(query_response.data)

    async def on_private_message(self, pm):
        if pm.recipient == self:
            await pm.author.message(pm.content)
            await pm.author.message(await pm.author.get_rank())

EchoClient(name=username, password=password)
