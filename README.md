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
1. This uses the serverless framework, which generates a CloudFormation stack and deploys it to your AWS account in the eu-west-1 region (adjustable)
1. This CloudFormation stack deploys a Lambda and a role for this lambda to allow it to do what it needs to do.
1. Finally this CloudFormation stack configures that Lambda to be executed once a day automatically via CloudWatch Events.
1. When this lambda runs, it scans through EVERY AWS region for any instances with the tag Key of "backup".  If it finds any, it will create a snapshot of them, preserving all the tags
1. After its done taking snapshots, it will then scan through all the AMIs that this script created, and will evaluate if it's time to delete those AMIs if they are old enough


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

If you'd like to specify the number of days to retain backups, set the key "Retention" with a numeric value.

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
Scanning for AMIs with tags (FarleysBackupInstanceRotater)
  Found AMI to consider: ami-008e6cb79f78f1469
           Delete After: 06-12-2018
This item is too new, skipping...
Scanning region: eu-west-1
Scanning for instances with tags (backup,Backup)
  Found 0 instances to backup...
Scanning for AMIs with tags (FarleysBackupInstanceRotater)
Scanning region: eu-west-2
```

### That's IT!
Now every day, once a day this lambda will run and automatically make no-downtime snapshots of your servers.

## Removal

Simple remove with the serverless remove command

```
serverless remove
```


## Changelog / Recent Features

* June 6, 2018 - Initial public release


## Support, Feedback & Questions

Please feel free to file Github bugs if you find any.  It's probably easier if you fork my repo to make your own modifications detailed above and commit them.  If you make any fixed/changes that are awesome, please send me pull requests or patches.

If you have any questions/problems beyond that, feel free to email me at one of the emails in [author](#author) above.