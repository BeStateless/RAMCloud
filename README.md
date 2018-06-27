# RAMCloud

This is the Stateless fork of RAMCloud. Instead of maintaining a normal git fork
we use [stgit](http://www.procode.org/stgit/) to maintain a patchset. This
simplifies things by keeping the upstream history entirely outside of our repo
and the set of stateless-specific patches is very clear. This should make it
easy to incorporate our changes upstream while pulling in new changes from
upstream regularly.

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
