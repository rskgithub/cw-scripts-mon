#!/usr/bin/env python

import re
import argparse


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
MEGA = 1048576
GIGA = 1073741824


def parse_args():
    ap = argparse.ArgumentParser()
    #ap.add_argument('--help', dest='show_help', action='store_true')
    #ap.add_argument('--version', dest='show_version', action='store_true')
    ap.add_argument('--mem-util', dest='report_mem_util', action='store_true')
    ap.add_argument('--mem-used', dest='report_mem_used', action='store_true')
    ap.add_argument('--mem-avail', dest='report_mem_avail', action='store_true')
    ap.add_argument('--swap-util', dest='report_swap_util', action='store_true')
    ap.add_argument('--swap-used', dest='report_swap_used', action='store_true')
    #ap.add_argument('--disk-path:s' => \@mount_path')
    ap.add_argument('--disk-space-util', dest='report_disk_util', action='store_true')
    ap.add_argument('--disk-space-used', dest='report_disk_used', action='store_true')
    ap.add_argument('--disk-space-avail', dest='report_disk_avail', action='store_true')
    #ap.add_argument('--auto-scaling:s', dest='auto_scaling')
    #ap.add_argument('--aggregated:s', dest='aggregated')
    ap.add_argument('--memory-units', dest='mem_units')
    ap.add_argument('--disk-space-units', dest='disk_units')
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
    mem_units = 'Megabytes'
    mem_unit_div = MEGA
    #if (!defined($mem_units) || lc($mem_units) eq 'megabytes') {
    #  $mem_units = 'Megabytes';
    #  $mem_unit_div = MEGA;
    #}
    #elsif (lc($mem_units) eq 'bytes') {
    #  $mem_units = 'Bytes';
    #  $mem_unit_div = 1;
    #}
    #elsif (lc($mem_units) eq 'kilobytes') {
    #  $mem_units = 'Kilobytes';
    #  $mem_unit_div = KILO;
    #}
    #elsif (lc($mem_units) eq 'gigabytes') {
    #  $mem_units = 'Gigabytes';
    #  $mem_unit_div = GIGA;
    #}
    #else {
    #  exit_with_error("Unsupported memory units '$mem_units'. Use Bytes, Kilobytes, Megabytes, or Gigabytes.");
    #}

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


if __name__ == '__main__':
    args = parse_args()
    collect_memory_and_swap_metrics(args)
