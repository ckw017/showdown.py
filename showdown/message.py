# -*- coding: utf-8 -*-
"""Module for showdown's ChatMessage and PrivateMessage classes"""
import time
import math
from . import user, utils

class ChatMessage:
    """
    Class representing a chat message in a showdown chat room.

    Args:
        room_id (obj:`str`) : The ID of the room in which the message was sent
        timestamp (obj:`int` or None) : The timestamp when the message was sent
        author_str (obj:`str`) : A string representing the name and rank of the
            author
        content (obj:`str`) : A string representing the content of the message
        client (obj:`showdown.client.Client`, optional) : The Client to be used
            for the objects reply method

        Attributes:
            room_id (obj:`str`) : The ID of the room in which the message was
                sent
            timestamp (obj:`int` or None) : The timestamp when the message was
                sent
            author_str (obj:`str`) : A string representing the name and rank of
                the author
            content (obj:`str`) : A string representing the content of the 
                message
            client (obj:`showdown.client.Client` or None) : The Client to be
                used for the objects reply method
    """
    def __init__(self, room_id, timestamp, author_str, content, client=None):
        self.room_id = room_id
        self.timestamp = timestamp
        self.author = user.User(author_str, client=client)
        self.content = content
        self.client = client

    def __repr__(self):
        return '<ChatMessage ({}) [{}] {}: {}>'.format(
                 self.room_id, 
                 utils.timestamp_to_hh_mm_ss(self.timestamp), 
                 str(self.author),
                 utils.abbreviate(self.content)
               )

    def __str__(self):
        return '({}) [{}] {}: {}'.format(
                self.room_id,
                utils.timestamp_to_hh_mm_ss(self.timestamp), 
                str(self.author),
                self.content
            )

    @utils.require_client
    async def reply(self, content, client=None, delay=0, lifespan=math.inf):
        """
        Uses the provided client or the object's client attribute to send a
        message to the message's room of origin.

        Args:
            room_id (obj:`str`) : The content of the reply
            client (obj:`showdown.client.Client`, optional) : The client used
                to reply to the message. This will default to the message's 
                client object
        """
        await client.say(self.room_id, content, delay=delay, lifespan=lifespan)

class PrivateMessage:
    """
    Class representing a private message from another user.

    Args:
        author_str (obj:`str`) : A string representing the name and rank of the
            author
        recipient_str (obj:`str`) : A string representing the name and rank of 
            the recipient
    """
    def __init__(self, author_str, recipient_str, content, client=None):
        self.timestamp = int(time.time())
        self.author = user.User(author_str, client=client)
        self.recipient = user.User(recipient_str, client=client)
        self.content = content
        self.client = client

    def __repr__(self):
        return '<PrivateMessage ({}->{}) [{}]: {}>'.format(
               str(self.author), 
               str(self.recipient),
               utils.timestamp_to_hh_mm_ss(self.timestamp), 
               utils.abbreviate(self.content))

    def __str__(self):
        return '(private message) [{}] {}: {}'.format(
                utils.timestamp_to_hh_mm_ss(self.timestamp), 
                str(self.author),
                self.content
            )

    @utils.require_client
    async def reply(self, content, client=None, delay=0, lifespan=math.inf):
        """
        Uses the provided client or the object's client attribute to send a
        message to the message's room of origin.

        Args:
            room_id (obj:`str`) : The content of the reply
            client (obj:`showdown.client.Client`, optional) : The client used to 
                reply to the message. This will default to the message's client
                object
        """
        await client.private_message(self.author.id, content, delay=delay, lifespan=math.inf)