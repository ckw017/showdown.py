import asyncio
import aiohttp
import requests
import websockets
import sys
import pprint
import json
import time
import re
import logging
import time
import traceback
import random
import string
from . import events
from functools import wraps

ACTION_URL_BASE = 'https://play.pokemonshowdown.com/~~{}/action.php'
WEBSOCKET_URL_BASE = 'wss://{server_hostname}/showdown/{num_triplet}/{char_octet}/websocket'

server_map = {
    'azure': 'oppai.azure.lol',
    'showdown': 'sim2.psim.us'
}

logger = logging.getLogger(__name__)

def generate_ws_triplet():
    num = random.randint(0, 999)
    return str(num).zfill(3)

def generate_ws_octet():
    octet = ''
    for _ in range(8):
        octet += random.choice(string.ascii_lowercase)
    return octet


class User:
    def __init__(self, name):
        self.name = name
        self.id = clean(name)


    def __eq__(self, other):
        if type(other) == str:
            return self.id == clean(other)
        if issubclass(type(other), User):
            return self.id == other.id
        return False

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return '<User {}>'.format(self.name)

    async def request_user_details(self, client):
        await client.add_output('|/cmd userdetails {}'.format(self.id))

    async def get_rank(self, server_name='showdown'):
        params = {
            'act' : 'ladderget',
            'user' : self.id
        }
        async with aiohttp.ClientSession() as session:
            async with session.request('get', ACTION_URL_BASE.format(server_name), params=params) as response:
                result = await response.text()
        return parse_socket_input(result)

