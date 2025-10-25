import json, logging, sys, os, time

def setup_logging(level: str = "INFO"):
    lvl = getattr(logging, level.upper(), logging.INFO)
    logger = logging.getLogger("cathedral")
    logger.setLevel(lvl)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(lvl)
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    logger.handlers = [handler]
    logger.propagate = False
    return logger

def jlog(logger, **kv):
    try:
        kv.setdefault("ts", time.time())
        logger.info(json.dumps(kv, separators=(',',':')))
    except Exception as e:
        # Never raise from logging
        print(f'{{"level":"ERROR","msg":"log_failure","error":"{e}"}}')
