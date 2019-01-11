import time
from .user import User
from .utils import abbreviate

class ChatMessage:
    def __init__(self, room_id, inp_type, *params, client=None):
        self.room_id = room_id or 'lobby'
        if inp_type == 'c':
            self.timestamp = None
        elif inp_type == 'c:':
            self.timestamp = int(params[0])
            params = params[1:]
        author_str = params[0]
        auth, name = author_str[0], author_str[1:]
        self.author = User(name, client=client)
        self.auth = auth
        self.content = '|'.join(params[1:])

    def __repr__(self):
        return '<ChatMessage ({}) [{}] {}{}: {}>'.format(
               self.room_id, 
               self.timestamp,
               self.auth.strip(), 
               self.author.name,
               abbreviate(self.content))

class PrivateMessage:
    def __init__(self, author_name, recipient_name, *content, client=None):
        self.timestamp = int(time.time())
        self.author = User(author_name[1:], client=client)
        self.author_auth = author_name[0]
        self.recipient = User(recipient_name, client=client)
        self.recipient_auth = recipient_name[0]
        self.content = '|'.join(content)

    def __repr__(self):
        return '<PrivateMessage ({}{}->{}{}) [{}]: {}>'.format(
               self.author_auth.strip(), 
               self.author.name, 
               self.recipient_auth.strip(), 
               self.recipient.name,
               self.timestamp, 
               abbreviate(self.content))

class RawText:
    def __init__(self, room_id, content):
        self.room_id = room_id or 'lobby'
        self.content = content

    def __repr__(self):
        return '<RawText ({}) {}>'.format(
            self.room_id,
            abbreviate(self.content))