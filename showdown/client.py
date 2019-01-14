# -*- coding: utf-8 -*-
"""Module for showdown's Client class"""
import asyncio
import aiohttp
import requests
import websockets
import json
import time
import logging
import traceback
import warnings
import math
from functools import wraps
from . import message, room, server, user, utils

#Logging setup
logger = logging.getLogger(__name__)

class OutputToken:
    """
    Class used with the client's output queue to schedule when outputs should
    be used, delayed, or discarded.
    """
    def __init__(self, content, ignore_before, discard_after):
        self.content = [content] if type(content) is str else content
        self.ignore_before = ignore_before
        self.discard_after = discard_after
        self.sent = False
        self.discarded = False

    def expired(self):
        return time.time() > self.discard_after

    def ready(self):
        return time.time() > self.ignore_before

class Client(user.User):
    """
    Class for interacting with Showdown's websocket interface. Includes hooks
    for certain events and high-level methods to send and receive information
    from Showdown's servers.

    Notes:
        Once you create a client object, use Client.start() to begin you 
        connection. If want your bot to be anonymous (not logged in), run start
        with the keyword argument start(autologin=False)

    Args:
        name (:obj:`str`, optional) : The username of the account you would 
            like to log in to. By default, this is set to the empty string.
        password (:obj:`str`, optional) L The password of the account you would
            like to log in to. By default, this is set to the empty string.
        loop (optional) : the asyncio eventloop used by the client to send on 
            receive info across websockets. If no loop is specified, 
            asyncio.get_event_loop() will be used to create an event loop
        max_room_logs (:obj:`int`, optional) : The number of logs to save for
            active rooms. A log is any event that takes place in a room, 
            including user joins, leaves, chat messages, and raw html. This
            information is stored in a FIFO deque.
        server_id (:obj:`str`, optional) : The id of the server the client will
            connect to. For a list of all associated  servers, visit the page
            at https://pokemonshowdown.com/servers. This value defaults to 
            'showdown', the "main" showdown server.
        server_host (:obj:`str`, optional) : The host name of the server the
            client will connect to. This value is None by default, and will be
            retrieved automatically from 
            https://pokemonshowdown.com/servers/{host_name}.json

    Attributes:
        server (showdown.server.Server) : object representing the server the 
            client is connected to.
        websocket_url (str) : The url over which the client's websocket 
            connection is established
        password (str) : The password the client uses to login
        challengekeyid (str) : Id assigned by the server to identify the 
            client. Used to login.
        challengestr (str) : Token assigned by the server to identify the 
            client. Used to login.
        output_queue (asyncio.Queue) : Queue used to manage what is sent back
            to the server websocket.
        rooms (dict) : Dictionary with entries of {str : showdown.room.Room} 
            that maps room_id's to Rooms the client is currently connected to.
        max_room_logs (int) : The maximum number of logs stored in this client's
            Room objects.
        autologin (bool) : Bool denoting whether or not the client will 
            automatically login on a call to the Client.start method. Can be 
            set by using a keyword argument in Client.start
        websocket (websockets.websocket) : The socket the client uses to 
            communicate with the server. Initialized to None until 
            Client.start() is called.
        loop (asyncio event loop (Differs between platforms)) : The event loop
            used for the client's websocket interactions and methods specified
            with the on_interval decorator
    """

    def __init__(self, name='Guest', password='', loop=None, max_room_logs=5000,
                    server_id='showdown', server_host=None):
        super().__init__(name, client=self)

        # URL setup
        self.server = server.Server(id=server_id, host=server_host, client=self)
        self.websocket_url = self.server.generate_ws_url()
        logger.info('Using websocket at {}'.format(self.websocket_url))

        # Initialize client attributes
        self.password = password
        self.challengekeyid, self.challstr = None, None
        self.output_queue = asyncio.Queue()
        self.rooms = {}
        self.challenges = {};
        self.max_room_logs = max_room_logs
        self.autologin = True
        self.websocket = None #Initialized in _handler
        self.session = None
        self.loop = loop or asyncio.get_event_loop()

    def start(self, autologin=True):
        """
        Starts the event loop stored in the Client's loop attribute.
    
        Returns:
            bool : True if exited gracefully (on an interrupt), else False

        Args:
            autologin (:obj:`bool`, optional) : Bool denoting whether or not the
            client will automatically login after connecting to the server. 
            Defaults to True.
        """
        self.autologin = autologin
        try:
            if self.loop.is_running():
                asyncio.ensure_future(
                    self._handler(),
                    loop=self.loop
                )
                logger.info("The client's event loop was already running. "
                            "The client will run as a task on the loop.")
                return True
            else:
                self.loop.run_until_complete(self._handler())
        except KeyboardInterrupt:
            logger.info('Interrupt signal received. Closing client connection.')
            self.websocket.close() if self.websocket else None
            logger.info('Event loop closed.')
            return True
        except:
            import traceback
            traceback.print_exc()
            return False

    async def _handler(self):
        """
        |coro|

        Creates websocket connection and adds any methods flagged by the 
        on_interval decorator to the event loop.
        """
        async with websockets.connect(self.websocket_url) as self.websocket, \
                                  aiohttp.ClientSession() as session:
            self.server.set_session(session)
            tasks = []
            for att in dir(self):
                att = getattr(self, att)
                if hasattr(att, '_is_interval_task') and att._is_interval_task:
                    tasks.append(asyncio.ensure_future(att()))
            done, pending = await asyncio.wait(tasks, 
                                return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()

    def on_interval(interval=0.0):
        """
        A decorator creator to flag methods that the client should loop in an 
        interval

        Params:
            interval (:obj:`float`, optional) :  The length of the interval to 
            run the method on in seconds

        Returns:
            func - A decorator function that loops the passed in func on the 
            specified interval, and flagged to be added to the client's event
            loop.

        Example:
            class OUChecker(showdown.Client):
                @on_interval(interval=3.0):
                async def check_ou_matches(self):
                    '''Checks the ou ladder ever 3 seconds'''
                    await self.query_battles(tier='gen7ou')
        """
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
        """
        |coro|

        Waits for relevant output to appear in the client's output_queue 
        attribute, and sends it back to the server through websocket.

        Returns:
            None
        """
        out = await self.output_queue.get()
        now = time.time()
        if not out.ready():
            logger.info('>>> Requeuing {}'.format(out))
            await self.output_queue.put(out)
            await asyncio.sleep(.05)
            return
        if out.expired():
            logger.info('>>> Discarding {}'.format(out))
            out.discarded = True
            return
        content = [out.content] if type(out.content) is str else out.content
        logger.info('>>> Sending:\n{}'.format(content))
        await self.websocket.send(json.dumps(content))
        out.sent = True
        await asyncio.sleep(len(content) * .5)

    async def add_output(self, content, delay=0, lifespan=math.inf):
        """
        |coro|

        Adds output to be sent across the client's connection to the server.

        Params:
            content (:obj:`str` or obj:`list` of obj:`str`) : Content to be sent
                to the server.
            delay (:obj:`int` or obj:`float`, optional) : The minimum delay
                before sending the content. If the client's output queue 
                encounters this value before the delay has passed, it will 
                ignore the content.
            lifespan (:obj:`int` or obj:`float`, optional) : The maximum delay
                before content is discarded from the client's output queue.

        Returns:
            namedtuple : Token representing the content to be sent.
        """
        assert type(lifespan) in (int, float), \
            'lifespan must be float or int'
        assert type(delay) in (int, float), \
            'delay must be float or int'
        assert delay < lifespan, \
            'Delay should be strictly less than lifespan'
        assert delay >= 0 and lifespan >= 0, \
            'Lifespan and delay should be nonnegative'

        now = time.time()
        ignore_before = now + delay
        discard_after = now + lifespan
        token = OutputToken(content, ignore_before, discard_after)
        await self.output_queue.put(token)
        return token

    @on_interval()
    async def receiver(self):
        """
        |coro|

        Awaits input from websocket and parses the important stuff. Subclasses 
        can hook into the input through Client.on_receive.
        """
        socket_input = await self.websocket.recv()
        logger.debug('<<< Received:\n{}'.format(socket_input))

        #Showdown sends this response on initial connection
        if socket_input == 'o':
            logger.info('Connected on {}'.format(self.websocket_url))
            asyncio.ensure_future(
                self.on_connect(),
                loop=self.loop
            )
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
                response_type, data = params[0], '|'.join(params[1:])
                data = json.loads(data)
                asyncio.ensure_future(
                    self.on_query_response(response_type, data),
                    loop=self.loop
                )
                if response_type == 'savereplay':
                    asyncio.ensure_future(
                        self.server.save_replay_async(data),
                        loop = self.loop)

            #Challenge updates
            elif inp_type == 'updatechallenges':
                self.challenges = json.loads(params[0])
                asyncio.ensure_future(
                    self.on_challenge_update(self.challenges),
                    loop = self.loop
                )

            #Messages
            elif inp_type == 'c:' or inp_type == 'c':
                timestamp = None
                if inp_type == 'c:':
                    timestamp, params = int(params[0]), params[1:]
                author_str, *content = params
                content = '|'.join(content)
                chat_message = message.ChatMessage(room_id, timestamp,
                    author_str, content, client=self)
                asyncio.ensure_future(
                    self.on_chat_message(chat_message),
                    loop=self.loop
                )
            elif inp_type == 'pm':
                author_str, recipient_str, *content = params
                content = '|'.join(content)
                private_message = message.PrivateMessage(
                    author_str, recipient_str, content, client=self)
                asyncio.ensure_future(
                    self.on_private_message(private_message),
                    loop = self.loop
                )

            #Rooms
            elif inp_type == 'init':
                room_type = params[0]
                room_obj = room.class_map.get(room_type, room.Room)(
                    room_id, client=self, max_logs=self.max_room_logs)
                self.rooms[room_id] = room_obj
                asyncio.ensure_future(
                    self.on_room_init(room_obj),
                    loop=self.loop
                )
            elif inp_type == 'deinit':
                if room_id in self.rooms:
                    asyncio.ensure_future(
                        self.on_room_deinit(self.rooms.pop(room_id)),
                        loop = self.loop
                    )

            #add content to proper room
            if isinstance(self.rooms.get(room_id, None), room.Room):
                self.rooms[room_id].add_content(inp)

            asyncio.ensure_future(
                self.on_receive(room_id, inp_type, params),
                loop=self.loop
            )

    async def login(self):
        """
        |coro|

        Logins in the user using the name, password, challstr and challengekeyid
        paramaters.
        """
        if not self.challengekeyid:
            raise Exception('Cannot login, challstr has not been received yet')
        if not self.name:
            raise Exception('Cannot login, no username has been specified')
        if not self.password:
            raise Exception('Cannot login, no password has been specified')

        logger.info('Logging in as "{}"'.format(self.name))
        login_data = await self.server.login_async(self.name, 
            self.password, self.challstr, self.challengekeyid)
        if not login_data['actionsuccess']:
            raise ValueError('Failed to log in as user `{}`.'
                ' Raw login result:\n{}'.format(self.name, result_data))
        else:
            logger.info('Login succeeded')
        await self.websocket.send('["|/trn {},0,{}"]'
            .format(self.name, login_data['assertion']))
        asyncio.ensure_future(
            self.on_login(login_data),
            loop=self.loop
        )

    async def set_avatar(self, avatar_id, delay=0, lifespan=math.inf):
        """
        |coro|
        
        Sets the user's avatar to the specified avatar_id value.
        """
        await self.add_output('|/avatar {}'.format(avatar_id), 
            delay=delay, lifespan=lifespan)

    async def use_command(self, room_id, command_name, *args,
        delay=0, lifespan=math.inf):
        """
        |coro|

        Sends a generic command to the specified room. For example, to send the
        `/mute user, No spamming!` command in the Monotype room, you can use
        client.use_command('monotype', 'mute', 'user', 'No spamming!')
        """
        await self.add_output('{}|/{} {}'.format(
            room_id, command_name, ', '.join(args)),
            delay=delay, lifespan=lifespan)

    # # # # # # # # # # # #
    # Ladder interactions #
    # # # # # # # # # # # #

    async def upload_team(self, team, delay=0, lifespan=math.inf):
        """
        |coro|
        
        Upload's the specified team to the server. Generally isn't needed 
        on its own, and is more useful as a subroutine for validate_team and 
        search_battles.
        """
        team_str = utils.to_team_str(team)
        await self.add_output('|/utm {}'.format(team_str),
            delay=delay, lifespan=lifespan)

    async def validate_team(self, team, battle_format, 
        delay=0, lifespan=math.inf):
        """
        |coro|
        
        Uploads the specified team to the server and validates for the 
        format specified by battle_format.
        """
        battle_format = utils.name_to_id(battle_format)
        team = team or 'null'
        await self.upload_team(team, delay=delay, lifespan=lifespan)
        await self.add_output('|/vtm {}'.format(battle_format),
            delay=delay, lifespan=lifespan)

    async def search_battles(self, team, battle_format, 
        delay=0, lifespan=math.inf):
        """
        |coro|
        
        Uploads the specified team and searches for battles for the format 
        specified by battle_format.

        Notes:
            You can specify the team to be None or the empty string for 
            tiers like randombattles, where no team is needed to be provided.
        """
        battle_format = utils.name_to_id(battle_format)
        await self.upload_team(team, delay=delay, lifespan=lifespan)
        await self.add_output('|/search {}'.format(battle_format),
            delay=delay, lifespan=lifespan)

    async def cancel_search(self, delay=0, lifespan=math.inf):
        """
        |coro|
        
        Cancels a battle search.
        """
        await self.add_output('|/cancelsearch', 
            delay=delay, lifespan=lifespan)

    # # # # # # # # # # # 
    # Room interactions #
    # # # # # # # # # # # 

    async def join(self, room_id, delay=0, lifespan=math.inf):
        """
        |coro|
        
        Makes the client join  the room specified by the given room_id.

        Params:
            room_id (:obj:`str`) : The id of the room you want to join. 
                Ex: 'lobby', 'ou'

        Notes:
            This method takes a str. Attempting to pass in a Room object will
            fail. Use the Room.leave() method instead, or Client.leave(room.id)
        """
        assert type(room_id) is str, "Paramater room_id should be a string."
        await self.add_output('|/join {}'.format(room_id),
            delay=delay, lifespan=lifespan)

    async def leave(self, room_id, delay=0, lifespan=math.inf):
        """
        |coro|
        
        Makes client leave the room specified by the given room_id.

        Params:
            room_id (:obj:`str`) : The id of the room you want to leave. 
                Ex: 'lobby', 'ou'

        Notes:
            This method takes a str. Attempting to pass in a Room object will
            fail. Use the Room.leave() method instead, or Client.leave(room.id).
        """
        assert type(room_id) is str, "Parameter room_id should be a string."
        await self.add_output('{}|/leave'.format(room_id),
            delay=delay, lifespan=lifespan)

    # # # # # # # # # # # #
    # Battle interactions #
    # # # # # # # # # # # #

    async def save_replay(self, battle_id, delay=0, lifespan=math.inf):
        """
        |coro|
        
        Requests data from the server to save the battle specified by battle_id.

        Params:
            battle_id (:obj:`str`) : The id of the battle you want to save the 
                replay for. Ex: 'battle-gen7monotype-12345678'

        Returns:
            None
        
        Notes:
            This method takes a str. Attempting to pass in a Battle object will
            fail. Use the Battle.save_replay() method instead, or 
            Client.save_replay(battle.id)

            The actual upload is handled on the server's response through a
            query response with type "savereplay".
        """
        assert type(battle_id) is str, battle_id.startswith('battle-')
        await self.add_output('{}|/savereplay'.format(battle_id,
            delay=delay, lifespan=lifespan))

    async def forfeit(self, battle_id, delay=0, lifespan=math.inf):
        """
        |coro|
        
        Forfeit the match specified by battle_id.

        Returns:
            None

        Params:
            battle_id (:obj:`str`) : The id of the battle you want to forfeit.
                Ex: 'battle-gen7monotype-12345678'
        """
        await self.add_output('{}|/forfeit'.format(battle_id),
            delay=delay, lifespan=lifespan)

    # # # # # # # 
    # Messages  #
    # # # # # # #

    async def private_message(self, user_name, content, strict=False, 
        delay=0, lifespan=math.inf):
        """
        |coro|
        
        Sends a private message with content to the user specified by user_name.
        The client must be logged in for this to work.

        Params:
            user_name (:obj:`str`) : The name of the user the client will send 
                the message to.
            content (:obj:`str`) : The content of the message.
            strict (:obj:`bool`, optional) : If this flag is set, passing in 
                content more than 300 characters will raise an error. Otherwise,
                the message will be senttruncated with a warning. This paramater
                 defaults to False.

        Notes:
            Content should be less than 300 characters long. Longer messages 
            will be concatenated. If the strict flag is set, an error will be 
            raised instead.

        Returns:
            None

        Raises:
            ValueError: if the message is longer than 300 characters and the 
            strict flag is set.
        """
        content = utils.clean_message_content(content, strict=strict)
        user_id = utils.name_to_id(user_name)
        await self.add_output('|/msg {}, {}'.format(user_id, content),
            delay=0, lifespan=math.inf)

    async def say(self, room_id, content, strict=False,
        delay=0, lifespan=math.inf):
        """
        |coro|
        
        Sends a chat message to the room specified by room_id. The client must
        be logged in for this to work

        Params:
            room_id (:obj:`str`) : The id of the room the client will send the 
                message to.
            content (:obj:`str`) : The content of the message.
            strict (:obj:`bool`, optional) : If this flag is set, passing in 
                content more than 300 characters will raise an error. Otherwise,
                the message will be sent truncated with a warning. This 
                paramater defaults to False.

        Notes:
            Content should be less than 300 characters long. Longer messages 
            will be concatenated. If the strict flag is set, an error will be
            raised instead.

        Returns:
            None

        Raises:
            ValueError: if the message is longer than 300 characters and the 
                strict flag is set
        """
        content = utils.clean_message_content(content, strict=strict)
        if room_id == 'lobby':
            room_id = ''
        await self.add_output('{}|{}'.format(room_id, content),
            delay=delay, lifespan=lifespan)

    # # # # # # # #
    # Challenges  #
    # # # # # # # #

    async def send_challenge(self, player_id, team, tier):
        """
        |coro|
        
        Challenge the player specified by player_id, with the team encoded in
        team, and in the corresponding tier.
        """
        await self.upload_team(team)
        await self.use_command('', 'challenge', player_id, tier)

    async def cancel_challenge(self):
        """
        |coro|

        Cancel a challenge to the player.
        """
        await self.use_command('', 'cancelchallenge')


    async def accept_challenge(self, player_id, team):
        """
        |coro|

        Accept a challenge from the player specified by player_id
        """
        await self.upload_team(team)
        await self.use_command('', 'accept', player_id)

    async def reject_challenge(self, player_id):
        """
        Deny a challenge from the player specified by player_id
        """
        await self.user_command('', 'reject', player_id)

    # # # # # #
    # Queries #
    # # # # # #

    async def query_rooms(self, delay=0, lifespan=math.inf):
        """
        |coro|
        
        Queries the server for a list of public rooms. The result will appear
        as a query response with type 'rooms'.

        Returns:
            None
        """
        await self.add_output('|/cmd rooms',
            delay=delay, lifespan=lifespan)

    async def query_battles(self, tier='', min_elo=None, 
        delay=0, lifespan=math.inf):
        """
        |coro|

        Queries the server for a list of public battles. The result will appears
        as a query response with type 'roomlist'.

        Params:
            tier (:obj:`str`) : The tier of the battle.
                Ex: 'gen7monotype'
            min_elo (:obj:`int`) : Minimum elo of the battle. Defaults to None, 
                which will query for all battles regardless of rating.

        Returns:
            None
        """
        tier = utils.name_to_id(tier)
        output = '|/cmd roomlist {}'.format(utils.name_to_id(tier))
        if min_elo is not None:
            output += ', {}'.format(min_elo)
        await self.add_output(output,
            delay=delay, lifespan=lifespan)

    # # # # #
    # Hooks #
    # # # # #

    async def on_connect(self):
        """
        |coro|

        Hook for subclasses. Called immediately after the client starts it 
        connection with the server.

        Notes:
            Does nothing by default.
        """
        pass

    async def on_login(self, login_response):
        """
        |coro|

        Hook for subclasses. Called immediately after the client logs in.

        Params:
            login_response (:obj:`dict`) : The sent by the server upon login 
                attempt. 

        Notes:
            Does nothing by default.
        """
        pass

    async def on_room_init(self, room_obj):
        """
        |coro|

        Hook for subclasses. Called when the client receives a room init message
        (generally upon joining a new room)
    
        Params:
            room_obj (:obj:`room.Room`) : Room object for the room that was 
                initialized.

        Notes:
            Does nothing by default.
        """
        pass

    async def on_room_deinit(self, room_obj):
        """
        |coro|

        Hook for subclasses. Called when the client receives a room deinit 
        message (generally upon leaving a room, or when a battle expires)
    
        Params:
            room_obj (:obj:`room.Room`) : Room object for the room that was 
                initialized.

        Notes:
            Does nothing by default.
        """
        pass

    async def on_query_response(self, response_type, data):
        """
        |coro|

        Hook for subclasses. Called when the client receives query response
        from the server.
    
        Params:
            response_type (:obj:`str`) : The response type.
                Ex: 'savereplay', 'rooms', 'roomlist', 'userdetails'
            data (:obj:`dict`) : The json response from the server bundled with 
                the response

        Notes:
            Does nothing by default.
        """
        pass

    async def on_challenge_update(self, challenge_data):
        """
        |coro|

        Hook for subclasses. Called when the client receives a challenge
        update from the server.

        Params:
            response_type (:obj:`dict`) : A dict containing information about
                active incoming and outgoing challenges.
                Ex: {"challengesFrom":{"scriptkitty":"gen7randombattle"},
                     "challengeTo":{"to":"scriptkitty","format":"gen7randombattle"}

        Notes:
            Does nothing by default
        """
        pass

    async def on_chat_message(self, chat_message):
        """
        |coro|

        Hook for subclasses. Called when the client receives a chat message.
    
        Params:
            chat_message (:obj:`showdown.message.ChatMessage`) : An object
                representing the received message.

        Notes:
            Does nothing by default.
        """
        pass

    async def on_private_message(self, private_message):
        """
        |coro|

        Hook for subclasses. Called when the client receives a private message.
    
        Params:
            private_message (:obj:`showdown.message.PrivateMessage`) : An object 
                representing the received message.

        Notes:
            Does nothing by default.
        """
        pass

    async def on_receive(self, room_id, inp_type, params):
        """
        |coro|

        Hook for subclasses. Called when the client receives any data from the
        server.
    
        Params:
            room_id (:obj:`str`) : ID of the room with which the information is 
                associated with. Messages with unspecified IDs default to '
                lobby', though may not necessarily be associated with 'lobby'.
            inp_type (:obj:`str`) : The type of information received.
                Ex: 'l' (user leave), 'j' (user join), 'c:' (chat message)
            params (:obj:`list`) : List of the parameters associated with the 
                inp_type. Ex: a user leave has params of ['zarel'], where 'zarel'
                represents the user id of the user that left.

        Notes:
            Does nothing by default.
        """
        pass
