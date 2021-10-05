#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
import boto3, json, time, os, logging, botocore, requests
from botocore.exceptions import ClientError
from crhelper import CfnResource

# Set logging verbosity
logger = logging.getLogger()
if 'log_level' in os.environ:
    logger.setLevel(os.environ['log_level'])
    logger.info("Log level set to %s" % logger.getEffectiveLevel())
else:
    logger.setLevel(logging.INFO)
logging.getLogger('boto3').setLevel(logging.CRITICAL)
logging.getLogger('botocore').setLevel(logging.CRITICAL)

session = boto3.Session()
helper = CfnResource(json_logging=False, log_level='INFO', boto_level='CRITICAL', sleep_on_delete=15)

@helper.create
def create(event, context):
    try:
        logger.info(event)
        if event['RequestType'] in ['Create']:
            targetAccount = event['ResourceProperties']['SourceAccount']
            newRelicSecret = os.environ['newRelicSecret']
            newRelicAccId = os.environ['newRelicAccId']
            newRelicAccessKey = get_secret_value(newRelicSecret)
            
            if newRelicAccessKey:
                newRelicIntegrationList = newrelic_get_schema(newRelicAccessKey)
                newrelic_registration(targetAccount, newRelicAccessKey, newRelicAccId, newRelicIntegrationList)
            else:
                logger.error("Unable to find the NewRelic secret token, skipping")
                send_to_dlq(event)        
        else:
            logger.info("Non stackset instance create event, skipping")
        
    except Exception as describeException:
        logger.info('Error : {}'.format(describeException))
        send_to_dlq(event)
    
    return None #Generate random ID

def send_to_dlq(event):
    try:
        sqsClient = session.client('sqs')
        newRelicDLQ = os.environ['newRelicDLQ']
        sqsResponse = sqsClient.send_message(
            QueueUrl=newRelicDLQ,
            MessageBody=json.dumps(event))
        logger.info("Sent to DLQ: {}".format(event))
    except Exception as sqsException:
        logger.error("Failed to send to DLQ: {}".format(sqsException))

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
        return False
    
def newrelic_registration(aws_account_id, access_key, newrelic_account_id, newrelic_integration_list):
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
                arn: "{2}"
            }}]
        }}) 
        {{
            linkedAccounts 
            {{
                id name authLabel
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
    if response.status_code == 200:
        link_response = json.loads(response.text)
        
        try:
            link_accound_id = link_response['data']['cloudLinkAccount']['linkedAccounts'][0]['id']
            service_payload = []
            for service in newrelic_integration_list:
                service_payload.append('{0}: [{{ linkedAccountId: {1} }}]'.format(service, link_accound_id))
            
            integration_payload = '''
            mutation 
            {{
              cloudConfigureIntegration (
                accountId: {0},
                integrations: 
                {{
                  aws: 
                  {{
                    {1}
                  }}
                }} 
              ) 
              {{
                integrations 
                {{
                  id
                  name
                  service 
                  {{
                    id 
                    name
                  }}
                }}
                errors 
                {{
                  type
                  message
                }}
              }}
            }}
            '''.format(newrelic_account_id, '\n'.join(service_payload))
            logger.debug('NerdGraph integration payload : {}'.format(json.dumps(integration_payload)))
            integration_response = requests.post(nerdGraphEndPoint, headers={'API-Key': access_key}, verify=True, data=integration_payload)
            logger.info('NerdGraph integration response code : {}'.format(integration_response.status_code))
            logger.info('NerdGraph integration response : {}'.format(integration_response.text))
            
        except Exception as create_exception:
            if len(link_response['data']['cloudLinkAccount']['errors']) > 0:
                logger.warning('NerdGraph error messages : {}'.format(link_response['data']['cloudLinkAccount']['errors']))    
                for error in link_response['data']['cloudLinkAccount']['errors']:
                    if 'AWS account is already linked ' in error['message']:
                        logger.warning('AWS Account {} already linked, skipping'.format(aws_account_id))
            else:
                logger.error('Exception {}'.format(create_exception))

def newrelic_get_integration(access_key, newrelic_account_id):
    nerdGraphEndPoint = os.environ['nerdGraphEndPoint']
    service_query = '''
    {{
      actor 
      {{
        account(id: {0}) 
        {{
          cloud 
          {{
            provider(slug: "aws") 
            {{
              services 
              {{
                slug
              }}
            }}
          }}
        }}
      }}
    }}
    '''.format(newrelic_account_id)
    
    try:
        response = requests.post(nerdGraphEndPoint, headers={'API-Key': access_key}, verify=True, data=service_query)
        temp_list = json.loads(response.text)['data']['actor']['account']['cloud']['provider']['services']
        newrelic_integration_list = []
        for slug in temp_list:
            newrelic_integration_list.append(slug['slug'])
        logger.info('NerdGraph AWS available integrations : {}'.format(newrelic_integration_list))
        return newrelic_integration_list
    except Exception as e:
        logger.error(e)

def newrelic_get_schema(access_key):
    nerdGraphEndPoint = os.environ['nerdGraphEndPoint']
    schema_query = '''
    {
        __schema 
        {
            types 
            {
                name
                inputFields 
                {
                    name
                }
            }
        }
    }
    '''
    try:
        response = requests.post(nerdGraphEndPoint, headers={'API-Key': access_key}, verify=True, data=schema_query)
        logger.info(json.loads(response.text))
        temp_types = json.loads(response.text)['data']['__schema']['types']
        temp_integration_input = [input['inputFields'] for input in temp_types if input['name'] == 'CloudAwsIntegrationsInput'][0]
        newrelic_integration_list = [input['name'] for input in temp_integration_input]
        logger.info('NerdGraph AWS available integrations : {}'.format(newrelic_integration_list))
        return newrelic_integration_list
    except Exception as e:
        logger.error(e)

# CfCT Register lambda handler 
# only takes signal from SNS topic, based on cloudformation custom resource sent by spoke account via stackset
def lambda_handler(event, context):
    logger.info(json.dumps(event))
    try:
        if 'Records' in event: 
            messages = event['Records']
            for message in messages:
                payload = json.loads(message['Sns']['Message'])
                helper(payload, context)
    except Exception as e:
        helper.init_failure(e)