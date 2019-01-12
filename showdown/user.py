import json
import re
import requests
import string
from .utils import *

USER_DATA_BASE = 'https://pokemonshowdown.com/users/{user_id}.json'

class User:
    def __init__(self, user_str, client=None):
        if user_str[0].lower() not in string.ascii_lowercase:
            self.auth = user_str[0]
            name = user_str[1:]
        else:
            self.auth = ' '
            name = user_str
        self.set_name(name)
        self.id = name_to_id(name)
        self.client = client
        self._user_data = None

    def __eq__(self, other):
        return isinstance(other, User) and self.id == other.id

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.id)

    def __repr__(self):
        return '<{} `{}`>'.format(self.__class__.__name__, str(self))

    def __str__(self):
        return '{}{}'.format(self.auth.strip(), self.name)    

    def set_name(self, name):
        self.name = name
        self.id = name_to_id(name)

    def name_matches(self, username):
        return self.id == name_to_id(username)

    @require_client
    async def message(self, content):
        await self.client.private_message(self, content)

    @require_client
    async def request_user_details(self):
        await self.client.add_output('|/cmd userdetails {}'.format(self.id))

    def _get_user_data(self, force_update=False):
        if not force_update and self._user_data is not None:
            return
        response = requests.get(USER_DATA_BASE.format(user_id = self.id))
        if response.ok:
            self._user_data = response.json()

    @property
    def ratings(self):
        self._get_user_data(force_update=True)
        return self._user_data['ratings']

    @property
    def register_time(self):
        self._get_user_data()
        return self._user_data['registertime']

    @property
    def register_name(self):
        self._get_user_data()
        return self._user_data['username']

    def ladder_get(self, server_name=None):
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