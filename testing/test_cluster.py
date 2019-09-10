import os
import ramcloud
import Table_pb2
import unittest
from pyexpect import expect
import cluster_test_utils as ctu

class TestCluster(unittest.TestCase):
    def setUp(self):
        self.ramcloud_network = ctu.make_docker_network('ramcloud-net', '10.0.0.0/16')
        self.node_image = ctu.get_node_image()
        self.rc_client = ramcloud.RAMCloud()
        self.node_containers = {}

    def tearDown(self):
        for (_, container) in self.node_containers.items():
            container.remove(force=True)
        self.ramcloud_network.remove()

    def createTestValue(self):
        self.rc_client.create_table('test', serverSpan = 2)
        self.table = self.rc_client.get_table_id('test')
        self.rc_client.write(self.table, 'testKey', 'testValue')

    def make_cluster(self, num_nodes):
        self.assertGreaterEqual(num_nodes, 3)

        self.ensemble = {i: '10.0.1.{}'.format(i) for i in xrange(1, num_nodes + 1)}
        zk_servers = ctu.ensemble_servers_string(self.ensemble)
        external_storage = 'zk:' + ctu.external_storage_string(self.ensemble)
        for i in xrange(1, num_nodes + 1):
            hostname = 'ramcloud-node-{}'.format(i)
            self.node_containers[self.ensemble[i]] = ctu.launch_node('main',
                                                                     hostname,
                                                                     zk_servers,
                                                                     external_storage,
                                                                     i,
                                                                     self.ensemble[i],
                                                                     self.node_image,
                                                                     self.ramcloud_network)
        self.rc_client.connect(external_storage, 'main')

    def simple_recovery(self, kill_command):
        self.make_cluster(num_nodes=7)
        self.createTestValue()
        value = self.rc_client.read(self.table, 'testKey')
        expect(value).equals(('testValue', 1))

        # find the host corresponding to the server with our table and 'testKey',
        # then kill its rc-server!
        locator =  self.rc_client.testing_get_service_locator(self.table, 'testKey')
        host = ctu.get_host(locator)
        self.node_containers[host].exec_run(kill_command)

        # read the value again (without waiting for the server to recover). It 
        # should come out to the same value
        value = self.rc_client.read(self.table, 'testKey')
        expect(value).equals(('testValue', 1))

    def test_zookeeper_read(self):
        self.make_cluster(num_nodes=4)
        self.createTestValue()
        zk_client = ctu.get_zookeeper_client(self.ensemble)

        # Read the ZooKeeper entry for the table and make sure it looks sane.
        # This mostly tests our ability to read from ZooKeeper and parse the
        # GRPC contents correctly.
        table_data = zk_client.get('/ramcloud/main/tables/test')[0]
        table_parsed = Table_pb2.Table()
        table_parsed.ParseFromString(table_data)
        expect(table_parsed.id).equals(1L)
        expect(table_parsed.name).equals("test")

    def test_read_write(self):
        self.make_cluster(num_nodes=3)
        self.rc_client.create_table('test_table')
        table = self.rc_client.get_table_id('test_table')
        self.rc_client.create(table, 0, 'Hello, World!')
        value, version = self.rc_client.read(table, 0)

        expect(value).equals('Hello, World!')

    def test_two_writes(self):
        self.make_cluster(num_nodes=4)
        self.rc_client.create_table('test_table')
        table = self.rc_client.get_table_id('test_table')
        self.rc_client.create(table, 1, 'Hello')
        self.rc_client.write(table, 1, 'Nice day')
        self.rc_client.write(table, 1, 'Good weather')
        value, version = self.rc_client.read(table, 1)

        expect(value).equals('Good weather')

    def test_01_simple_recovery_graceful_server_down(self):
        self.simple_recovery(kill_command = 'killall -SIGTERM rc-server')

    def test_01_simple_recovery_forced_server_down(self):
        self.simple_recovery(kill_command = 'killall -SIGKILL rc-server')

if __name__ == '__main__':
    unittest.main()
