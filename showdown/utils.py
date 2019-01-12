import json
import re
import random
import string
import inspect
import warnings
from functools import wraps

def require_client(func): #TODO give these methods a keyword arg for a client
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        client = kwargs.get('client', None) or getattr(self, 'client', None) 
        if client is None:
            msg = ('{0} object does not have a client -- this function will do '
                   'nothing. To set a client, initialize the object with '
                   '{0}(..., client=your_client). Alternatively, you can '
                   'use the client keyword argument in the method.'
                   .format(self.__class__.__name__))
            raise Exception(msg)
        else:
            print(kwargs)
            print(args)
            kwargs['client'] = client
            return await func(self, *args, **kwargs)
    return wrapper

def clean_message_content(content):
    content = str(content)
    if len(content) > 300:
        warnings.warn('Message content is too long (>300 characters). Truncating.')
        content = content[:300]
    return content

def abbreviate(content):
    content = str(content)
    content_length = len(content)
    return content[:20].rstrip() + ('...' if content_length > 20 else '')

def name_to_id(input_str):
    return re.sub(r'(\W|_)', '', input_str.lower()).strip()

#Parsing
def parse_text_input(text_input):
    tokens = text_input.strip().split('|')
    if len(tokens) == 1:
        inp_type = 'rawtext'
        params = tokens
    else:
        inp_type = tokens[1].lower()
        params = tokens[2:]
    return inp_type, params

def parse_http_input(http_input):
    if http_input.startswith(']'):
        return json.loads(http_input[1:])
    raise ValueError('Unexpected http input:\n{}'.format(http_input))

def parse_socket_input(socket_input):
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