#!/usr/bin/env python

import sys
import argparse

from .tcp_server import TcpServer
from .logger import Logger
from .flag import flags


flags.add_argument(
        "-p",
        "--port",
        default=8899,
        type=int,
        help="the port to which the server bind")

flags.add_argument(
        "-m",
        "--man-in-the-middle",
        action="store_true",
        help="man in the middle interception")


if __name__ == '__main__':
    args: argparse.Namespace = flags.parse_args()
    Logger.setup(add_console_logger=True)
    server = TcpServer('127.0.0.1', args.port)
    server.run()

