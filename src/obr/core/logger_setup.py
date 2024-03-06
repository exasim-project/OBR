import logging
import logging.config

logger = logging.getLogger("OBR")


SUCCESS_LEVELV_NUM = 25
logging.addLevelName(SUCCESS_LEVELV_NUM, "SUCCESS")


def success(self, message, *args, **kws):
    # Yes, logger takes its '*args' as 'args'.
    self._log(SUCCESS_LEVELV_NUM, message, args, **kws)


logging.Logger.success = success


def setup_logging(log_fold=""):
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    log_fold = log_fold + "/" if log_fold else log_fold

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
                "filename": f"{log_fold}.obr/obr.log",
                "maxBytes": 10000,
                "backupCount": 3,
            },
        },
        "loggers": {
            "OBR": {"level": "INFO", "handlers": ["stdout_simple", "file_detailed"]}
        },
    }

    logging.config.dictConfig(config=config_dict)
