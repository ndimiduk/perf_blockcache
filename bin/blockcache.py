#
# Use fabric to test different blockcache configurations.
#
# test:
#   start_hbase:<conf>
#   test_seq_write:<conf>,<n>
#   flush_table:<conf>
#   warm_cache:<conf>,<n>
#   test_rand_read:<conf>,<n>
#   stop_hbase:<conf>
#   archive_logs:<conf>,<n>
#   clear_logs:<conf>
#
# test --reuse-data
#   start_hbase:<conf>
#   warm_cache:<conf>,<n>
#   test_rand_read:<conf>,<n>
#   stop_hbase:<conf>
#   archive_logs:<conf>,<n>
#   clear_logs:<conf>
#

from __future__ import with_statement
from contextlib import closing
from fabric.api import *
from fabric.contrib.files import exists, sed
from os import environ, getcwd
from os.path import basename, dirname, exists, splitext
from StringIO import StringIO
from tempfile import mkstemp

env.hosts = env.hosts or ['localhost']

hbase_home = environ.get('HBASE_HOME', '/usr/lib/hbase')
configs_base = environ.get('CONFIGS_BASE', getcwd())
logs_home = '%s/runs' % configs_base
tmpfs_path = environ.get('TMPFS_PATH', '/tmp/bucketcache_tmpfs')

@task
def list_configs():
    "[] List available HBase configs"
    paths = local('ls -1d %s/*/' % configs_base, capture=True).split()
    configs = set([basename(dirname(x)) for x in paths])
    print configs
    return configs

def is_config(conf):
    "Return true if `conf` is a valid config name, false otherwise"
    return list_configs() & set([conf])

def assert_conf(conf):
    if not is_config(conf):
        raise Exception('%s is not a known config.' % conf)

def build_cmd(cmd, conf=None):
    if conf:
        assert_conf(conf)
        return '%s/bin/%s --config %s/%s' % (hbase_home,cmd,configs_base,conf)
    else:
        return '%s/bin/%s' % (hbase_home,cmd)

@task
def mount_tmpfs(mb):
    "[mb] Mount the tmpfs with a max capacity of `mb`"
    run('mkdir -p %s' % tmpfs_path)
    sudo('mount -t tmpfs tmpfs %s -o size=%sm' % (tmpfs_path,mb))

@task
def umount_tmpfs():
    "[] Unmount the tmpfs"
    sudo('umount %s' % tmpfs_path)

@task
def clear_logs(conf):
    "[conf] Delete existing HBase logs"
    assert_conf(conf)
    local('source %s/%s/hbase-env.sh && rm -rf $HBASE_LOG_DIR/*' % (configs_base,conf))

@task
def archive_logs(conf, n):
    "[conf, n] Archive any hbase/logs and test run logs."
    local('mkdir -p %s' % logs_home)
    archive = '%s/%s-%s.tar' % (logs_home, conf, n)
    test_logs = 'find . -iname "*%s*%sM*txt"' % (conf,n)
    log_dir = local('source %s/%s/hbase-env.sh && echo $HBASE_LOG_DIR' % (configs_base,conf), capture=True)
    print log_dir
    with lcd(log_dir):
        local('tar cvf %s *' % archive)
    with lcd(logs_home):
        local('tar rvf %s $(%s)' % (archive,test_logs))
        local('%s | xargs rm' % test_logs)
    local('gzip %s' % archive)

@task
def stop_hbase(conf):
    "[conf] Stop HBase using the specified `conf`"
    sudo('%s stop regionserver' % build_cmd('hbase-daemon.sh', conf), user='hbase')
    sudo('%s stop master' % build_cmd('hbase-daemon.sh', conf), user='hbase')

@task
def start_hbase(conf):
    "[conf] Start HBase using the specified `conf`"
    # ./bin/hbase-daemon.sh --config ../perf_blockcache/on-heap-3g
    sudo('%s start regionserver' % build_cmd('hbase-daemon.sh', conf), user='hbase')
    sudo('%s start master' % build_cmd('hbase-daemon.sh', conf), user='hbase')

@task
def drop_table(conf=None, table='TestTable'):
    "[conf=None, table='TestTable'] Drop the table"
    # echo "disable 'TestTable'" | ./bin/hbase shell
    local('echo "disable \'%s\'" | %s shell' % (table,build_cmd('hbase', conf)))
    # echo "drop 'TestTable'" | ./bin/hbase shell
    local('echo "drop \'%s\'" | %s shell' % (table,build_cmd('hbase', conf)))

@task
def flush_table(conf=None, table='TestTable'):
    "[conf=None, table='TestTable'] Flush table buffers"
    # echo "disable 'TestTable'" | ./bin/hbase shell
    local('echo "disable \'%s\'" | %s shell' % (table,build_cmd('hbase', conf)))
    # echo "enable 'TestTable'" | ./bin/hbase shell
    local('echo "enable \'%s\'" | %s shell' % (table,build_cmd('hbase', conf)))

