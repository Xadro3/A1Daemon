from http.client import HTTPConnection
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import Mock

from a1daemon.server import Application, make_handler


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.hardware = Mock()
        self.hardware.snapshot.return_value = {'writes_enabled':False}
        self.server = ThreadingHTTPServer(('127.0.0.1',0),make_handler(Application(self.hardware,'test-token')))
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, method, path, body=None, headers=None):
        client = HTTPConnection('127.0.0.1',self.server.server_port)
        client.request(method,path,body,headers or {})
        response=client.getresponse()
        status,data=response.status,response.read()
        client.close()
        return status,data

    def test_unauthenticated_api_is_rejected(self):
        self.assertEqual(self.request('GET','/api/state')[0],401)
        self.assertEqual(self.request('POST','/api/power','{}',{'Content-Type':'application/json'})[0],403)
        self.hardware.set_power.assert_not_called()

    def test_authorized_state_and_static_panel(self):
        self.assertEqual(self.request('GET','/api/state',headers={'Authorization':'Bearer test-token'})[0],200)
        self.assertIn(b'Claw control',self.request('GET','/')[1])

    def test_dns_rebinding_host_is_rejected(self):
        self.assertEqual(self.request('GET','/api/state',headers={'Host':'untrusted.example','Authorization':'Bearer test-token'})[0],403)

    def test_cross_site_form_cannot_change_power(self):
        self.assertEqual(self.request('POST','/api/power','{}',{'Authorization':'Bearer test-token','Content-Type':'text/plain'})[0],415)
        self.hardware.set_power.assert_not_called()

    def test_invalid_payload_is_rejected(self):
        for body in ['[]','{bad']:
            self.assertEqual(self.request('POST','/api/power',body,{'Authorization':'Bearer test-token','Content-Type':'application/json'})[0],400)


if __name__ == '__main__': unittest.main()
