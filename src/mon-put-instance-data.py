#!/usr/bin/env python

'''
This script was inspired by aws-scripts-mon:
http://docs.amazonwebservices.com/AmazonCloudWatch/latest/DeveloperGuide/mon-scripts-perl.html

Use '--help' to see full usage.

Examples

 To perform a simple test run without posting data to Amazon CloudWatch

  ./mon-put-instance-data.py --mem-util --verify --verbose

 To set a five-minute cron schedule to report memory and disk space utilization to CloudWatch

  */5 * * * * /opt/cw-scripts-mon/mon-put-instance-data.py --mem-util --disk-space-util --disk-path=/ --from-cron

  A complementary systemd.timer unit is provided in contrib/ directory, if you do not want to use cron.
'''

import re
import random
import argparse
import subprocess
from time import sleep
from pprint import pprint
from datetime import datetime
from urllib.request import urlopen

import boto3


KILO = 1024
MEGA = KILO * 1024
GIGA = MEGA * 1024


UNITS = {
    'Bytes': 1,
    'Kilobytes': KILO,
    'Megabytes': MEGA,
    'Gigabytes': GIGA,
}


METRIC_DATA = []


def is_running_on_ec2():
    # https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/identify_ec2_instances.html
    try:
        return open('/sys/hypervisor/uuid').read().startswith('ec2')
    except FileNotFoundError:
        return False


EC2 = is_running_on_ec2()


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        '--cpu-util', dest='report_cpu_util', action='store_true',
        help='Reports CPU utilization in percentages.'
    )
    ap.add_argument(
        '--mem-util', dest='report_mem_util', action='store_true',
        help='Reports memory utilization in percentages.'
    )
    ap.add_argument(
        '--mem-used', dest='report_mem_used', action='store_true',
        help='Reports memory used in megabytes.'
    )
    ap.add_argument(
        '--mem-avail', dest='report_mem_avail', action='store_true',
        help='Reports available memory in megabytes.'
    )
    ap.add_argument(
        '--swap-util', dest='report_swap_util', action='store_true',
        help='Reports swap utilization in percentages.'
    )
    ap.add_argument(
        '--swap-used', dest='report_swap_used', action='store_true',
        help='Reports allocated swap space in megabytes.'
    )
    ap.add_argument(
        '--disk-path', dest='mount_path', nargs='+',
        help='Selects the disk by the path on which to report.'
    )
    ap.add_argument(
        '--disk-space-util', dest='report_disk_util', action='store_true',
        help='Reports disk space utilization in percentages.'
    )
    ap.add_argument(
        '--disk-space-used', dest='report_disk_used', action='store_true',
        help='Reports allocated disk space in gigabytes.'
    )
    ap.add_argument(
        '--disk-space-avail', dest='report_disk_avail', action='store_true',
        help='Reports available disk space in gigabytes.'
    )
    #ap.add_argument('--auto-scaling:s', dest='auto_scaling')
    #ap.add_argument('--aggregated:s', dest='aggregated')
    ap.add_argument(
        '--memory-units', dest='mem_units', choices=UNITS.keys(), default='Megabytes',
        help='Specifies units for memory metrics.'
    )
    ap.add_argument(
        '--disk-space-units', dest='disk_units', choices=UNITS.keys(), default='Gigabytes',
        help='Specifies units for disk space metrics.'
    )
    ap.add_argument(
        '--mem-used-incl-cache-buff', dest='mem_used_incl_cache_buff', action='store_true',
        help='Count memory that is cached and in buffers as used.'
    )
    ap.add_argument(
        '--cpu-sample-interval', type=float, default=1.0,
        help='Sample interval when collecting CPU utilization metrics.'
    )
    ap.add_argument(
        '--verify', dest='verify', action='store_true',
        help='Checks configuration and prepares a remote call.'
    )
    ap.add_argument(
        '--from-cron', dest='from_cron', action='store_true',
        help='Specifies that this script is running from cron.'
    )
    #ap.add_argument('--verbose', dest='verbose', action='store_true')
    #ap.add_argument('--aws-credential-file:s', dest='aws_credential_file', action='store_true')
    #ap.add_argument('--aws-access-key-id:s', dest='aws_access_key_id', action='store_true')
    #ap.add_argument('--aws-secret-key:s', dest='aws_secret_key', action='store_true')
    #ap.add_argument('--enable-compression', dest='enable_compression', action='store_true')
    #ap.add_argument('--aws-iam-role:s', dest='aws_iam_role', action='store_true')

    args = ap.parse_args()
    return args


