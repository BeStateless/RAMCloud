import copy
import docker
import kazoo.client
import kazoo.exceptions
import logging
import logging.config
import os
import ramcloud

import CoordinatorClusterClock_pb2
import CoordinatorUpdateInfo_pb2
import EnumerationIterator_pb2
import Histogram_pb2
import Indexlet_pb2
import LogMetrics_pb2
import MasterRecoveryInfo_pb2
import MetricList_pb2
import ProtoBufTest_pb2
import RecoveryPartition_pb2
import ServerConfig_pb2
import ServerListEntry_pb2
import ServerList_pb2
import ServerStatistics_pb2
import SpinLockStatistics_pb2
import TableConfig_pb2
import Tablets_pb2
import TableManager_pb2
import Table_pb2

from google.protobuf import text_format

logging.config.fileConfig('/src/testing/log.ini')
logger = logging.getLogger('cluster')

docker_client = docker.from_env()
docker_api = docker.APIClient(base_url='unix://var/run/docker.sock')

ten_minutes = 600  # number of seconds in 10 minutes

cluster_cidr = "169.254.3.0/24"
cluster_ip_prefix = "169.254.3"
cluster_notation = 24

docker_image_name = "ramcloud-test"
docker_network_name = "ramcloud-net"
docker_node_prefix = "ramcloud-node"

def set_cluster_cidr(val):
    # We are changing these global variables in this method!
    global cluster_cidr, cluster_ip_prefix, cluster_notation
    cluster_cidr=val
    cn = cluster_cidr.split('/')
    if (len(cn) < 2):
        logger.error("Missing required '/' in cidr, provided: {}".format(cluster_cidr))
        exit(1)
    cluster_notation = int(cn[1])
    if (cluster_notation != 16 and cluster_notation != 24):
        logger.error("Only cidr notation of /16 or /24 is supported at the moment, provided: {}".format(cluster_cidr))
        exit(1)
    ip_parts = cn[0].split('.')
    if (len(ip_parts) < 4):
        logger.error("IPv4 format with 4 numbers expected, provided: {}".format(cluster_cidr))
        exit(1)
    cluster_ip_prefix = '.'.join(ip_parts[0:3])

def set_docker_names(val):
    # We are changing these global variables in this method!
    global docker_image_name, docker_network_name, docker_node_prefix
    names = val.split(',')
    if (len(names) < 3):
        logger.error("Three names required, provided: {}".format(val))
        exit(1)
    (docker_image_name, docker_network_name, docker_node_prefix) = names[0:3]

def get_zookeeper_client(ensemble, read_only=True):
    client = kazoo.client.KazooClient(hosts=external_storage_string(ensemble), read_only=read_only)
    client.start()
    return client

def get_host(locator):
    # locator should be in format 'k1=v1,k2=v2,....,kn=vn'
    args = [x for x in locator.split(',') if x.find('=') >= 0]
    arg_map = {k : v for (k,v) in [a.split('=', 2) for a in args]}
    return arg_map['basic+udp:host']

def external_storage_string(ensemble):
    return ','.join(['{}:2181'.format(ip) for (_, ip) in list(ensemble.items())])

def ensemble_servers_string(ensemble):
    return ' '.join(['server.{}={}:2888:3888;2181'.format(zkid, ip) for (zkid, ip) in list(ensemble.items())])

def get_node_image():
    existing_images = docker_client.images.list(name=docker_image_name)
    if (len(existing_images) > 0):
        logger.info('Found existing {} image, using that...'.format(docker_image_name))
        return existing_images[0]
    logger.info('Building {} image...'.format(docker_image_name))
    node_image = docker_client.images.build(path='/src',
                                            dockerfile='/src/config/Dockerfile.node',
                                            tag=docker_image_name)[0]
    logger.info('Building {} image...succeeded'.format(docker_image_name))
    return node_image

def make_docker_network(name, subnet):
    logger.info('Creating docker network %s on subnet %s...', name, subnet)
    # When cluster_notation is 16, gateway is None (auto-determined), and when cluster_notation is 24,
    # then the gateway should be a.b.c.254, with a.b.c dictated by cluster_ip_prefix
    # NOTE: There are probably other valid cluster_notation values that work with docker.types.IPAMPool,
    # but this requires a bit of careful time and experimentation to find out.
    gateway=None
    if (cluster_notation == 24):
        gateway="{}.254".format(cluster_ip_prefix)
    ramcloud_net_pool = docker.types.IPAMPool(subnet=subnet, gateway=gateway)
    ramcloud_net_config = docker.types.IPAMConfig(pool_configs=[ramcloud_net_pool])
    network = docker_client.networks.create(name, ipam=ramcloud_net_config, check_duplicate=True)
    logger.info('Creating docker network %s on subnet %s...succeeded', name, subnet)
    return network

