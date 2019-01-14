# -*- coding: utf-8 -*-
"""
An example client that searches for battles
on the monotype ladder on login.
"""
import showdown
import logging
import asyncio
from pprint import pprint

logging.basicConfig(level=logging.INFO)
with open('./examples/data/login.txt', 'rt') as f:
    username, password = f.read().strip().splitlines()

with open('./examples/data/mono-ghost.txt') as f:
    team = f.read()

class LadderClient(showdown.Client):
    async def on_login(self, login_data):
        await self.search_battles(team, 'gen7monotype')

    async def on_receive(self, *params):
        print(params)

    async def on_room_init(self, room_obj):
        if isinstance(room_obj, showdown.room.Battle):
            await asyncio.sleep(3)
            await room_obj.say('Oh my, look at the time! Gotta go, gg.')
            await room_obj.forfeit()
            await room_obj.leave()

LadderClient(name=username, password=password).start()