import json
import boto3
import os
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ.get('TABLE_NAME', 'Receipts')
table = dynamodb.Table(TABLE_NAME)
# deploy test
def lambda_handler(event, context):
    print(event)
    try:
        # Query String 파라미터에서 userId 추출
        query_params = event.get('queryStringParameters') or {}
        user_id = query_params.get('userId')

        if not user_id:
            return {
                'statusCode': 400,
                'headers': {'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'userId는 필수 파라미터입니다.'})
            }

        # Scan 대신 Query를 사용해 해당 유저의 데이터만 가져옴
        response = table.query(
            KeyConditionExpression=Key('userId').eq(user_id)
        )
        
        items = response.get('Items', [])

        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Credentials': True
            },
            'body': json.dumps(items)
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': str(e)})
        }