def launch_node(cluster_name, hostname, zk_servers, external_storage, zkid, ip, image, network):
    environment = {
        'ZOO_MY_ID': zkid,
        'ZOO_SERVERS': zk_servers,
        'RC_EXTERNAL_STORAGE': external_storage,
        'RC_CLUSTER_NAME': cluster_name,
        'RC_IP': ip
    }

    networking_config = docker_api.create_networking_config({
        network.name: docker_api.create_endpoint_config(ipv4_address=ip)
    })

    logger.info('Launching node container %s with IP address %s...', hostname, ip)
    container_dictionary = docker_api.create_container(image.id,
                                                       environment=environment,
                                                       hostname=hostname,
                                                       name=hostname,
                                                       networking_config=networking_config)
    container_id = container_dictionary.get('Id')

    # It's possible to create the container but be unable to start it. If that happens, we need to clean up after
    # ourselves before returning to the caller.
    try:
        docker_api.start(container_id)
    except Exception as exc:
        logger.exception('Error starting container %s. Will attempt to delete...', ip)
        docker_client.remove(docker_client.containers.get(container_id))
        raise

    logger.info('Launching node container %s with IP address %s...successful', hostname, ip)
    return docker_client.containers.get(container_id)

def get_status():
    docker_containers = docker_client.containers.list(all=True, filters={"name":"{}-*".format(docker_node_prefix)})
    docker_network = False
    try:
        docker_network = docker_client.networks.get(docker_network_name)
    except docker.errors.NotFound as nf:
        pass
    if not docker_containers:
        logger.info('No ramcloud nodes found')
    else:
        logger.info('Found %s ramcloude nodes', len(docker_containers))
    if not docker_network:
        logger.info('ramcloud network not found')
    else:
        logger.info('Found ramcloud network')
    return (docker_network, docker_containers)

def destroy_network_and_containers(docker_network, docker_containers):
    try:
        for dc in docker_containers:
            print("removing container:", dc.name)
            dc.remove(force=True)
        if docker_network:
            print("removing network:", docker_network)
            docker_network.remove()
    except docker.errors.NotFound as nf:
        print("unable to destroy containers and/or network")

def get_ensemble(num_nodes = 3):
    # NOTE: There is probably a more flexible way to support ip's for the nodes,
    # but the manner shown here works when cluster_notation is 16 or 24
    return {i: '{}.{}'.format(cluster_ip_prefix, i) for i in range(1, num_nodes + 1)}

def get_table_names(ensemble):
    try:
        zkc = get_zookeeper_client(ensemble)
        return zkc.get_children('/ramcloud/main/tables')
    except kazoo.exceptions.NoNodeError as nne:
        # If tables in zk exists but wasn't initialized, then this is thrown, so return an empty list
        return []

def drop_tables(ensemble, table_names):
    r = ramcloud.RAMCloud()
    external_storage = 'zk:' + external_storage_string(ensemble)
    r.connect(external_storage, 'main')
    for table_name in table_names:
        r.drop_table(table_name)

def output_logs_detached(docker_containers, path="/src/tmp"):
    if not os.path.exists(path):
        os.makedirs(path)
    for container in docker_containers:
        outfile = '%s/%s.out' % (path, container.name)
        f = open(outfile, 'wb')
        # make a stream of output logs to iterate and write to file
        # (uses less memory than storing the container log as a string),
        # and don't keep the stream open for new logs, since we want
        # to get thru outputting whatever we got for this container
        # before doing same for next container.
        for line in container.logs(stream=True, follow=False):
            f.write(line)
        f.close()

