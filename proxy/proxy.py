#!/usr/local/bin/python3

import sys
import types

from .server import ProxyServer


def parse_arguments():
    port = int(sys.argv[1])
    conf = types.SimpleNamespace(port=port)
    return conf


def run():
    conf = parse_arguments()
    server = ProxyServer(conf)
    server.forever_run()

