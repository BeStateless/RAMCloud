# RAMCloud

**THIS REPO IS DEPRECATED!!!**

If you are looking for the current RAMCloud repo maintained by Stateless, which is used by the Stateless Software Router version 4.0 & later, it is [here](https://gitlab.com/stateless/ramcloud). 

## Older Instructions

This is the Stateless fork of RAMCloud. Instead of maintaining a normal git fork
we use [stgit](http://www.procode.org/stgit/) to maintain a patchset. This
simplifies things by keeping the upstream history entirely outside of our repo
and the set of stateless-specific patches is very clear. This should make it
easy to incorporate our changes upstream while pulling in new changes from
upstream regularly.

# General Workflow

While the below sections discuss in detail all of the elements of this
repository and how they work together, a simple overview of a general workflow
one might use to develop changes against RAMCloud is presented first.

Generally, if you want to change any RAMCloud code, you will need a development
environment containing all of the dependencies required to build RAMCloud.
First, you should fork the `BeStateless/RAMCloud` repository. Don't do your work
out of the official repository, use your own fork. Once your fork has been
created, create a local copy of it by cloning it from GitHub. After the source
code has been retrieved, a docker-based development environment can be created
using:

    ./config/dev-env

This will drop you into a bash shell in the development environment container.
Then, inside the development environment, you will want to build RAMCloud by
running:

    ./config/make-ramcloud

This will place all of the RAMCloud build artifacts at `./RAMCloud/install`.

Less common: If an inner RAMCloud directory was already existing, and you do 
NOT want to refresh patches from `patches/series` you can do:

    ./config/make-ramcloud --nopatch

(Optional) One other thing you can do within this development environment shell
is run the unit tests for RAMCloud. Note, in order to do that, you must pass the
`--debug` option when you compile RAMCloud with the `./config/make-ramcloud`
script. Once RAMCloud is built with `DEBUG=yes`, the unit tests can be ran with:

    ./config/make-ramcloud-unit-test

As outlined in the `Known Unit Test Issues` section, there are some known
issues with the unit tests.

After RAMCloud has been built (via make-ramcloud), a full standalone test suite
may be run using this command (shown below) in the dev-env container. The tests
are called "standalone" since the coordinators and servers are treated as
standalone products, and interacted with via python test files acting as a
RAMCloud client.

    ./config/make-ramcloud-standalone-test

This will build a `ramcloud-test` Docker image from the build artifacts at
`/src/RAMCloud/install`, then spin up a three-node ZooKeeper ensemble, 3 or 4
RAMCloud coordinators, and 3 or 4 RAMCloud servers. Once that infrastructure has
been spun up, the python RAMCloud client is used to connect to the running
RAMCloud cluster, create a RAMCloud table, write a value to the table, read that
value back, and validate that it has the correct value.

Because standalone tests run slow. If you only wish to rerun one specific
standalone test (for example, test_zookeeper_read() within the class 
TestInfrastructure of file test_infrastructure.py), you can do so this way.

    python3 -m unittest test_infrastructure.TestInfrastructure.test_zookeeper_read

In addition, the comments of cluster_test_utils.py provides some suggestions
to try in the Python interpreter (within the development environment container)
for debugging if you run into trouble with the standalone tests.

To make changes to the RAMCloud code simply make changes to the code in the
`./RAMCloud` directory on your host machine, and then run
`./config/make-ramcloud` again on the the development environment bash shell.
Once RAMCloud is rebuilt, you can run the unit and standalone tests again to
run the updated code.

# Bringing up your own RAMCloud test cluster

There's a script to simplify bringing up/down/resetting your RAMCloud cluster for you,
especially if you feel like debugging RAMCloud from python3 interpreter (arguably a
really nice way to troubleshoot in RAMCloud). It's the file testing/ramcloud_test_cluster.py,
from within the development environment (it's ./config/dev-env to bring this up, as
mentioned in previous section). From this dev environment, you can run:

    python3 testing/ramcloud_test_cluster.py

This shows the status of your RAMCloud cluster. (Nifty, aye?) It may say you don't have
a cluster up or not. You can bring one up or clear out all RAMCloud tables in this
cluster by doing:

    python3 testing/ramcloud_test_cluster.py -a reset

The nice thing about this command is clearing out all tables without wasting time bringing
down then up RAMCloud. You can also do this to bring down the cluster when you're done.

    python3 testing/ramcloud_test_cluster.py -a stop

The -a option also supports start and status, in addition to reset and stop. start will
hard-reset the cluster if it's up already (slower), or in the event there's no cluster up,
it brings one up. status shows if a cluster is up or not (it's equiv to omitting the -a option)

There's also the -n option, which controls the number of nodes to bring up (each node has
zk + rc-coordinator + rc-server). When -n is ommitted, it defaults to 3. You should RARELY
ever need to change this from the default. 3 is arguably the minimum # of nodes needed for
"good behavior" in zk (due to consensus algorithm with tie-breaker) and rc-server (due to
needing one instance for master copy, one instance for backup, and one instance for
"probation" until it is trusted by the other rc-servers and elected rc-coordinator)

In the event you do need to mess with -n (let's say you want it at 4), note that you WILL
need to hard-reset the cluster (ie doing -a reset will NOT work). Something like this should
achieve the effect you want:

    python3 testing/ramcloud_test_cluster.py -a start -n 4

After this point, you can continue to soft-reset the cluster, and it keeps the same number of
nodes. I.e., this command should work at this point:

    python3 testing/ramcloud_test_cluster.py -a reset

# Obtaining the Patched Code

First, install `stgit` through your package manager, e.g. `apt-get install
stgit` or `zypper in stgit`. Alternatively, you can clone the
[stgit repo](https://github.com/ctmarinas/stgit.git) and install it manually if
you want to run the latest and greatest version.

Next, run the following commands.

```
git clone git@github.com:BeStateless/RAMCloud.git
cd RAMCloud
./patch
```

Now the patched code is in the `RAMCloud` directory in the repository root with
stgit set up on the tip of the patch set.

# Making New Patches

To make a new patch simply use `stg new patch-name.patch`, edit the files you
want to include in the patch, use `stg refresh` to incorporate those changes
into the patch, and finally use `stg export -d ../patches` from the inner
`RAMCloud` directory to export the new patch. Modifying an existing patch,
reordering patches, rebasing onto newer upstream changes, and other operations
are explained in the
[stgit tutorial](http://procode.org/stgit/doc/tutorial.html).

# Updating Existing Patches

If you want to change an existing patch, first retreive the fully patched code.
After you have the code, from the _inner_ `RAMCloud` directory you can use the
command `stg series` to show all patches in the series. Find the patch you want
to edit and use the command `stg goto ${patch}` where `${patch}` is the name of
the patch to be edited. From there, edit the code as needed. Once all edits are
made, use `stg refresh` to add the working changes to the patch. Once the patch
is updated, go back to the last patch in the series using the command
`stg goto $(stg series | tail -1 | cut -c2-)` (there may be an easier command to
do that, but this one works). Finally, once you are back at the top of the stack
of patches, you can use `stg export -d ../` to export the updated patch.

# Debugging

On your host machine (i.e., not the development environment container), it will
help to modify the kernel.core_pattern in your /etc/sysctl.conf file. See
`http://man7.org/linux/man-pages/man5/core.5.html` for more information on how
the different values work, and the `%` placeholders. This will allow you to
debug RAMCloud crashes using GDB by placing core dumps at a known location.

# Looking at ZooKeeper Contents

It is easy to use the ZooKeeper CLI to look at the contents of ZooKeeper, which
is used by RAMCloud to store persistent configuration information. Simply run
the command

    docker run -it --rm --net ramcloud-net zookeeper zkCli.sh -server ramcloud-node-1

The command may be run within the dev-env or on your host, it does not matter.

# Modifying Standalone Test Packages

Changes to command-line packages used in the development environment container
need to be made to config/Dockerfile.dev, and changes to command-line packages
used in the node containers running RAMCloud or ZooKeeper need to be made to
config/Dockerfile.node

Changes to the packages used in the Standalone Tests (python 3.7) need to be
made to config/Pipfile. Then, within the development environment container,
do the following:

    cd /src/config
    pipenv update

This will modify the config/Pipfile.lock file with the appropriate new packages,
existing package versions, and modified hash values.

# Known Standalone Test Issues

Standalone tests may exhibit the warning shown below. 

```
/usr/lib/python3.7/copy.py:291: ResourceWarning: unclosed <socket.socket fd=51, family=AddressFamily.AF_UNIX, type=SocketKind.SOCK_STREAM, proto=0>
  for key, value in slotstate.items():
```

Or possibly also this one.

```
sys:1: ResourceWarning: unclosed <socket.socket fd=50, family=AddressFamily.AF_UNIX, type=SocketKind.SOCK_STREAM, proto=0, raddr=/var/run/docker.sock>
```

However, per conversation on this link shown here, these aren't something to be
concerned about.

https://github.com/psf/requests/issues/3912


# Known Unit Test Issues

The following unit tests appear to fail consistently after rebasing RAMCloud.
Further investigation required.

InfRcTransportTest.sanityCheck
InfRcTransportTest.ClientRpc_sendZeroCopy
InfRcTransportTest.InfRcSession_abort_onClientSendQueue
InfRcTransportTest.InfRcSession_abort_onOutstandingRpcs
InfRcTransportTest.InfRcSession_cancelRequest_rpcPending
InfRcTransportTest.InfRcSession_cancelRequest_rpcSent
InfRcTransportTest.getRpcInfo
InfRcTransportTest.ClientRpc_sendRequest_sessionAborted
InfRcTransportTest.ServerRpc_getClientServiceLocator
InfUdDriverTest.basics

For other tests, we pass for 90% of the time it is ran, but there are still
failures, segfaults, or freezes for the other 10%. None of the freezes have 
been replicated in gdb, but the failures and segfaults have been.

The most common segfaults are (1) in MultiFileStorage.cc:784 trying to read
from a specific file on disk, with the file set up in a manner different than
on prod, and (2) in UdpDriver.cc:357 making a recieve messages socket call
using a mock Syscall object, also different from prod behavior.

Other less frequent segfaults include: WorkerTimer.cc:379, ServerRpcPool.h:55,
and ServerIdRpcWrapper.cc:180.

The most common test failure is at PortAlarmTest.cc:292. This line used to
crash, but using an assert on the null-check prevents the pointer from being
used once it's determined that it's null. Fixing the cause behind the problem
is less intuitive. It involves modifying PortAlarmTest's static member variables
and/or AlartmentPort to reset properly once PortAlarmTest is completely reset.
This class's tests pass on the first run for all unit tests for RAMCloud, but
fail on subsequent runs precisely for this reason.

Other less frequent observed test failures include:
WorkerTimerTest.stopInternal_handlerDoesntFinishQuickly,
WorkerTimerTest.start_startDispatchTimer,
WorkerTimerTest.sync,
SegmentManagerTest.freeUnreferencedSegments_blockByWorkerTimer,
PortAlarmTest.triple_alarm,
LoggerTest.logMessage_discardEntriesBecauseOfOverflow,
UdpDriverTest.readerThreadMain_errorInRecvmmsg.
