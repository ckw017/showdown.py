import showdown
import logging
import warnings
from pprint import pprint

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

with open('./examples/data/login.txt', 'rt') as f,\
     open('./examples/data/owner.txt', 'rt') as o:
    username, password = f.read().splitlines()
    ownername = o.read()

class ReplayClient(showdown.Client):
    def __init__(self, **kwargs):
        showdown.Client.__init__(self, **kwargs)
        self.owner = showdown.User(ownername, client=self)

    async def on_query_response(self, response_type, data):
        if response_type == 'roomlist':
            for battle_id in set(data['rooms']) - set(self.rooms):
                self.rooms[battle_id] = None
                await self.join(battle_id)

    async def on_private_message(self, pm):
        if pm.recipient == self:
            await pm.reply(pm.author.register_time)

    async def on_receive(self, room_id, inp_type, params):
        if inp_type == 'win':
            await self.save_replay(room_id)

    @showdown.Client.on_interval(interval=3)
    async def check_monotype(self): 
        await self.query_battles(tier='gen7ou', min_elo=1500)

ReplayClient(name=username, password=password).start()