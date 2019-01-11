import showdown
import logging
from pprint import pprint

logging.basicConfig(level=logging.INFO)
with open('./tests/data/login.txt', 'rt') as f,\
     open('./tests/data/owner.txt', 'rt') as o:
    username, password = f.read().splitlines()
    ownername = o.read()


class FollowerClient(showdown.Client):
    def on_init(self):
        self.owner = showdown.User(ownername, client=self)

    async def on_query_response(self, query_response):
        if query_response.type == 'userdetails':
            rooms = query_response.data['rooms']
            if not rooms:
                return
            for room in rooms:
                await self.join(room)
        if 'lobby' in self.rooms:
            pprint(self.rooms['lobby'].userlist)

    @showdown.Client.on_interval(interval=3)
    async def get_owner_details(self): 
        await self.owner.request_user_details()


FollowerClient(name=username, password=password)
