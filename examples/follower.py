import showdown
import logging
from pprint import pprint

logging.basicConfig(level=logging.INFO)
with open('./examples/data/login.txt', 'rt') as f,\
     open('./examples/data/owner.txt', 'rt') as o:
    username, password = f.read().splitlines()
    ownername = o.read()


class FollowerClient(showdown.Client):
    def __init__(self, **kwargs):
        showdown.Client.__init__(self, **kwargs)
        self.owner = showdown.User(ownername, client=self)

    async def on_query_response(self, query_response):
        if query_response.type == 'userdetails':
            rooms = query_response.data['rooms']
            if not rooms:
                return
            for room in rooms:
                await self.join(room)

    async def on_chat_message(self, chat_message):
        if chat_message.author == self.owner and chat_message.content=='.outputlogs':    
            print('\n'.join(self.rooms[chat_message.room_id].logs))

    async def on_private_message(self, pm):
        if pm.recipient == self:
            await pm.author.message(pm.author.register_time)

    @showdown.Client.on_interval(interval=3)
    async def get_owner_details(self): 
        await self.owner.request_user_details()

FollowerClient(name=username, password=password, server_id='azure').start()
