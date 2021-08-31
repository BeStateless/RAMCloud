import cluster_test_utils as ctu
import argparse
import test_exhaustive_calls
import sys

# If you're trying to make fake data in RAMCloud, this works from Python3 interpreter,
# assuming you started up the default 3-node test cluster:
#
# >>> import ramcloud
# >>> import cluster_test_utils as ctu
# >>> rc = ramcloud.RAMCloud()
# >>> rc.connect('zk:169.254.3.1:2181,169.254.3.2:2181,169.254.3.3:2181', 'main')
# >>> rc.create_table('test')
# >>> tid = rc.get_table_id('test')
# >>> rc.write(tid, 'testKey', 'testValue')
# >>> rc.read(tid, 'testKey')

if __name__ == '__main__':
    # We list all argument default values as part of the "help menu"
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--action', '-a', metavar='A', type=str, default="status",
                        help="Defines the action to take, which is one of: status reset log start stop")
    parser.add_argument('--nodes', '-n', type=int, default=3,
                        help="Number of zk, rc-coordinator, and rc-server instances to bring up. Only relevant when there's no cluster up yet.")
    parser.add_argument('--path', '-p', type=str, default="/src/tmp",
                        help="Path to place logs in when action is set to \"log\"")
    parser.add_argument('--cidr', '-c', type=str, default="169.254.3.0/24",
                        help="IPv4 CIDR to use for the docker network, docker nodes, and zk ensemble in the RAMCloud test cluster. "
                             "NOTE that only CIDR notations of /24 or /16 are supported at the moment in this program.")
    parser.add_argument('--docker-names', '-d', type=str, default="ramcloud-test,ramcloud-net,ramcloud-node",
                        help="Three comma-separated names without spaces, corresponding to IMAGE,NETWORK,NODE where: "
                             "IMAGE is the name of the docker image to either look for or build, "
                             "NETWORK is the name of the docker network to create (not an IP address), "
                             "and NODE is the prefix to use for the names of the docker containers corresponding to the nodes, and "
                             "appears as NODE-1, NODE-2, NODE-3, etc.")
    parser.add_argument('--transport', '-t', type=str, default="basic+udp",
                        help="The transport type to use when looking up rc-server and rc-coordinator instances. "
                             "Use infrc instead of udp if you want RoCEv2. ")

args = parser.parse_args()

print("action =",args.action)
print("nodes =",args.nodes)
print("path =",args.path)

ctu.set_cluster_cidr(args.cidr)
ctu.set_docker_names(args.docker_names)

print("cidr = {}.0/{}".format(ctu.cluster_ip_prefix, ctu.cluster_notation))
print("docker_names = {},{},{}".format(ctu.docker_image_name, ctu.docker_network_name, ctu.docker_node_prefix))

if (args.action == "start"):
    x = ctu.ClusterTest()
    x.setUp(num_nodes = args.nodes, transport=args.transport)
elif (args.action == "status"):
    ctu.get_status()
elif (args.action == "stop"):
    docker_network, docker_containers = ctu.get_status()
    ctu.destroy_network_and_containers(docker_network, docker_containers)
elif (args.action == "log"):
    docker_network, docker_containers = ctu.get_status()
    if (not docker_network or not docker_containers):
        print("No network or containers currently up to log")
        exit()
    ensemble = ctu.get_ensemble(len(docker_containers))
    ctu.output_logs_detached(docker_containers, args.path)
    ctu.output_zk_detached(ensemble, args.path)
elif (args.action == "reset"):
    docker_network, docker_containers = ctu.get_status()
    if (not docker_network):
        # No network (or containers), means bring up new cluster
        print("Bringing up new cluster with ", args.nodes, " nodes")
        x = ctu.ClusterTest()
        x.setUp(num_nodes = args.nodes, transport=args.transport)
    elif (not docker_containers):
        # A network but no containers means no data, so take it down, & bring back up
        print("Inconsistent State")
        print("Bringing up new cluster with ", args.nodes, " nodes")
        ctu.destroy_network_and_containers(docker_network, [])
        x = ctu.ClusterTest()
        x.setUp(num_nodes = args.nodes, transport=args.transport)
    else:
        # We have a network and containers. Get the ensemble, table names, then drop all tables!
        print("Found a cluster with ", len(docker_containers), " nodes")
        print("Identifying tables")
        ensemble = ctu.get_ensemble(len(docker_containers))
        table_names = ctu.get_table_names(ensemble)
        print("Table names = ", table_names)
        print("Dropping all tables")
        ctu.drop_tables(ensemble, table_names)
elif (args.action == 'rq'):
    test_exhaustive_calls.run_queries()
else:
    parser.print_help()
