import json
import boto3
import os

dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ.get('TABLE_NAME', 'Receipts')
table = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': '*',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
    }

    if event.get('httpMethod') == 'OPTIONS':
        return {'statusCode': 200, 'headers': headers, 'body': ''}

    try:
        query_params = event.get('queryStringParameters') or {}
        user_id = query_params.get('userId')

        if not user_id:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'userId가 필요합니다.'})
            }

        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('userId').eq(user_id)
        )

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(response.get('Items', []), ensure_ascii=False)
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }