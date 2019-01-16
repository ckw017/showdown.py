# Intro
A client for [Pokemon Showdown!](https://pokemonshowdown.com/) for Python 3.4 and 3.5. This was written to make it easier to write bots, interact with users, moderate chat rooms, and collect data.

# Setup
Install the package with ``pip3 install --user showdownpy``. This will also install the package's ``websockets`` and ``aiohttp`` dependencies if you do not already have them.

# Example
Examples have been provided in the ``./examples directory``. Make sure to create your own versions of the ``login.txt`` and ``owner.txt`` files in ``./examples/data/`` directory. Templates for those files have been provided.

The client on its own doesn't do very much, and is instead intended to be extended and modified. This can be done through various "hook" coroutines left in the base class. The following program uses the ``on_private_message`` hook to echo back the content of any PMs it receives.

```python3
"""
An example client that echoes back any message that is 
private messaged to it
"""
import showdown

with open('./examples/data/login.txt', 'rt') as f:
    username, password = f.read().strip().splitlines()
   
class EchoClient(showdown.Client):
    async def on_private_message(self, pm):
        if pm.recipient == self:
            await pm.reply(pm.content)

EchoClient(name=username, password=password).start()
```

Other hooks include ``on_connect``, ``on_login``, ``on_room_init``, ``on_room_deinit``, ``on_query_response`` and ``on_chat_message``.

These hooks are by no means all inclusive (Showdown has somewhere upwards of 40 different types of messages it uses to interact with clients in its protocol), and so a catch-all hook `on_receive` is also present. Each hook is given its own task on the event loop, so you don't have to worry about any tasks blocking each other.

The bot can also be used for collecting data on battles. The following bot anonymously joins ongoing matches in the format 'OU' and saves replays of them when a user finishes.

```python3
"""
An example client that joins all OU battles
and saves replays.
"""
import showdown

with open('./examples/data/login.txt', 'rt') as f:
    username, password = f.read().strip().splitlines()

class ReplayClient(showdown.Client):
    async def on_query_response(self, response_type, data):
        if response_type == 'roomlist':
            for battle_id in set(data['rooms']) - set(self.rooms):
                await self.join(battle_id)

    async def on_receive(self, room_id, inp_type, params):
        if inp_type == 'win':
            with open('./data/' + room_id, 'wt') as f:
                f.write('\n'.join(self.rooms[room_id].logs))
    @showdown.Client.on_interval(interval=3)
    async def check_ou(self): 
        await self.query_battles(tier='gen7ou', lifespan=3)

ReplayClient(name=username, password=password).start(autologin=False)
```

It is recommended that you save local copies of these matches rather than upload them, as to not overwhelm Showdown's replay server.

# Contributions
This package is still a work in progress, and any contributions would be great! I'm currently prioritizing documentation over new features, but if you have an idea for something let me know. Feel free to share anything you make with the client and if its succint enough I may add it to the pool of examples.
