# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function, unicode_literals

from aiohttp import web

from wolframclient.cli.utils import SimpleCommand
from wolframclient.utils.api import asyncio
from wolframwebengine.server.app import create_session, create_view


class Command(SimpleCommand):
    """ Run test suites from the tests modules.
    A list of patterns can be provided to specify the tests to run.
    """

    ServerRunner = web.ServerRunner
    Server = web.Server
    TCPSite = web.TCPSite

    def add_arguments(self, parser):
        parser.add_argument("path", default=".", nargs="?")
        parser.add_argument("--port", default=18000, help="Insert the port.")
        parser.add_argument("--domain", default="localhost", help="Insert the domain.")
        parser.add_argument("--kernel", default=None, help="Insert the kernel path.")
        parser.add_argument(
            "--poolsize", default=1, help="Insert the kernel pool size.", type=int
        )
        parser.add_argument(
            "--cached",
            default=False,
            help="The server will cache the WL input expression.",
            action="store_true",
        )
        parser.add_argument(
            "--lazy",
            default=False,
            help="The server will start the kernels on the first request.",
            action="store_true",
        )
        parser.add_argument(
            "--index", default="index.m", help="The file name to search for folder index."
        )

    def handle(self, domain, port, path, kernel, poolsize, lazy, cached, **opts):

        session = create_session(kernel, poolsize=poolsize)
        view = create_view(session, path, cached=cached, **opts)

        async def main():

            self.print("======= Serving on http://%s:%s/ ======" % (domain, port))

            runner = self.ServerRunner(self.Server(view))
            await runner.setup()
            await self.TCPSite(runner, domain, port).start()

            if not lazy:
                await session.start()

            while True:
                await asyncio.sleep(3600)

        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(main())
        except KeyboardInterrupt:
            self.print("Requested server shutdown, closing session...")
            loop.run_until_complete(session.stop())

        loop.close()
