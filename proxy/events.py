"""
    events.py: events manager
"""

import selectors

from .connection import TcpConnection
from .constants import DEFAULT_SELECTOR_SELECT_TIMEOUT


class EventManager:

    def __init__(self):
        self.selector = selectors.SelectSelector()

    def set_event(self, conn, event, data):
        if conn.selected_event == 0:
            self.selector.register(conn.sock, event, data)
        else:
            self.selector.modify(conn.sock, event, data)
        conn.selected_event = event

    def add_event(self, conn: TcpConnection, event, data):
        if conn.selected_event == 0:
            conn.selected_event = event
            self.selector.register(conn.sock, conn.selected_event, data)
        else:
            conn.selected_event |= event
            self.selector.modify(conn.sock, conn.selected_event, data)

    def remove_event(self, conn: TcpConnection, event, data):
        conn.selected_event &= (~event)
        if conn.selected_event == 0:
            self.selector.unregister(conn.sock)
        else:
            self.selector.modify(conn.sock, conn.selected_event, data)

    def unregister(self, conn: TcpConnection):
        if conn.selected_event != 0:
            self.selector.unregister(conn.sock)
            conn.selected_event = 0

    def select_events(self):
        events = self.selector.select(timeout=DEFAULT_SELECTOR_SELECT_TIMEOUT)
        return events