def get_instance_id():
    if EC2:
        return get_instance_id_ec2()
    else:
        return get_instance_id_cloud_init()


def get_instance_id_ec2():
    resp = urlopen('http://169.254.169.254/latest/meta-data/instance-id')
    instance_id = resp.read().decode().rstrip()
    return instance_id


def get_instance_id_cloud_init():
    # CentOS-7-x86_64-GenericCloud-1809 (https://cloud.centos.org/centos/7/images/)
    # uses cloud-init 0.7.9. (https://cloudinit.readthedocs.io/en/0.7.9/topics/dir_layout.html)
    # This is a quite old version and should serve other distributions as well.
    # Don't reply on the directory layout of newer versions.
    # Note: CentOS has rebased its cloud-init source to upstream 18.2 on 2018-10-30
    # (https://git.centos.org/blobdiff/rpms!cloud-init.git/c60dcdee662fa585e0ef611c5cd5c48078259a68/SPECS!cloud-init.spec).
    # The new rpm is in @updates repo as of 2019-01 and should be in the next GenericCloud image.
    with open('/var/lib/cloud/data/instance-id') as f:
        instance_id = f.read().rstrip()
    return instance_id


def add_metric(name, unit, value, xdims=None):

    # xdims = extra dimensions?
    xdims = xdims or {}

    # construct a MetricDatum dict and put it into the MetricData list
    # https://docs.aws.amazon.com/AmazonCloudWatch/latest/APIReference/API_MetricDatum.html
    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudwatch.html#CloudWatch.Client.put_metric_data
    instance_id = get_instance_id()
    dims = {
        'InstanceId': instance_id
    }
    dims.update(xdims)
    dimensions = [{'Name': k, 'Value': v} for k, v in dims.items()]
    timestamp = datetime.utcnow()
    metric_datum = {
        'MetricName': name,
        'Dimensions': dimensions,
        'Timestamp': timestamp,
        'Values': [value],
        'Unit': unit,
    }
    METRIC_DATA.append(metric_datum)


def put_metric():

    if not METRIC_DATA:
        return

    client = boto3.client('cloudwatch')
    resp = client.put_metric_data(
        Namespace='System/Linux',
        MetricData=METRIC_DATA,
    )
    req_id = resp['ResponseMetadata']['RequestId']
    return req_id


def collect_memory_and_swap_metrics(args):

    # decide on the reporting units for memory and swap usage
    mem_units = args.mem_units
    mem_unit_div = UNITS[mem_units]

    # collect memory and swap metrics
    with open('/proc/meminfo', 'r') as m:
        raw_meminfo = m.read()

    meminfo = {}
    for line in raw_meminfo.splitlines():
        matched = re.match(r'^(.*?):\s+(\d+)', line)
        if matched:
            k, v = matched.groups()
            meminfo[k] = int(v)

    # meminfo values are in kilobytes
    mem_total = meminfo['MemTotal'] * KILO
    mem_free = meminfo['MemFree'] * KILO
    mem_cached = meminfo['Cached'] * KILO
    mem_buffers = meminfo['Buffers'] * KILO
    mem_avail = mem_free

    if not args.mem_used_incl_cache_buff:
        mem_avail += mem_cached + mem_buffers

    mem_used = mem_total - mem_avail
    swap_total = meminfo['SwapTotal'] * KILO
    swap_free = meminfo['SwapFree'] * KILO
    swap_used = swap_total - swap_free

    if args.report_mem_util:
        mem_util = 100 * mem_used / mem_total if mem_total > 0 else 0
        add_metric('MemoryUtilization', 'Percent', mem_util)
    if args.report_mem_used:
        add_metric('MemoryUsed', mem_units, mem_used / mem_unit_div)
    if args.report_mem_avail:
        add_metric('MemoryAvailable', mem_units, mem_avail / mem_unit_div)

    if args.report_swap_util:
        swap_util = 100 * swap_used / swap_total if swap_total > 0 else 0
        add_metric('SwapUtilization', 'Percent', swap_util)
    if args.report_swap_used:
        add_metric('SwapUsed', mem_units, swap_used / mem_unit_div)


