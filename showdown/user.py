import json
import re
import requests
from .utils import parse_http_input

ACTION_URL_BASE =  'https://play.pokemonshowdown.com/~~{}/action.php'

def name_to_id(input_str):
    return re.sub(r'(\W|_)', '', input_str.lower()).strip()

class User:
    def __init__(self, name, client=None):
        self.set_name(name)
        self.id = name_to_id(name)
        self.client = client

    def set_name(self, name):
        self.name = name
        self.id = name_to_id(name)

    def name_matches(username):
        return self.id == name_to_id(username)

    def __eq__(self, other):
        if issubclass(type(other), User):
            return other.id == self.id
        return False

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return '<User {}>'.format(self.name)

    async def message(self, content):
        if self.client:
            await self.client.private_message(self, content)
        else:
            raise Exception("A client is needed to use this method.")

    async def request_user_details(self):
        if self.client:
            await self.client.add_output('|/cmd userdetails {}'.format(self.id))
        else:
            raise Exception("A client is needed to use this method.")

    async def get_rank(self, server_name=None):
        params = {
            'act' : 'ladderget',
            'user' : self.id
        }
        if server_name is None:
            if self.client:
                server_name = self.client.server_name
            else:
                server_name = 'showdown'
        result = requests.get(ACTION_URL_BASE.format(server_name), params=params).text
        return parse_http_input(result)

#Base class for UserJoin/UserLeave
class _UserMove:
    def __init__(self, room_id, user_str, client=None):
        self.auth = user_str[0]
        self.user = User(user_str[1:], client=client)
        self.room_id = room_id or 'lobby'

    def __repr__(self):
        return '<{} ({}) {}{}>'.format(self.__class__.__name__, \
               self.room_id, self.auth.strip(), self.user.name)

class UserJoin(_UserMove):
    pass

class UserLeave(_UserMove):
    pass

class UserNameChange:
    def __init__(self, room_id, new_user_str, old_id, client=None):
        self.room_id = room_id
        self.new_user = User(new_user_str[1:], client)
        self.new_auth = new_user_str[0].strip()
        self.old_id = old_id

    def __repr__(self):
        return '<NameChange ({}) {}->{}{}>'.format(
            self.room_id,
            self.old_id, 
            self.new_auth, 
            self.new_user.name)