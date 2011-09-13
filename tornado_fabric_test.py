#!/usr/bin/env python

import sys
import logging
from threading import Thread

import fabric.tasks
from fabric.api import cd, run, local, settings
from tornado import ioloop, web


host = '10.1.1.194'
user = 'deploy'
password = 'password'

logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format='%(asctime)s %(name)-12s %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FabricTest(fabric.tasks.Task):
    def run(self):
        with cd('/tmp'):
            local("echo \"This is done locally.\"")
            run("echo \"This is done remotely.\"")
            run("ls -lht | head && sleep 10")
            run("echo \"Slept for 10 seconds... was Tornado responsive?\"")
            run("touch tornado.txt")


class TaskStatus(object):
    """ Singleton that holds the status info for running tasks. """
    __instance = None
    MAX_SIZE = 2048        # Bytes

    def __new__(cls, *args, **kwargs):
        if not cls.__instance:
            cls.__instance = super(TaskStatus, cls).__new__(cls, *args, **kwargs)
            cls.__instance.fabric_task_running = False
            cls.__instance.fabric_task_output = FabricOutput([ 'Empty' ])
            cls.__instance.fabric_task = None

            # Make sure the cache doesn't get too big.
            cls.__instance._periodic_callback = ioloop.PeriodicCallback(
                cls.__instance._check_max_size,
                1000 * 60 * 30          # Check every 30 minutes.
            )
            cls.__instance._periodic_callback.start()

        return cls.__instance

    def __del__(self):
        self._periodic_callback.stop()

    def _check_max_size(self):
        logger.debug('Checking status cache max size.')
        logger.debug(
            "Removed %d lines from the output cache." %
            self.fabric_task_output.set_max_size(self.MAX_SIZE)
        )


class FabricOutput(object):
    """ Copy the behaviour of a File Object. """
    def __init__(self, initial=[]):
        self._contents = initial

    def __nonzero__(self):
        return bool(self._contents)

    def write(self, obj):
        self._contents.append(obj)

    def getvalue(self, sep=''):
        return sep.join(self._contents)

    def read(self, start=0):
        return ( len(self._contents), ''.join(self._contents[start:]) )

    def flush(self):
        pass

    def isatty(self):
        return False

    def set_max_size(self, bytes=1048576):
        remove_x_lines = 0
        cache_size = 0
        for entry in self._contents:
            cache_size += len(entry)

        if cache_size > bytes:
            avg_entry_len = cache_size / len(self._contents)
            remove_x_lines = int((cache_size - bytes) / avg_entry_len)
            self._contents = self._contents[remove_x_lines:]

        return remove_x_lines


class WatchFabricTaskRun(web.RequestHandler):
    def initialize(self):
        self._cursor = 0
        self._periodic_callback = ioloop.PeriodicCallback(self._check_output, 500)


    def on_connection_close(self):
        self._periodic_callback.stop()


    @web.asynchronous
    def get(self):
        self.write('Task output:<br>')
        self.flush()
        self._periodic_callback.start()


    def _check_output(self):
        self._cursor, output = TaskStatus().fabric_task_output.read(self._cursor)
        self.write(output.replace("\n", '<br>'))
        self.flush()


class RunFabricTask(web.RequestHandler):
    def prepare(self):
        if TaskStatus().fabric_task_running:
            self.finish()


    def get(self):
        ts = TaskStatus()

        ts.fabric_task_running = True
        ts.fabric_task_output = FabricOutput()
        ts.fabric_task = Thread(
            target=_run_fabric_task,
            args=(FabricTest, ts.fabric_task_output, _task_done)
        )
        ts.fabric_task.start()
        self.write("Started task...<br>")
        self.flush()


def _task_done():
    ts = TaskStatus()

    ts.fabric_task_running = False
    ts.fabric_task = None


def _run_fabric_task(fabric_task, output_stream, done_callback):
    sys.stdout = output_stream
    with settings(host_string=host, user=user, password=password):
        fabric_task().run()
    sys.stdout = sys.__stdout__
    ioloop.IOLoop.instance().add_callback(done_callback)


application = web.Application( [
    (r"/watch", WatchFabricTaskRun),
    (r"/run", RunFabricTask)
] )


if __name__ == '__main__':
    application.listen(8888)
    ioloop.IOLoop.instance().start()
