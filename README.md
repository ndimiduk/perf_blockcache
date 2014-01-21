# HBase BlockCache Performance Showdown

Automation scripts for comparing different HBase `BlockCache` implementations.
It uses the `PerformanceEvaluation` tool to submit queries against the HBase
RegionServer and collects their reported response latencies. Nothing in this
harness is specific to `BlocCache` -- any configurations can be tested
side-by-side. However, more work is needed to test other attributes of the
system.

## Setup

`bin/run_suite.sh` is the main entry point for running these tests. It is a
bash script that drives repeated invocations of the `bin/blockcache.py` script.
The latter does the work of launching HBase with a specific configuration,
populating the test table, running the test, and collecting up the logs.
Everything assumes it's running on a single node deployment, so there's no
fancy log collection or aggregation across multiple hosts.

To run the full suite of tests, create a config directory for each
configuration you want to test. The scripts assume these all share the same
base path.

You also need to apply the `shell_count.patch` to your HBase install. That lets
the test harness warm cache for the smallest database sizes with minimal
hassle.

Everything here was run against an Ambari-established HDP-2.0 installation.
Ambari is only used to establish the initial installation. After that,
configurations and process management are all handled by the scripts.

There are patch files provided under `config_patches` for a bunch of different
`BlockCache` implementations and memory footprint sizes. They are designed to
maximize the size of a specific `BlockCache` implementation so as to illustrate
relative performance. Treat them as guidelines for building your own configs,
*not* as production-ready recommendations. These are generated as both a delta
from the stock `conf` directory shipped with HBase, and as the delta from the
Ambari generated config. The Ambari diffs are more informative in terms of
illustrating what changes are necessary to build a particular configuration
over your existing config.

## Usage

`bin/blockcache.py` assumes a couple environment variables have been set,
namely `HBASE_HOME` and `CONFIGS_BASE`. Have a look at the header of that
script for further details.

Make sure you've stopped the HBase processes, and then just run
`bin/run_suite.sh`. This will kick off the testing. After a configuration is
run, the HBase logs and the `PerformanceEvaluation` output are archived into a
tgz under `$CONFIGS_BASE/runs`. Each archive is named for the set of parameters
from that particular test, ie, 'bucket-offheap-8g-12.tar.gz.

Once your tests have been run, use `bin/dumpstats.py` to parse the logs and
generate summary statistics. The result is a text file sitting next to the
archive ending in `-summary.txt`, something like
'bucket-offheap-8g-12.txt-summary.txt'. `dumpstats.py` is also controlled by
environment variable, so you can set `$LOGS_HOME` or just run from the `runs`
directory containing all the archives.
