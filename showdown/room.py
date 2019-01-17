# -*- coding: utf-8 -*-
"""Module for Room and Battle objects"""

import math
import time
from collections import deque
from . import utils, user

class Room:
    """
    Class representing a room on showdown. Tracks messages sent into the room,
    userlists, and includes utility methods to be used in conjunction with
    a client.

    Args:
        room_id (:obj:`str`) : The room's id. Ex: 'lobby', 'healthfitness'
        client (:obj:`showdown.client.Client`, optional) : The client to be
            used with the Room object's utility functions. Defaults to None.
        max_logs (:obj:`int`) : The maximum number of logs to be included in
            the Room object. Logs include chat messages, room intros, tour.
            updates, etc...

    Attributes:
        id (:obj:`str`) : The room's id.
        logs (:obj:`collections.deque`) : Queue containing all of the logs
            associated with the room.
        userlist (:obj:`dict`) : Dictionary with entries of {user_id : User}
            containing all the room's current users.
        client (:obj:`showdown.client.Client`) : The client to be
            used with the Room object's utility functions. Defaults to None.
        title (:obj:`str`) : The room's title. Ex: 'Lobby', 'Monotype'
    """
    def __init__(self, room_id, client=None, max_logs=5000):
        self.id = room_id
        self.logs = deque(maxlen=max_logs)
        self.userlist = {}
        self.client = client
        self.title = None
        self.init_time = time.time()

    def __eq__(self, other):
        return isinstance(other, Room) and self.id == other.id

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.id)

    def __repr__(self):
        return '<{} `{}`>'.format(self.__class__.__name__, self.title)

    def add_content(self, content):
        """
        Adds content to the Room object's logs attribute. Content is also
        parsed and used to update the Room's state through the update method.
        """
        self.logs.append(content)
        inp_type, params = utils.parse_text_input(content)
        self.update(inp_type, *params)

    def _add_user(self, user_str):
        """
        Adds a user object built from user_str to the Room's roomlist
        """
        new_user = user.User(user_str, client=self.client)
        self.userlist[new_user.id] = new_user

    def _remove_user(self, user_id):
        """
        Removes a user object built from user_str from the Room's roomlist
        """
        self.userlist.pop(user_id, None)

    def update(self, inp_type, *params):
        """
        Updates the Room's state from input. This his method isn't intended to
        be called directly, but rather through a client's receiver method.
        """

        #Title set
        if inp_type == 'title':
            self.title = params[0]

        #Userlist init
        if inp_type == 'users':
            user_strs = params[0].split(',')[1:]
            for user_str in user_strs:
                self._add_user(user_str)

        #User name change
        elif inp_type == 'n':
            user_str, old_id = params
            self._remove_user(old_id)
            self._add_user(user_str)

        #User leave
        elif inp_type == 'l':
            user_id = utils.name_to_id(params[0])
            self._remove_user(user_id)

        #User join
        elif inp_type == 'j':
            user_str = params[0]
            self._add_user(user_str)

    @utils.require_client
    async def request_auth(self, client=None, delay=0, lifespan=math.inf):
        """
        Request room auth using the specified client or the Room's client
        attribute. The actual info will be sent to the clienet with inp_type
        of 'popup'.
        """
        await client.use_command(self.id, 'roomauth',
            delay=delay, lifespan=lifespan)

    @utils.require_client
    async def say(self, content, client=None, delay=0, lifespan=math.inf):
        """
        Send a message to the room using the specified client or the Room's
        client attribute.
        """
        await client.say(self.id, content, delay=delay, lifespan=lifespan)

    @utils.require_client
    async def join(self, client=None, delay=0, lifespan=math.inf):
        """
        Join the room using the specified client or the room's client
        attribute.
        """
        await client.join(self.id, delay=0, lifespan=lifespan)

    @utils.require_client
    async def leave(self, client=None, delay=0, lifespan=math.inf):
        """
        Leave the room using the specified client or the room's client
        attribute.
        """
        await client.leave(self.id, delay=delay, lifespan=lifespan)

