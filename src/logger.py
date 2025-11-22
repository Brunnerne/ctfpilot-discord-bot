import logging
import sys

class Logger:
    def __init__(self, verbose: bool, debug: bool = False):
        self.logger = logging.getLogger("discord_manager")
        self.logger.propagate = True
        # Remove all handlers associated with the logger object
        if self.logger.hasHandlers():
            self.logger.handlers.clear()
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        if debug:
            self.logger.setLevel(logging.DEBUG)
            self.logger.debug('Debug logging enabled')
        elif verbose:
            self.logger.setLevel(logging.INFO)
            self.logger.info('Verbose logging enabled')
        else:
            self.logger.setLevel(logging.WARNING)

    def write(self, msg: str):
        self.logger.log(logging.INFO, msg)

    def log(self, msg: str):
        self.logger.info(msg)

    def debug(self, msg: str):
        self.logger.debug(msg)

    def info(self, msg: str):
        self.logger.info(msg)

    def error(self, msg: str):
        self.logger.error(msg)

    def warning(self, msg: str):
        self.logger.warning(msg)