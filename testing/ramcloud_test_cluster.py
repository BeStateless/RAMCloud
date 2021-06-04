import cluster_test_utils as ctu
import argparse
import sys

# If you're trying to make fake data in RAMCloud, this works from Python3 interpreter,
# assuming you started up the default 3-node test cluster:
#
# >>> import ramcloud
# >>> import cluster_test_utils as ctu
# >>> rc = ramcloud.RAMCloud()
# >>> rc.connect('zk:10.0.1.1:2181,10.0.1.2:2181,10.0.1.3:2181', 'main')
# >>> rc.create_table('test')
# >>> tid = rc.get_table_id('test')
# >>> rc.write(tid, 'testKey', 'testValue')
# >>> rc.read(tid, 'testKey')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--action', '-a', metavar='A', type=str, default="status",
                        help="Defines the action to take: status, reset, log, start, stop")
    parser.add_argument('--nodes', '-n', type=int, default=3,
                        help="Number of zk, rc-coordinator, and rc-server instances to bring up. Only relevant when there's no cluster up yet. Default is 3")
    parser.add_argument('--path', '-p', type=str, default="/src/tmp",
                        help="Path to place logs in when action is set to \"log\"")

args = parser.parse_args()

print("action =",args.action)
print("nodes =",args.nodes)
print("path =",args.path)
if (args.action == "start"):
    x = ctu.ClusterTest()
    x.setUp(num_nodes = args.nodes)
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
        x.setUp(num_nodes = args.nodes)
    elif (not docker_containers):
        # A network but no containers means no data, so take it down, & bring back up
        print("Inconsistent State")
        print("Bringing up new cluster with ", args.nodes, " nodes")
        ctu.destroy_network_and_containers(docker_network, [])
        x = ctu.ClusterTest()
        x.setUp(num_nodes = args.nodes)
    else:
        # We have a network and containers. Get the ensemble, table names, then drop all tables!
        print("Found a cluster with ", len(docker_containers), " nodes")
        print("Identifying tables")
        ensemble = ctu.get_ensemble(len(docker_containers))
        table_names = ctu.get_table_names(ensemble)
        print("Table names = ", table_names)
        print("Dropping all tables")
        ctu.drop_tables(ensemble, table_names)
else:
    parser.print_help()
