#!/usr/bin/env python
####################
# NOTE: This code is from 
#    https://github.com/AndrewFarley/AWSAutomatedDailyInstanceAMISnapshots
####################
import boto3
import os
import sys
import traceback
import datetime
import time

# List every region you'd like to scan.  We'll need to update this if AWS adds a region
aws_regions = ['us-east-1','us-east-2','us-west-1','us-west-2',
'ap-northeast-1','ap-northeast-2','ap-northeast-3','ap-south-1',
'ap-southeast-1','ap-southeast-2','ca-central-1',
'eu-central-1','eu-west-1','eu-west-2','eu-west-3']
# If in serverless.yml we limited to a specific region(s)
if 'LIMIT_TO_REGIONS' in os.environ and len(os.getenv('LIMIT_TO_REGIONS')):
    aws_regions = os.getenv('LIMIT_TO_REGIONS').split(',')

# List of the tags on instances we want to look for to backup
tags_to_find = ['backup', 'Backup']

# Default Retention Time (in days)
default_retention_time = 7
if 'DEFAULT_RETENTION_TIME' in os.environ and len(os.getenv('DEFAULT_RETENTION_TIME')):
    default_retention_time = int(os.getenv('DEFAULT_RETENTION_TIME'))

# This is the key we'll set on all AMIs we create, to detect that we are managing them
global_key_to_tag_on = "AWSAutomatedDailySnapshots"
if 'KEY_TO_TAG_ON' in os.environ and len(os.getenv('KEY_TO_TAG_ON')):
    global_key_to_tag_on = str(os.getenv('KEY_TO_TAG_ON'))

dry_run = False
if 'DRY_RUN' in os.environ and (os.getenv('DRY_RUN') == 'true' or os.getenv('DRY_RUN') == 'True'):
    dry_run = True

