#!/usr/bin/env python

import re
import argparse
import subprocess


USAGE = '''\
Usage: mon-put-instance-data.py [options]

  Collects memory, swap, and disk space utilization on a cloud-init
  instance and sends this data as custom metrics to Amazon CloudWatch.

Description of available options:

  --mem-util          Reports memory utilization in percentages.
  --mem-used          Reports memory used in megabytes.
  --mem-avail         Reports available memory in megabytes.
  --swap-util         Reports swap utilization in percentages.
  --swap-used         Reports allocated swap space in megabytes.
  --disk-path=PATH    Selects the disk by the path on which to report.
  --disk-space-util   Reports disk space utilization in percentages.
  --disk-space-used   Reports allocated disk space in gigabytes.
  --disk-space-avail  Reports available disk space in gigabytes.

  --aggregated[=only]    Adds aggregated metrics for instance type, AMI id, and region.
                         If =only is specified, does not report individual instance metrics
  --auto-scaling[=only]  Reports Auto Scaling metrics in addition to instance metrics.
                         If =only is specified, does not report individual instance metrics

  --mem-used-incl-cache-buff  Count memory that is cached and in buffers as used.
  --memory-units=UNITS        Specifies units for memory metrics.
  --disk-space-units=UNITS    Specifies units for disk space metrics.

    Supported UNITS are bytes, kilobytes, megabytes, and gigabytes.

  --aws-credential-file=PATH  Specifies the location of the file with AWS credentials.
  --aws-access-key-id=VALUE   Specifies the AWS access key ID to use to identify the caller.
  --aws-secret-key=VALUE      Specifies the AWS secret key to use to sign the request.
  --aws-iam-role=VALUE        Specifies the IAM role used to provide AWS credentials.

  --from-cron  Specifies that this script is running from cron.
  --verify     Checks configuration and prepares a remote call.
  --verbose    Displays details of what the script is doing.
  --version    Displays the version number.
  --help       Displays detailed usage information.

Examples

 To perform a simple test run without posting data to Amazon CloudWatch

  ./mon-put-instance-data.py --mem-util --verify --verbose

 To set a five-minute cron schedule to report memory and disk space utilization to CloudWatch

  */5 * * * * ~/aws-scripts-mon/mon-put-instance-data.py --mem-util --disk-space-util --disk-path=/ --from-cron

This script was inspired by aws-scripts-mon:
http://docs.amazonwebservices.com/AmazonCloudWatch/latest/DeveloperGuide/mon-scripts-perl.html
'''

KILO = 1024
MEGA = KILO * 1024
GIGA = MEGA * 1024


UNITS = {
    'Bytes': 1,
    'Kilobytes': KILO,
    'Megabytes': MEGA,
    'Gigabytes': GIGA,
}


def parse_args():
    ap = argparse.ArgumentParser()
    #ap.add_argument('--help', dest='show_help', action='store_true')
    #ap.add_argument('--version', dest='show_version', action='store_true')
    ap.add_argument('--mem-util', dest='report_mem_util', action='store_true')
    ap.add_argument('--mem-used', dest='report_mem_used', action='store_true')
    ap.add_argument('--mem-avail', dest='report_mem_avail', action='store_true')
    ap.add_argument('--swap-util', dest='report_swap_util', action='store_true')
    ap.add_argument('--swap-used', dest='report_swap_used', action='store_true')
    ap.add_argument('--disk-path', dest='mount_path', nargs='+')
    ap.add_argument('--disk-space-util', dest='report_disk_util', action='store_true')
    ap.add_argument('--disk-space-used', dest='report_disk_used', action='store_true')
    ap.add_argument('--disk-space-avail', dest='report_disk_avail', action='store_true')
    #ap.add_argument('--auto-scaling:s', dest='auto_scaling')
    #ap.add_argument('--aggregated:s', dest='aggregated')
    ap.add_argument('--memory-units', dest='mem_units', choices=UNITS.keys(), default='Megabytes')
    ap.add_argument('--disk-space-units', dest='disk_units', choices=UNITS.keys(), default='Gigabytes')
    ap.add_argument('--mem-used-incl-cache-buff', dest='mem_used_incl_cache_buff', action='store_true')
    ap.add_argument('--verify', dest='verify', action='store_true')
    ap.add_argument('--from-cron', dest='from_cron', action='store_true')
    ap.add_argument('--verbose', dest='verbose', action='store_true')
    #ap.add_argument('--aws-credential-file:s', dest='aws_credential_file', action='store_true')
    #ap.add_argument('--aws-access-key-id:s', dest='aws_access_key_id', action='store_true')
    #ap.add_argument('--aws-secret-key:s', dest='aws_secret_key', action='store_true')
    ap.add_argument('--enable-compression', dest='enable_compression', action='store_true')
    #ap.add_argument('--aws-iam-role:s', dest='aws_iam_role', action='store_true')

    args = ap.parse_args()
    return args


def add_metric(*args, **kwargs):
    print(args, kwargs)


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

    if args.mem_used_incl_cache_buff:
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

        if args.report_disk_util:
            disk_util = 0
            disk_util = 100 * disk_used / disk_total if disk_total > 0 else 0
            add_metric('DiskSpaceUtilization', 'Percent', disk_util, fsystem, mount)
        if args.report_disk_used:
            add_metric('DiskSpaceUsed', disk_units, disk_used / disk_unit_div, fsystem, mount)
        if args.report_disk_avail:
            add_metric('DiskSpaceAvailable', disk_units, disk_avail / disk_unit_div, fsystem, mount)


def main():

    # parse and validate args
    args = parse_args()
    report_mem = bool(args.report_mem_util or args.report_disk_used or args.report_mem_avail or args.report_swap_util or args.report_swap_used)
    report_disk = bool(args.report_disk_util or args.report_disk_used or args.report_disk_avail)
    if report_disk and not args.mount_path:
        raise SystemExit('Value of disk path is not specified.')
    if args.mount_path and not report_disk:
        raise SystemExit('Metrics to report disk space are provided but disk path is not specified.')
    if not (report_mem or report_disk):
        raise SystemExit('No metrics specified for collection and submission to CloudWatch.')

    if report_mem:
        collect_memory_and_swap_metrics(args)
    if report_disk:
        collect_disk_space_metrics(args)


if __name__ == '__main__':
    main()
