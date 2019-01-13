import showdown
import logging
import warnings
from showdown.utils import strip_prefix
from pprint import pprint

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

with open('./examples/data/login.txt', 'rt') as f,\
     open('./examples/data/owner.txt', 'rt') as o:
    username, password = f.read().strip().splitlines()
    ownername = o.read().strip()

class FollowerClient(showdown.Client):
    def __init__(self, **kwargs):
        showdown.Client.__init__(self, **kwargs)
        self.owner = showdown.User(ownername, client=self)

    async def on_query_response(self, response_type, data):
        logger.info(data)
        if response_type == 'userdetails':
            user_rooms = set(map(strip_prefix, data.get('rooms') or {}))
            bot_rooms = set(self.rooms)
            for room in user_rooms - bot_rooms:
                await self.join(room)
            for room in bot_rooms - user_rooms:
                await self.leave(room)

    @showdown.Client.on_interval(interval=3)
    async def get_owner_details(self): 
        await self.owner.request_user_details()

FollowerClient(name=username, password=password).start()