"""
    worker.py: A worker class to handle client events
"""

from collections import deque
import threading
import logging
import ssl

from .connection import TcpConnection
from .events import EventManager
from .constants import EVENT_READ, EVENT_WRITE
from .http_handler import HttpProxyHandler

logger = logging.getLogger(__name__)


class Worker:
    def __init__(self, work_queue: deque, lock: threading.Lock):
        self.work_queue = work_queue
        self.event_manager = EventManager()
        self.handlers = {}
        self.lock = lock

    def check_for_new_works(self):
        with self.lock:
            if len(self.work_queue) <= 0:
                return
            conn: TcpConnection = self.work_queue.popleft()
            handler = None
            if conn.tag == "client":
                handler = HttpProxyHandler(conn, self.work_queue, self.lock)
                self.handlers[handler.id] = handler
            elif conn.tag == "upstream":
                handler = self.handlers.get(conn.handler_id)
            logger.info('Receive a new %s work, fileno %d',
                        conn.tag, conn.fileno())
            if handler:
                self.event_manager.set_event(conn, EVENT_READ, data=handler)

    def clear_works(self):
        hids = []
        for handler in self.handlers.values():
            handler: HttpProxyHandler
            if handler.client.is_closed() and \
                    handler.client.selected_event != 0:
                self.event_manager.unregister(handler.client)
            if (
                handler.upstream
                and handler.upstream.is_closed()
                and handler.upstream.selected_event != 0
            ):
                self.event_manager.unregister(handler.upstream)
            if (
                handler.client.is_closed()
                and handler.upstream
                and handler.upstream.is_closed()
            ):
                hids.append(handler.id)
        for hid in hids:
            self.handlers.pop(hid)
            logger.info('Delete handler %s', hid)

    def get_events(self):
        events = []
        for handler in self.handlers.values():
            if not handler.client.is_closed():
                event = 0 if handler.client.is_read_closed() else EVENT_READ
                if handler.client.has_buffer():
                    event |= EVENT_WRITE
                events.append((handler.client, event, handler))
            if handler.upstream and not handler.upstream.is_closed():
                event = 0 if handler.upstream.is_read_closed() else EVENT_READ
                if handler.upstream.has_buffer():
                    event |= EVENT_WRITE
                events.append((handler.upstream, event, handler))
        return events

    def update_events(self, events):
        for conn, event, handler in events:
            self.event_manager.set_event(conn, event, handler)

    def check_pending_works(self):
        events = self.event_manager.select_events()
        works = {}
        for key, mask in events:
            handler = key.data
            works.setdefault(handler.id, (handler, [], []))
            if mask & EVENT_READ:
                works[handler.id][1].append(key.fileobj)
            if mask & EVENT_WRITE:
                works[handler.id][2].append(key.fileobj)
        return works

    def handle_works(self, works: dict):
        for handler, readables, writables in works.values():
            handler: HttpProxyHandler
            for fo in readables:
                try:
                    handler.read_from_fd(fo.fileno())
                except (ssl.SSLWantReadError, BlockingIOError):
                    pass
            for fo in writables:
                try:
                    handler.write_to_fd(fo.fileno())
                except (ssl.SSLWantWriteError, BlockingIOError):
                    pass

    def run_forever(self):
        try:
            while True:
                self.clear_works()
                self.check_for_new_works()
                events = self.get_events()
                self.update_events(events)
                works = self.check_pending_works()
                self.handle_works(works)
        except KeyboardInterrupt:
            pass
        finally:
            for handler in self.handlers.values():
                self.event_manager.unregister(handler.client)
                if not handler.client.is_closed():
                    handler.client.close()
                if handler.upstream:
                    self.event_manager.unregister(handler.upstream)
                    if not handler.upstream.is_closed():
                        handler.upstream.close()

