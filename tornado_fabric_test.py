#!/usr/bin/env python

import sys
from cStringIO import StringIO
from threading import Thread
from multiprocessing import Process

from fabric.tasks import Task
from fabric.api import run, local, settings
from tornado import ioloop, web


async_task_output = None


class FabricTest(Task):
    def run(self):
        local("echo \"This is done locally.\"")
        run("echo \"This is done remotely.\"")
        run("ls -lht /tmp | head && sleep 10")
        run("echo \"Slept for 10 seconds... was Tornado responsive?\"")


class RunFabricTaskInSeparateThread(web.RequestHandler):
    @web.asynchronous
    def get(self):
        async_task_output = StringIO()
        self.t = Thread(target=run_fabric_task, args=(async_task_output, ))
        self.t.start()
        self.write("Started thread...")
        self.t.join()
        self.write(async_task_output.getvalue())
        async_task_output = None


def run_fabric_task(output_stream):
    sys.stdout = output_stream
    with settings(
            host_string='10.1.1.194',
            user='deploy',
            password='GwyDeGZqsX'):
        FabricTest().run()
    sys.stdout = sys.__stdout__


application = web.Application( [
    (r"/", Dummy),
    (r"/run_fabric_task_in_separate_thread", RunFabricTaskInSeparateThread)
] )


if __name__ == '__main__':
    application.listen(8888)
    ioloop.IOLoop.instance().start()