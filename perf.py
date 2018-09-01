from io import StringIO as cio
import logging, structlog as sl
from threading import Lock
import time

# log setup:
log = logging.getLogger()
handler = logging.StreamHandler(cio())
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
log.addHandler(handler)
log.setLevel(10)

# structlog setup. lets creeate the (threadsafe) Memory logger:
class Str:
    def info(msg, stream=cio(), lock=Lock()):
        with lock:
            stream.write(msg)
            stream.flush()
slog = sl.wrap_logger(Str, [lambda _, __, ev: '%(event)s' % ev])

for m in slog.info, log.info:
    print('structlog:' if m == slog.info else 'stdlib log')
    t1 = time.time()
    for i in range(100000):
        m('info_msg')
    print(time.time() - t1)

