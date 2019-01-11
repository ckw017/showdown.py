import asyncio
import requests
import websockets
import json
import time
import re
import logging
import traceback
from . import utils
from . import user, message, room
from .server import Server
from functools import wraps

#Logging setup
logger = logging.getLogger(__name__)

class Client(user.User):
    def __init__(self, name='', password=None, loop=None, max_room_logs=5000,
                    server_id='showdown', server_host=None):
        super().__init__(name, client=self)

        # URL setup
        self.server = Server(id=server_id, host=server_host)
        self.action_url = self.server.generate_action_url()
        self.websocket_url = self.server.generate_ws_url()
        logger.info('Using showdown action url at  {}'.format(self.action_url))
        logger.info('Using showdown websocket at {}'.format(self.websocket_url))

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
        result_data = utils.parse_http_input(result.text)
        assertion_data = result_data['assertion']
        await self.websocket.send('["|/trn {},0,{}"]'.format(self.name, assertion_data))
        await self.on_login(result_data)

    async def upload_team(self, team_str):
        await self.add_output('|/utm {}'.format(team_str))

    async def validate_team(self, team_str, tier):
        await self.upload_team(team_str)
        await self.add_output('|/vtm {}'.format(tier))

    async def search_battles(self, team_str, battle_format):
        await self.upload_team(team_str)
        await self.add_output('|/search {}'.format(battle_format))

    async def cancel_search(self):
        await self.add_output('|/cancelsearch')

    async def save_replay(self, battle_id):
        assert battle_id.startswith('battle-')
        await self.add_output('{}|/savereplay'.format(battle_id))

    async def private_message(self, user, content):
        content = str(content)[:300]
        await self.add_output('|/msg {}, {}'.format(user.name, content))

    async def forfeit(self, battle):
        await self.add_output('{}|/forfeit'.format(battle))

    async def leave(self, room):
        await self.add_output('{}|/leave'.format(room))

    async def join(self, room):
        room = utils.name_to_id(room)
        await self.add_output('|/join {}'.format(room))

    async def say(self, msg, room=''):
        msg = str(msg)[:300]
        await self.add_output('{}|{}'.format(room, msg))

    async def query_rooms(self):
        await self.add_output('|/cmd rooms')

    async def query_battles(self, tier='', min_elo=None):
        message = '|/cmd roomlist {}'.format(name_to_id(tier))
        if min_elo is not None:
            message += ', {}'.format(min_elo)
        await self.add_output(message)

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
                    elapsed = time.time() - start_time
                    await asyncio.sleep(max(0, interval - elapsed))
            wrapper.is_interval_task = True
            return wrapper
        return decorator


    @on_interval()
    async def sender(self):
        out = await self.output_queue.get()
        out = [out] if type(out) is str else out
        logger.debug('>>> Sending:\n{}'.format(out))
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
        inputs = utils.parse_socket_input(socket_input)
        for room_id, inp in inputs:
            logger.debug('Parsing:\n{}'.format(inp))
            inp_type, params = utils.parse_text_input(inp)

            # Parse main types of input
            if inp_type == 'challstr':
                self.challengekeyid, self.challstr = params
                logger.info('Received challstr {}'.format(params))
                await self.on_challstr()
                if self.name and self.password and self.autologin:
                    await self.login()
                elif self.autologin:
                    logger.warn('Cannot login without username and password.')
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
                if query_response.type == 'savereplay':
                    pass #TODO: upload replay stuff here
            elif inp_type == 'formats':
                self.server.set_formats(*params)
            elif inp_type == 'customgroups':
                self.server.set_custom_groups(*params)
            elif inp_type == 'c:' or inp_type == 'c':
                chat_message = message.ChatMessage(room_id, inp_type, *params, client=self)
                logger.info(chat_message)
                await self.on_chat_message(chat_message)
            elif inp_type == 'pm':
                private_message = message.PrivateMessage(*params, client=self)
                logger.info(private_message)
                await self.on_private_message(private_message)
            elif inp_type == 'init':
                room_type = params[0]
                if room_type == 'chat':
                    room_class = room.Room
                elif room_type == 'battle':
                    room_class = room.Battle
                room_obj = room_class(room_id, client=self, max_logs=self.max_room_logs)
                self.rooms[room_id] = room_obj
                await self.on_room_init(room_obj)
            elif inp_type == 'deinit':
                if room_id in self.rooms:
                    await self.on_room_deinit(self.rooms.pop(room_id))
            elif inp_type == 'tournament':
                tour_update = room.TourUpdate(room_id, *params)
                logger.info(tour_update)
                await self.on_tour_update(tour_update)
            elif inp_type == 'rawtext':
                raw_text = message.RawText(room_id, *params)
                logger.info(raw_text)
                await self.on_raw_text(raw_text)
            else:
                logger.debug('Unhandled case:\n'
                            'room_id: {}\n'
                            'inp_type: {}\n'
                            'params: {}'.format(room_id, inp_type, params))

            await self.update_rooms(room_id, inp)
            await self.on_receive(room_id, inp_type, params)

    async def update_rooms(self, room_id, inp):
        if room_id in self.rooms:
            self.rooms[room_id].add_content(inp)

    #Hooks
    async def on_connect(self):
        pass

    async def on_challstr(self):
        pass

    async def on_login(self, login_response):
        pass

    async def on_user_leave(self, user_leave):
        pass

    async def on_user_join(self, user_join):
        pass

    async def on_user_name_change(self, user_name_change):
        pass

    async def on_tour_update(self, tour_update):
        pass

    async def on_room_init(self, room):
        pass

    async def on_room_deinit(self, room_obj):
        pass

    async def on_query_response(self, query_response):
        pass

    async def on_chat_message(self, chat_message):
        pass

    async def on_private_message(self, private_message):
        pass

    async def on_raw_text(self, raw_text):
        pass

    async def on_receive(self, room_id, inp_type, params):
        pass

class QueryResponse:
    def __init__(self, qtype, data):
        self.type = qtype
        self.data = json.loads(data)

    def __repr__(self):
        return '<QueryResponse ({}) {}>'.format(
            self.type,
            utils.abbreviate(str(self.data)))
