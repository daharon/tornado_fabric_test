#!/usr/bin/env python

import sys
from cStringIO import StringIO
from threading import Thread
from multiprocessing import Process
import logging

from fabric.tasks import Task
from fabric.api import cd, run, local, settings
from tornado import ioloop, web


logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format='%(asctime)s %(name)-12s %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FabricTest(Task):
    def run(self):
        with cd('/tmp'):
            local("echo \"This is done locally.\"")
            run("echo \"This is done remotely.\"")
            run("ls -lht | head && sleep 10")
            run("echo \"Slept for 10 seconds... was Tornado responsive?\"")
            run("touch tornado.txt")


class Dummy(web.RequestHandler):
    def get(self):
        self.write("This is a dummy handler!")


class IsTaskRunning(web.RequestHandler):
    def get(self):
        cls = RunFabricTaskInSeparateThread
        self.write("Task Running:  %s<br>" % str(cls.fabric_task_running))


class RunFabricTaskInSeparateThread(web.RequestHandler):
    fabric_task_running = False
    _fabric_task_output = None
    _fabric_task = None
    _periodic_callback = None


    def prepare(self):
        output = "Task currently running:  %s<br>" % str(RunFabricTaskInSeparateThread.fabric_task_running)

        if RunFabricTaskInSeparateThread.fabric_task_running:
            self.finish(output)
        else:
            self.write(output)
            self.flush()


    @web.asynchronous
    def get(self):
        cls = RunFabricTaskInSeparateThread

        cls.fabric_task_running = True
        cls._fabric_task_output = StringIO()
        cls._fabric_task = Thread(
            target=run_fabric_task,
            args=(FabricTest, cls._fabric_task_output, self._task_done)
        )
        cls._fabric_task.start()
        self.write("Started task...<br>")
        self.flush()

        cls._periodic_callback = ioloop.PeriodicCallback(self._on_output, 100)
        cls._periodic_callback.start()


    def _on_output(self):
        cls = RunFabricTaskInSeparateThread

        if cls._fabric_task is not None and cls._fabric_task.is_alive():
            output = cls._fabric_task_output.read()
            self.write(output.replace("\n", '<br>'))
            self.flush()


    def _task_done(self):
        cls = RunFabricTaskInSeparateThread

        cls.fabric_task_running = False
        cls._fabric_task = None
        cls._periodic_callback.stop()
        output = cls._fabric_task_output.getvalue()
        self.finish('<br>'.join(output.splitlines()))


def run_fabric_task(fabric_task, output_stream, done_callback):
    sys.stdout = output_stream
    with settings(host_string='10.1.1.194', user='deploy', password='GwyDeGZqsX'):
        fabric_task().run()
    sys.stdout = sys.__stdout__
    ioloop.IOLoop.instance().add_callback(done_callback)


application = web.Application( [
    (r"/", Dummy),
    (r"/task_running", IsTaskRunning),
    (r"/run_fabric_task_in_separate_thread", RunFabricTaskInSeparateThread)
] )


if __name__ == '__main__':
    application.listen(8888)
    ioloop.IOLoop.instance().start()
