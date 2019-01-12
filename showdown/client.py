import asyncio
import requests
import websockets
import json
import time
import logging
import traceback
import warnings
from . import message, room, server, user, utils
from functools import wraps

#Logging setup
logger = logging.getLogger(__name__)

class Client(user.User):
    def __init__(self, name='Guest', password=None, loop=None, max_room_logs=5000,
                    server_id='showdown', server_host=None):
        super().__init__(name, client=self)

        # URL setup
        self.server = server.Server(id=server_id, host=server_host)
        self.action_url = self.server.generate_action_url()
        self.websocket_url = self.server.generate_ws_url()
        logger.info('Using action url at {}'.format(self.action_url))
        logger.info('Using websocket at {}'.format(self.websocket_url))

        # Store client params
        self.password = password
        self.challengekeyid, self.challstr = None, None
        self.output_queue = asyncio.Queue()
        self.rooms = {}
        self.max_room_logs = max_room_logs
        self.loop = loop or asyncio.get_event_loop()

    def start(self, autologin=True):
        self.autologin = autologin
        self.loop.run_until_complete(self.handler())

    async def handler(self):
        async with websockets.connect(self.websocket_url) as self.websocket:
            tasks = []
            for att in dir(self):
                att = getattr(self, att)
                if hasattr(att, '_is_interval_task') and att._is_interval_task:
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
                    elapsed = time.time() - start_time
                    await asyncio.sleep(max(0, interval - elapsed))
            wrapper._is_interval_task = True
            return wrapper
        return decorator

    @on_interval()
    async def sender(self):
        out = await self.output_queue.get()
        out = [out] if type(out) is str else out
        logger.debug('>>> Sending:\n{}'.format(out))
        await self.websocket.send(json.dumps(out))
        await asyncio.sleep(len(out) * .5)

    async def add_output(self, out):
        await self.output_queue.put(out)

    @on_interval()
    async def receiver(self):
        socket_input = await self.websocket.recv()
        logger.debug('<<< Received:\n{}'.format(socket_input))

        #Showdown sends this response on initial connection
        if socket_input == 'o':
            logger.info('Connected on {}'.format(self.websocket_url))
            await self.on_connect()
            return

        inputs = utils.parse_socket_input(socket_input)
        for room_id, inp in inputs:
            logger.debug('||| Parsing:\n{}'.format(inp))
            inp_type, params = utils.parse_text_input(inp)
            
            #Set challstr attributes and autologin
            if inp_type == 'challstr':
                self.challengekeyid, self.challstr = params
                if self.name and self.password and self.autologin:
                    await self.login()
                elif self.autologin:
                    msg = ("Cannot login without username and password. If "
                           "you don't want your client to be logged in, "
                           "you can use Client.start(autologin=False).")
                    raise Exception(msg)

            #Process query response
            elif inp_type == 'queryresponse':
                response_type, data = params
                data = json.loads(data)
                await self.on_query_response(response_type, data)
                if response_type == 'savereplay':
                    pass #TODO: upload replay stuff here

            #Messages
            elif inp_type == 'c:' or inp_type == 'c':
                chat_message = message.ChatMessage(room_id, inp_type, *params, client=self)
                await self.on_chat_message(chat_message)
            elif inp_type == 'pm':
                private_message = message.PrivateMessage(*params, client=self)
                await self.on_private_message(private_message)

            #Rooms
            elif inp_type == 'init':
                room_type = params[0]
                room_obj = room.class_map.get(room_type, room.Room)(
                    room_id, client=self, max_logs=self.max_room_logs)
                self.rooms[room_id] = room_obj
                await self.on_room_init(room_obj)
            elif inp_type == 'deinit':
                if room_id in self.rooms:
                    await self.on_room_deinit(self.rooms.pop(room_id))

            #add content to proper room
            if room_id in self.rooms:
                self.rooms[room_id].add_content(inp)

            await self.on_receive(room_id, inp_type, params)

    async def login(self):
        if not self.challengekeyid:
            raise Exception('Cannot login, challstr has not been received yet')
        if not self.name:
            raise Exception('Cannot login, no username has been specified')
        if not self.password:
            raise Exception('Cannot login, no password has been specified')

        data = {'act': 'login',
                'name': self.name,
                'pass': self.password,
                'challenge': self.challstr,
                'challengekeyid': self.challengekeyid}

        logger.info('Logging in as "{}"'.format(self.name))
        result = requests.post(self.action_url, data = data)
        result_data = utils.parse_http_input(result.text)
        assertion_data = result_data['assertion']
        await self.websocket.send('["|/trn {},0,{}"]'.format(self.name, assertion_data))
        await self.on_login(result_data)

    async def set_avatar(self, avatar_id):
        await self.add_output('|/avatar {}'.format(avatar_id))

    #Ladder interactions
    async def upload_team(self, team_str):
        await self.add_output('|/utm {}'.format(team_str))

    async def validate_team(self, team_str, battle_format):
        battle_format = utils.name_to_id(battle_format)
        await self.upload_team(team_str)
        await self.add_output('|/vtm {}'.format(battle_format))

    async def search_battles(self, team_str, battle_format):
        battle_format = utils.name_to_id(battle_format)
        await self.upload_team(team_str)
        await self.add_output('|/search {}'.format(battle_format))

    async def cancel_search(self):
        await self.add_output('|/cancelsearch')

    #Rooms
    async def leave(self, room_name):
        room_id = utils.name_to_id(room_name)
        await self.add_output('{}|/leave'.format(room_id))

    async def join(self, room_name):
        room_id = utils.name_to_id(room_name)
        await self.add_output('|/join {}'.format(room_id))

    #Battles
    async def save_replay(self, battle_id):
        await self.add_output('{}|/savereplay'.format(battle_id))

    async def forfeit(self, battle_id):
        await self.add_output('{}|/forfeit'.format(battle_id))

    #Messages
    async def private_message(self, user_name, content):
        content = utils.clean_message_content(content)
        user_id = utils.name_to_id(user_name)
        await self.add_output('|/msg {}, {}'.format(user_id, content))

    async def say(self, room_name, content):
        content = utils.clean_message_content(content)
        room_id = utils.name_to_id(room_name)
        if room_id == 'lobby':
            room_id = ''
        await self.add_output('{}|{}'.format(room_id, content))

    #Queries
    async def query_rooms(self):
        await self.add_output('|/cmd rooms')

    async def query_battles(self, tier='', min_elo=None):
        output = '|/cmd roomlist {}'.format(utils.name_to_id(tier))
        if min_elo is not None:
            output += ', {}'.format(min_elo)
        await self.add_output(output)

    #Hooks
    async def on_connect(self):
        pass

    async def on_login(self, login_response):
        pass

    async def on_room_init(self, room_obj):
        pass

    async def on_room_deinit(self, room_obj):
        pass

    async def on_query_response(self, response_type, data):
        pass

    async def on_chat_message(self, chat_message):
        pass

    async def on_private_message(self, private_message):
        pass

    async def on_receive(self, room_id, inp_type, params):
        pass