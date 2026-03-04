import logging
import colorlog
from logging.handlers import TimedRotatingFileHandler


def setup_logger():


    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    file_handler = TimedRotatingFileHandler('logs/log.txt', 'midnight', 1, 7, 'utf8')
    file_handler.setLevel(logging.ERROR)
    file_format = logging.Formatter("%(levelname)s——%(asctime)s  %(message)s  %(lineno)d", '%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(file_format)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = colorlog.ColoredFormatter('%(log_color)s%(levelname)s——%(asctime)s  %(message)s',
                                               datefmt='%Y-%m-%d %H:%M:%S',
                                               log_colors={'INFO': 'green',
                                                           'WARNING': 'yellow',
                                                           'ERROR': 'red',
                                                           }
                                               )

    console_handler.setFormatter(console_format)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# 创建全局日志管理器
log = setup_logger()
