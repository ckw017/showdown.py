import time
from . import user, utils

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
        self.author = user.User(author_str, client=client)
        self.content = '|'.join(params[1:])

    def __repr__(self):
        return '<ChatMessage ({}) [{}] {}: {}>'.format(
                 self.room_id, 
                 self.timestamp, 
                 str(self.author),
                 abbreviate(self.content)
               )

    @utils.require_client
    async def reply(self, content, client=None):
        await client.say(self.room_id, content)

class PrivateMessage:
    def __init__(self, author_str, recipient_str, *content, client=None):
        self.timestamp = int(time.time())
        self.author = user.User(author_str, client=client)
        self.recipient = user.User(recipient_str, client=client)
        self.content = '|'.join(content)
        self.client = client

    def __repr__(self):
        return '<PrivateMessage ({}->{}) [{}]: {}>'.format(
               str(self.author), 
               str(self.recipient),
               self.timestamp, 
               utils.abbreviate(self.content))

    @utils.require_client
    async def reply(self, content, client=None):
        await client.private_message(self.author.id, content)