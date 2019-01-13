import random
import string
import requests
import traceback
import logging
import json
from . import utils
from functools import wraps

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

def _generate_ws_triplet():
    num = random.randint(0, 999)
    return str(num).zfill(3)

def _generate_ws_octet():
    octet = ''
    for _ in range(8):
        octet += random.choice(string.ascii_lowercase)
    return octet

def generate_ws_url(server_hostname):
    return WEBSOCKET_URL_BASE.format(
            server_hostname = server_hostname,
            num_triplet     = _generate_ws_triplet(),
            char_octet      = _generate_ws_octet())

def generate_action_url(server_id):
    return ACTION_URL_BASE.format(server_id = server_id)

def require_session(func):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        session = kwargs.get('session', None) or getattr(self, 'session', None) 
        if session is None:
            raise Exception("You can't use {0}.{1} without setting an aiohttp ClientSession. "
                            "This can be done with {0}.set_session method. You can also "
                            "use the keyword argument {0}.{1}(session=your_session)."
                            .format(self.__class__.__name__, func.__name__))
        else:
            kwargs['session'] = session
            return await func(self, *args, **kwargs)
    return wrapper

class Server:
    def __init__(self, id='showdown', host=None, client=None):
        self.id = id
        self.host = host or get_host(self.id)
        self.client = client
        self.action_url = generate_action_url(self.id)
        self.session = None

    def __repr__(self):
        return '<Server id={} host={}>'.format(\
            self.id,
            self.host)

    def set_session(self, session):
        self.session = session

    def generate_ws_url(self):
        return generate_ws_url(self.host)

    async def request_rooms(self):
        await self.client.request_rooms()

    @require_session
    async def save_replay_async(self, battle_data, session=None):
        headers = {
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        battle_data['act'] = 'uploadreplay'
        async with self.session.post(self.action_url, data=battle_data, headers=headers) \
                  as result:
            logger.info('^^^ Saved replay for `{}`, outcome: {}'.format(
                    battle_data['id'],
                    await result.text()
                )
            )
            return result

    @require_session
    async def login_async(self, name, password, challstr, challengekeyid, session=None):
        data = {
            'act': 'login',
            'name': name,
            'pass': password,
            'challenge': challstr,
            'challengekeyid': challengekeyid
        }
        async with self.session.post(self.action_url, data=data) as result:
            return utils.parse_http_input(await result.text())
            