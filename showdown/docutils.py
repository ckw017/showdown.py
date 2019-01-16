import inspect
import asyncio
import sys

base_coro_docstring = """
{indent}|coro|
"""

delay_docstring = """
delay (:obj:`int` or obj:`float`, optional) : The minimum delay
    before sending this command. If the client's output queue 
    encounters this value before the delay has passed, it will 
    ignore the content. Defaults to 0.
"""

lifespan_docstring = """
lifespan (:obj:`int` or obj:`float`, optional) : The maximum delay
    before the command is discarded from the client's output queue.
    Defaults to math.inf.
"""

room_id_docstring = """
room_id (:obj:`str`) : The id of the target room.
    Ex: 'writing', 'battle-gen7monotype-1234567'
"""

team_docstring = '''
team (:obj:`str`) : A team in human readable format.
    Ex: """Doublade @ Eviolite  
           Ability: No Guard  
           EVs: 252 HP / 252 Atk / 4 SpD  
           Brave Nature  
           IVs: 0 Spe  
           - Swords Dance  
           - Gyro Ball  
           - Shadow Sneak  
           - Shadow Claw"""
'''

battle_format_docstring = """
battle_format (:obj:`str`) : The name of the format to use
    Ex: 'gen7monotype', 'gen6randombattle'
"""

battle_id_docstring = """
battle_id (:obj:`str`) : The id of the battle for. 
    Ex: 'battle-gen7monotype-12345678'
"""

avatar_id_docstring = """
avatar_id (:obj:`str`) : The id of the avatar you want to use.
    Ex: 260 (Cynthia), 148 (Claire), "teamrocket"
"""

strict_docstring = """
strict (:obj:`bool`, optional) : If this flag is set, passing in 
    content more than 300 characters will raise an error. Otherwise,
    the message will be senttruncated with a warning. This parameter
    defaults to False.
"""

content_docstring = """
content (:obj:`str`) : The content of the message.
    Ex: 'Hello showdown!'
"""

user_id_docstring = """
user_id (:obj:`str`) : The id of the target user.
    Ex: 'zarel', 'scriptkitty', 'skymin20'
"""

strict_notes_docstring = """
Content should be less than 300 characters long. Longer messages 
will be concatenated. If the strict flag is set, an error will be 
raised instead.
"""

strict_error_docstring = """
ValueError: if the message is longer than 300 characters and the 
    strict flag is set.
"""

indent_formatter = '{indent}'
def process_base_docstrings(base_docstring):
    base_docstring=base_docstring.strip()
    result = ''
    for i, row in enumerate(base_docstring.splitlines()):
        if i > 0 and not row.startswith(indent_formatter):
            row = indent_formatter + row
        result +=  row + '\n'
    return result.strip()

base_docstrings = {}
for name, val in dict(globals()).items():
    if name.endswith('_docstring'):
        name = name.replace('_docstring', '')
        base_docstrings[name] = process_base_docstrings(val)

def format(indent=3):
    full_indent = indent * '    '
    partial_indent = (indent - 1) * '    '
    docstrings = {
        k:v.format(indent=full_indent) for k,v in base_docstrings.items()
    }
    coro_docstring = base_coro_docstring.format(indent=partial_indent)
    def wrapper(func):
        doc = func.__doc__
        if inspect.iscoroutinefunction(func) and \
            not doc.startswith(coro_docstring):
            doc = coro_docstring + doc
        doc = doc.format(**docstrings)
        func.__doc__ = doc
        return func
    return wrapper