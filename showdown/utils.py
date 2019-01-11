import json
import re
import random
import string

#Base URLs
ACTION_URL_BASE =  'https://play.pokemonshowdown.com/~~{server_name}/action.php'
WEBSOCKET_URL_BASE = 'wss://{server_hostname}/showdown/{num_triplet}/{char_octet}/websocket'

#Default servers {server_name:server_hostname}
server_map = {
    'azure': 'oppai.azure.lol',
    'showdown': 'sim2.psim.us'
}

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

def generate_action_url(server_name):
    return ACTION_URL_BASE.format(server_name = server_name)

def abbreviate(content):
    content_length = len(content)
    return content[:20].rstrip() + ('...' if content_length > 20 else '')

def name_to_id(input_str):
    return re.sub(r'(\W|_)', '', input_str.lower()).strip()

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
                room_id = loaded[0][1:]
                raw_events = loaded[1:]
            else:
                room_id = None
                raw_events = loaded
            for event in raw_events:
                result.append((room_id, event))
        return result
    raise ValueError('Unexpected socket input:\n{}'.format(socket_input))