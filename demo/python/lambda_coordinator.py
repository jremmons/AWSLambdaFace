import multiprocessing as mp
import datetime
import boto3
import socket
import json 
import random

FRAME_IDX_MIN = 1
FRAME_IDX_MAX = 120000
FRAMES_PER_LAMBDA = 75
PORT = 10000

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

# fire up lambda worker
def launch_lambda(bundle):
    conn = boto3.client('lambda', region_name=bundle['region'])
    
    while True:
        response = conn.invoke(
            FunctionName=bundle['function_name'],
            InvocationType='Event',
            LogType='Tail',
            Payload=json.dumps(bundle['job_args'])
        )

        if response['ResponseMetadata']['HTTPStatusCode'] == 202:
            break
        else:
            print response

    return response

def start_lambda_coordinator_server():
    pool = mp.Pool(25)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', PORT))
    sock.listen(1)
    print "server started"

    end = False
    while( not end ):
        conn, addr = sock.accept()

        # get the result
        data = ''
        while True:
            d = conn.recv(4096)
            if(d == ''):
                break
                
            if(d[-1] == ':'):
                data += d[:-1]
                break
                
            data += d
        conn.close()
        
        print data
        message = eval( data )
        request_id = message['request_id']
        index = message['index']
  
        dynamodb = boto3.client('dynamodb', region_name='us-west-2')
        t = datetime.datetime.now().strftime(DATETIME_FORMAT)
        dynamodb.update_item(TableName='demo-excamera', 
                            Key={ 'uuid4' : { 'S' : index } },  
                             ExpressionAttributeNames={ '#ST' : 'stage', '#T' : 'time_current_op' },
                             ExpressionAttributeValues={ ':s' : { 'S' : 'lambda_coordinator_starting_jobs' }, 
                                                         ':t' : { 'S' : t } },
                             UpdateExpression='SET #ST = :s, #T = :t',
        )
        

        # get lambda params
        lambda_names = ['arn:aws:lambda:us-west-1:387291866455:function:demo_excamera_recognizeface',
                        'arn:aws:lambda:us-west-2:387291866455:function:demo_excamera_recognizeface',
                        'arn:aws:lambda:us-east-1:387291866455:function:demo_excamera_recognizeface',
                        'arn:aws:lambda:us-east-2:387291866455:function:demo_excamera_recognizeface',
        #                'arn:aws:lambda:eu-west-1:387291866455:function:demo_excamera_recognizeface',
        #                'arn:aws:lambda:eu-central-1:387291866455:function:demo_excamera_recognizeface',
        #                'arn:aws:lambda:eu-west-2:387291866455:function:demo_excamera_recognizeface',
        #                'arn:aws:lambda:ap-southeast-1:387291866455:function:demo_excamera_recognizeface',
        #                'arn:aws:lambda:ap-southeast-2:387291866455:function:demo_excamera_recognizeface',
        #                'arn:aws:lambda:ap-northeast-2:387291866455:function:demo_excamera_recognizeface'
        ]

        lambda_regions = ['us-west-1',
                          'us-west-2',
                          'us-east-1',
                          'us-east-2',
        #                  'eu-west-1',
        #                  'eu-central-1',
        #                  'eu-west-2',
        #                  'ap-southwest-1',
        #                  'ap-southwest-2',
        #                  'ap-northeast-2'
        ]

        assert(len(lambda_names) == len(lambda_regions))

        lambda_job_args = [ {"frame_start_idx": i, "frame_stop_idx": min(i+FRAMES_PER_LAMBDA, FRAME_IDX_MAX), "face_model": \
                             request_id+".csv.gz", "request_id": request_id} \
                            for i in xrange(FRAME_IDX_MIN, FRAME_IDX_MAX, FRAMES_PER_LAMBDA)]


        lambda_bundle = []
        for i in xrange(len(lambda_job_args)):
            j = i % len(lambda_names)
            
            bundle = {
                'function_name' : lambda_names[j],
                'region' : lambda_regions[j],
                'job_args' : lambda_job_args[i]
            }
            lambda_bundle.append(bundle)

        # shuffle the list
        random.shuffle(lambda_bundle)

        responses = pool.map(launch_lambda, lambda_bundle)

        print responses

        print len(lambda_job_args)
        print FRAME_IDX_MIN, FRAME_IDX_MAX, FRAMES_PER_LAMBDA
        print len(responses)

        # end = True
        t = datetime.datetime.now().strftime(DATETIME_FORMAT)
        dynamodb.update_item(TableName='demo-excamera', 
                             Key={ 'uuid4' : { 'S' : index } },  
                             ExpressionAttributeNames={ '#ST' : 'stage', '#T' : 'time_current_op' },
                             ExpressionAttributeValues={ ':s' : { 'S' : 'lambda_coordinator_jobs_started' }, 
                                                         ':t' : { 'S' : t } },
                             UpdateExpression='SET #ST = :s, #T = :t',
        )

    conn.close()
    sock.close()

if __name__ == "__main__":
    start_lambda_coordinator_server()
