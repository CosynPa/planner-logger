"""
Implementation from https://github.com/jupyter-widgets/ipywidgets/issues/1532#issuecomment-317515361
"""

import collections
import functools
import time


def get_ioloop():
    import IPython, zmq
    ipython = IPython.get_ipython()
    if ipython and hasattr(ipython, 'kernel'):
        return zmq.eventloop.ioloop.IOLoop.instance()


def debounced(delay_seconds=0.5, method=False):
    def wrapped(f):
        counters = collections.defaultdict(int)

        @functools.wraps(f)
        def execute(*args, **kwargs):
            if method: # if it is a method, we want to have a counter per instance
                key = args[0]
            else:
                key = None
            counters[key] += 1
            def debounced_execute(counter=counters[key]):
                if counter == counters[key]: # only execute if the counter wasn't changed in the meantime
                    f(*args, **kwargs)
            ioloop = get_ioloop()

            def thread_safe():
                ioloop.add_timeout(time.time() + delay_seconds, debounced_execute)

            ioloop.add_callback(thread_safe)
        return execute
    return wrapped
