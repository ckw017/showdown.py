# -*- coding: utf-8 -*-
"""Module for Room and Battle objects"""

import math
import json
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
        try:
            self.update(inp_type, *params)
        except:
            import traceback
            print(self.id)
            traceback.print_exc()

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
        Updates the Room's state from input. This method isn't intended to
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

def _get_empty_player_metadata():
    return {
        'switches': 0, 'faints': 0, 'lead': None,
        'teampreview': [], 'nicknames': {},
        'fainted': {}, 'teamsize': None, 'teaminfo': {}
    }

def _get_empty_team_metadata():
    return {
        'start_item': None,
        'curr_item': None,
        'moves': [],
        'tricked': False
    }

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
        p2 (:obj:`showdown.user.User`) : User object representing player two in
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
        outcome: Outcome of the battle. One of: (None, "knockout", "forfeit",
            "timeout")
        player_metadata (:obj:`dict`) : Metadata about the players in the battle
        latest_request (:obj:`dict`) : The most recently received "Choice
            Request" data. See SIM-PROTOCOL.md on the official showdown repo
            for more details.
    """
    def __init__(self, room_id, client=None, max_logs=5000):
        Room.__init__(self, room_id, client=client, max_logs=max_logs)
        self.rules = []
        self.p1, self.p2 = None, None
        self.rated = False
        self.ended = False
        self.end_time = False # Timestamp when `win` upkeep is received
        self.tier = None
        self.turns = 0
        self.winner, self.loser = None, None
        self.winner_id, self.loser_id = None, None
        self.outcome = None
        self.player_metadata = {
            'p1': _get_empty_player_metadata(),
            'p2': _get_empty_player_metadata()
        }
        self.latest_request = None

    def update(self, inp_type, *params):
        #TODO: Fix this up
        # A full implementation that maintains metadata about the battle is a
        # bit beyond the scope of my intentions, but could be done probably by
        # looking into how the official client tracks state
        """
        Updates the Room's state from input. This method isn't intended to
        be called directly, but rather through a client's receiver method.
        """
        Room.update(self, inp_type, *params)
        if inp_type == 'player':
            player_id, name = params[0], params[1]
            if not(name and player_id in ('p1', 'p2')):
                # Strange case where name is empty string
                # Related to a player leaving a battle midway?
                return
            setattr(self, player_id, user.User(name, client=self.client))
        elif inp_type == 'teamsize':
            pid, count = params[:2]
            self.player_metadata[pid]['teamsize'] = int(count)
        elif inp_type == 'faint':
            pid = params[0][:2]
            ident = params[0][5:]
            curr_player_metadata = self.player_metadata[pid]
            curr_player_metadata['faints'] += 1
            curr_player_metadata['fainted'][ident] = self.turns
        elif inp_type in {'switch', 'drag'}:
            pid = params[0][:2]
            ident = params[0][5:]
            details = params[1]
            isnickname = not details.startswith(ident)

            # Update switch/lead info
            curr_player_metadata = self.player_metadata[pid]
            curr_player_metadata['switches'] += 1
            if not curr_player_metadata['lead']:
                curr_player_metadata['lead'] = details

            # Add to teaminfo
            teaminfo = curr_player_metadata['teaminfo']
            if ident not in teaminfo:
                teaminfo[ident] = _get_empty_team_metadata()

            # Update nickname info
            nicks = curr_player_metadata['nicknames']
            if isnickname and (ident not in nicks):
                nicks[ident] = details
        elif inp_type == 'poke':
            pid, preview = params[:2]
            self.player_metadata[pid]['teampreview'].append(preview)
        elif inp_type == 'rated':
            self.rated = True
        elif inp_type == 'turn':
            self.turns = int(params[0])
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
            self.end_time = time.time()
            if not self.outcome:
                self.outcome = 'knockout'
        elif inp_type == 'request':
            if not params[0]:
                return
            self.latest_request = json.loads(params[0])
        elif inp_type == '-message':
            msg = params[0]
            if msg.endswith(' forfeited.'):
                self.outcome = 'forfeit'
            elif msg.endswith('due to inactivity.'):
                self.outcome  = 'timeout'
        elif inp_type == 'switch':
            species = params[0].split(',')[0]
        elif inp_type == 'move':
            full_params = ''.join(params)
            if '[from]' in full_params:
                return # Magic bounce shenanigans
            pid = params[0][:2]
            ident = params[0][5:]
            teaminfo = self.player_metadata[pid]['teaminfo']
            if params[1] not in teaminfo[ident]['moves']:
                teaminfo[ident]['moves'].append(params[1])
        elif inp_type == '-item':
            # Detects item reveals from frisk, etc...
            full_params = ''.join(params)
            pid = params[0][:2]
            ident = params[0][5:]
            item = params[1]
            memberinfo = self.player_metadata[pid]['teaminfo'][ident]
            memberinfo['curr_item'] = item
            if '[from] move:' in full_params:
                memberinfo['tricked'] = True
                return # Trick/Switcheroo shenanigans
                # TODO: maintain some state to track what gets tricked to where
            if not memberinfo['tricked']:
                memberinfo['start_item'] = item
        elif inp_type == '-enditem':
            # Detects item consumption and knock offs
            full_params = ''.join(params)
            pid = params[0][:2]
            ident = params[0][5:]
            item = params[1]
            memberinfo = self.player_metadata[pid]['teaminfo'][ident]
            memberinfo['curr_item'] = 'No Item'
            if not memberinfo['tricked']:
                memberinfo['start_item'] = item
        elif inp_type == '-mega':
            return # TODO: Update held item with megastone info


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
    async def switch(self, switch_id, client=None,
        delay=0, lifespan=math.inf):
        """
        |coro|

        Uses the specified client or the object's client to switch into a
        different pokemon. The client must be one of the players in the battle
        for this to work.
        """

        await self.client.use_command(self.id, 'choose', 'switch {}'
            .format(switch_id),
            delay=delay, lifespan=lifespan)

    @utils.require_client
    async def move(self, move_id, mega=False, dynamax=False, zmove=False, client=None,
        delay=0, lifespan=math.inf):
        """
        |coro|

        Selects the move specified by move_id to be used in the next turn. The
        client must be one of the players in this battle for this to work.

        Args:
            move_id:
            mega: set to True to specify mega evolution in this turn
            dynamax: set to True to dynamax in this turn
            zmove: set to True to use a Z-move this turn

        """
        modifier = ''
        if mega:
            modifier = 'mega'
        if dynamax:
            modifier = 'max'
        if zmove:
            modifier = 'zmove'
        await self.client.use_command(self.id, 'choose', 'move {}{}'
            .format(move_id, modifier),
            delay=delay, lifespan=lifespan)

    @utils.require_client
    async def undo_move(self, client=None, delay=0, lifespan=math.inf):
        """
        |coro|

        Cancels the last move sent. The client must be one of the
        players in the battle for this to work.
        """
        await self.client.use_comand(self.id, 'undo',
            delay=delay, lifespan=lifespan)

    @utils.require_client
    async def start_poke(self, start_id, client=None,
        delay=0, lifespan=math.inf):
        """
        |coro|

        Uses the specified client or the object's client to send the first pokemon
        into battle (only applies to formats with teampreview). The client must be
        one of the players in the battle for this to work.
        """

        await self.client.use_command(self.id, 'choose', 'team {}'.format(start_id),
            delay=delay, lifespan=lifespan)

class_map = {
    'chat': Room,
    'battle': Battle
}