class Client(User):
    def __init__(self, name='', password=None, server_name='showdown', server_hostname=None):
        super().__init__(name)
        self.init_time = time.time()
        self.on_init() # Subclasses can override to do stuff on init

        # Set server info
        if not server_hostname:
            if server_name not in server_map:
                # TODO: More specific exception here
                raise Exception('Unrecognized server name: "{}". Please specify a `server_hostname'.format(server_name))
            server_hostname = server_map[server_name]

        # URL setup
        self.action_url = ACTION_URL_BASE.format(server_name)
        self.websocket_url = WEBSOCKET_URL_BASE.format(
            server_hostname = server_hostname,
            num_triplet     = generate_ws_triplet(),
            char_octet      = generate_ws_octet())
        logger.debug('Using showdown action url at  {}'.format(self.action_url))
        logger.debug('Using showdown websocket at {}'.format(self.websocket_url))

        # Store client params
        self.server_name = server_name
        self.server_hostname = server_hostname
        self.password = password
        self.challengekeyid, self.challstr = None, None
        self.output_queue = asyncio.Queue()

        # Start event loop
        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(self.handler())


    def set_password(self, password):
        self.password = password

    def set_name(self, name):
        self.name = name

    async def set_avatar(self, avatar_id):
        await self.add_output('|/avatar {}'.format(avatar_id))

    async def login(self):
        if not self.challengekeyid:
            raise Exception('Cannot login, challstr has not been received yet')
        if not self.password:
            raise Exception('Cannot login, no password has been specified')

        data = {'act': 'login',
                'name': self.name,
                'pass': self.password,
                'challenge': self.challstr,
                'challengekeyid': self.challengekeyid}

        logger.info('Logging in as {}'.format(self.name))
        result = requests.post(self.action_url, data = data)
        result_data = parse_socket_input(result.text)
        assertion_data = result_data['assertion']
        await self.websocket.send('["|/trn {},0,{}"]'.format(self.name, assertion_data))
        await self.on_login()

    async def upload_team(self, team_str):
        await self.add_output('|/utm {}'.format(team_str))

    async def validate_team(self, team_str, tier):
        await self.upload_team(team_str)
        await self.add_output('|/vtm {}'.format(tier))

    async def search_battles(self, team_str, tier):
        await self.upload_team(team_str)
        await self.add_output('|/search {}'.format(tier))

    async def private_message(self, user, content):
        await self.add_output('|/msg {}, {}'.format(user.name, content))

    async def forfeit(self, battle):
        await self.add_output('{}|/forfeit'.format(battle))

    async def leave(self, room):
        await self.add_output('{}|/leave'.format(room))

    async def join(self, room):
        await self.add_output('|/join {}'.format(room))

    async def say(self, msg, room=''):
        await self.add_output('{}|{}'.format(room, msg))

    async def add_output(self, out):
        await self.output_queue.put(out)

    def add_output_nowait(self, out):
        self.output_queue.put_nowait(out)

    async def handler(self):
        async with websockets.connect(self.websocket_url) as self.websocket:
            tasks = []
            for att in dir(self):
                att = getattr(self, att)
                if hasattr(att, 'is_interval_task') and att.is_interval_task:
                    tasks.append(asyncio.ensure_future(att()))
            done, pending = await asyncio.wait(tasks, 
                                return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()

    def on_interval(interval=0):
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                while True:
                    start_time = time.time()
                    await func(*args, **kwargs)
                    await asyncio.sleep(max(0, interval - (time.time() - start_time)))
            wrapper.is_interval_task = True
            return wrapper
        return decorator


    @on_interval()
    async def receiver(self):
        inp = await self.websocket.recv()
        if inp == 'o':
            await self.on_connect()
            return
        inps = parse_socket_input(inp)
        for room_id, inp in inps:
            if room_id == None:
                logger.warn('NULL room_id. Input of `{}`'.format(inp))
            tokens = inp.strip().split('|')
            if len(tokens) == 1:
                inp_type = 'raw_text'
                params = tokens
            else:
                inp_type = tokens[1].lower()
                params = tokens[2:]
            logger.debug('<<< Received:\n{}'.format(inp))

            #Thoughts: clean this up somehow?
            if inp_type == 'challstr':
                self.challengekeyid, self.challstr = params
                await self.on_challstr()
            elif inp_type == 'j':
                await self.on_join(events.Join(room_id, *params))
            elif inp_type == 'l':
                await self.on_leave(events.Leave(room_id, *params))
            elif inp_type == 'raw':
                await self.on_raw(events.RawHTML(room_id, *params))
            elif inp_type == 'uhtml':
                await self.on_uhtml(events.UHTML(room_id, *params))
            elif inp_type == 'init':
                await self.on_room_init(events.RoomInit(room_id, *params))
            elif inp_type == 'updateuser':
                await self.on_updateuser(events.UpdateUser(*params))
            elif inp_type == 'updatesearch':
                await self.on_updatesearch(events.UpdateSearch(*params))
            elif inp_type == 'updatechallenges':
                await self.on_updatechallenges(events.UpdateChallenges(*params))
            elif inp_type == 'c' or inp_type == 'c:':
                await self.on_chat_message(events.ChatMessage(room_id, inp_type, *params))
            elif inp_type == 'pm':
                await self.on_private_message(events.PrivateMessage(*params))
            elif inp_type == 'n':
                await self.on_name_change(events.NameChange(*params))
            elif inp_type == 'queryresponse':
                if params[0] == 'userdetails':
                    await self.on_user_details(events.UserDetails(params[1]))
                else:
                    logger.warn('Unhandled case: {}, {}'.format(room_id, inp))
            else:
                logger.warn('Unhandled case: {}, {}'.format(room_id, inp))

    @on_interval()
    async def sender(self):
        out = await self.output_queue.get()
        out = [out] if type(out) is str else out
        logger.debug('>>> Sending `{}`'.format(out))
        await self.websocket.send(json.dumps(out))
        await asyncio.sleep(len(out) * .5)

    async def on_challstr(self):
        logger.info('Received challstr')

    async def on_user_details(self, user_details):
        logger.info(user_details)

    async def on_name_change(self, name_change):
        logger.info(name_change)

    async def on_private_message(self, private_message):
        logger.info(private_message)

    async def on_chat_message(self, chat_message):
        logger.info(chat_message)

    async def on_updatechallenges(self, updatechallenges):
        logger.info(updatechallenges)

    async def on_updatesearch(self, updatesearch):
        logger.info(updatesearch)

    async def on_updateuser(self, updateuser):
        logger.info(updateuser)

    async def on_room_init(self, room_init):
        logger.info(room_init)

    async def on_uhtml(self, uhtml):
        logger.info(uhtml)

    async def on_raw(self, raw):
        logger.info(raw)

    async def on_leave(self, leave):
        logger.info(leave)

    async def on_join(self, join):
        logger.info(join)

    async def on_connect(self):
        logger.info('Connected to {}'.format(self.server_name))

    async def on_login(self):
        pass

    def on_init(self):
        pass

cleaner_re = re.compile('(\W|_)')
def clean(input_str):
    return cleaner_re.sub('', input_str.lower())

def parse_socket_input(socket_input):
    if socket_input.startswith(']'):
        return json.loads(socket_input[1:])
    elif socket_input.startswith('a'):
        loaded = json.loads(socket_input[1:])
        result = []
        for row in loaded:
            loaded = row.splitlines()
            if loaded[0].startswith('>'):
                room_id = loaded[0][1:]
                raw_events = loaded[1:]
            else:
                room_id = None
                raw_events = loaded
            for event in raw_events:
                result.append((room_id, event))
        return result


    raise Exception('Weird socket input: {}'.format(socket_input))
