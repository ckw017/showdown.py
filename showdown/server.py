# -*- coding: utf-8 -*-
"""Module for Server objects"""

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
WEBSOCKET_URL_BASE = 'ws://{server_hostname}/showdown/{num_triplet}/{char_octet}/websocket'

def get_host(server_id):
    """
    Requests a server's host name from showdown.
    
    Example:
        >>> get_host('showdown')
        'sim2.psim.us:8000'
    """
    info_url = SERVER_INFO_URL_BASE.format(server_id=server_id)
    logger.info('Requesting server host from {}'.format(info_url))
    response = requests.get(info_url)
    if not response.ok:
        raise ValueError('Info for server `{}` is unavailable.'
            .format(server_id))
    try:
        data = response.json()
        return '{}:{}'.format(data['host'], data['port'])
    except:
        traceback.print_exc()
        raise ValueError('Malformed server_info data at `{}`.'
            .format(info_url))

def _generate_ws_triplet():
    """
    Generates a zero-filled string of a random three digit base ten number.
    """
    num = random.randint(0, 999)
    return str(num).zfill(3)

def _generate_ws_octet():
    """
    Generates a string of 8 random lowercase letter characters.
    """
    octet = ''
    for _ in range(8):
        octet += random.choice(string.ascii_lowercase)
    return octet

def generate_ws_url(server_hostname):
    """
    Generates a valid websocket URL for the given server_hostname
    """
    return WEBSOCKET_URL_BASE.format(
            server_hostname = server_hostname,
            num_triplet     = _generate_ws_triplet(),
            char_octet      = _generate_ws_octet())

def generate_action_url(server_id):
    """
    Generates an action url for the given server_id
    """
    return ACTION_URL_BASE.format(server_id = server_id)

def require_session(func):
    """
    Decorator that requires the server to have a valid aiohttp session.
    """
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
    """
    Class representing a showdown server that can be connected to. Various HTTP
    interactions can be made through objects. Such methods require a valid
    aiohttp session (set through Server.set_session) asynchronously, otherwise
    synchronous options are provided as well.

    Params:
        id (:obj:`str`, optional) : The server's id. 
            Ex: 'showdown', 'smogtours', 'azure'
            Defaults to 'showdown'
        host (:obj:`str`, optional) : The server's host. If not specified, 
            the object will automatically determine this by calling get_host
        client (:obj:`showdown.client.Client`, optional) : client object 
            connected to this server.

    Attributes:
        id (:obj:`str`, optional) : The server's id. 
            Ex: 'showdown', 'smogtours', 'azure'
            Defaults to 'showdown'
        host (:obj:`str`, optional) : The server's host. If not specified, 
            the object will automatically determine this by calling get_host
        client (:obj:`showdown.client.Client`, optional) : client object 
            connected to this server.
        action_url (:obj:`str`, optional) : The server's action url
        session (:obj:`aiohttp.ClientSession`) : Asynchronous http session
            used for querying data through post requests.
    """
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
        """
        Sets the server's session attribute.
        """
        self.session = session

    def generate_ws_url(self):
        """
        Returns a valid websocket URI for this server.
        """
        return generate_ws_url(self.host)

    @utils.require_client
    async def request_rooms(self, client=None):
        """
        Uses the specified client or the object's client attribute to request
        A list of the rooms on the server. The server will respond with a
        query response of type 'rooms'
        """
        await self.client.request_rooms()

    @require_session
    async def save_replay_async(self, battle_data, session=None):
        """
        Makes an asynchronous post request to upload the replay specified by 
        battle_data.
        """
        headers = {
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        battle_data['act'] = 'uploadreplay'
        async with self.session.post(self.action_url, data=battle_data, 
            headers=headers) as result:
            logger.info('^^^ Saved replay for `{}`, outcome: {}'.format(
                    battle_data['id'],
                    await result.text()
                )
            )
            return result

    @require_session
    async def login_async(self, name, password, challstr, challengekeyid, session=None):
        """
        Makes an asynchronous post request to obtain login data for the user
        specified by the method's parameters.
        """
        data = {
            'act': 'login',
            'name': name,
            'pass': password,
            'challenge': challstr,
            'challengekeyid': challengekeyid
        }
        async with self.session.post(self.action_url, data=data) as result:
            return utils.parse_http_input(await result.text())
            