# -*- coding: utf-8 -*-
"""Module for showdown's User class"""
import json
import re
import requests
import string
import math
from . import utils, server

USER_DATA_URL_BASE = 'https://pokemonshowdown.com/users/{user_id}.json'

class User:
    '''
    Class representing on a User on Showdown. Includes utility methods for
    sending private messages and requesting data.

    Args:
        user_str (obj:`str`) : A string representing the user of interest. This
            can be the user's name, or the user's name prefixed by their auth
            group. Ex: "~Zarel", "Script Kitty", "balto", "%Lux"
        client (obj:`showdown.client.Client`, optional) : client to be used in
            the object's utility methods

    Attributes:
        name (obj:`str`) : String representing the user's name. Can contain
            uppercase and nonletter characters
            Ex: 'Script Kitty @.@'
        id (obj:`str`) : String representing the user's id. Can only consist
            of lowercase letters
            Ex: 'scriptkitty'
        client (obj:`showdown.client.Client` or None) : client used in the
            object's utility methods
    '''
    def __init__(self, user_str, client=None):
        if not user_str:
            self.auth = ' '
            name = ''
        elif user_str[0].lower() not in string.ascii_lowercase:
            self.auth = user_str[0]
            name = user_str[1:]
        else:
            self.auth = ' '
            name = user_str
        self.set_name(name)
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
        """
        Utility method to set the object's name and id attributes

        Args:
            name (obj:`str`) : The name used to set the User object's new
                name and id
        """
        self.name = name
        self.id = utils.name_to_id(name)

    def name_matches(self, name):
        """
        Checks if the User object's id matches the id of the username passed in.
        
        Args:
            name (obj:`str`) : The name to compare with the User object's id

        Returns:
            bool : True if the name matches, else False

        Examples:
           >>> User("~Zarel ^_^").name_matches('Zar-el'))
           True 
           >>> User("~Zarel ^_^").name_matches('zarel'))
           True
           >>> User("~Zarel ^_^").name_matches('Carl'))
           False
        """
        return self.id == utils.name_to_id(name)

    @utils.require_client
    async def challenge(self, team, tier, client=None):
        """
        |coro|

        Uses the specified client or the object's client attribute to send
        a challenge to the user represented by this object.
        """
        await client.send_challenge(self.id, team, tier)

    @utils.require_client
    async def cancel_challenge(self):
        """
        |coro|

        Uses the specified client or the object's client attribute to cancel
        a challenge to the user represented by this object.
        """
        await client.cancel_challenge()

    @utils.require_client
    async def reject_challenge(self, client=None):
        """
        |coro|

        Uses the specified client or the object's client attribute to reject
        a challenge from the user represented by this object.
        """
        await client.reject_challenge(self.id)

    @utils.require_client
    async def accept_challenge(self, team, client=None):
        """
        |coro|

        Uses the specified client or the object's client attribute to accept
        a challenge from the user represented by this object.
        """
        await client.accept_challenge(self.id, team)

    @utils.require_client
    async def send_message(self, content, strict=False, client=None, 
        delay=0, lifespan=math.inf):
        """
        |coro|

        Uses the specified client or the object's client attribute to send a 
        message to the represented user.

        Args:
            content (obj:`str`) : The content of the message to be sent.
            strict (obj:`bool`, optional) : See help(Client.say)
            client (obj:`showdown.client.Client` or None, optional) : client 
                used to send the message
            delay (obj:`int` or obj:`float`, optional) : See 
                help(Client.add_output)
            lifespan (obj:`int` or obj:`float`, optional) : See 
                help(Client.add_output)

        Returns:
            None
        """
        await client.private_message(self.id, content, strict=False, 
            delay=delay, lifespan=lifespan)

    @utils.require_client
    async def request_user_details(self, client=None, 
        delay=0, lifespan=math.inf):
        """
        |coro|

        Uses the specified client or the object's client attribute to request 
        details on the user. The response will be sent back as a query response
        with a response_type of 'userdetails'. You can wait for this response
        using the Client.on_query_response method.
        
        Args:
            client (obj:`showdown.client.Client` or None, optional) : client 
                used to request the details.
            delay (obj:`int` or obj:`float`, optional) : See 
                help(Client.add_output).
            lifespan (obj:`int` or obj:`float`, optional) : See 
                help(Client.add_output).

        Returns:
            None
        """
        await self.client.add_output('|/cmd userdetails {}'.format(self.id),
            delay=delay, lifespan=lifespan)

    def _get_user_data(self, force_update=False):
        if not force_update and self._user_data is not None:
            return
        response = requests.get(USER_DATA_URL_BASE.format(user_id = self.id))
        if response.ok:
            self._user_data = response.json()

    def get_ratings(self):
        """
        Gets the user's ratings (rank) on the main showdown server. Use
        User.get_ladder to find their ratings on other servers or for
        win loss ratios.

        Returns:
            dict representing the user's ratings

        Examples:
            >>> from pprint import pprint
            >>> pprint(User('zarel').get_ratings())
            {'gen2ou': {'elo': '1000',
                        'gxe': '47.6',
                        'rpr': '1480.9917808997',
                        'rprd': '124.38541619468'},
             'lc': {'elo': '1000',
                    'gxe': '45',
                    'rpr': '1459.8393856612',
                    'rprd': '122.8583080769'}}
        """
        self._get_user_data(force_update=True)
        return self._user_data['ratings']

    def get_register_time(self):
        """
        Gets the time the user's account was registered.

        Returns:
            An int representing the unix timestamp of the account's
            registration time

        Examples:
            >>> User('zarel').get_register_time()
            1304640
        """
        self._get_user_data()
        return self._user_data['registertime'] // 1000

    def get_register_name(self):
        """
        Gets the name with which the user's account was registered.

        Returns:
            A string representing the account's registration name

        Examples:
            >>> showdown.User('crashy').get_register_name()
            'Crashy ★ - '
        """
        self._get_user_data()
        return self._user_data['username']


    def get_ladder(self, server_id=None):
        """
        Gets the user's ratings on the server for the specified server.
        Includes more detailed information that User.get_ratings

        Examples:
            from pprint import pprint
            >>> pprint(User('argus2spooky').get_ladder())
            [{'col1': '1033',
              'elo': '1736.1765984494',
              'entryid': '15753610',
              'formatid': 'gen7monotype',
              'gxe': '80.7',
              'l': '415',
              'r': '1769.8943143527',
              'rd': '25',
              'rpr': '1769.8943143527',
              'rprd': '25.876418629631',
              'rpsigma': '0',
              'rptime': '1547456400',
              'sigma': '0',
              't': '0',
              'userid': 'argus2spooky',
              'username': 'Argus2Spooky',
              'w': '618'}]
        """
        params = {
            'act' : 'ladderget',
            'user' : self.id
        }
        if server_id is None:
            if self.client:
                server_id = self.client.server.id
            else:
                server_id = 'showdown'
        result = requests.get(server.ACTION_URL_BASE.format(server_id=server_id), 
            params=params).text
        return utils.parse_http_input(result)

    async def get_ladder_async(self, server_id='showdown'):
        raise NotImplementedError