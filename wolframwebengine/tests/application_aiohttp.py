from __future__ import absolute_import, print_function, unicode_literals

import re

from aiohttp import web
from aiohttp.formdata import FormData
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from wolframclient.language import wl
from wolframclient.utils.functional import first
from wolframclient.utils.importutils import module_path
from wolframwebengine.server.app import create_session, create_view
from wolframwebengine.web import aiohttp_wl_view


class MyAppTestCase(AioHTTPTestCase):
    async def get_application(self):

        self.session = create_session(poolsize=1)
        routes = web.RouteTableDef()

        @routes.get('/')
        async def hello(request):
            return web.Response(text="Hello from aiohttp")

        @routes.get('/form')
        @routes.post('/form')
        @aiohttp_wl_view(self.session)
        async def form_view(request):
            return wl.FormFunction({"x": "String"}, wl.Identity, "JSON")

        @routes.get('/api')
        @routes.post('/api')
        @aiohttp_wl_view(self.session)
        async def api_view(request):
            return wl.APIFunction({"x": "String"}, wl.Identity, "JSON")

        path = module_path('wolframwebengine.tests', 'sampleapp')

        for cached in (True, False):

            root = cached and '/cached' or '/app'
            view = create_view(
                session=self.session,
                path=path,
                cached=cached,
                root=root,
                index='index.m')

            routes.get(root + '{name:.*}')(view)
            routes.post(root + '{name:.*}')(view)

        app = web.Application()
        app.add_routes(routes)

        return app

    @unittest_run_loop
    async def test_aiohttp(self):

        for cached in (True, False):

            root = cached and '/cached' or '/app'

            for loc, content in (
                ('', '"Hello from / in a folder!"'),
                ('/', '"Hello from / in a folder!"'),
                ('/index.m', '"Hello from / in a folder!"'),
                ('/foo', '"Hello from foo"'),
                ('/foo/', '"Hello from foo"'),
                ('/foo/index.m', '"Hello from foo"'),
                ('/foo/bar', '"Hello from foo/bar"'),
                ('/foo/bar', '"Hello from foo/bar"'),
                ('/foo/bar/index.m', '"Hello from foo/bar"'),
                ('/foo/bar/something.m', '"Hello from foo/bar/something"'),
            ):
                resp = await self.client.request("GET", root + loc)
                self.assertEqual(resp.status, 200)
                self.assertEqual(await resp.text(), content)

            for loc in ('/some-random-url', '/404', '/some-/nonsense'):
                resp = await self.client.request("GET", root + loc)
                self.assertEqual(resp.status, 404)

            resp1 = await self.client.request("GET", root + "/random.m")
            resp2 = await self.client.request("GET", root + "/random.m")

            self.assertTrue(re.match("[0-1].[0-9]+", await resp1.text()))
            (cached and self.assertEqual
             or self.assertNotEqual)(await resp1.text(), await resp2.text())

            resp = await self.client.request("GET", root + "/some.json")

            self.assertEqual(resp.status, 200)
            self.assertEqual(await resp.json(), [1, 2, 3])
            self.assertEqual(resp.headers['Content-Type'], 'application/json')

            for fmt in ('wxf', 'mx'):

                resp = await self.client.request("GET", root + 'some.' + fmt)

                self.assertEqual(resp.status, 200)
                self.assertEqual(len(await resp.json()), 4)
                self.assertEqual(
                    (await resp.json())[0:3],
                    ["hello", "from", fmt.upper()])
                self.assertEqual(resp.headers['Content-Type'],
                                 'application/json')

        resp = await self.client.request("GET", "/")

        self.assertEqual(resp.status, 200)
        self.assertEqual(await resp.text(), "Hello from aiohttp")

        resp = await self.client.request("GET", "/api")

        self.assertEqual(resp.status, 400)
        self.assertEqual((await resp.json())["Success"], False)
        self.assertEqual(resp.headers['Content-Type'], 'application/json')

        resp = await self.client.request("GET", "/api?x=a")

        self.assertEqual(resp.status, 200)
        self.assertEqual((await resp.json())["x"], "a")
        self.assertEqual(resp.headers['Content-Type'], 'application/json')

        resp = await self.client.request("GET", "/form")

        self.assertEqual(resp.status, 200)
        self.assertEqual(
            first(resp.headers['Content-Type'].split(';')), 'text/html')

        resp = await self.client.request("POST", "/form", data={'x': "foobar"})

        self.assertEqual(resp.status, 200)
        self.assertEqual((await resp.json())["x"], "foobar")
        self.assertEqual(resp.headers['Content-Type'], 'application/json')

        data = FormData()
        data.add_field('x', b'foobar', filename='somefile.txt')

        resp = await self.client.request("POST", "/form", data=data)

        self.assertEqual(resp.status, 200)
        self.assertEqual((await resp.json())["x"], "foobar")
        self.assertEqual(resp.headers['Content-Type'], 'application/json')

    def tearDown(self):
        if self.session.started:
            self.loop.run_until_complete(self.session.stop())
        super().tearDown()
