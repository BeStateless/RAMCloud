import ramcloud
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

        ensemble = {i: '10.0.1.{}'.format(i) for i in xrange(1, num_nodes + 1)}
        zk_servers = ctu.ensemble_servers_string(ensemble)
        external_storage = ctu.external_storage_string(ensemble)
        for i in xrange(1, num_nodes + 1):
            hostname = 'ramcloud-node-{}'.format(i)
            self.node_containers[ensemble[i]] = ctu.launch_node('main',
                                                            hostname,
                                                            zk_servers,
                                                            external_storage,
                                                            i,
                                                            ensemble[i],
                                                            self.node_image,
                                                            self.ramcloud_network)
        self.rc_client.connect(external_storage, 'main')

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

    @unittest.skip("trying stuff out")
    def test_01_simple_recovery(self):
        self.make_cluster(num_nodes=3)  # num_nodes=8
        self.createTestValue()
        value = self.rc_client.read(self.table, 'testKey')
        expect(value).equals(('testValue', 1))

        # find the host corresponding to the server with our table and 'testKey',
        # then kill it!
        locator =  self.rc_client.testing_get_service_locator(self.table, 'testKey')
        host = ctu.get_host(locator)
        self.node_containers[host].kill()

        # read the value again (without waiting for the server to recover). It 
        # should come out to the same value
        value = self.rc_client.read(self.table, 'testKey')
        expect(value).equals(('testValue', 1))

if __name__ == '__main__':
    unittest.main()
