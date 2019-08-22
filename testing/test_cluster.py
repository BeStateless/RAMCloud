import docker
import logging
import logging.config
import ramcloud
import time
import unittest
from pyexpect import expect

logging.config.fileConfig('/src/testing/log.ini')
logger = logging.getLogger('cluster')

docker_client = docker.from_env()
docker_api = docker.APIClient(base_url='unix://var/run/docker.sock')

def get_docker_images():
    logger.info('Pulling zookeeper image...')
    zookeeper_image = docker_client.images.pull('zookeeper', tag='latest')
    logger.info('Pulling zookeeper image...succeeded')
    logger.info('Building ramcloud-test image...')
    ramcloud_image = docker_client.images.build(path='/src',
                                                dockerfile='/src/config/Dockerfile.ramcloud',
                                                tag='ramcloud-test')[0]
    logger.info('Building ramcloud-test image...succeeded')
    return (zookeeper_image, ramcloud_image)

def make_docker_network(name, subnet):
    logger.info('Creating docker network %s on subnet %s...', name, subnet)
    ramcloud_net_pool = docker.types.IPAMPool(subnet=subnet)
    ramcloud_net_config = docker.types.IPAMConfig(pool_configs=[ramcloud_net_pool])
    network = docker_client.networks.create(name, ipam=ramcloud_net_config, check_duplicate=True)
    logger.info('Creating docker network %s on subnet %s...succeeded', name, subnet)
    return network

def launch_zookeeper_cluster(hosts, image, network):
    assert len(hosts) >= 3

    # Build the ZOO_SERVERS environment variable string.
    zoo_servers = []
    for (hostname, (zkid, ip)) in hosts.items():
        zoo_servers.append('server.{}={}:2888:3888;2181'.format(zkid, ip))
    zoo_servers = ' '.join(zoo_servers)

    # Launch each ZooKeeper container.
    zookeeper_containers = {}
    for (hostname, (zkid, ip)) in hosts.items():
        environment = {
            'ZOO_MY_ID': zkid,
            'ZOO_SERVERS': zoo_servers
        }

        networking_config = docker_api.create_networking_config({
            network.name: docker_api.create_endpoint_config(ipv4_address=ip)
        })

        logger.info('Launching ZooKeeper container %s with zkid %d and IP address %s...', hostname, zkid, ip)
        container = docker_api.create_container(image.id,
                                                environment=environment,
                                                hostname=hostname,
                                                name=hostname,
                                                networking_config=networking_config)
        docker_api.start(container.get('Id'))
        logger.info('Launching ZooKeeper container %s with zkid %d and IP address %s...successful', hostname, zkid, ip)
        zookeeper_containers[hostname] = container
    return zookeeper_containers

def external_storage_string(zookeeper_hosts):
    external_storage = []
    for (_, (_, ip)) in zookeeper_hosts.items():
        external_storage.append('{}:2181'.format(ip))
    return 'zk:{}'.format(','.join(external_storage))

def launch_ramcloud_containers(executable, arg, hosts, ensemble, cluster_name, image, network):
    containers = {}
    for (hostname, ip) in hosts.items():
        entrypoint = [executable, '--externalStorage', external_storage_string(ensemble), '--clusterName', cluster_name]
        if arg:
            entrypoint += [arg, 'basic+udp:host={},port=11111'.format(ip)]

        networking_config = docker_api.create_networking_config({
            network.name: docker_api.create_endpoint_config(ipv4_address=ip)
        })

        logger.info('Launching %s container %s with IP address %s...', executable, hostname, ip)
        container = docker_api.create_container(image.id,
                                                entrypoint=entrypoint,
                                                hostname=hostname,
                                                name=hostname,
                                                networking_config=networking_config)
        docker_api.start(container.get('Id'))
        logger.info('Launching %s container %s with IP address %s...successful', executable, hostname, ip)
        containers[hostname] = container
    return containers

def launch_ramcloud_coordinators(hosts, ensemble, cluster_name, image, network):
    return launch_ramcloud_containers('rc-coordinator', '--coordinator', hosts, ensemble, cluster_name, image, network)

def launch_ramcloud_servers(hosts, ensemble, cluster_name, image, network):
    return launch_ramcloud_containers('rc-server', '--local', hosts, ensemble, cluster_name, image, network)

class TestCluster(unittest.TestCase):
    def test_read_write(self):
        (zookeeper_image, ramcloud_image) = get_docker_images()
        ramcloud_network = make_docker_network('ramcloud-net', '10.0.0.0/16')

        zookeeper_hosts = {
            'zookeeper-1': (1, '10.0.1.1'),
            'zookeeper-2': (2, '10.0.1.2'),
            'zookeeper-3': (3, '10.0.1.3')
        }

        zookeeper_containers = launch_zookeeper_cluster(zookeeper_hosts, zookeeper_image, ramcloud_network)

        coordinator_hosts = {
            'rc-coordinator-1': '10.0.2.1',
            'rc-coordinator-2': '10.0.2.2',
            'rc-coordinator-3': '10.0.2.3'
        }

        coordinator_containers = launch_ramcloud_coordinators(coordinator_hosts,
                                                              zookeeper_hosts,
                                                              'main',
                                                              ramcloud_image,
                                                              ramcloud_network)

        server_hosts = {
            'rc-server-1': '10.0.3.1',
            'rc-server-2': '10.0.3.2',
            'rc-server-3': '10.0.3.3'
        }

        server_containers = launch_ramcloud_servers(server_hosts,
                                                    zookeeper_hosts,
                                                    'main',
                                                    ramcloud_image,
                                                    ramcloud_network)

        rc_client = ramcloud.RAMCloud()
        rc_client.connect(external_storage_string(zookeeper_hosts), 'main')
        rc_client.create_table('test_table')
        table = rc_client.get_table_id('test_table')
        rc_client.create(table, 0, 'Hello, World!')
        value, version = rc_client.read(table, 0)

        expect(value).equals('Hello, World!')

if __name__ == '__main__':
    unittest.main()
