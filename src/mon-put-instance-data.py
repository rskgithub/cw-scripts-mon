#!/usr/bin/env python


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
