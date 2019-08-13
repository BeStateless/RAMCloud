# RAMCloud

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
Then, inside the development environment, you will want to obtain the patched
code by running:

    ./patch

That will place the patched RAMCloud source at `./RAMCloud` relative to the
repository root. Once the patched code has been obtained, RAMCloud can be built
with the following command run in the development environment shell:

    ./config/make-ramcloud

This will place all of the RAMCloud build artifacts at `./RAMCloud-install`.

(Optional) One other thing you can do within this development environment shell 
is run the unit tests for RAMCloud. You can do this with:

    ./config/make-ramcloud-test

As outlined in the `Known Unit Test Issues` section, there are some known 
issues with the unit tests.

After RAMCloud has been built (via make-ramcloud), a local cluster can be built
using the commands from the repository root on your host machine, i.e. _not_ in
the development environment container:

    cd ./config
    docker-compose up --build --detach

This will build a `ramcloud-test` Docker image from the build artifacts at
`./RAMCloud-install`, then spin up a three-node ZooKeeper ensemble, three
RAMCloud coordinators, and three RAMCloud servers. Once that infrastructure has
been spun up, a RAMCloud client container will be spawned that runs the
`rc-client` binary to test the RAMCloud functionality. Presently this process
relies on timed `sleep` commands to stage the bringup of the components
correctly. We really should use docker-compose health checks to make sure each
stage completes before moving on to the next one, but that is substantially more
difficult to implement, so `sleep` works for now. The cluster takes about 30
seconds to come up. Run the following to look at the RAMCloud client test
program logs to see if it completed successfully (run this on your host, not in
the development environment container):

    docker logs config_rc-client-1_1

The exit status of the RAMCloud client test can be seen using the command run
from your host, not from the development environment container:

    docker inspect --format '{{.State.ExitCode}}' config_rc-client-1_1

If the exit status is `0` then the test completed successfully, otherwise a
failure occurred.

To take down the cluster run this command from the `./config` directory outside
the development environment container:

    docker-compose down --timeout 0

To make changes to the RAMCloud code simply make changes to the code in the
`./RAMCloud` directory on your host machine, and then run
`./config/make-ramcloud` again on the the development environment bash shell.
Once RAMCloud is rebuilt, you can run `docker-compose up --build --detach` on
your host again to run the updated code.

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

# Making New Changes

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

# Incremental Development

To enter a development environment issue the following command from the
repository root:

    ./config/dev-env

Once in the development environment the following commands can be run to patch
the RAMCloud source and build RAMCloud

    ./patch
    ./config/make-ramcloud

This will place the patched RAMCloud source in the `RAMCloud` directory in the
repository root, and it will store the build artifacts in `RAMCloud-install`
also in the repository root. Once the patched source is created, you can edit
the files in the RAMCloud directory and rerun `./config/make-ramcloud` to
perform an incremental build. If you need to make a clean build you can just
delete the RAMCloud directory and the contents of the RAMCloud-install directory
and run the above commands again to rebuild it.

# Debugging

On your host machine (i.e., not the development environment container), it will
help to modify the kernel.core_pattern in your /etc/sysctl.conf file. See 
`http://man7.org/linux/man-pages/man5/core.5.html` for more information on how 
the different values work, and the `%` placeholders.

# Containers

There are two dockerfiles, `./config/Dockerfile` and `./config/Dockerfile.local`
that can be used to make a Docker image containing all of the `rc-coordinator`,
`rc-server`, and `rc-client` binaries. The `./config/Dockerfile` builds the
binaries from source. The `./config/Dockerfile.local` assumes the `dev-env` has
been used to build RAMCloud already and that the RAMCloud build artifacts are in
`./RAMCloud-install`. The `./config/Dockerfile.local` is designed to be very
fast at making updated containers. The `./config/Dockerfile` is designed to be
more like an "official" build and builds RAMCloud from source patched using the
patch series in the repository. That build is much slower, but doesn't require
manual building within a dev-env.

The script `./config/make-container` is a wrapper around both of the docker
files. You can use `./config/make-container` to make the full build. You can use
`./config/make-container --local` to make the quick build assuming you've
already run `./config/make-ramcloud` in the `dev-env`.

# Docker Compose

There is a docker-compose file at `./config/docker-compose.yml` that is
configured to set up a three-node ZooKeeper ensemble, launch three RAMCloud
Coordinator instances, launch three RAMCloud server instances, and then launch
the RAMCloud client test binary to make sure that the RAMCloud server is
functional.

The environment variable `RAMCLOUD_DOCKERFILE_EXTENSION` controls whether or not
the `ramcloud-test` image is built from the `Dockerfile` or `Dockerfile.local`
as described above. The default is to build from `Dockerfile.local`. You can do
`export RAMCLOUD_DOCKERFILE_EXTENSION=` to use the long build.

Use `docker-compose build` to build the necessary containers. Use
`docker-compose up` to launch the testing environment synchronously. Use
`docker-compose up --detach` to launch the testing environment in the
background. Finally, you can use `docker-compose up --detach --build` to build
_and_ launch the testing environment in the background in one command.

# Looking at ZooKeeper Contents

It is easy to use the ZooKeeper CLI to look at the contents of ZooKeeper, which
is used by RAMCloud to store persistent configuration information. Simply run
the command

    docker run -it --rm --net config_ramcloud-test zookeeper zkCli.sh -server zookeeper-1

# Known Unit Test Issues

The unit tests pass for 90% of the time it is ran, but has failures, segfaults,
or freezes for the other 10%. None of the freezes have been replicated in gdb,
but the failures and segfaults have been.

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
