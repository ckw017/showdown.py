from . import client
import traceback
import json
import time


class NameChange:
    def __init__(self, new_user_str, old_id):
        self.new_user = client.User(new_user_str[1:])
        self.new_auth = new_user_str[0].strip()
        self.old_id = old_id

    def __repr__(self):
        return '<NameChange {}->{}{}>'.format(self.old_id, self.new_auth, self.new_user.name)

class ChatMessage:
    def __init__(self, room_id, inp_type, *params):
        self.room_id = room_id
        if inp_type == 'c':
            self.timestamp = None
        elif inp_type == 'c:':
            self.timestamp = int(params[0])
            params = params[1:]
        author_str = params[0]
        self.author = client.User(author_str[1:].strip())
        self.auth = author_str[0].strip()
        self.content = '|'.join(params[1:])

    def __repr__(self):
        return '<ChatMessage ({}) [{}] {}{}: {}{}>'.format( \
               self.room_id, self.timestamp, self.auth, self.author.name, \
               self.content[:20].rstrip(), '...' if len(self.content) > 20 else '')

class PrivateMessage:
    def __init__(self, author_name, recipient_name, *content):
        self.timestamp = int(time.time())
        self.author = client.User(author_name[1:])
        self.auth = author_name[0].strip()
        self.recipient = client.User(recipient_name)
        self.rauth = recipient_name[0].strip()
        self.content = '|'.join(content)

    def __repr__(self):
        return '<PrivateMessage ({}{}->{}{}) [{}]: {}{}>'.format( \
               self.auth, self.author.name, self.rauth, self.recipient.name, self.timestamp,\
               self.content[:20].rstrip(), '...' if len(self.content) > 20 else '')

class UserDetails:
    def __init__(self, raw_data):
        raw_data = json.loads(raw_data)
        self.raw = raw_data
        self.user = client.User(raw_data['userid'])
        self.rooms = raw_data['rooms']
        self.is_online = not (self.rooms is False)
        self.avatar = raw_data.get('avatar', 0)
        self.group = raw_data.get('group', ' ').strip()

    def __repr__(self):
        return '<UserDetails {}{} ({})>'.format(self.group, self.user.name, 
            'online' if self.is_online else 'offline')


class _RoomChange:
    def __init__(self, room_id, user_str):
        self.user = client.User(user_str[1:])
        self.auth = user_str[0].strip()
        self.room_id = room_id

    def __repr__(self):
        return '<{} ({}) {}{}>'.format(self.__class__.__name__, \
               self.room_id, self.auth, self.user.name)

class Join(_RoomChange):
    pass

class Leave(_RoomChange):
    pass

class _JSONContent:
    def __init__(self, *content):
        content = '|'.join(content).strip()
        try:
            self.content = json.loads(content)
        except:
            traceback.print_exc()
            self.content = {}
            print('Problem while parsing content: {}'.format(content))

    def __repr__(self):
        return '<{}>'.format(self.__class__.__name__)

class UpdateSearch(_JSONContent):
    pass

class UpdateChallenges(_JSONContent):
    pass

class _RoomAndContent:
    def __init__(self, room_id, *content):
        content = '|'.join(content)
        self.room_id = room_id
        self.content = content

    def __repr__(self):
        return '<{} ({}) {}{}>'.format(self.__class__.__name__, self.room_id, \
            self.content[:30].rstrip(), '...' if len(self.content) > 30 else '')

class RoomInit(_RoomAndContent):
    pass

class RawHTML(_RoomAndContent):
    pass

class UHTML(_RoomAndContent):
    pass

class UpdateUser:
    def __init__(self, username, logged_in, avatar_id, *rest):
        self.user = client.User(username)
        self.logged_in = logged_in.strip()
        self.avatar_id = avatar_id.strip()
        self.rest = rest

    def __str__(self):
        return '<UpdateUser {}|{}|{}>'.format(self.user.name, self.logged_in, self.avatar_id)
