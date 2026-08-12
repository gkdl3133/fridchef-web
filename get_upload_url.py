import json
import boto3
import os
import uuid

s3_client = boto3.client('s3')
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'my-refrigerator-receipts-nonong')
# deploy test
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
                'body': json.dumps({'error': 'userId가 필요합니다.'}, ensure_ascii=False)
            }

        # 프론트엔드가 요구하는 receiptId와 S3 파일 키 생성
        receipt_id = str(uuid.uuid4())
        file_name = f"{user_id}/{receipt_id}.jpg"

        # S3 Presigned URL 생성 (프론트엔드 헤더의 메타데이터와 완벽히 일치시킴)
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': file_name,
                'ContentType': 'image/jpeg',
                'Metadata': {
                    'userid': user_id,
                    'receiptid': receipt_id
                }
            },
            ExpiresIn=300
        )

        # 프론트엔드가 기대하는 형태({ uploadUrl, receiptId })로 응답 반환
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'uploadUrl': presigned_url,
                'receiptId': receipt_id
            }, ensure_ascii=False)
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)}, ensure_ascii=False)
        }