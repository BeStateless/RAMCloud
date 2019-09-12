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

class TestInfrastructure(unittest.TestCase):
    def setUp(self):
        x.setUp(num_nodes = 3)

    def tearDown(self):
        x.tearDown()

    @timeout(ten_minutes)
    def test_zookeeper_read(self):
        x.createTestValue()  # create a table to test on
        zk_client = ctu.get_zookeeper_client(x.ensemble)

        # Read the ZooKeeper entry for the table and make sure it looks sane.
        # This mostly tests our ability to read from ZooKeeper and parse the
        # GRPC contents correctly.
        table_data = zk_client.get('/ramcloud/main/tables/test')[0]
        table_parsed = Table_pb2.Table()
        table_parsed.ParseFromString(table_data)
        expect(table_parsed.id).equals(1L)
        expect(table_parsed.name).equals("test")

    @timeout(ten_minutes)
    def test_read_write(self):
        x.rc_client.create_table('test_table')
        table = x.rc_client.get_table_id('test_table')
        x.rc_client.create(table, 0, 'Hello, World!')
        value, version = x.rc_client.read(table, 0)

        expect(value).equals('Hello, World!')

    @timeout(ten_minutes)
    def test_two_writes(self):
        x.rc_client.create_table('test_table')
        table = x.rc_client.get_table_id('test_table')
        x.rc_client.create(table, 1, 'Hello')
        x.rc_client.write(table, 1, 'Nice day')
        x.rc_client.write(table, 1, 'Good weather')
        value, version = x.rc_client.read(table, 1)

        expect(value).equals('Good weather')

if __name__ == '__main__':
    unittest.main()
