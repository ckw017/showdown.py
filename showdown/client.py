# -*- coding: utf-8 -*-
"""Module for showdown's Client class"""
import asyncio
import aiohttp
import websockets
import json
import time
import logging
import traceback
import math
import signal
from functools import wraps
from . import message, room, server, user, utils, docutils

# Keyboard interrupts should continue to work
signal.signal(signal.SIGINT, signal.SIG_DFL)

# Logging setup
logger = logging.getLogger(__name__)

DEFAULT_RECONNECT_SLEEP = 5
MAX_RECONNECT_SLEEP = 180  # Three minutes


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
        Once you create a client object, use Client.start() to begin your
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
        max_room_logs (int) : The maximum number of logs stored in this
            client's Room objects.
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

    def __init__(
        self,
        name="",
        password="",
        *,
        loop=None,
        max_room_logs=5000,
        server_id="showdown",
        server_host=None,
        strict_exceptions=False
    ):
        super().__init__(name, client=self)

        # URL setup
        self.server = server.Server(
            id=server_id, host=server_host, client=self
        )
        self.websocket_url = self.server.generate_ws_url()
        logger.info("Using websocket at {}".format(self.websocket_url))

        # Initialize client attributes
        self.password = password
        self.max_room_logs = max_room_logs
        self.autologin = True
        self.autoreconnect = False
        self.loop = loop or asyncio.get_event_loop()
        self._set_defaults()
        self.strict_exceptions = strict_exceptions

    def _set_defaults(self):
        # Defaults values for reconnections
        self._tasks = []
        self._transient_tasks = set()
        self._reaper_queue = asyncio.Queue()
        self.websocket = None
        self.session = None
        self.challengekeyid, self.challstr = None, None
        self.output_queue = asyncio.Queue()
        self.rooms = {}
        self.challenges = {}
        self.connected = False

    def start(self, autologin=True, autoreconnect=False):
        """
        Starts the event loop stored in the Client's loop attribute.

        Args:
            autologin (:obj:`bool`, optional) : Bool denoting whether or not
                the client will automatically login after connecting to the
                server. Defaults to True.

        Returns:
            bool : True if exited attached to existing loop, False otherwise
        """
        self.autologin = autologin
        self.autoreconnect = autoreconnect
        if self.loop.is_running():
            self.add_task(self._handler())
            logger.info(
                "The client's event loop was already running. "
                "The client will run as a new task on the loop."
            )
            return True
        else:
            self.loop.run_until_complete(self._handler())
            return False

    @docutils.format()
    async def _handler(self):
        """
        Creates websocket connection and adds any methods flagged by the
        on_interval decorator to the event loop.
        """
        reconnect_delay = DEFAULT_RECONNECT_SLEEP
        while True:
            try:
                async with websockets.connect(
                    self.websocket_url
                ) as self.websocket, aiohttp.ClientSession() as self.session:
                    self.connected = True
                    self.server.set_session(self.session)
                    for att in dir(self):
                        att = getattr(self, att)
                        if (
                            hasattr(att, "_is_interval_task")
                            and att._is_interval_task
                        ):
                            self._tasks.append(asyncio.ensure_future(att()))
                    done, pending = await asyncio.wait(
                        self._tasks, return_when=asyncio.FIRST_COMPLETED
                    )
                    for task in pending:
                        task.cancel()
                    for task in done:
                        if task.exception():
                            raise task.exception()
            except:
                import traceback

                traceback.print_exc()
                await self._on_disconnect(self.autoreconnect)
                if not self.autoreconnect:
                    logger.info(
                        "An exception has occurred. The bot will "
                        "go offline. To reconnect automatically start the "
                        "bot with Client.start(autoreconnect=True)."
                    )
                    return

                logger.info(
                    "An exception has occurred. The bot will "
                    "reconnect. To forgo autoreconnect start the bot with "
                    "Client.start(autoreconnect=False)."
                )

            logger.info(
                "Sleeping for {}s before reconnecting".format(reconnect_delay)
            )
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(
                MAX_RECONNECT_SLEEP, reconnect_delay * 2
            )  # Bounded exponential backoff

    async def _on_disconnect(self, reconnecting):
        if self.connected:
            for t in self._tasks + list(self._transient_tasks):
                if not t.cancelled():
                    t.cancel()
                    logger.debug("Cancelled: {}".format(t))
            self._set_defaults()
            utils.require_coro(self.on_disconnect)
            await self.on_disconnect(reconnecting)

    def add_task(self, coro, transient=False):
        task = asyncio.ensure_future(coro, loop=self.loop)
        if not transient:
            self._tasks.append(task)
        else:
            self._transient_tasks.add(task)
            task.add_done_callback(lambda t: self._reaper_queue.put_nowait(t))
        return task

    def on_interval(interval=0.0):
        """
        A decorator creator to flag methods that the client should loop in an
        interval

        Args:
            interval (:obj:`float`, optional) :  The length of the interval to
                run the method on in seconds. Defaults to 0.0.

        Returns:
            func - A decorator function that loops the passed in func on the
                specified interval, and flagged to be added to the client's
                event loop.

        Example:
            class OUChecker(showdown.Client):
                @on_interval(interval=3.0):
                async def check_ou_matches(self):
                    '''Checks the ou ladder ever 3 seconds'''
                    await self.query_battles(battle_format='gen7ou')
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
    async def _transient_task_reaper(self):
        task = await self._reaper_queue.get()
        self._transient_tasks.remove(task)
        if task.exception():
            if self.strict_exceptions:
                logger.info(
                    "Exception caught in Client._transient_task_reaper. "
                    "Disconnecting. Set strict_exceptions=False if"
                    " you don't want this behavior"
                )
                raise task.exception()
            try:
                raise task.exception()
            except:
                logger.info(
                    "Exception caught in Client._transient_task_reaper. "
                    "Ignoring and continuing. Set strict_exceptions=True if"
                    " you don't want this behavior"
                )
                traceback.print_exc()

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
        if not out.ready():
            logger.info(">>> Requeuing {}".format(out))
            await self.output_queue.put(out)
            await asyncio.sleep(0.05)
            return
        if out.expired():
            logger.info(">>> Discarding {}".format(out))
            out.discarded = True
            return
        content = [out.content] if type(out.content) is str else out.content
        logger.info(">>> Sending:\n{}".format(content))
        await self.websocket.send(json.dumps(content))
        out.sent = True
        await asyncio.sleep(len(content) * 0.5)

    @docutils.format()
    async def add_output(self, content, delay=0, lifespan=math.inf):
        """
        Adds output to be sent across the client's connection to the server.

        Args:
            content (:obj:`str` or obj:`list` of obj:`str`) : Content to be
                sent to the server.
            {delay}
            {lifespan}

        Returns:
            namedtuple : Token representing the content to be sent.
        """
        assert type(lifespan) in (int, float), "lifespan must be float or int"
        assert type(delay) in (int, float), "delay must be float or int"
        assert delay < lifespan, "Delay should be strictly less than lifespan"
        assert (
            delay >= 0 and lifespan >= 0
        ), "Lifespan and delay should be nonnegative"

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
        logger.debug("<<< Received:\n{}".format(socket_input))

        # Showdown sends this response on initial connection
        if socket_input == "o":
            logger.info("Connected on {}".format(self.websocket_url))
            self.connected = True
            self.add_task(self.on_connect())
            return

        inputs = utils.parse_socket_input(socket_input)
        for room_id, inp in inputs:
            room_id = room_id or "lobby"
            logger.debug("||| Parsing:\n{}".format(inp))
            inp_type, params = utils.parse_text_input(inp)

            # Set challstr attributes and autologin
            if inp_type == "challstr":
                self.challengekeyid, self.challstr = params
                if self.name and self.password and self.autologin:
                    await self.login()
                elif self.autologin:
                    msg = (
                        "Cannot login without username and password. If "
                        "you don't want your client to be logged in, "
                        "you can use Client.start(autologin=False)."
                    )
                    raise Exception(msg)

            # Process query response
            elif inp_type == "queryresponse":
                response_type, data = params[0], "|".join(params[1:])
                data = json.loads(data)
                self.add_task(
                    self.on_query_response(response_type, data), transient=True
                )
                if response_type == "savereplay":
                    self.add_task(
                        self.server.save_replay_async(data), transient=True
                    )

            # Challenge updates
            elif inp_type == "updatechallenges":
                self.challenges = json.loads(params[0])
                self.add_task(
                    self.on_challenge_update(self.challenges), transient=True
                )

            # Messages
            elif inp_type == "c:" or inp_type == "c":
                timestamp = None
                if inp_type == "c:":
                    timestamp, params = int(params[0]), params[1:]
                author_str, *content = params
                content = "|".join(content)
                chat_message = message.ChatMessage(
                    room_id, timestamp, author_str, content, client=self
                )
                self.add_task(
                    self.on_chat_message(chat_message), transient=True
                )
            elif inp_type == "pm":
                author_str, recipient_str, *content = params
                content = "|".join(content)
                private_message = message.PrivateMessage(
                    author_str, recipient_str, content, client=self
                )
                self.add_task(
                    self.on_private_message(private_message), transient=True
                )

            # Rooms
            elif inp_type == "init":
                room_type = params[0]
                room_obj = room.class_map.get(room_type, room.Room)(
                    room_id, client=self, max_logs=self.max_room_logs
                )
                self.rooms[room_id] = room_obj
                self.add_task(self.on_room_init(room_obj), transient=True)
            elif inp_type == "deinit":
                if room_id in self.rooms:
                    self.add_task(
                        self.on_room_deinit(self.rooms.pop(room_id)),
                        transient=True,
                    )

            # add content to proper room
            if isinstance(self.rooms.get(room_id, None), room.Room):
                self.rooms[room_id].add_content(inp)

            self.add_task(
                self.on_receive(room_id, inp_type, params), transient=True
            )

    async def login(self, avatar_id=0):
        """
        |coro|

        Logins in the user using the name, password, challstr and
        challengekeyid parameters.
        """
        if not self.challengekeyid:
            raise Exception("Cannot login, challstr has not been received yet")
        if not self.name:
            raise Exception("Cannot login, no username has been specified")
        if not self.password:
            raise Exception("Cannot login, no password has been specified")

        logger.info('Logging in as "{}"'.format(self.name))
        login_data = await self.server.login_async(
            self.name, self.password, self.challstr, self.challengekeyid
        )
        if not login_data["actionsuccess"]:
            raise ValueError(
                "Failed to log in as user `{}`."
                " Raw login result:\n{}".format(self.name, login_data)
            )
        else:
            logger.info("Login succeeded")
        await self.websocket.send(
            '["|/trn {},{},{}"]'.format(
                self.name, avatar_id, login_data["assertion"]
            )
        )
        self.add_task(self.on_login(login_data), transient=True)

    @docutils.format()
    async def set_avatar(self, avatar_id, delay=0, lifespan=math.inf):
        """
        Sets the user's avatar to the specified avatar_id value.

        Args:
            {avatar_id}
            {delay}
            {lifespan}
        """
        await self.add_output(
            "|/avatar {}".format(avatar_id), delay=delay, lifespan=lifespan
        )

    @docutils.format()
    async def use_command(
        self, room_id, command_name, *args, delay=0, lifespan=math.inf
    ):
        """
        Sends a generic command to the specified room. For example, to send the
        `/mute user, No spamming!` command in the Monotype room, you can use
        client.use_command('monotype', 'mute', 'user', 'No spamming!')

        Args:
            {room_id}
            command_name (:obj:`str`) : The name of the command to use.
                Ex: 'leave', 'mute', 'forfeit'
            {delay}
            {lifespan}
        """
        await self.add_output(
            "{}|/{} {}".format(room_id, command_name, ", ".join(args)),
            delay=delay,
            lifespan=lifespan,
        )

    # # # # # # # # # # # #
    # Ladder interactions #
    # # # # # # # # # # # #

    @docutils.format()
    async def upload_team(self, team, *, delay=0, lifespan=math.inf):
        """
        Upload's the specified team to the server. Generally isn't needed
        on its own, and is more useful as a subroutine for validate_team and
        search_battles.

        Args:
            {team}
            {delay}
            {lifespan}
        """
        team_str = utils.to_team_str(team)
        await self.add_output(
            "|/utm {}".format(team_str), delay=delay, lifespan=lifespan
        )

    @docutils.format()
    async def validate_team(
        self, team, battle_format, *, delay=0, lifespan=math.inf
    ):
        """
        Uploads the specified team to the server and validates for the
        format specified by battle_format.

        Args:
            {team}
            {delay}
            {lifespan}
        """
        battle_format = utils.name_to_id(battle_format)
        team = team or "null"
        await self.upload_team(team, delay=delay, lifespan=lifespan)
        await self.add_output(
            "|/vtm {}".format(battle_format), delay=delay, lifespan=lifespan
        )

    @docutils.format()
    async def search_battles(
        self,
        team,
        battle_format,
        hide_from_spectators=False,
        delay=0,
        lifespan=math.inf,
    ):
        """
        Uploads the specified team and searches for battles for the format
        specified by battle_format.

        Args:
            {team}
            {delay}
            {lifespan}

        Notes:
            You can specify the team to be None or the empty string for
            battle_formats like randombattles, where no team is needed to be
            provided.
        """
        battle_format = utils.name_to_id(battle_format)
        await self.upload_team(team, delay=delay, lifespan=lifespan)
        await self.add_output(
            "|{}/search {}".format(
                "/hidenext " if hide_from_spectators else "", battle_format
            ),
            delay=delay,
            lifespan=lifespan,
        )

    @docutils.format()
    async def cancel_search(self, *, delay=0, lifespan=math.inf):
        """
        Cancels a battle search.

        Args:
            {delay}
            {lifespan}
        """
        await self.add_output("|/cancelsearch", delay=delay, lifespan=lifespan)

    # # # # # # # # # # #
    # Room interactions #
    # # # # # # # # # # #

    @docutils.format()
    async def join(self, room_id, *, delay=0, lifespan=math.inf):
        """
        Makes the client join  the room specified by the given room_id.

        Args:
            {room_id}
            {delay}
            {lifespan}

        Notes:
            This method takes a str. Attempting to pass in a Room object will
            fail. Use the Room.leave() method instead, or Client.leave(room.id)
        """
        assert type(room_id) is str, "Paramater room_id should be a string."
        await self.add_output(
            "|/join {}".format(room_id), delay=delay, lifespan=lifespan
        )

    @docutils.format()
    async def leave(self, room_id, *, delay=0, lifespan=math.inf):
        """
        Makes client leave the room specified by the given room_id.

        Args:
            {room_id}
            {delay}
            {lifespan}

        Notes:
            This method takes a str. Attempting to pass in a Room object will
            fail. Use the Room.leave() method instead, or
            Client.leave(room.id).
        """
        assert type(room_id) is str, "Parameter room_id should be a string."
        await self.add_output(
            "{}|/leave".format(room_id), delay=delay, lifespan=lifespan
        )

    # # # # # # # # # # # #
    # Battle interactions #
    # # # # # # # # # # # #

    @docutils.format()
    async def save_replay(self, battle_id, *, delay=0, lifespan=math.inf):
        """
        Requests data from the server to save the battle specified by
        battle_id.

        Args:
            {battle_id}
            {delay}
            {lifespan}

        Returns:
            None

        Notes:
            This method takes a str. Attempting to pass in a Battle object will
            fail. Use the Battle.save_replay() method instead, or
            Client.save_replay(battle.id)

            The actual upload is handled on the server's response through a
            query response with type "savereplay".
        """
        assert type(battle_id) is str, battle_id.startswith("battle-")
        await self.add_output(
            "{}|/savereplay".format(battle_id), delay=delay, lifespan=lifespan
        )

    @docutils.format()
    def save_replay_local(self, battle_id, output_path=None):
        """
        Saves logs from a battle locally to output_path.

        Args:
            {battle_id}
            output_path (:obj:`str`, optional) : The path to the file the logs
                will be saved. Defaults to "`battle_id`.txt"

        Returns:
            None
        """
        assert (
            battle_id in self.rooms
        ), "Client is not in the room " "{}, replay cannot be saved.".format(
            battle_id
        )
        if output_path is None:
            output_path = "{}.txt".format(battle_id)
        assert type(output_path) is str, "output_path must be a string."
        with open(output_path, "wt") as f:
            f.write("\n".join((self.rooms[battle_id].logs)))

    @docutils.format()
    async def forfeit(self, battle_id, *, delay=0, lifespan=math.inf):
        """
        Forfeit the match specified by battle_id.

        Returns:
            None

        Args:
            battle_id (:obj:`str`) : The id of the battle you want to forfeit.
                Ex: 'battle-gen7monotype-12345678'
        """
        await self.add_output(
            "{}|/forfeit".format(battle_id), delay=delay, lifespan=lifespan
        )

    # # # # # # #
    # Messages  #
    # # # # # # #

    @docutils.format()
    async def private_message(
        self, user_name, content, strict=False, *, delay=0, lifespan=math.inf
    ):
        """
        Sends a private message with content to the user specified by
        user_name. The client must be logged in for this to work.

        Args:
            user_name (:obj:`str`) : The name of the user the client will send
                the message to.
            {content}
            {strict}

        Notes:
            {strict_notes}

        Returns:
            None

        Raises:
            {strict_error}
        """
        content = utils.clean_message_content(content, strict=strict)
        user_id = utils.name_to_id(user_name)
        await self.add_output(
            "|/msg {}, {}".format(user_id, content), delay=0, lifespan=math.inf
        )

    @docutils.format()
    async def say(
        self, room_id, content, strict=False, delay=0, lifespan=math.inf
    ):
        """
        Sends a chat message to the room specified by room_id. The client must
        be logged in for this to work

        Args:
            {room_id}
            {content}
            {strict}
            {delay}
            {lifespan}

        Notes:
            {strict_notes}

        Returns:
            None

        Raises:
            {strict_error}
        """
        content = utils.clean_message_content(content, strict=strict)
        await self.add_output(
            "{}|{}".format(room_id, content), delay=delay, lifespan=lifespan
        )

    # # # # # # # #
    # Challenges  #
    # # # # # # # #

    @docutils.format()
    async def send_challenge(self, user_id, team, battle_format):
        """
        Challenge the player specified by user_id, with the team encoded in
        team, and in the corresponding battle_format.

        Args:
            {user_id}
            {team}
            {battle_format}

        """
        await self.upload_team(team)
        await self.use_command("", "challenge", user_id, battle_format)

    @docutils.format()
    async def cancel_challenge(self, *, delay=0, lifespan=math.inf):
        """
        Cancel an outgoing challenge.

        Args:
            {delay}
            {lifespan}
        """
        await self.use_command(
            "", "cancelchallenge", delay=delay, lifespan=lifespan
        )

    @docutils.format()
    async def accept_challenge(
        self, user_id, team, *, delay=0, lifespan=math.inf
    ):
        """
        Accept a challenge from the player specified by user_id

        Args:
            {user_id}
            {team}
            {delay}
            {lifespan}
        """
        await self.upload_team(team)
        await self.use_command(
            "", "accept", user_id, delay=delay, lifespan=lifespan
        )

    @docutils.format()
    async def reject_challenge(self, user_id, *, delay=0, lifespan=math.inf):
        """
        Reject a challenge from the player specified by user_id

        Args:
            {user_id}
            {delay}
            {lifespan}
        """
        await self.user_command(
            "", "reject", user_id, delay=delay, lifespan=lifespan
        )

    # # # # # #
    # Queries #
    # # # # # #

    @docutils.format()
    async def query_rooms(self, *, delay=0, lifespan=math.inf):
        """
        Queries the server for a list of public rooms. The result will appear
        as a query response with type 'rooms'.

        Args:
            {delay}
            {lifespan}

        Returns:
            None
        """
        await self.add_output("|/cmd rooms", delay=delay, lifespan=lifespan)

    @docutils.format()
    async def query_battles(
        self, battle_format="", min_elo=None, delay=0, lifespan=math.inf
    ):
        """
        Queries the server for a list of public battles. The result will
        appears as a query response with type 'roomlist'.

        Args:
            {battle_format}
            min_elo (:obj:`int`) : Minimum elo of the battle. Defaults to None,
                which will query for all battles regardless of rating.
            {delay}
            {lifespan}

        Returns:
            None
        """
        battle_format = utils.name_to_id(battle_format)
        output = "|/cmd roomlist {}".format(utils.name_to_id(battle_format))
        if min_elo is not None:
            output += ", {}".format(min_elo)
        await self.add_output(output, delay=delay, lifespan=lifespan)

    # # # # #
    # Hooks #
    # # # # #

    async def on_disconnect(self, reconnecting):
        """
        |coro|

        Hook for subclasses. Called after the client's websocket and aiohttp
        sessions cease.

        Args:
            reconnecting: True if the client will reconnect, False otherwise

        Notes:
            Does nothing by default.
        """
        pass

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

        Args:
            login_response (:obj:`dict`) : The sent by the server upon login
                attempt.

        Notes:
            Does nothing by default.
        """
        pass

    async def on_room_init(self, room_obj):
        """
        |coro|

        Hook for subclasses. Called when the client receives a room init
        message (generally upon joining a new room)

        Args:
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

        Args:
            room_obj (:obj:`room.Room`) : Room object for the room that was
                deinitialized.

        Notes:
            Does nothing by default.
        """
        pass

    async def on_query_response(self, query_type, response):
        """
        |coro|

        Hook for subclasses. Called when the client receives query response
        from the server.

        Args:
            query_type (:obj:`str`) : The query type.
                Ex: 'savereplay', 'rooms', 'roomlist', 'userdetails'
            response (:obj:`dict`) : The json response from the server bundled
                with the response

        Notes:
            Does nothing by default.
        """
        pass

    async def on_challenge_update(self, challenge_data):
        """
        |coro|

        Hook for subclasses. Called when the client receives a challenge
        update from the server.

        Args:
            challenge_data (:obj:`dict`) : A dict containing information about
                active incoming and outgoing challenges.
                Ex: {"challengesFrom":{"scriptkitty":"gen7randombattle"},
                     "challengeTo":{"to":"scriptkitty","format":"gen7ou"}

        Notes:
            Does nothing by default.
            Note that challengesFrom is plural, since a client can receive
            multiple challenges, but challengesTo is singular, since only one
            challenge can be sent at a time.
        """
        pass

    async def on_chat_message(self, chat_message):
        """
        |coro|

        Hook for subclasses. Called when the client receives a chat message.

        Args:
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

        Args:
            private_message (:obj:`showdown.message.PrivateMessage`) : An
                object representing the received message.

        Notes:
            Does nothing by default.
        """
        pass

    async def on_receive(self, room_id, inp_type, params):
        """
        |coro|

        Hook for subclasses. Called when the client receives any data from the
        server.

        Args:
            room_id (:obj:`str`) : ID of the room with which the information is
                associated with. Messages with unspecified IDs default to '
                lobby', though may not necessarily be associated with 'lobby'.
            inp_type (:obj:`str`) : The type of information received.
                Ex: 'l' (user leave), 'j' (user join), 'c:' (chat message)
            params (:obj:`list`) : List of the parameters associated with the
                inp_type. Ex: a user leave has params of ['zarel'], where
                'zarel' represents the user id of the user that left.

        Notes:
            Does nothing by default.
        """
        pass
