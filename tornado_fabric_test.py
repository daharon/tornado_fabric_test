#!/usr/bin/env python

import sys
from cStringIO import StringIO
from threading import Thread
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


class RunFabricTaskInSeparateThread(web.RequestHandler):
    fabric_task_output = None
    fabric_task = None
    periodic_callback = None

    @web.asynchronous
    def get(self):
        cls = RunFabricTaskInSeparateThread

        logger.debug('Fabric Task:  ' + str(cls.fabric_task))

        if cls.fabric_task is None:
            cls.fabric_task_output = StringIO()
            cls.fabric_task = Thread(
                target=run_fabric_task,
                args=(FabricTest, cls.fabric_task_output)
            )
            logger.debug('Task is alive?  ' + str(cls.fabric_task.is_alive()))
            cls.fabric_task.start()
            self.write("Started task...<br>")

            cls.periodic_callback = ioloop.PeriodicCallback(self._on_output, 100)
            cls.periodic_callback.start()
        else:
            self.write("Task currently running...<br>")


    def _on_output(self):
        cls = RunFabricTaskInSeparateThread

        if not cls.fabric_task.is_alive():
            cls.periodic_callback.stop()
            output = cls.fabric_task_output.getvalue()
            cls.fabric_task = None
            self.finish('<br>'.join(output.splitlines()))
        else:
            output = cls.fabric_task_output.readline()
            self.write(output.replace("\n", '<br>'))
            self.flush()


def run_fabric_task(fabric_task, output_stream):
    sys.stdout = output_stream
    with settings(host_string='10.1.1.194', user='deploy', password='GwyDeGZqsX'):
        fabric_task().run()
    sys.stdout = sys.__stdout__


application = web.Application( [
    (r"/", Dummy),
    (r"/run_fabric_task_in_separate_thread", RunFabricTaskInSeparateThread)
] )


if __name__ == '__main__':
    application.listen(8888)
    ioloop.IOLoop.instance().start()
