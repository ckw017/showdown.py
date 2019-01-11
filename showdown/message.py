import time
from .user import User
from .utils import abbreviate

class ChatMessage:
    def __init__(self, room_id, inp_type, *params, client=None):
        self.room_id = room_id
        if inp_type == 'c':
            self.timestamp = None
        elif inp_type == 'c:':
            self.timestamp = int(params[0])
            params = params[1:]
        author_str = params[0]
        self.author = User(author_str, client=client)
        self.content = '|'.join(params[1:])

    def __repr__(self):
        return '<ChatMessage ({}) [{}] {}: {}>'.format(
               self.room_id, 
               self.timestamp, 
               str(self.author),
               abbreviate(self.content))

class PrivateMessage:
    def __init__(self, author_str, recipient_str, *content, client=None):
        self.timestamp = int(time.time())
        self.author = User(author_str, client=client)
        self.recipient = User(recipient_str, client=client)
        self.content = '|'.join(content)

    def __repr__(self):
        return '<PrivateMessage ({}->{}) [{}]: {}>'.format(
               str(self.author), 
               str(self.recipient),
               self.timestamp, 
               abbreviate(self.content))

class RawText:
    def __init__(self, room_id, content):
        self.room_id = room_id
        self.content = content

    def __repr__(self):
        return '<RawText ({}) {}>'.format(
            self.room_id,
            abbreviate(self.content))