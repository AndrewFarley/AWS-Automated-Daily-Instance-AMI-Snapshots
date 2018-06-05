# Create Rotating Instance AMIs Backups
With serverless!

**Found at:** https://github.com/AndrewFarley/AWSAutomatedDailyInstanceAMISnapshots
## Author
* Farley - farley _at_ **neonsurge** _dot_ com

## Purpose
1. A nearly idiot-proof way to begin doing automated daily snapshots of instances across your entire AWS account.
1. To promote people to back-things-up, by giving them an easy way to begin doing so.
1. To try to save them money in regards to backups by deleting them after a while (7 days by default)


## Prerequisites

- [Serverless Framework v1.0+](https://serverless.com/)
- [Nodejs v4.3+](https://nodejs.org/)
- [Setup your AWS credentials](https://serverless.com/framework/docs/providers/aws/guide/credentials/)

## Setup

* Make sure your CLI has a default AWS credentials setup (via ```aws configure```) or that you have chosen a profile and can use the aws CLI properly on your terminal.  Additionally make sure you have NodeJS installed 4.3+ installed on your machine.

* Clone this repository with ```git clone git@github.com:AndrewFarley/AWSAutomatedDailyInstanceAMISnapshots.git``` then enter the folder with ```cd AWSAutomatedDailyInstanceAMISnapshots``` and run ```serverless deploy```

* Go into your AWS Console and tag any instances you want to be backed up with the tag Key "backup".  The value can be anything, or nothing, it just scans for the key.

* That's IT!  To make sure your tag works, go run the lambda yourself manually and check the log output.  To do this from the command line just run `serverless invoke --function daily_snapshot --log` or go to the Lambda console and do it from there.  This project deploys to the eu-west-1 region by default, so you'll find it there.  But, it runs across your ENTIRE AWS ACCOUNT by default, so it doesn't matter where it is deployed.

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