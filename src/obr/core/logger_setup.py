import logging

# class CustomFormatter(logging.Formatter):
#
#     # log formating stuff
#     grey = "\x1b[38;20m"
#     yellow = "\x1b[33;20m"
#     red = "\x1b[31;20m"
#     bold_red = "\x1b[31;1m"
#     reset = "\x1b[0m"
#     format="%(message)-150s [OBR %(levelname)s, %(filename)s:%(lineno)d]"
#
#     FORMATS = {
#         logging.DEBUG: grey + format + reset,
#         logging.INFO: grey + format + reset,
#         logging.WARNING: yellow + format + reset,
#         logging.ERROR: red + format + reset,
#         logging.CRITICAL: bold_red + format + reset
#     }
#
#     def format(self, record):
#         log_fmt = self.FORMATS.get(record.levelno)
#         formatter = logging.Formatter(log_fmt)
#         return formatter.format(record)


def setup_logging():
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    config_dict = {
        "version": 1,
        "disable_existing_loggers": True,
        "formatters": {
            "colored_console": {
                "()": "coloredlogs.ColoredFormatter",
                "format": " %(name)s: %(message)s",
                "datefmt": "%H:%M:%S",
            },
            "detailed": {
                "format": (
                    "[OBR] %(message)-150s [OBR %(levelname)s, %(filename)s:%(lineno)d]"
                )
            },
        },
        "handlers": {
            "stdout_simple": {
                "level": "INFO",
                "class": "logging.StreamHandler",
                "formatter": "colored_console",
                "stream": "ext://sys.stdout",
            },
            "file_detailed": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "detailed",
                "filename": ".obr/obr.log",
                "maxBytes": 10000,
                "backupCount": 3,
            },
        },
        "loggers": {
            "OBR": {"level": "INFO", "handlers": ["stdout_simple", "file_detailed"]}
        },
    }

    logging.config.dictConfig(config=config_dict)
