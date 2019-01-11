from collections import deque
from .utils import parse_text_input, name_to_id, abbreviate
from .user import UserLeave, UserJoin, UserNameChange, User

class Room:
    def __init__(self, room_id, client=None, max_logs=5000):
        self.id = room_id
        self.logs = deque(maxlen=max_logs)
        self.userlist = {}
        self.client = client
        self.title = None

    def add_content(self, content):
        self.logs.append(content)
        inp_type, params = parse_text_input(content)
        self.update(inp_type, params)

    def update(self, inp_type, params):
        if inp_type == 'title':
            self.title = params[0]
        if inp_type == 'users':
            user_strs = params[0].split(',')[1:]
            for user_str in user_strs:
                user = User(user_str)
                self.userlist[user.id] = user
        elif inp_type == 'n':
            user_str, old_id = params
            if old_id in self.userlist:
                del self.userlist[old_id]
            user = User(user_str, client=self.client)
            self.userlist[user.id] = user
        elif inp_type == 'l':
            user_id = name_to_id(params[0])
            if user_id in self.userlist:
                del self.userlist[user_id]
        elif inp_type == 'j':
            user_str = params[0]
            user = User(user_str, client=self.client)
            self.userlist[user.id] = user

    def __eq__(self, other):
        return isinstance(other, Room) and self.id == other.id

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.id)

    async def request_auth(self):
        if self.client:
            self.client.add_output('{}|/roomauth'.format(self.id))
        else:
            raise Exception('A client is needed to perform this action')

    async def say(self, content):
        if self.client:
            self.client.say(self.id, content)
        else:
            raise Exception('A client is needed to perform this action')

    def __repr__(self):
        return '<{} {}>'.format(self.__class__.__name__, self.title)

class Battle(Room):
    def __init__(self, room_id, client=None, max_logs=5000):
        Room.__init__(self, room_id, client=client, max_logs=max_logs)
        self.rules = []
        self.players = {
            'p1': None,
            'p2': None
        }
        self.rated = False
        self.tier = None
        self.winner, self.loser = None, None
        self.winner_id, self.loser_id = None, None

    def update(self, inp_type, params):
        Room.update(self, inp_type, params)
        if inp_type == 'player':
            player_id, name = params[0], params[1]
            self.players[player_id] = User(name)
        elif inp_type == 'rated':
            self.rated = True
        elif inp_type == 'tier':
            self.tier = name_to_id(params[0])
        elif inp_type == 'rule':
            self.rules.append(params[0])
        elif inp_type == 'win':
            winner_name = params[0]
            if self.players['p1'].name_matches(winner_name):
                self.winner = self.players['p1']
                self.winner_id = 'p1'
                self.loser = self.players['p2']
                self.loser_id = 'p2'
            elif self.players['p2'].name_matches(winner_name):
                self.winner = self.players['p2']
                self.winner_id = 'p2'
                self.loser = self.players['p1']
                self.loser_id = 'p1'

    async def savereplay(self):
        if self.client:
            await self.client.savereplay(self.id)
        else:
            raise Exception('A client is needed to perform this action')

class Tournament:
    pass

class TourUpdate:
    def __init__(self, room_id, *params):
        self.room_id = room_id
        self.type = params[0]
        self.params = params[1:]

    def __repr__(self):
        return '<TourUpdate ({}) type={} params={}>'.format(\
            self.room_id,
            self.type,
            abbreviate(self.params))