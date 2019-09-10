import docker
import kazoo.client
import logging
import logging.config
import ramcloud

logging.config.fileConfig('/src/testing/log.ini')
logger = logging.getLogger('cluster')

docker_client = docker.from_env()
docker_api = docker.APIClient(base_url='unix://var/run/docker.sock')

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

def get_zookeeper_client(ensemble, read_only=True):
    client = kazoo.client.KazooClient(hosts=external_storage_string(ensemble), read_only=read_only)
    client.start()
    return client
