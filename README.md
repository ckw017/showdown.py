# Intro
A client for [Pokemon Showdown!](https://pokemonshowdown.com/) for Python 3.5+. This was written to make it easier to write bots, interact with users, moderate chat rooms, and collect data.

# Setup
I'm planning to upload the module to PyPI as soon as I hammer out all the documentation. For now, you can clone in the repository with ``git clone https://github.com/ckw017/showdown.py``, and use ``import showdown`` as you normally would inside the project directory. Install requirements using ``pip3 install --user -r requirements.txt``

# Example
Examples have been provided in the ./examples directory. Make sure to create your own versions of the login.txt and owner.txt files in ./examples/data/ directory. Example files have been provided.

The client on its own doesn't do very much, and is instead intended to be extended and modified. This can be done through various "hooks" left in the base class. The following program uses the ``on_private_message`` hook to echo back the content of any PMs it receives.

```
import showdown
import logging

logging.basicConfig(level=logging.INFO)
with open('./examples/data/login.txt', 'rt') as f:
    username, password = f.read().strip().splitlines()


class EchoClient(showdown.Client):
    async def on_private_message(self, pm):
        if pm.recipient == self:
            await pm.reply(pm.content)

EchoClient(name=username, password=password).start()
```

Other hooks include ``on_connect``, ``on_login``, ``on_room_init``, ``on_room_deinit``, ``on_query_response`` and ``on_chat_message``.

These hooks are by no means all inclusive (Showdown has somewhere upwards of 40 different types of messages it uses to interact with clients), and so a catch-all hook `on_receive` is also present.