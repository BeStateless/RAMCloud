import ramcloud
import unittest
from pyexpect import expect
import cluster_test_utils as ctu

class TestCluster(unittest.TestCase):
    def setUp(self):
        self.ramcloud_network = ctu.make_docker_network('ramcloud-net', '10.0.0.0/16')
        (self.zookeeper_image, self.ramcloud_image) = ctu.get_docker_images()
        self.rc_client = ramcloud.RAMCloud()
        self.zookeeper_containers = {}
        self.coordinator_containers = {}
        self.server_containers = {}

    def tearDown(self):
        for (hostname, container) in self.server_containers.items():
            container.remove(force=True)
        for (hostname, container) in self.coordinator_containers.items():
            container.remove(force=True)
        for (hostname, container) in self.zookeeper_containers.items():
            container.remove(force=True)
        self.ramcloud_network.remove()

    def make_cluster(self, num_zookeepers, num_coordinators, num_servers):
        self.assertGreaterEqual(num_zookeepers, 3)
        self.assertGreaterEqual(num_coordinators, 1)
        self.assertGreaterEqual(num_servers, 1)

        zookeeper_hosts = {'zookeeper-%s'%ii : (ii, '10.0.1.%s'%ii) for ii in xrange(1, 1+num_zookeepers)}
        self.zookeeper_containers = ctu.launch_zookeeper_cluster(zookeeper_hosts, self.zookeeper_image, self.ramcloud_network)

        external_storage = ctu.external_storage_string(zookeeper_hosts)
        self.rc_client.connect(external_storage, 'main')

        coordinator_hosts = {'rc-coordinator-%s'%ii : '10.0.2.%s'%ii for ii in xrange(1, 1+num_coordinators)}
        self.coordinator_containers = ctu.launch_ramcloud_coordinators(coordinator_hosts,
                                                                external_storage,
                                                                'main',
                                                                self.ramcloud_image,
                                                                self.ramcloud_network)

        server_hosts = {'rc-server-%s'%ii : '10.0.3.%s'%ii for ii in xrange(1, 1+num_servers)}
        self.server_containers = ctu.launch_ramcloud_servers(server_hosts,
                                                    external_storage,
                                                    'main',
                                                    self.ramcloud_image,
                                                    self.ramcloud_network)


    def test_read_write(self):
        self.make_cluster(num_zookeepers=3, num_coordinators=3, num_servers=3)
        self.rc_client.create_table('test_table')
        table = self.rc_client.get_table_id('test_table')
        self.rc_client.create(table, 0, 'Hello, World!')
        value, version = self.rc_client.read(table, 0)

        expect(value).equals('Hello, World!')

    def test_two_writes(self):
        self.make_cluster(num_zookeepers=4, num_coordinators=2, num_servers=5)
        self.rc_client.create_table('test_table')
        table = self.rc_client.get_table_id('test_table')
        self.rc_client.create(table, 1, 'Hello')
        self.rc_client.write(table, 1, 'Nice day')
        self.rc_client.write(table, 1, 'Good weather')
        value, version = self.rc_client.read(table, 1)

        expect(value).equals('Good weather')

if __name__ == '__main__':
    unittest.main()
