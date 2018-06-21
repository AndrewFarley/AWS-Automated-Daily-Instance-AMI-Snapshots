# Create Rotating Instance AMIs Backups
With serverless!

**Found at:** https://github.com/AndrewFarley/AWSAutomatedDailyInstanceAMISnapshots
## Author
* Farley - farley _at_ **neonsurge** _dot_ com

## Purpose
1. A nearly idiot-proof way to begin doing automated daily snapshots of instances across your entire AWS account.
1. To promote people to back-things-up, by giving them an easy way to begin doing so.
1. To try to save them money in regards to backups by deleting them after a while (7 days by default)


## What does this do...?
1. This uses the serverless framework, which deploys a Lambda to your AWS account in the eu-west-1 region (adjustable)
1. This lambda is given a limited role to allow it to do only what it needs to do, no funny stuff
1. This also tells CloudWatch Events to run this automatically once a day
1. When this lambda runs, it scans through every region for any instances with the tag Key of "backup".  If it finds any, it will create a snapshot of them, preserving all the tags in the AMI (but not in the volume snapshots, see Issue #2)
1. After its done taking snapshots, it will then scan through all the AMIs that this script previosuly created, and will evaluate if it's time to delete those AMIs if they are old enough


## Prerequisites

- [Serverless Framework v1.0+](https://serverless.com/)
- [Nodejs v4.3+](https://nodejs.org/)
- [Setup your AWS credentials](https://serverless.com/framework/docs/providers/aws/guide/credentials/)

## Setup

```bash
# Make sure your CLI has a default AWS credentials setup, if not run this...
aws configure

# Clone this repository with...
git clone git@github.com:AndrewFarley/AWSAutomatedDailyInstanceAMISnapshots.git
cd AWSAutomatedDailyInstanceAMISnapshots

# Deploy it with...
serverless deploy

# Run it manually with...
serverless invoke --function daily_snapshot --log
```

Now go tag your instances (manually, or automatically if you have an automated infrastructure like [Terraform](https://www.terraform.io/) or [CloudFormation](https://aws.amazon.com/cloudformation/)) with the Key "Backup" (with any value) which will trigger this script to back that instance up.

If you'd like to specify the number of days to retain backups, set the key "Retention" with a numeric value.  If you do not specify this, by default keeps the AMIs for 7 days.

![ec2 image tag example](./snapshot.png)

After tagging some servers, try to run it manually again and check the output to see if it detected your server. To make sure your tag works, go run the lambda yourself manually and check the log output.  If you tagged some instances and it ran successfully, your output will look something like this...

```bash
bash-3.2$ serverless invoke --function daily_snapshot --log
--------------------------------------------------------------------
Scanning region: eu-central-1
Scanning for instances with tags (backup,Backup)
  Found 2 instances to backup...
  Instance: i-00001111222233334
      Name: jenkins-build-server
      Time: 7 days
       AMI: ami-00112233445566778
  Instance: i-55556666777788889
      Name: primary-webserver
      Time: 7 days
       AMI: ami-11223344556677889
Scanning for AMIs with tags (AWSAutomatedDailySnapshots)
  Found AMI to consider: ami-008e6cb79f78f1469
           Delete After: 06-12-2018
This item is too new, skipping...
Scanning region: eu-west-1
Scanning for instances with tags (backup,Backup)
  Found 0 instances to backup...
Scanning for AMIs with tags (AWSAutomatedDailySnapshots)
Scanning region: eu-west-2
```

### That's IT!
Now every day, once a day this lambda will run and automatically make no-downtime snapshots of your servers.

## Updating
If you'd like to tweak this function it's very easy to do without ever having to edit code or re-deploy it.  Simply edit the environment variables of the Lambda.  If you didn't change the region this deploys to, you should be able to [CLICK HERE](https://eu-west-1.console.aws.amazon.com/lambda/home?region=eu-west-1#/functions/daily-instance-snapshot-dev-daily_snapshot) and simply update any of the environment variables in the Lambda and hit save.  Seen below...

![lambda update env variable](./snapshot2.png)

 * **DEFAULT_RETENTION_TIME** is the default number of days that it will keep backups for
 * **DRY_RUN** you only need to set to true briefly, if you want to test-run this script to see what it would do.  Warning: if you set this to true, make sure you un-set it, otherwise your lambda won't do anything.
 * **KEY_TO_TAG_ON** is the tag that this script will set on any AMI it creates.  This is what we will scan for to cleanup AMIs afterwards.  WARNING: Changing this value will cause any previous AMIs this script made to suddenly be hidden to this script, so you will need to delete yourself.
 * **LIMIT_TO_REGIONS** helps to speed this script up a lot by not wasting time scanning regions you aren't actually using.  So, if you'd like this script to speed up then set the this to the regions (comma-delimited) you wish to only scan.  Eg: us-west-1,eu-west-1.

## Removal

Simple remove with the serverless remove command.  Please keep in mind any AMIs this script may have created will still be in place, you will need to delete those yourself.

```
serverless remove
```


## Changelog / Major Recent Features

* June 6, 2018  - Initial public release
* June 21, 2018 - Moved configuration to env variables, bugfix, more exception handling


## Support, Feedback & Questions

Please feel free to file Github bugs if you find any.  It's probably easier if you fork my repo to make your own modifications detailed above and commit them.  If you make any fixed/changes that are awesome, please send me pull requests or patches.

If you have any questions/problems beyond that, feel free to email me at one of the emails in [author](#author) above.