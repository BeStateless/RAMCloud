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

class TestBackupServer(unittest.TestCase):
    def setUp(self):
        x.setUp(num_nodes = 4)
        x.createTestValue()
        # NOTE: This has to be done after the first table is made. Otherwise, data isn't always present.
        x.buildServerIdMap()

    def tearDown(self):
        x.tearDown()

    @timeout(ten_minutes)
    def test_down_can_still_read(self):
        value = x.rc_client.read(x.table, 'testKey')
        expect(value).equals(('testValue', 1))
        server_id = x.rc_client.testing_get_server_id(x.table, 'testKey')

        # find the host corresponding to the backup data, and kill that
        backup_id = x.getPlusOneBackupId(server_id)
        host = x.server_id_to_host[backup_id]
        x.node_containers[host].exec_run('killall -SIGKILL rc-server')

        # read the value again (without waiting for backup to recover).
        # We expect the same value.
        value = x.rc_client.read(x.table, 'testKey')
        expect(value).equals(('testValue', 1))

    @timeout(ten_minutes)
    def test_down_can_still_write(self):
        value = x.rc_client.read(x.table, 'testKey')
        expect(value).equals(('testValue', 1))
        server_id = x.rc_client.testing_get_server_id(x.table, 'testKey')

        # find the host corresponding to the backup data, and kill that
        backup_id = x.getPlusOneBackupId(server_id)
        host = x.server_id_to_host[backup_id]
        x.node_containers[host].exec_run('killall -SIGKILL rc-server')

        # after the backup goes down, we try to write (not read). We expect
        # the read that follows to correctly contain our value.
        x.rc_client.write(x.table, 'testKey', 'testValue2')
        value = x.rc_client.read(x.table, 'testKey')
        expect(value).equals(('testValue2', 2))

    @timeout(ten_minutes)
    def test_two_downs_can_still_read(self):
        value = x.rc_client.read(x.table, 'testKey')
        expect(value).equals(('testValue', 1))
        server_id = x.rc_client.testing_get_server_id(x.table, 'testKey')

        # find the host corresponding to the backup data, and kill that
        backup_id = x.getPlusOneBackupId(server_id)
        host = x.server_id_to_host[backup_id]
        x.node_containers[host].exec_run('killall -SIGKILL rc-server')

        # read the value again (without waiting for backup to recover).
        # We expect the same value.
        value = x.rc_client.read(x.table, 'testKey')
        expect(value).equals(('testValue', 1))

        # down the master server after 3 seconds. This should be enough
        # time for a new backup of the data to be made before it's lost
        # forever.
        time.sleep(3)
        host = x.server_id_to_host[server_id]
        x.node_containers[host].exec_run('killall -SIGKILL rc-server')

        # read the value again. We expect the same value.
        value = x.rc_client.read(x.table, 'testKey')
        expect(value).equals(('testValue', 1))

    @timeout(ten_minutes)
    def test_two_downs_can_still_write(self):
        value = x.rc_client.read(x.table, 'testKey')
        expect(value).equals(('testValue', 1))
        server_id = x.rc_client.testing_get_server_id(x.table, 'testKey')

        # find the host corresponding to the backup data, and kill that
        backup_id = x.getPlusOneBackupId(server_id)
        host = x.server_id_to_host[backup_id]
        x.node_containers[host].exec_run('killall -SIGKILL rc-server')

        # write a new value without waiting for backup to recover.
        x.rc_client.write(x.table, 'testKey', 'testValue2')

        # down the master server after 3 seconds. This should be enough
        # time for a new backup of the data to be made before it's lost
        # forever.
        time.sleep(3)
        host = x.server_id_to_host[server_id]
        x.node_containers[host].exec_run('killall -SIGKILL rc-server')

        # read the value again. We expect the new value.
        value = x.rc_client.read(x.table, 'testKey')
        expect(value).equals(('testValue2', 2))

if __name__ == '__main__':
    unittest.main()
