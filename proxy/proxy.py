#!/usr/local/bin/python3

import sys
import types
import signal

from .server import ProxyServer
from .tcp_server import TcpServer

server = None

def signal_handler(signal_num, frame):
    print('receive signal:', signal_num)
    server.close()
    sys.exit(0)


signal.signal(signal.SIGHUP, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGABRT, signal_handler)




def run():
    global server
    server = TcpServer('127.0.0.1', 8899)
    server.run_forever()

