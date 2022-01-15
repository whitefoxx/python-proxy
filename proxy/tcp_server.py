"""
    tcp_server.py: A basic tcp server.
"""

from typing import Optional
import logging
import socket
import selectors
from collections import deque
import threading

from .connection import TcpConnection
from .worker import Worker


logger = logging.getLogger(__name__)


class TcpServer:

    def __init__(self, addr, port):
        self.addr = addr
        self.port = port
        self.work_queue = deque()
        self.lock = threading.Lock()
        self.local_worker = Worker(self.work_queue, self.lock)
        self.local_thread: Optional[threading.Thread] = None
        self.selector = selectors.DefaultSelector()
        self.setup()

    def setup(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((self.addr, self.port))
        self.sock.listen()
        self.sock.setblocking(False)
        self.selector.register(self.sock, selectors.EVENT_READ, data=None)
        logger.info('Start server at %s, port %d', self.addr, self.port)

    def accept_new_client(self):
        sock, addr = self.sock.accept()
        logger.info('Accept new connection %s, fileno %d', addr, sock.fileno())
        sock.setblocking(False)
        conn = TcpConnection(sock, addr)
        with self.lock:
            self.work_queue.append(conn)

    def start_local_worker(self):
        self.local_thread = threading.Thread(
            target=self.local_worker.run_forever)
        self.local_thread.daemon = True
        self.local_thread.start()

    def run_forever(self):
        try:
            while True:
                events = self.selector.select()
                for key, _ in events:
                    if key.data is None:
                        self.accept_new_client()
        except KeyboardInterrupt:
            pass
        finally:
            self.selector.unregister(self.sock)
            self.sock.close()

    def run(self):
        self.start_local_worker()
        self.run_forever()
