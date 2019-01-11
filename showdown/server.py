import random
import string
import requests
import traceback
import logging

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
        self.rooms = []

    def generate_ws_url(self):
        return generate_ws_url(self.host)

    def generate_action_url(self):
        return generate_action_url(self.id)

    def set_custom_groups(self, *params):
        pass

    def set_formats(self, *params):
        pass

    async def request_rooms(self):
        await self.client.request_rooms()