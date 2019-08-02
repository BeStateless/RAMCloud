# Install the dependencies required to build RAMCloud. This is used as the development environment.
FROM debian:buster as dev
RUN apt-get update \
 && apt-get install --yes \
      build-essential \
      g++ \
      git \
      libboost-dev \
      libboost-filesystem-dev \
      libboost-program-options-dev \
      libboost-system-dev \
      libibverbs-dev \
      libpcre++-dev \
      libssl-dev \
      libzookeeper-mt-dev \
      protobuf-compiler \
      stgit \
 && rm -rf /var/lib/apt/lists/*
ENV INSTALL_DIR=/tmp/RAMCloud-install

# Build RAMCloud from the patched source code.
FROM dev as build
COPY . /src
WORKDIR /src
RUN ./patch && ./config/make-ramcloud

# Copy the build artifacts from the build image and only install the runtime dependencies for RAMCloud.
FROM debian:buster
RUN apt-get update \
 && apt-get install --yes \
      libboost-filesystem1.67.0 \
      libboost-program-options1.67 \
      libboost-system1.67.0 \
      libibverbs1 \
      libpcrecpp0v5 \
      libprotobuf17 \
      libssl1.1 \
      libzookeeper-mt2 \
 && rm -rf /var/lib/apt/lists/*
COPY --from=build /tmp/RAMCloud-install /usr/local