def output_zk_detached(ensemble, path="/src/tmp"):
    if not os.path.exists(path):
        os.makedirs(path)
    zk_client = get_zookeeper_client(ensemble)
    zk_table_configs = [
        ZkTableConfiguration(
            outfile = "config.out", 
            zk_path = "/zookeeper/config", 
            proto = "string", 
            is_leaf = True),
        ZkTableConfiguration(
            outfile = "quota.out", 
            zk_path = "/zookeeper/quota", 
            proto = "string", 
            is_leaf = True),
        ZkTableConfiguration(
            outfile = "coordinatorClusterClock.out", 
            zk_path = "/ramcloud/main/coordinatorClusterClock", 
            proto = CoordinatorClusterClock_pb2.CoordinatorClusterClock(), 
            is_leaf = True),
        ZkTableConfiguration(
            outfile = "tables.out", 
            zk_path = "/ramcloud/main/tables", 
            proto = Table_pb2.Table(), 
            is_leaf = False),
        ZkTableConfiguration(
            outfile = "tableManager.out", 
            zk_path = "/ramcloud/main/tableManager", 
            proto = TableManager_pb2.TableManager(), 
            is_leaf = True),
        ZkTableConfiguration(
            outfile = "coordinator.out", 
            zk_path = "/ramcloud/main/coordinator", 
            proto = "string", 
            is_leaf = True),
        ZkTableConfiguration(
            outfile = "servers.out", 
            zk_path = "/ramcloud/main/servers", 
            proto = ServerListEntry_pb2.ServerListEntry(), 
            is_leaf = False),
        ZkTableConfiguration(
            outfile = "coordinatorUpdateManager.out", 
            zk_path = "/ramcloud/main/coordinatorUpdateManager", 
            proto = CoordinatorUpdateInfo_pb2.CoordinatorUpdateInfo(), 
            is_leaf = True),
        ZkTableConfiguration(
            outfile = "clientLeaseAuthority.out", 
            zk_path = "/ramcloud/main/clientLeaseAuthority", 
            proto = "string", 
            is_leaf = False),
    ]
    for zk_table_config in zk_table_configs:
        zk_table_config.dump(path, zk_client)

# ClusterTest Usage in Python interpreter:
# >>> import cluster_test_utils as ctu
# >>> x = ctu.ClusterTest()
# >>> x.setUp()
# >>> x.createTestValue()
# < Do some stuff >
# >>> x.outputLogs()
# >>> x.zkDump()
# < Check output files in /src/tmp >
# >>> x.tearDown()
class ClusterTest:
    def setUp(self, num_nodes = 4):
        assert (num_nodes >= 3), ("num_nodes(%s) must be at least 3."%num_nodes)

        # clean out any old docker fixtures
        docker_containers = docker_client.containers.list(all=True, filters={"name":"{}-*".format(docker_node_prefix)})
        try:
            for dc in docker_containers:
                print("removing container:", dc.name)
                dc.remove(force=True)
            docker_network = docker_client.networks.get(docker_network_name)
            print("removing network:", docker_network);
            docker_network.remove()
        except docker.errors.NotFound as nf:
            # NotFound is ignored because we're trying to remove the network whether it's there or not
            pass

        self.ramcloud_network = make_docker_network(docker_network_name, cluster_cidr)
        self.node_image = get_node_image()
        self.rc_client = ramcloud.RAMCloud()
        self.node_containers = {}
        self.ensemble = {i: '{}.{}'.format(cluster_ip_prefix, i) for i in range(1, num_nodes + 1)}
        zk_servers = ensemble_servers_string(self.ensemble)
        external_storage = 'zk:' + external_storage_string(self.ensemble)
        for i in range(1, num_nodes + 1):
            hostname = '{}-{}'.format(docker_node_prefix, i)
            self.node_containers[self.ensemble[i]] = launch_node('main',
                                                                 hostname,
                                                                 zk_servers,
                                                                 external_storage,
                                                                 i,
                                                                 self.ensemble[i],
                                                                 self.node_image,
                                                                 self.ramcloud_network)
        self.rc_client.connect(external_storage, 'main')

    def buildServerIdMap(self):
        zk_client = get_zookeeper_client(self.ensemble)
        zk_config = ZkTableConfiguration(
                outfile = "servers.out", 
                zk_path = "/ramcloud/main/servers", 
                proto = ServerListEntry_pb2.ServerListEntry(), 
                is_leaf = False)
        server_protos = zk_config.getTable(zk_client)
        self.server_id_to_host = {s.server_id : get_host(s.service_locator) for s in server_protos}
        self.host_to_server_id = {get_host(s.service_locator) : s.server_id for s in server_protos}
        zk_client.stop()

    # This method assumes we're running rc-server with the usePlusOneBackup flag set to true.
    # We might modify this method in future to account for downed server instances.
    def getPlusOneBackupId(self, master_server_id):
        n = len(self.node_containers)
        backup_server_id = master_server_id + 1
        if (backup_server_id > n):
            backup_server_id = 1
        return backup_server_id

    def createTestValue(self):
        self.rc_client.create_table('test')
        self.table = self.rc_client.get_table_id('test')
        self.rc_client.write(self.table, 'testKey', 'testValue')

    # Definitely useful to invoke this method from the Python interpreter.
    def outputLogs(self, path="/src/tmp"):
        if not os.path.exists(path):
            os.makedirs(path)
        for (_, container) in list(self.node_containers.items()):
            outfile = '%s/%s.out' % (path, container.name)
            f = open(outfile, 'wb')
            # make a stream of output logs to iterate and write to file
            # (uses less memory than storing the container log as a string),
            # and don't keep the stream open for new logs, since we want
            # to get thru outputting whatever we got for this container
            # before doing same for next container.
            for line in container.logs(stream=True, follow=False):
                f.write(line)
            f.close()

    def zkDump(self, path="/src/tmp", zk_client=None, stop_zk=True):
        if not os.path.exists(path):
            os.makedirs(path)
        if not zk_client:
            zk_client = get_zookeeper_client(self.ensemble)
        zk_table_configs = [
            ZkTableConfiguration(
                outfile = "config.out", 
                zk_path = "/zookeeper/config", 
                proto = "string", 
                is_leaf = True),
            ZkTableConfiguration(
                outfile = "quota.out", 
                zk_path = "/zookeeper/quota", 
                proto = "string", 
                is_leaf = True),
            ZkTableConfiguration(
                outfile = "coordinatorClusterClock.out", 
                zk_path = "/ramcloud/main/coordinatorClusterClock", 
                proto = CoordinatorClusterClock_pb2.CoordinatorClusterClock(), 
                is_leaf = True),
            ZkTableConfiguration(
                outfile = "tables.out", 
                zk_path = "/ramcloud/main/tables", 
                proto = Table_pb2.Table(), 
                is_leaf = False),
            ZkTableConfiguration(
                outfile = "tableManager.out", 
                zk_path = "/ramcloud/main/tableManager", 
                proto = TableManager_pb2.TableManager(), 
                is_leaf = True),
            ZkTableConfiguration(
                outfile = "coordinator.out", 
                zk_path = "/ramcloud/main/coordinator", 
                proto = "string", 
                is_leaf = True),
            ZkTableConfiguration(
                outfile = "servers.out", 
                zk_path = "/ramcloud/main/servers", 
                proto = ServerListEntry_pb2.ServerListEntry(), 
                is_leaf = False),
            ZkTableConfiguration(
                outfile = "coordinatorUpdateManager.out", 
                zk_path = "/ramcloud/main/coordinatorUpdateManager", 
                proto = CoordinatorUpdateInfo_pb2.CoordinatorUpdateInfo(), 
                is_leaf = True),
            ZkTableConfiguration(
                outfile = "clientLeaseAuthority.out", 
                zk_path = "/ramcloud/main/clientLeaseAuthority", 
                proto = "string", 
                is_leaf = False),
        ]
        for zk_table_config in zk_table_configs:
            zk_table_config.dump(path, zk_client)
        if stop_zk:
            zk_client.stop()

    def tearDown(self):
        for (_, container) in list(self.node_containers.items()):
            container.remove(force=True)
        self.ramcloud_network.remove()

