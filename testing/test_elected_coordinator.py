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

class TestElectedCoordinator(unittest.TestCase):
    def setUp(self):
        x.setUp(num_nodes = 4)
        x.createTestValue()

    def tearDown(self):
        x.tearDown()

    @timeout(ten_minutes)
    def test_down_can_still_read(self):
        value = x.rc_client.read(x.table, 'testKey')
        expect(value).equals(('testValue', 1))

        # find the host corresponding to the elected coordinator, kill its rc-coordinator!
        # we should still be able to get the testKey.
        zk_client = ctu.get_zookeeper_client(x.ensemble)
        locator =  zk_client.get('/ramcloud/main/coordinator')[0]
        host = ctu.get_host(locator)
        x.node_containers[host].exec_run('killall -SIGKILL rc-coordinator')

        # after the coordinator is down, we try to read. We expect
        # to see our value.
        value = x.rc_client.read(x.table, 'testKey')
        time.sleep(3)  # 3 seconds is needed for a new coordinator to be elected & results to show in zk
        new_locator =  zk_client.get('/ramcloud/main/coordinator')[0]

        expect(value).equals(('testValue', 1))
        expect(new_locator).not_equals(None)
        expect(new_locator).not_equals(locator)

if __name__ == '__main__':
    unittest.main()
