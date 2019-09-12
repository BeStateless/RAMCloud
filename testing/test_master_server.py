import os
import ramcloud
import time
import Table_pb2
import unittest
from pyexpect import expect
from timeout_decorator import timeout
from cluster_test_utils import ten_minutes
import cluster_test_utils as ctu

x = ctu.ClusterTest()

class TestMasterServer(unittest.TestCase):
    def setUp(self):
        x.setUp(num_nodes = 4)
        x.createTestValue()

    def tearDown(self):
        x.tearDown()

    def simple_recovery(self, kill_command):
        value = x.rc_client.read(x.table, 'testKey')
        expect(value).equals(('testValue', 1))

        # find the host corresponding to the server with our table and 'testKey',
        # then kill its rc-server!
        locator =  x.rc_client.testing_get_service_locator(x.table, 'testKey')
        host = ctu.get_host(locator)
        x.node_containers[host].exec_run(kill_command)

        # read the value again (without waiting for the server to recover). It 
        # should come out to the same value
        value = x.rc_client.read(x.table, 'testKey')
        expect(value).equals(('testValue', 1))

    @timeout(ten_minutes)
    def test_graceful_down_can_still_read(self):
        self.simple_recovery(kill_command = 'killall -SIGTERM rc-server')

    @timeout(ten_minutes)
    def test_forced_down_can_still_read(self):
        self.simple_recovery(kill_command = 'killall -SIGKILL rc-server')

    @timeout(ten_minutes)
    def test_down_can_still_write(self):
        value = x.rc_client.read(x.table, 'testKey')
        expect(value).equals(('testValue', 1))

        # find the host corresponding to the server with our table and 'testKey',
        # then kill its rc-server!
        locator =  x.rc_client.testing_get_service_locator(x.table, 'testKey')
        host = ctu.get_host(locator)
        x.node_containers[host].exec_run('killall -SIGKILL rc-server')

        # after the master server is down, we try to write (not read). We expect
        # the read that follows to correctly contain our value.
        x.rc_client.write(x.table, 'testKey', 'testValue2')
        value = x.rc_client.read(x.table, 'testKey')
        expect(value).equals(('testValue2', 2))

if __name__ == '__main__':
    unittest.main()
