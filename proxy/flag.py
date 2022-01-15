"""
    flag.py: A flag class to store the command line options
"""

import argparse


class FlagParser:

    def __init__(self):
        self.parser = argparse.ArgumentParser()

    def add_argument(self, *args, **kwargs):
        self.parser.add_argument(*args, **kwargs)

    def parse_args(self):
        self.args = self.parser.parse_args()
        return self.args


flags = FlagParser()
