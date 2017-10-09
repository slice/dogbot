import logging
import sys


def setup_logging():
    # configure logging, and set the root logger's info to INFO
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # formatters
    console_fmt = logging.Formatter('[{asctime}] [{levelname: <7}] {name}: {message}', '%I:%M:%S %p', style='{')
    nice_fmt = logging.Formatter('%(asctime)s [%(name)s %(levelname)s] %(message)s', '%m/%d/%Y %I:%M:%S %p')

    # enable debug logging for us, but not for discord
    logging.getLogger('discord').setLevel(logging.INFO)
    logging.getLogger('dog').setLevel(logging.DEBUG)

    # main file handler, only info
    file_handler = logging.FileHandler(filename='dog.log', encoding='utf-8')
    file_handler.setFormatter(nice_fmt)

    # stream handler (stdout)
    stream = logging.StreamHandler(stream=sys.stdout)
    stream.setFormatter(console_fmt)

    # handle from all logs
    root_logger.addHandler(stream)
    root_logger.addHandler(file_handler)