def collect_disk_space_metrics(args):

    # exit on empty mount paths
    if not args.mount_path:
        raise SystemExit('Disk path is not specified')

    # decide on the reporting units for disk space usage
    disk_units = args.disk_units
    disk_unit_div = UNITS[disk_units]

    # collect disk space metrics
    raw_df = subprocess.check_output(
        ['df', '-klP'] + args.mount_path
    )

    df_lines = raw_df.decode().splitlines()[1:]
    for line in df_lines:
        fields = line.split()
        # Result of df is reported in 1k blocks
        disk_total = int(fields[1]) * KILO
        disk_used = int(fields[2]) * KILO
        disk_avail = int(fields[3]) * KILO
        fsystem = fields[0]
        mount = fields[5]

        xdims = {
            'Filesystem': fsystem,
            'MountPath': mount,
        }
        if args.report_disk_util:
            disk_util = 100 * disk_used / disk_total if disk_total > 0 else 0
            add_metric('DiskSpaceUtilization', 'Percent', disk_util, xdims=xdims)
        if args.report_disk_used:
            add_metric('DiskSpaceUsed', disk_units, disk_used / disk_unit_div, xdims=xdims)
        if args.report_disk_avail:
            add_metric('DiskSpaceAvailable', disk_units, disk_avail / disk_unit_div, xdims=xdims)


def collect_cpu_metrics(args):

    def _sample():
        with open('/proc/stat', 'r') as f:
            raw_stat = f.read()
        # user nice system idle iowait irq  softirq steal guest guest_nice
        #  0    1     2      3     4    5      6      7     8       9
        stats = [int(i) for i in raw_stat.splitlines()[0].split()[1:]]
        total = sum(stats[:8])
        idle = stats[3] + stats[4]
        busy = total - idle
        return (total, busy)

    # Based on the Linux implemention of psutil
    total1, busy1 = _sample()
    sleep(args.cpu_sample_interval)
    total2, busy2 = _sample()
    total_delta, busy_delta = max(0, total2 - total1), max(0, busy2 - busy1)
    try:
        cpu_util = 100 * busy_delta / total_delta
    except ZeroDivisionError:
        cpu_util = 0.0

    if args.report_cpu_util:
        add_metric('CPUUtilization', 'Percent', cpu_util)


def main():

    # parse and validate args
    args = parse_args()
    report_mem = bool(args.report_mem_util or args.report_mem_used or args.report_mem_avail or args.report_swap_util or args.report_swap_used)
    report_disk = bool(args.report_disk_util or args.report_disk_used or args.report_disk_avail)
    report_cpu = bool(args.report_cpu_util)
    if report_disk and not args.mount_path:
        raise SystemExit('Value of disk path is not specified.')
    if args.mount_path and not report_disk:
        raise SystemExit('Metrics to report disk space are provided but disk path is not specified.')
    if not (report_mem or report_disk or report_cpu):
        raise SystemExit('No metrics specified for collection and submission to CloudWatch. Try --help.')

    if report_mem:
        collect_memory_and_swap_metrics(args)
    if report_disk:
        collect_disk_space_metrics(args)
    if report_cpu:
        collect_cpu_metrics(args)

    if args.verify:
        pprint(METRIC_DATA)
        print('Verification completed successfully. No actual metrics sent to CloudWatch.')
        raise SystemExit()
    else:
        if args.from_cron:
            # avoid a storm of calls at the beginning of a minute
            sleep(random.randint(0, 20))
        req_id = put_metric()
        if not args.from_cron:
            print(f'Successfully reported metrics to CloudWatch. Reference Id: {req_id}')


if __name__ == '__main__':
    main()