def parse_memsize(conf):
    """How large is the memory footprint of conf, based on its name.

Will be fooled by a character sequence of 'g' followed by a '-'.
    """

    def is_int(x):
        try:
            int(x)
            return True
        except ValueError:
            return False

    return int([x[:-1] for x in conf.split('-') if x.endswith('g') and is_int(x[:-1])][0])

def parse_cachesize(conf):
    "Guess at a config's cache size, based on name."
    return parse_memsize(conf) / 2

@task
def warm_cache(conf=None, n=None, table='TestTable'):
    "[conf=None, n=None, table='TestTable'] Warm the BlockCache."
    # Use hbase shell> count (assumes patched table.rb) when n is not provided
    # or n > Cache, randomRead otherwise
    if not n or int(n) <= parse_cachesize(conf) :
        local('echo "count \'TestTable\', INTERVAL => 100000" | {hbase} shell'.format(hbase=build_cmd('hbase', conf)))
    else:
        test_rand_read(conf, n, False, 0.1, 1)

@task
def test_seq_write(conf, n):
    "[conf, n] Run sequentialWrite using `conf` with `n` clients"
    # TODO: push client count logic down into PerfEval tool.
    # assumes ~1kb rowsize!
    total_rows = 1024 * 1024 * int(n)
    splits = 5 # TODO: don't hard-code 5 clients.
    rows_per_client = total_rows / 5
    cmd = '{hbase} org.apache.hadoop.hbase.PerformanceEvaluation --nomapred --rows={rows_per_client} --compress=LZO --presplit={n} sequentialWrite {splits}'.format(hbase=build_cmd('hbase', conf), n=n, splits=splits, rows_per_client=rows_per_client)
    # log_file = '{logs_home}/blockcache-{conf}-{total_rows_mm}Mrows-{n}splits-LZO-sequentialWrite-{n}n'.format(conf=conf, n=n, total_rows_mm=total_rows_mm, logs_home=logs_home)
    # ./bin/hbase --config ../perf_blockcache/on-heap-3g org.apache.hadoop.hbase.PerformanceEvaluation --nomapred --rows=1000000 --compress=LZO --presplit=5 sequentialWrite 5 &> /grid/1/ndimiduk/blockcache-on-heap-3g-5Mrows-5splits-LZO-sequentialWrite-5n
    local(cmd)

@task
def test_rand_read(conf, n, log=True, sample=0.01, iterations=3):
    "[conf, n, log=True, sample=0.01, iterations=3] Run randomRead using `conf` with `n` clients, `iterations` times."
    total_rows = 1024 * 1024 * int(n)
    splits = 5
    rows_per_client = total_rows / 5
    if log:
        # only collect latency data when we collect logs
        latency = '--latency'
    else:
        latency = ''
    cmd = '{hbase} org.apache.hadoop.hbase.PerformanceEvaluation --nomapred --rows={rows_per_client} --sampleRate={sample} {latency} randomRead {splits}'.format(hbase=build_cmd('hbase', conf), splits=splits, rows_per_client=rows_per_client, sample=sample, latency=latency)
    for r in range(iterations):
        if log:
            log_file = '{logs_home}/blockcache-{conf}-{n}Mrows-{splits}splits-LZO-0.01samplerate-randomRead-{splits}n.{r}.txt'.format(logs_home=logs_home, conf=conf, splits=splits, n=n, r=r)
            # ./bin/hbase --config ... org.apache.hadoop.hbase.PerformanceEvaluation --nomapred --rows=1000000 --sampleRate=0.01 --latency randomRead 5
            local('echo %s > %s' % (cmd, log_file))
            local('%s >> %s 2>&1' % (cmd, log_file))
        else:
            local(cmd)

@task
def test_seq_read(conf, n):
    "[conf, n] Run SequentialRead using `conf` with `n` clients"
    total_rows = 1024 * 1024 * int(n)
    splits = 5
    rows_per_client = total_rows / 5
    cmd = '{hbase} org.apache.hadoop.hbase.PerformanceEvaluation --nomapred --rows={rows_per_client} sequentialRead {splits}'.format(hbase=build_cmd('hbase', conf), splits=splits, rows_per_client=rows_per_client)
    # log_file = '{logs_home}/blockcache-{conf}-{n}Mrows-{splits}splits-LZO-sequentialRead-{n}n'.format(logs_home=logs_home, conf=conf, n=n, total_rows_mm=total_rows_mm)
    # ./bin/hbase --config ../perf_blockcache/on-heap-3g org.apache.hadoop.hbase.PerformanceEvaluation --nomapred --rows=1000000 sequentialRead 5 &> /grid/1/ndimiduk/blockcache-on-heap-3g-5Mrows-5splits-LZO-sequentialRead-5n
    local(cmd)
