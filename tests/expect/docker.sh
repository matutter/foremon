#!/bin/bash
#
# Run expect tests in a docker container. Pass the python-version as arg[1] to
# use a different docker image.
#
#

root="$( cd "$( dirname "${BASH_SOURCE[0]}" )/../.." >/dev/null 2>&1 && pwd )"

PYTHON_VERSION=${PYTHON_VERSION:-"3.8"}

cd $root

docker run -it --rm \
    -e TERM=$TERM \
    -v $root/config:/config \
    -v $root/tests:/tests \
    -v $root/dist:/dist \
    --entrypoint bash \
    python:$PYTHON_VERSION \
    -c '
apt-get update -y -q
apt-get install -y -q expect
pip install /dist/foremon*.tar.gz
for f in `ls -1 tests/expect/*.exp`; do
    expect $f
done
'