class ZkTableConfiguration:
    def __init__(self, outfile, zk_path, proto, is_leaf):
        self.outfile = outfile
        self.zk_path = zk_path
        self.proto = proto
        self.is_leaf = is_leaf

    def getTable(self, zk_client):
        # TODO: Find a way to combine this method and dump(). This is non-intuitive at moment.
        if not zk_client.exists(self.zk_path):
            return None
        zk_paths = [self.zk_path]
        if not self.is_leaf:
            zk_paths = ["%s/%s" % (self.zk_path, child) for child in zk_client.get_children(self.zk_path)]
        items = []
        for zk_path in zk_paths:
            data = zk_client.get(zk_path)[0]
            item = ""
            if type(self.proto) is str:
                item = data
            else:
                item = copy.deepcopy(self.proto)
                item.ParseFromString(data)
            items.append(item)
        return items

    def dump(self, outpath, zk_client):
        # If the zk_path doesn't exist, then don't output anything. That's not an error.
        # "/ramcloud/main/tableManager" doesn't always exist, for example.
        if not zk_client.exists(self.zk_path):
            return
        zk_paths = [self.zk_path]
        if not self.is_leaf:
            zk_paths = ["%s/%s" % (self.zk_path, child) for child in zk_client.get_children(self.zk_path)]
        outfile_complete = "%s/%s" % (outpath, self.outfile)
        f = open(outfile_complete, 'w')
        for zk_path in zk_paths:
            data = zk_client.get(zk_path)[0]
            outstring = ""
            if type(self.proto) is str:
                outstring = data.decode()
            else:
                outproto = copy.deepcopy(self.proto)
                outproto.ParseFromString(data)
                outstring = text_format.MessageToString(outproto)
            liner = "%s ==>\n"%zk_path
            f.write(liner)
            f.write(outstring)
            f.write('\n')
        f.close()
