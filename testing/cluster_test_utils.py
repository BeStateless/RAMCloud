import docker
import kazoo.client
import logging
import logging.config
import os
import ramcloud

logging.config.fileConfig('/src/testing/log.ini')
logger = logging.getLogger('cluster')

docker_client = docker.from_env()
docker_api = docker.APIClient(base_url='unix://var/run/docker.sock')

ten_minutes = 600  # number of seconds in 10 minutes

def get_zookeeper_client(ensemble, read_only=True):
    client = kazoo.client.KazooClient(hosts=external_storage_string(ensemble), read_only=read_only)
    client.start()
    return client

def get_host(locator):
    # locator should be in format 'k1=v1,k2=v2,....,kn=vn'
    args = filter(lambda x: x.find('=') >= 0, locator.split(','))
    arg_map = {k : v for (k,v) in map(lambda a: a.split('=', 2), args)}
    return arg_map['basic+udp:host']

def external_storage_string(ensemble):
    return ','.join(['{}:2181'.format(ip) for (_, ip) in ensemble.items()])

def ensemble_servers_string(ensemble):
    return ' '.join(['server.{}={}:2888:3888;2181'.format(zkid, ip) for (zkid, ip) in ensemble.items()])

def get_node_image():
    logger.info('Building ramcloud-test-node image...')
    node_image = docker_client.images.build(path='/src',
                                            dockerfile='/src/config/Dockerfile.node',
                                            tag='ramcloud-test')[0]
    logger.info('Building ramcloud-test-node image...succeeded')
    return node_image

def make_docker_network(name, subnet):
    logger.info('Creating docker network %s on subnet %s...', name, subnet)
    ramcloud_net_pool = docker.types.IPAMPool(subnet=subnet)
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

# ClusterTest Usage in Python interpreter:
# >>> import cluster_test_utils as ctu
# >>> x = ctu.ClusterTest()
# >>> x.setUp()
# >>> x.createTestValue()
# < Do some stuff >
# >>> x.outputLogs()
# >>> x.tearDown()
class ClusterTest:
    def setUp(self, num_nodes = 4):
        assert (num_nodes >= 3), ("num_nodes(%s) must be at least 3."%num_nodes)
        self.ramcloud_network = make_docker_network('ramcloud-net', '10.0.0.0/16')
        self.node_image = get_node_image()
        self.rc_client = ramcloud.RAMCloud()
        self.node_containers = {}
        self.ensemble = {i: '10.0.1.{}'.format(i) for i in xrange(1, num_nodes + 1)}
        zk_servers = ensemble_servers_string(self.ensemble)
        external_storage = 'zk:' + external_storage_string(self.ensemble)
        for i in xrange(1, num_nodes + 1):
            hostname = 'ramcloud-node-{}'.format(i)
            self.node_containers[self.ensemble[i]] = launch_node('main',
                                                                 hostname,
                                                                 zk_servers,
                                                                 external_storage,
                                                                 i,
                                                                 self.ensemble[i],
                                                                 self.node_image,
                                                                 self.ramcloud_network)
        self.rc_client.connect(external_storage, 'main')

    def createTestValue(self):
        self.rc_client.create_table('test')
        self.table = self.rc_client.get_table_id('test')
        self.rc_client.write(self.table, 'testKey', 'testValue')

    # Definitely useful to invoke this method from the Python interpreter.
    def outputLogs(self, path="/src/tmp"):
        if not os.path.exists(path):
            os.makedirs(path)
        for (_, container) in self.node_containers.items():
            outfile = '%s/%s.out' % (path, container.name)
            f = open(outfile, 'w')
            # make a stream of output logs to iterate and write to file 
            # (uses less memory than storing the container log as a string), 
            # and don't keep the stream open for new logs, since we want 
            # to get thru outputting whatever we got for this container 
            # before doing same for next container.
            for line in container.logs(stream=True, follow=False):
                f.write(line)
            f.close()

    def tearDown(self):
        for (_, container) in self.node_containers.items():
            container.remove(force=True)
        self.ramcloud_network.remove()
