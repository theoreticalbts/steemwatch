FROM phusion/baseimage:0.9.19

RUN                         \
    apt-get update &&       \
    apt-get install -y      \
        python3             \
        python-virtualenv   \
    &&                      \
    apt-get clean &&        \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ADD . /usr/local/src/steemwatch

RUN                         \
    VE=/usr/local/ve/steemwatch &&                                \
    virtualenv -p $(which python3) "$VE" &&                       \
    "$VE/bin/python3" --help