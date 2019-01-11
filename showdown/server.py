import random
import string
import requests
import traceback
import logging
import json
from . import utils

#Logging setup
logger = logging.getLogger(__name__)

#Base URLs
SERVER_INFO_URL_BASE = 'https://pokemonshowdown.com/servers/{server_id}.json'
ACTION_URL_BASE =  'https://play.pokemonshowdown.com/~~{server_id}/action.php'
WEBSOCKET_URL_BASE = 'wss://{server_hostname}/showdown/{num_triplet}/{char_octet}/websocket'

def get_host(server_id):
    info_url = SERVER_INFO_URL_BASE.format(server_id=server_id)
    logger.info('Requesting server host from {}'.format(info_url))
    response = requests.get(info_url)
    if not response.ok:
        raise ValueError('Info for server `{}` is unavailable.'.format(server_id))
    try:
        data = response.json()
        return '{}'.format(data['host'])
    except:
        traceback.print_exc()
        raise ValueError('Malformed server_info data at `{}`.'.format(info_url))

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

def generate_action_url(server_id):
    return ACTION_URL_BASE.format(server_id = server_id)

class Server:
    def __init__(self, id='showdown', host=None, client=None):
        self.id = id
        self.host = host or get_host(self.id)
        self.client = client
        self.rooms = None
        self.formats = None

    def __repr__(self):
        return '<Server id={} host={}>'.format(\
            self.id,
            self.host)

    def generate_ws_url(self):
        return generate_ws_url(self.host)

    def generate_action_url(self):
        return generate_action_url(self.id)

    def set_custom_groups(self, *group_data):
        pass

    def set_formats(self, *format_data):
        self.formats = {}
        curr_category, curr_priority = None, '6'
        for token in format_data:
            if ',' not in token:
                curr_category = FormatCategory(token, curr_priority)
                continue
            format_name, format_type = token.split(',')
            if format_name:
                battle_format = BattleFormat(
                        format_name, 
                        curr_category, 
                        format_type, 
                        client=self.client
                )
                self.formats[battle_format.id] = battle_format
            else:
                curr_priority = format_type

    async def request_rooms(self):
        await self.client.request_rooms()

class FormatCategory:
    def __init__(self, name, priority):
        self.name = name
        self.priority = priority

class BattleFormat:
    def __init__(self, name, category, format_type, client=None):
        self.name = name
        self.id = utils.name_to_id(name)
        self.type = format_type
        self.client = client

    def __repr__(self):
        return '<BattleFormat {},{}>'.format(self.name, self.type)

    def search(self, team_str):
        if self.client:
            self.client.search_battles(team_str, self.id)