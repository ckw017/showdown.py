# -*- coding: utf-8 -*-
"""
An example client that challenges a player to 
a random battle when PM'd, or accepts any
random battle challenge.
"""
import showdown
import logging
import asyncio
from pprint import pprint

logging.basicConfig(level=logging.INFO)
with open('./examples/data/login.txt', 'rt') as f,\
     open('./examples/data/mono-ghost.txt', 'rt') as team:
    ghost_team = team.read()
    username, password = f.read().strip().splitlines()

class ChallengeClient(showdown.Client):
    async def on_private_message(self, pm):
        if pm.recipient == self:
            await self.cancel_challenge()
            await pm.author.challenge('', 'gen8randombattle')

    async def on_challenge_update(self, challenge_data):
        incoming = challenge_data.get('challengesFrom', {})
        for user, tier in incoming.items():
            if 'random' in tier:
                await self.accept_challenge(user, 'null')
            if 'gen7monotype' in tier:
                await self.accept_challenge(user, ghost_team)

    async def on_room_init(self, room_obj):
        if room_obj.id.startswith('battle-'):
            await asyncio.sleep(3)
            await room_obj.say('Oh my, look at the time! Gotta go, gg.')
            await room_obj.forfeit()
            await room_obj.leave()

ChallengeClient(name=username, password=password).start()
