from queue import Queue
from .utils import parse_text_input, name_to_id
from .user import UserLeave, UserJoin, UserNameChange, User

class Room:
    def __init__(self, room_id, client=None, max_logs=1000):
        self.id = room_id
        self.logs = Queue(maxsize=max_logs)
        self.userlist = {}
        self.client = client
        self.title = None

    def add_content(self, content):
        self.logs.put(content)
        inp_type, params = parse_text_input(content)
        self.update(inp_type, params)

    def update(self, inp_type, params):
        if inp_type == 'title':
            self.title = params[0]
        if inp_type == 'users':
            user_strs = params[0].split(',')[1:]
            for user_str in user_strs:
                u = User(user_str[1:])
                self.userlist[u.id] = (user_str[0], u)
        elif inp_type == 'n':
            name_change = UserNameChange(self.id, *params, client=self.client)
            old_id = name_change.old_id
            if old_id in self.userlist:
                del self.userlist[old_id]
            user = name_change.new_user
            self.userlist[user.id] = (name_change.new_auth, user)
        elif inp_type == 'l':
            user_leave = UserLeave(self.id, *params, client=self.client)
            user = user_leave.user
            if user.id in self.userlist:
                del self.userlist[user.id]
        elif inp_type == 'j':
            user_str = params[0]
            user_auth, user_name = user_str[0], user_str[1:]
            user = User(user_name, client=self.client)
            self.userlist[user.id] = (user_auth, user)

    async def request_auth(self):
        if self.client:
            self.client.add_output('{}|/roomauth'.format(self.id))
        else:
            raise Exception('A client is needed to perform this action')

    async def say(self, content):
        if self.client:
            self.client.say(self.id, content)
        else:
            raise Exception('A client is needed to perform this action')