class Battle(Room):
    """
    Subclass of Room representing a battle room on Showdown. Has additional
    attributes and utility methods.

    Args:
        room_id (:obj:`str`) : The room's id. Ex: 'lobby', 'healthfitness'
        client (:obj:`showdown.client.Client`, optional) : The client to be
            used with the Room object's utility functions. Defaults to None.
        max_logs (:obj:`int`) : The maximum number of logs to be included in
            the Room object. Logs include chat messages, room intros, tour.
            updates, etc...


    Inherited attributes:
        id (:obj:`str`) : The room's id.
        logs (:obj:`collections.deque`) : Queue containing all of the logs
            associated with the room.
        userlist (:obj:`dict`) : Dictionary with entries of {user_id : User}
            containing all the room's current users.
        client (:obj:`showdown.client.Client`) : The client to be
            used with the Room object's utility functions. Defaults to None.
        title (:obj:`str`) : The room's title. Ex: 'Zarel vs. Aegisium Z'

    Attributes:
        rules (:obj:`list`) : A list of strings describing the match's rules
        p1 (:obj:`showdown.user.User`) : User object representing player one in
            the match
        p1 (:obj:`showdown.user.User`) : User object representing player two in
            the match
        rated (:obj:`bool`) : True if the match is rated (on ladder), else False
        tier (:obj:`str`) : String representing the matches tier.
            Ex: 'gen7monotype', 'gen7ou'
        winner (:obj:`showdown.user.User`) : User object representing the winner
            of the battle. Defaults to None if the match has not ended yet.
        winner_id (:obj:`str`) : String representing the match id of the
            battle's winner. Ex: 'p1', 'p2'
        loser (:obj:`showdown.user.User`) : User object representing the loser
            of the battle. Defaults to None if the match has not ended yet.
        loser_id (:obj:`str`) : String representing the match id of the
            battle's loser. Ex: 'p1', 'p2'
        ended (:obj:`bool`) : True if a player has won the match, else False
    """
    def __init__(self, room_id, client=None, max_logs=5000):
        Room.__init__(self, room_id, client=client, max_logs=max_logs)
        self.rules = []
        self.p1, self.p2 = None, None
        self.rated = False
        self.ended = False
        self.tier = None
        self.winner, self.loser = None, None
        self.winner_id, self.loser_id = None, None

    def update(self, inp_type, *params): #TODO: Fix this up
        """
        Updates the Room's state from input. This his method isn't intended to
        be called directly, but rather through a client's receiver method.
        """
        Room.update(self, inp_type, *params)
        if inp_type == 'player':
            player_id, name = params[0], params[1]
            if not name or player_id not in ('p1', 'p2'):
                return
            setattr(self, player_id, user.User(name, client=self.client))
        elif inp_type == 'rated':
            self.rated = True
        elif inp_type == 'tier':
            self.tier = utils.name_to_id(params[0])
        elif inp_type == 'rule':
            self.rules.append(params[0])
        elif inp_type == 'win':
            winner_name = params[0]
            if self.p1.name_matches(winner_name):
                self.winner, self.winner_id = self.p1, 'p1'
                self.loser, self.loser_id = self.p2, 'p2'
            elif self.p2.name_matches(winner_name):
                self.winner, self.winner_id = self.p2, 'p2'
                self.loser, self.loser_id = self.p1, 'p1'
            self.ended = True

    @utils.require_client
    async def save_replay(self, client=None, delay=0, lifespan=math.inf):
        """
        |coro|

        Uses the specified client or the object's client attribute to save a
        replay of the battle. The battle must be ended before for this method
        to work. 
        """
        await client.save_replay(self.id, delay=delay, lifespan=lifespan)

    @utils.require_client
    async def forfeit(self, client=None, delay=0, lifespan=math.inf):
        """
        |coro|

        Uses the specified client or the object's client attribute to forfeit
        the battle. The client must be one of the players in the battle for this
        to work.
        """
        await client.forfeit(self.id, delay=delay, lifespan=lifespan)

    #TODO: Test everything below here

    @utils.require_client
    async def set_timer_on(self, client=None, delay=0, lifespan=math.inf):
        """
        |coro|

        Uses the specified client or the object's client attribute to turn on
        the battle timer. The client must be one of the players in the battle 
        for this to work.
        """
        await self.client.use_command(self.id, 'timer', 'on',
            delay=delay, lifespan=lifespan)

    @utils.require_client
    async def set_timer_off(self, client=None, delay=0, lifespan=math.inf):
        """
        |coro|

        Uses the specified client or the object's client attribute to turn off
        the battle timer. The client must be one of the players in the battle 
        for this to work.
        """
        await self.client.use_command(self.id, 'timer', 'off',
            delay=delay, lifespan=lifespan)

    @utils.require_client
    async def switch(self, switch_id, turn_num, client=None, 
        delay=0, lifespan=math.inf):
        """
        |coro|

        Uses the specified client or the object's client to switch into a
        different pokemon. The client must be one of the players in the battle 
        for this to work.
        """
        await self.client.use_command(self.id, 'timer', 'on',
            delay=delay, lifespan=lifespan)

    @utils.require_client
    async def move(self, move_id, turn_num, mega=False, client=None,
        delay=0, lifespan=math.inf):
        """
        |coro|

        Uses the specified client or the object's client attribute to turn on
        the battle timer. The client must be one of the players in the battle 
        for this to work.
        """
        await self.client.use_command(self.id, 'choose', 'move {}{}|{}'
            .format(move_id, ' mega' if mega else '', turn_num),
            delay=delay, lifespan=lifespan)

    @utils.require_client
    async def undo(self, client=None, delay=0, lifespan=math.inf):
        """
        |coro|
        
        Uses the specified client or the object's client attribute to undo their
        last move or switch. The player must be on of the players in the battle
        for this to work.
        """
        await self.client.use_comand(self.id, 'undo',
            delay=delay, lifespan=lifespan)

class_map = {
    'chat': Room,
    'battle': Battle
}