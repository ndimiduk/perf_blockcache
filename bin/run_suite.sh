#!/bin/bash
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# A little automation for running the test on different HBAse configurations
# and database sizes.
#

set -e
set -x

# CONTROL is the command execution tool being driven by this script.
CONTROL="/grid/1/ndimiduk/fab/bin/fab -f /grid/1/ndimiduk/perf_blockcache/blockcache.py"

do_test() {
    #
    # Run a single test. Assumes the database has already been established and
    # the config actually exists.
    #
    # $1: conf, The HBase configuration name to use, ie, "bucket-heap-20g"
    # $2: size, The size of the database under test, ie, "10".
    #

    conf=$1
    size=$2

    ${CONTROL} start_hbase:${conf}
    sleep 30 # let the cluster settle down
    ${CONTROL} warm_cache:${conf},${size}
    ${CONTROL} test_rand_read:${conf},${size}
    ${CONTROL} stop_hbase:${conf}
    sleep 30 # let the logs sync to disk
    ${CONTROL} archive_logs:${conf},${size}
    ${CONTROL} clear_logs:${conf}
}

do_suite() {
    #
    # Run the full suite over the range of database sizes. Right now, all
    # config names are hard-coded, as are the database sizes. Sizes are
    # calculated based on the size of the configuration's memory footprint and
    # make the assumption that ~50% of memory is dedicated to BlockCache.
    #
    # $1: memory footprint, the amount of memory dedicated to HBase. Used to
    # identify a specific configuration directory.
    #

    for size in $(echo "($1 * 0.5)/1" | bc) $(echo "($1 * 1.5)/1" | bc) $(echo "($1 * 4.5)/1" | bc) ; do
        # create, populate table
        ${CONTROL} "start_hbase:lrublockcache-${1}g"
        sleep 30 # let the cluster settle down
        ${CONTROL} "test_seq_write:lrublockcache-${1}g,${size}"
        ${CONTROL} "stop_hbase:lrublockcache-${1}g"
        sleep 30 # let the logs sync to disk
        ${CONTROL} "clear_logs:lrublockcache-${1}g"

        # handle special config: bucket-tmpfs-XXg
        # this step may be unnecessary if already have a tmpfs mount. check
        # `mount | grep tmpfs` to see if you have something usable. Just be
        # sure to update the path specified in the config's hbase-site.xml at
        # the 'hbase.bucketcache.ioengine' property.
        ${CONTROL} "mount_tmpfs:$(echo "${1} * 6000" | bc)"
        do_test "bucket-tmpfs-${1}g" $size
        ${CONTROL} umount_tmpfs

        # run through standard configs. prefer off-heap impls, especially at
        # higher memory sizes.
        for conf in "slabcache-${1}g" "bucket-offheap-${1}g" "lrublockcache-${1}g" ; do
            do_test $conf $size
        done

    done
}

do_suite 8
do_suite 20
do_suite 50
do_suite 60