#####################
# Helper function to backup tagged instances in a region
#####################
def backup_tagged_instances_in_region(ec2):
    
    print("Scanning for instances with tags ({})".format(','.join(tags_to_find)))

    # Get our reservations
    try:
        reservations = ec2.describe_instances(Filters=[{'Name': 'tag-key', 'Values': tags_to_find}])['Reservations']
    except:
        # Don't fatal error on regions that we haven't activated/enabled
        if 'OptInRequired' in str(sys.exc_info()):
            print("  Region not activated for this account, skipping...")
            return
        else:
            raise

    # Iterate through reservations and get instances
    instance_reservations = [[i for i in r['Instances']] for r in reservations]
    # TODO: Help I can't do this pythonically...  PR welcome...
    instances = []
    for instance_reservation in instance_reservations:
        for this_instance in instance_reservation:
            if this_instance['State']['Name'] != 'terminated':
                instances.append(this_instance)

    # Get our instances and iterate through them...
    print("  Found {} instances to backup...".format(len(instances)))
    for instance in instances:
        print("  Instance: {}".format(instance['InstanceId']))

        # Get the name of the instance, if set...
        try:
            instance_name = [t.get('Value') for t in instance['Tags']if t['Key'] == 'Name'][0]
        except:
            instance_name = instance['InstanceId']
        print("      Name: {}".format(instance_name))
        
        # Get days to retain the backups from tags if set...
        try:
            retention_days = [int(t.get('Value')) for t in instance['Tags']if t['Key'] == 'Retention'][0]
        except:
            retention_days = default_retention_time
        print('      Time: {} days'.format(retention_days))
        
        # Catch if we were dry-running this
        if dry_run:
            print("DRY_RUN: Would have created an AMI...")
            print("   InstanceId : {}".format(instance['InstanceId']))
            print("   Name       : {}".format("{}-backup-{}".format(instance_name, datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S'))))
        else:
            # Create our AMI
            try:
                image = ec2.create_image(
                    InstanceId=instance['InstanceId'],
                    Name="{}-backup-{}".format(instance_name, datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')),
                    Description="Automatic Daily Backup of {} from {}".format(instance_name, instance['InstanceId']),
                    NoReboot=True,
                    DryRun=False
                )
                print("       AMI: {}".format(image['ImageId']))
                
                # Tag our AMI appropriately
                delete_fmt = (datetime.date.today() + datetime.timedelta(days=retention_days)).strftime('%m-%d-%Y')
                instance['Tags'].append({'Key': 'DeleteAfter', 'Value': delete_fmt})
                instance['Tags'].append({'Key': 'OriginalInstanceID', 'Value': instance['InstanceId']})
                instance['Tags'].append({'Key': global_key_to_tag_on, 'Value': 'true'})
                # Remove any tags prefixed with aws: since they are internal and we aren't allowed to set.  These can come from CloudFormation, or from Autoscalers
                finaltags = []
                for index, item in enumerate(instance['Tags']):
                    if item['Key'].startswith('aws:'):
                        print("Modifying internal aws tag so it doesn't fail: {}".format(item['Key']))
                        finaltags.append({'Key': 'internal-{}'.format(item['Key']), 'Value': item['Value']})
                    else:
                        finaltags.append(item)
                response = ec2.create_tags(
                    Resources=[image['ImageId']],
                    Tags=finaltags
                )
            except:
                print("Failure trying to create image or tag image.  See/report exception below")
                exc_info = sys.exc_info()
                traceback.print_exception(*exc_info)


#####################
# Helper function to delete expired AMIs
#####################
def delete_expired_amis(ec2):
    # Get our list of AMIs to consider deleting...
    try:
        print("Scanning for AMIs with tags ({})".format(global_key_to_tag_on))
        amis_to_consider = response = ec2.describe_images(
            Filters=[{'Name': 'tag-key', 'Values': [global_key_to_tag_on]}],
            Owners=['self'],
        )['Images']
    except:
        # Don't fatal error on regions that we haven't activated/enabled
        if 'OptInRequired' in str(sys.exc_info()):
            print("  Region not activated for this account, skipping...")
            return
        else:
            raise

    today_date = time.strptime(datetime.datetime.now().strftime('%m-%d-%Y'), '%m-%d-%Y')
    
    # Iterate and decide...
    for ami in amis_to_consider:
        print("  Found AMI to consider: {}".format(ami['ImageId']))

        # Figure out when the DeleteAfter is set to
        try:
            delete_after = [t.get('Value') for t in ami['Tags']if t['Key'] == 'DeleteAfter'][0]
        except:
            print("Unable to find when to delete this image after, skipping...")
            continue
        print("           Delete After: {}".format(delete_after))

        # Figure out if we should delete this AMI
        delete_date = time.strptime(delete_after, "%m-%d-%Y")
        if today_date < delete_date:
            print("This item is too new, skipping...")
            continue

        # Catch if we were dry-running this
        if dry_run:
            print("DRY_RUN, would have deleted ami : {}".format(ami['ImageId']))
            for snapshot in [i['Ebs']['SnapshotId'] for i in ami['BlockDeviceMappings'] if 'Ebs' in i]:
                print("DRY_RUN, would have deleted volume snapshot {}".format(ami['ImageId'], snapshot))
        else:
            # Delete this AMI...
            print(" === DELETING AMI : {}".format(ami['ImageId']))
            try:
                amiResponse = ec2.deregister_image( ImageId=ami['ImageId'] )
            except Exception as e:
                print("Unable to delete AMI: {}".format(e))
            
            # Delete all snapshots underneath that ami...
            for snapshot in [i['Ebs']['SnapshotId'] for i in ami['BlockDeviceMappings'] if 'Ebs' in i]:
                print(" === DELETING AMI {} SNAPSHOT : {}".format(ami['ImageId'], snapshot))
                try:
                    result = ec2.delete_snapshot(SnapshotId=snapshot)
                except Exception as e:
                    print("Unable to delete snapshot: {}".format(e))


#####################
# Lambda/script entrypoint
#####################
def lambda_handler(event, context):
    
    # For each region we want to scan...
    for aws_region in aws_regions:
        ec2 = boto3.client('ec2', region_name=aws_region)
        print("Scanning region: {}".format(aws_region))

        # First, backup tagged instances in that region
        backup_tagged_instances_in_region(ec2)
        
        # Then, go delete AMIs that have expired in that region
        delete_expired_amis(ec2)

# If ran on the CLI, go ahead and run it
if __name__ == "__main__":
    lambda_handler({},{})
