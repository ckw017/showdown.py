import time
from .user import User
from .utils import *

class ChatMessage:
    def __init__(self, room_id, inp_type, *params, client=None):
        self.room_id = room_id
        if inp_type == 'c':
            self.timestamp = None
        elif inp_type == 'c:':
            self.timestamp = int(params[0])
            params = params[1:]
        author_str = params[0]
        self.client = client
        self.author = User(author_str, client=client)
        self.content = '|'.join(params[1:])

    def __repr__(self):
        return '<ChatMessage ({}) [{}] {}: {}>'.format(
               self.room_id, 
               self.timestamp, 
               str(self.author),
               abbreviate(self.content))

    @require_client
    async def reply(self, message):
        await self.client.say(message, room_id=self.room_id)

class PrivateMessage:
    def __init__(self, author_str, recipient_str, *content, client=None):
        self.timestamp = int(time.time())
        self.author = User(author_str, client=client)
        self.recipient = User(recipient_str, client=client)
        self.content = '|'.join(content)
        self.client=client

    def __repr__(self):
        return '<PrivateMessage ({}->{}) [{}]: {}>'.format(
               str(self.author), 
               str(self.recipient),
               self.timestamp, 
               abbreviate(self.content))

    @require_client
    async def reply(self, message):
        await self.client.private_message(self.author.id, message)