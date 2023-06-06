import boto3, json, time, os, logging, botocore, requests
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
        stackset_check(payload)

def stackset_check(messages):
    cloudFormationClient = session.client('cloudformation')
    sqsClient = session.client('sqs')
    snsClient = session.client('sns')
    newRelicRegisterSNS = os.environ['newRelicRegisterSNS']
    newRelicDLQ = os.environ['newRelicDLQ']
    
    for stackSetName, params in messages.items():
        logger.info("Checking stack set instances: {} {}".format(stackSetName, params['OperationId']))
        try:
            stackset_status = cloudFormationClient.describe_stack_set_operation(
                StackSetName=stackSetName,
                OperationId=params['OperationId']
            )
            if 'StackSetOperation' in stackset_status:
                if stackset_status['StackSetOperation']['Status'] in ['RUNNING','STOPPING','QUEUED']:
                    logger.info("Stackset operation still running")
                    messageBody = {}
                    messageBody[stackSetName] = {'OperationId': params['OperationId']}
                    try:
                        logger.info("Sleep and wait for 20 seconds")
                        time.sleep(20)
                        snsResponse = snsClient.publish(
                            TopicArn=newRelicRegisterSNS,
                            Message = json.dumps(messageBody))

                        logger.info("Re-queued for registration: {}".format(snsResponse))
                    except Exception as snsException:
                        logger.error("Failed to send queue for registration: {}".format(snsException))
                
                elif stackset_status['StackSetOperation']['Status'] in ['SUCCEEDED']:
                    logger.info("Start registration")
                    cloudFormationPaginator = cloudFormationClient.get_paginator('list_stack_set_operation_results')
                    stackset_iterator = cloudFormationPaginator.paginate(
                        StackSetName=stackSetName,
                        OperationId=params['OperationId']
                    )
                    
                    newRelicSecret = os.environ['newRelicSecret']
                    newRelicAccId = os.environ['newRelicAccId']
                    newRelicAccessKey = get_secret_value(newRelicSecret)
                    
                    if newRelicAccessKey:
                        for page in stackset_iterator:
                            if 'Summaries' in page:
                                for operation in page['Summaries']:
                                    if operation['Status'] in ('SUCCEEDED'):
                                        targetAccount = operation['Account']
                                        newrelic_registration(targetAccount, newRelicAccessKey, newRelicAccId)
                    
                elif stackset_status['StackSetOperation']['Status'] in ['FAILED','STOPPED']:
                    logger.warning("Stackset operation failed/stopped")
                    messageBody = {}
                    messageBody[stackSetName] = {'OperationId': params['OperationId']}
                    try:
                        sqsResponse = sqsClient.send_message(
                            QueueUrl=newRelicDLQ,
                            MessageBody=json.dumps(messageBody))
                        logger.info("Sent to DLQ: {}".format(sqsResponse))
                    except Exception as sqsException:
                        logger.error("Failed to send to DLQ: {}".format(sqsException))
        
        except Exception as e:
            logger.error(e)

def get_secret_value(secret_arn):
    secretClient = session.client('secretsmanager')
    try:
        secret_response = secretClient.get_secret_value(
            SecretId=secret_arn
        )
        if 'SecretString' in secret_response:
            secret = json.loads(secret_response['SecretString'])['AccessKey']
            return secret 
    
    except Exception as e:
        logger.error('Get Secret Failed: ' + str(e))
    
def newrelic_registration(aws_account_id, access_key, newrelic_account_id):
    role_arn =  'arn:aws:iam::{}:role/NewRelicIntegrationRole_{}'.format(aws_account_id, newrelic_account_id)
    nerdGraphEndPoint = os.environ['nerdGraphEndPoint']
    
    link_payload = '''
    mutation 
    {{
        cloudLinkAccount(accountId: {0}, accounts: 
        {{
            aws: [
            {{
                name: "{1}", 
                arn: "{2}",
                metricCollectionMode: PUSH
            }}]
        }}) 
        {{
            linkedAccounts 
            {{
                id name authLabel createdAt updatedAt
            }}
            errors 
            {{
                type
                message
                linkedAccountId
            }}
        }}
    }}
    '''.format(newrelic_account_id, aws_account_id, role_arn)
    logger.debug('NerdGraph link account payload : {}'.format(json.dumps(link_payload)))
    
    response = requests.post(nerdGraphEndPoint, headers={'API-Key': access_key}, verify=True, data=link_payload)
    logger.info('NerdGraph response code : {}'.format(response.status_code))
    logger.info('NerdGraph response : {}'.format(response.text))


def lambda_handler(event, context):
    logger.info(json.dumps(event))
    try:
        if 'Records' in event:
            message_processing(event['Records'])
    except Exception as e:
        logger.error(e)