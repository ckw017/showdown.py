# -*- coding: utf-8 -*-
"""Miscellaneous utils for the showdown module"""
import json
import re
import random
import string
import inspect
import warnings
import datetime
from functools import wraps

def require_client(func): 
    """
    Decorator for class methods that require a client either through keyword
    argument, or through the object's client attribute.

    Returns:
        A wrapped version of the function. The object client attrobute will
        be passed in as the client keyword if None is provided.

    Raises:
        AssertionError : Raised when the method is called without a client
        keyword set and no client attribute. 
    """
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        client = kwargs.get('client', None) or getattr(self, 'client', None) 
        if client is None:
            msg = ('{0} object does not have a client -- {0}.{1} will do '
                   'nothing. To set a client, initialize the object with '
                   '{0}(..., client=your_client). Alternatively, you can '
                   'use the client keyword argument in the method.'
                   .format(self.__class__.__name__), func.__name__)
            raise AssertionError(msg)
        else:
            kwargs['client'] = client
            return await func(self, *args, **kwargs)
    return wrapper

def strip_prefix(s):
    """ 
    Strips off nonletter prefix from a string.

    Examples:
        >>> strip_prefix('~lobby')
        'lobby'
        >>> strip_prefix('+Argus2Spooky')
        'Argus2Spooky'
    """
    if s and s[0].lower() not in string.ascii_lowercase:
        s = s[1:]
    return s

def timestamp_to_hh_mm_ss(timestamp):
    """
    Converts a unix timestamp to hh:mm:ss format.

    Examples:
        >>> timestamp_to_hh_mm_ss(1234567)
        '06:56:07'

    """
    dt = datetime.datetime.utcfromtimestamp(timestamp)
    return dt.strftime('%H:%M:%S')

def clean_message_content(content, strict=False):
    """
    Truncates messages longer than 300 characters. If the strict flag is set,
    then an error is raised instead.
    
    Params:
        content (:obj:`str`) : Content to be cleaned

    Returns:
        (:obj:`str`) : Content truncated appropriately if longer than 300
            characters.

    Raises:
        ValueError : Raised when the strict flag is set and the content is
            longer than 300 characters.
    """
    content = str(content)
    if len(content) > 300:
        if strict:
            raise ValueError('Message content is too long (>300 characters). The '
                             'message will not be sent.')
        else:
            warnings.warn('Message content is too long (>300 characters). Truncating.')
            content = content[:300]
    return content

def abbreviate(content):
    """
    Truncates content below 20 characters. Adds '...' if the content has been
    truncated.

    Examples:
        >>> abbreviate('Hey, I just met you, and this is crazy')
        'Hey, I just met you,...'
    """
    content = str(content)
    content_length = len(content)
    return content[:20].rstrip() + ('...' if content_length > 20 else '')

def name_to_id(input_str):
    """
    Removes all non-letter or number characters from input_str, and lowercases.

    Example:
        >>> name_to_id('Zarel ^_^')
        'zarel'
    """
    return re.sub(r'(\W|_)', '', input_str.lower())

#Parsing
def parse_text_input(text_input):
    """
    Parses the text input received over the client's websocket connection.

    Returns:
        (input_type (str), params (list))
    """
    tokens = text_input.strip().split('|')
    if len(tokens) == 1:
        inp_type = 'rawtext'
        params = tokens
    else:
        inp_type = tokens[1].lower()
        params = tokens[2:]
    return inp_type, params

def parse_http_input(http_input):
    """
    Parses the input received over the client's http connection.

    Returns:
        dict : Dictionary representing a JSON object.
    """
    if http_input.startswith(']'):
        return json.loads(http_input[1:])
    raise ValueError('Unexpected http input:\n{}'.format(http_input))

def parse_socket_input(socket_input):
    """
    Parses the raw input received over the client's socket_input

    Returns:
        (room_id (str), text_input (str))
    """
    if socket_input.startswith('a'):
        loaded = json.loads(socket_input[1:])
        result = []
        for row in loaded:
            loaded = row.splitlines()
            if loaded[0].startswith('>'):
                room_id = loaded[0][1:] or 'lobby'
                raw_events = loaded[1:]
            else:
                room_id = 'lobby'
                raw_events = loaded
            for event in raw_events:
                result.append((room_id, event))
        return result
    raise ValueError('Unexpected socket input:\n{}'.format(socket_input))