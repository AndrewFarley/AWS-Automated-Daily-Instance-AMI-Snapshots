#!/usr/bin/env python3
####################
# NOTE: This code is from
#    https://github.com/AndrewFarley/AWS-Automated-Daily-Instance-AMI-Snapshots
####################
import boto3
import os
import sys
import traceback
import datetime
import time

# List every region you'd like to scan.  We'll need to update this if AWS adds a region
# Reference: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-regions-availability-zones.html
# LAST UPDATED: December 9, 2022
aws_regions = ['us-east-1','us-east-2','us-west-1','us-west-2',
'af-south-1','ap-east-1','ap-northeast-1','ap-northeast-2','ap-northeast-3',
'ap-south-1','ap-south-2','ap-southeast-1','ap-southeast-2','ap-southeast-3','ca-central-1',
'eu-central-1','eu-central-2','eu-north-1','eu-south-1','eu-south-2','eu-west-1','eu-west-2',
'eu-west-3','me-central-1','me-south-1','sa-east-1','us-gov-east-1','us-gov-west-1']
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
# Helper function to backup tagged volumes in a region
#####################
def backup_tagged_volumes_in_region(ec2):

    print("Scanning for volumes with tags ({})".format(','.join(tags_to_find)))

    # Get our volumes
    try:
        volumes = ec2.describe_volumes(Filters=[{'Name': 'tag-key', 'Values': tags_to_find}])
    except:
        # Don't fatal error on regions that we haven't activated/enabled
        if 'OptInRequired' in str(sys.exc_info()):
            print("  Region not activated for this account, skipping...")
            return
        else:
            raise

    # TODO: Help I can't do this pythonically...  PR welcome...
    volumes_array = []
    for volume in volumes['Volumes']:
        if volume['State'] in ['available','in-use']:
            volumes_array.append(volume)

    # Get our volumes and iterate through them...
    if len(volumes_array) == 0:
        return
    print("  Found {} volumes to backup...".format(len(volumes_array)))
    for volume in volumes_array:
        print("  Volume ID: {}".format(volume['VolumeId']))
        # pprint(volume)

        # Get the name of the instance, if set...
        try:
            volume_name = [t.get('Value') for t in volume['Tags']if t['Key'] == 'Name'][0]
        except:
            volume_name = volume['VolumeId']

        # Get the instance attachment, if attached (mostly just to print)...
        try:
            instance_id = volume['Attachments'][0]['InstanceId']
        except:
            instance_id = 'No attachment'

        print("Volume Name: {}".format(volume_name))
        print("Instance ID: {}".format(instance_id))

        # Get days to retain the backups from tags if set...
        try:
            retention_days = [int(t.get('Value')) for t in volume['Tags']if t['Key'] == 'Retention'][0]
        except:
            retention_days = default_retention_time
        print('       Time: {} days'.format(retention_days))

        # Catch if we were dry-running this
        if dry_run:
            print("Backup Name: {}".format("{}-backup-{}".format(volume_name, datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S.%f'))))
            print("DRY_RUN: Would have created a volume backup...")
        else:
            # Create our AMI
            try:
                # Get all the tags ready that we're going to set...
                delete_fmt = (datetime.date.today() + datetime.timedelta(days=retention_days)).strftime('%m-%d-%Y')
                tags = []
                tags.append({'Key': 'Name', 'Value': "{}-backup-{}".format(volume_name, datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S.%f'))})
                tags.append({'Key': 'DeleteAfter', 'Value': delete_fmt})
                tags.append({'Key': 'OriginalVolumeID', 'Value': volume['VolumeId']})
                tags.append({'Key': global_key_to_tag_on, 'Value': 'true'})
                # Also grab our old tags
                try:
                    if 'Tags' in volume:
                        for index, item in enumerate(volume['Tags']):
                            if item['Key'].startswith('aws:'):
                                print("Modifying internal aws tag so it doesn't fail: {}".format(item['Key']))
                                tags.append({'Key': 'internal-{}'.format(item['Key']), 'Value': item['Value']})
                            elif item['Key'] == 'Name':
                                pass  # Skip our old name, we're overriding it
                            else:
                                tags.append(item)
                except:
                    pass

                snapshot = ec2.create_snapshot(
                    Description="Automatic Backup of {} from {}".format(volume_name, volume['VolumeId']),
                    VolumeId=volume['VolumeId'],
                    TagSpecifications=[{
                        'ResourceType': 'snapshot',
                        'Tags': tags,
                    }],
                    # DryRun=True
                )
                print("Snapshot ID: {}".format(snapshot['SnapshotId']))

            except Exception as e:
                print('Caught exception while trying to process volume')
                pprint(e)


#####################
# Helper function to delete expired snapshots (of volumes)
#####################
def delete_expired_snapshots(ec2):
    try:
        print("Scanning for snapshots with tags ({})".format(global_key_to_tag_on))
        snapshots_to_consider = response = ec2.describe_snapshots(
            Filters=[{'Name': 'tag-key', 'Values': [global_key_to_tag_on]}],
        )['Snapshots']
    except:
        # Don't fatal error on regions that we haven't activated/enabled
        if 'OptInRequired' in str(sys.exc_info()):
            print("  Region not activated for this account, skipping...")
            return
        else:
            raise

    today_date = time.strptime(datetime.datetime.now().strftime('%m-%d-%Y'), '%m-%d-%Y')

    # Iterate and decide...
    if len(snapshots_to_consider) == 0:
        return
    print("  Found {} snapshots to consider...".format(len(snapshots_to_consider)))
    for snapshot in snapshots_to_consider:
        print("  Found snapshot to consider: {}".format(snapshot['SnapshotId']))
        print("                  For Volume: {}".format(snapshot['VolumeId']))

        # Figure out when the DeleteAfter is set to
        try:
            delete_after = [t.get('Value') for t in snapshot['Tags']if t['Key'] == 'DeleteAfter'][0]
        except:
            print("Unable to find when to delete this image after, skipping...")
            continue
        print("                Delete After: {}".format(delete_after))

        # Figure out if we should delete this snapshot
        delete_date = time.strptime(delete_after, "%m-%d-%Y")
        if today_date < delete_date:
            print("This item is too new, skipping...")
            continue

        # Catch if we were dry-running this
        if dry_run:
            print("DRY_RUN, would have deleted snapshot : {}".format(snapshot['SnapshotId']))
        else:
            # Delete this snapshot...
            print("       === DELETING SNAPSHOT: {}".format(snapshot['SnapshotId']))
            try:
                deleteSnapshotResponse = ec2.delete_snapshot( SnapshotId=snapshot['SnapshotId'] )
            except Exception as e:
                print("Unable to delete snapshot: {}".format(e))


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
    if len(instances) == 0:
        return
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
            print("   Name       : {}".format("{}-backup-{}".format(instance_name, datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S.%f'))))
        else:
            # Create our AMI
            try:
                image = ec2.create_image(
                    InstanceId=instance['InstanceId'],
                    Name="{}-backup-{}".format(instance_name, datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S.%f')),
                    Description="Automatic Backup of {} from {}".format(instance_name, instance['InstanceId']),
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
    if len(amis_to_consider) == 0:
        return
    print("  Found {} amis to consider...".format(len(amis_to_consider)))
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
        try:
            ec2 = boto3.client('ec2', region_name=aws_region)
            print("Scanning region: {}".format(aws_region))

            # Volumes...
            backup_tagged_volumes_in_region(ec2)   # First, backup tagged volumes in that region
            delete_expired_snapshots(ec2)            # Then delete snapshots that have expired

            # AMIs...
            backup_tagged_instances_in_region(ec2) # First, backup tagged instances in that region
            delete_expired_amis(ec2)               # Then, go delete AMIs that have expired in that region
        except Exception as e:
            print("Uncaught exception in main region loop: {}".format(e))


# If ran on the CLI, go ahead and run it
if __name__ == "__main__":
    lambda_handler({},{})
