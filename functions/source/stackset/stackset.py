import boto3, json, time, os, logging, botocore
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger('boto3').setLevel(logging.CRITICAL)
logging.getLogger('botocore').setLevel(logging.CRITICAL)
session = boto3.Session()

def message_processing(messages):
    target_stackset = {}
    for message in messages:
        payload = json.loads(message['Sns']['Message'])
        stackset_processing(payload)
    
def stackset_processing(messages):
    cloudFormationClient = session.client('cloudformation')
    snsClient = session.client('sns')
    newRelicStackSNS = os.environ['newRelicStackSNS']
    newRelicRegisterSNS = os.environ['newRelicRegisterSNS']
    
    for stackSetName, params in messages.items():
        logger.info("Processing stack instances for {}".format(stackSetName))
        param_accounts = params['target_accounts']
        param_regions = params['target_regions']
        logger.info("Target accounts : {}".format(param_accounts))
        logger.info("Target regions: {}".format(param_regions))
        
        try:
            stack_operations = True
            cloudFormationClient.describe_stack_set(StackSetName=stackSetName)
            cloudFormationPaginator = cloudFormationClient.get_paginator('list_stack_set_operations')
            stackset_iterator = cloudFormationPaginator.paginate(
                StackSetName=stackSetName
            )
            for page in stackset_iterator:
                if 'Summaries' in page:
                    for operation in page['Summaries']:
                        if operation['Status'] in ('RUNNING', 'STOPPING'):
                            stack_operations = False
                            break
                    if stack_operations == False: 
                        break
            
            if stack_operations:
                response = cloudFormationClient.create_stack_instances(StackSetName=stackSetName, Accounts=param_accounts, Regions=param_regions)
                logger.info("StackSet instance created {}".format(response))
                messageBody = {}
                messageBody[stackSetName] = {'OperationId': response['OperationId']}
                try:
                    snsResponse = snsClient.publish(
                        TopicArn=newRelicRegisterSNS,
                        Message = json.dumps(messageBody))
                        
                    logger.info("Queued for registration: {}".format(snsResponse))
                except Exception as snsException:
                    logger.error("Failed to send queue for registration: {}".format(snsException))                
            else:
                logger.warning("Existing StackSet operations still running")
                messageBody = {}
                messageBody[stackSetName] = messages[stackSetName]
                try:
                    logger.info("Sleep and wait for 20 seconds")
                    time.sleep(20)
                    snsResponse = snsClient.publish(
                        TopicArn=newRelicStackSNS,
                        Message = json.dumps(messageBody))
                        
                    logger.info("Re-queued for stackset instance creation: {}".format(snsResponse))
                except Exception as snsException:
                    logger.error("Failed to send queue for stackset instance creation: {}".format(snsException))

        except cloudFormationClient.exceptions.StackSetNotFoundException as describeException:
            logger.error('Exception getting stack set, {}'.format(describeException))
            raise describeException

def lifecycle_processing(event):
    if event['detail']['serviceEventDetails']['createManagedAccountStatus']['state'] == 'SUCCEEDED':
        cloudFormationClient = session.client('cloudformation')
        account_id = event['detail']['serviceEventDetails']['createManagedAccountStatus']['account']['accountId']
        stackSetName = os.environ["stackSetName"]
        stackset_instances = list_stack_instance_by_account(session, stackSetName, account_id)
        if event['region'] is not None:
            stackset_instances_regions = event['region'].split(" ")
        else:
            stackset_instances_regions = list_stack_instance_region(session, stackSetName)
        
        logger.info("Processing Lifecycle event for {}".format(account_id))
        #stackset instance does not exist, create a new one
        if len(stackset_instances) == 0:
            logger.info("Create new stackset instance for {} {} {}".format(stackSetName, account_id, stackset_instances_regions))
            messageBody = {}
            messageBody[stackSetName] = { 'target_accounts': [account_id], 'target_regions': stackset_instances_regions }
            stackset_processing(messageBody)
        
        #stackset instance already exist, check for missing region
        elif len(stackset_instances) > 0:
            stackset_region = []
            for instance in stackset_instances:
                stackset_region.append(instance['Region'])
            next_region = list(set(stackset_instances_regions) - set(stackset_region))
            if len(next_region) > 0:
                logger.info("Append new stackset instance for {} {} {}".format(stackSetName, account_id, next_region))
                messageBody = {}
                messageBody[stackSetName] = { 'target_accounts': [account_id], 'target_regions': next_region }
                stackset_processing(messageBody)
            else:
                logger.info("Stackset instance already exist : {}".format(stackset_instances))
    else:
         logger.error("Invalid event state, expected: SUCCEEDED : {}".format(event))    

def list_stack_instance_by_account(target_session, stack_set_name, account_id):
    '''
    List all stack instances based on the StackSet name and Account Id
    '''
    try:
        cfn_client = target_session.client('cloudformation')
        stackset_result = cfn_client.list_stack_instances(
            StackSetName = stack_set_name,
            StackInstanceAccount=account_id
            )
        
        if stackset_result and 'Summaries' in stackset_result:            
            stackset_list = stackset_result['Summaries']
            while 'NextToken' in stackset_result:
                stackset_result = cfn_client.list_stackset_instance(
                    NextToken = stackset_result['NextToken']
                )
                stackset_list.append(stackset_result['Summaries'])
            
            return stackset_list
        else:
            return False
    except Exception as e:
        LOGGER.error("List Stack Instance error: %s" % e)
        return False

def list_stack_instance_region(target_session, stack_set_name):
    '''
    List all stack instances based on the StackSet name
    '''
    try:
        cfn_client = target_session.client('cloudformation')
        stackset_result = cfn_client.list_stack_instances(
            StackSetName = stack_set_name
            )
        
        if stackset_result and 'Summaries' in stackset_result:            
            stackset_list = stackset_result['Summaries']
            while 'NextToken' in stackset_result:
                stackset_result = cfn_client.list_stackset_instance(
                    NextToken = stackset_result['NextToken']
                )
                stackset_list.append(stackset_result['Summaries'])
            
            stackset_list_region = []
            for instance in stackset_list:
                stackset_list_region.append(instance['Region'])
            stackset_list_region=list(set(stackset_list_region))

            return stackset_list_region
        else:
            return False
    except Exception as e:
        LOGGER.error("List Stack Instance error: %s" % e)
        return False
        
def lambda_handler(event, context):
    logger.info(json.dumps(event))
    try:
        if 'Records' in event:
            message_processing(event['Records'])
        elif 'detail' in event and event['detail']['eventName'] == 'CreateManagedAccount':
            lifecycle_processing(event)
    except Exception as e:
        logger.error(e)