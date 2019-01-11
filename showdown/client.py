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
from .utils import abbreviate, parse_http_input, parse_socket_input
from . import events, user, message
from functools import wraps

#Logging setup
logger = logging.getLogger(__name__)

#Base URLs
ACTION_URL_BASE =  'https://play.pokemonshowdown.com/~~{}/action.php'
WEBSOCKET_URL_BASE = 'wss://{server_hostname}/showdown/{num_triplet}/{char_octet}/websocket'

#Default servers
server_map = {
    'azure': 'oppai.azure.lol',
    'showdown': 'sim2.psim.us'
}

def generate_ws_triplet():
    num = random.randint(0, 999)
    return str(num).zfill(3)

def generate_ws_octet():
    octet = ''
    for _ in range(8):
        octet += random.choice(string.ascii_lowercase)
    return octet

def generate_ws_url(server_hostname):
    return WEBSOCKET_URL_BASE.format(
            server_hostname = server_hostname,
            num_triplet     = generate_ws_triplet(),
            char_octet      = generate_ws_octet())

class Client(user.User):
    def __init__(self, name='', password=None, autologin=True, server_name='showdown', server_hostname=None):
        super().__init__(name)
        self.init_time = time.time()
        self.on_init() # Subclasses can override to do stuff on init

        # Set server info
        if not server_hostname:
            if server_name not in server_map:
                # TODO: More specific exception here
                raise Exception('Unrecognized server name: "{}". Please specify a `server_hostname'.format(server_name))
            server_hostname = server_map[server_name]
        self.server_name = server_name
        self.server_hostname = server_hostname

        # URL setup
        self.action_url = ACTION_URL_BASE.format(server_name)
        self.websocket_url = generate_ws_url(server_hostname)
        logger.debug('Using showdown action url at  {}'.format(self.action_url))
        logger.debug('Using showdown websocket at {}'.format(self.websocket_url))

        # Store client params
        self.autologin = autologin
        self.password = password
        self.challengekeyid, self.challstr = None, None
        self.output_queue = asyncio.Queue()

        # Start event loop
        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(self.handler())

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
        result_data = parse_http_input(result.text)
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

    async def cancel_search(self):
        await self.add_output('|/cancelsearch')

    async def private_message(self, user, content):
        content = str(content)[:300]
        await self.add_output('|/msg {}, {}'.format(user.name, content))

    async def forfeit(self, battle):
        await self.add_output('{}|/forfeit'.format(battle))

    async def leave(self, room):
        await self.add_output('{}|/leave'.format(room))

    async def join(self, room):
        await self.add_output('|/join {}'.format(room))

    async def say(self, msg, room=''):
        msg = str(msg)[:300]
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
    async def sender(self):
        out = await self.output_queue.get()
        out = [out] if type(out) is str else out
        logger.debug('>>> Sending `{}`'.format(out))
        await self.websocket.send(json.dumps(out))
        await asyncio.sleep(len(out) * .5)

    @on_interval()
    async def receiver(self):
        socket_input = await self.websocket.recv()
        logger.debug('<<< Received:\n{}'.format(socket_input))
        if socket_input == 'o': #Showdown sends this response on first connection
            logger.info('Connected on {}'.format(self.websocket_url))
            await self.on_connect()
            return
        inputs = parse_socket_input(socket_input)
        for room_id, inp in inputs:
            logger.debug('Parsing:\n{}'.format(inp))
            tokens = inp.strip().split('|')

            #Seperate input type and params
            if len(tokens) == 1:
                inp_type = 'rawtext'
                params = tokens
            else:
                inp_type = tokens[1].lower()
                params = tokens[2:]

            # Parse main types of input
            if inp_type == 'challstr':
                self.challengekeyid, self.challstr = params
                logger.info('Received challstr {}'.format(params))
                await self.on_challstr()
                if self.name and self.password and self.autologin:
                    await self.login()
                elif self.autologin:
                    logger.warn('Cannot login without username or password.')
            elif inp_type == 'j':
                user_join = user.UserJoin(room_id, *params, client=self)
                logger.info(user_join)
                await self.on_user_join(user_join)
            elif inp_type == 'l':
                user_leave = user.UserLeave(room_id, *params, client=self)
                logger.info(user_leave)
                await self.on_user_leave(user_leave)
            elif inp_type == 'n':
                name_change = user.UserNameChange(room_id, *params, client=self)
                logger.info(name_change)
                await self.on_user_name_change(name_change)
            elif inp_type == 'queryresponse':
                query_response = QueryResponse(*params)
                logger.info(query_response)
                await self.on_query_response(query_response)
            elif inp_type == 'c:' or inp_type == 'c':
                chat_message = message.ChatMessage(room_id, inp_type, *params, client=self)
                logger.info(chat_message)
                await self.on_chat_message(chat_message)
            elif inp_type == 'pm':
                private_message = message.PrivateMessage(*params, client=self)
                logger.info(private_message)
                await self.on_private_message(private_message)
            elif inp_type == 'rawtext':
                raw_text = message.RawText(room_id, *params)
                logger.info(raw_text)
                await self.on_raw_text(raw_text)
            else:
                logger.info('Unhandled case:\n'
                            'room_id: {}\n'
                            'inp_type: {}\n'
                            'params: {}'.format(room_id, inp_type, params))
            await self.post_parse(room_id, inp_type, params)

    async def on_connect(self):
        pass

    async def on_challstr(self):
        pass

    async def on_login(self):
        pass

    async def on_user_name_change(self, name_change):
        pass

    async def on_user_leave(self, user_leave):
        pass

    async def on_user_join(self, user_join):
        pass

    async def on_query_response(self, query_response):
        pass

    async def on_chat_message(self, chat_message):
        pass

    async def on_private_message(self, private_message):
        pass

    async def on_raw_text(self, raw_text):
        pass

    async def post_parse(self, room_id, inp_type, params):
        pass

    def on_init(self):
        pass

class QueryResponse:
    def __init__(self, qtype, data):
        self.type = qtype
        self.data = json.loads(data)

    def __repr__(self):
        return '<QueryResponse ({}) {}>'.format(
            self.type,
            abbreviate(str(self.data)))
