import json
import boto3
import os
import base64
import urllib.parse
import urllib.request
from datetime import datetime
dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')
TABLE_NAME = os.environ.get('TABLE_NAME', 'Receipts')
table = dynamodb.Table(TABLE_NAME)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

def analyze_receipt_with_ai(bucket, key):
    # S3에서 이미지 읽기
    response = s3.get_object(Bucket=bucket, Key=key)
    image_bytes = response['Body'].read()
    base64_image = base64.b64encode(image_bytes).decode('utf-8')

    prompt = """
    이 영수증 이미지에서 구매한 식재료 항목들을 추출해줘.
    응답은 반드시 다른 설명 없이 JSON 배열 형태로만 출력해야 해.

    [응답 형식 예시]
    [
      {"name": "해표참기름", "category": "조미료", "quantity": 1},
      {"name": "대파", "category": "채소", "quantity": 1}
    ]

    카테고리는 (채소, 정육, 수산, 과일, 유제품, 조미료, 냉동/가공, 기타) 중 하나로 분류해줘.
    식재료가 아닌 공산품이나 수수료 등은 제외해줘.
    """

    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                    }
                ]
            }
        ],
        "max_tokens": 1000
    }

    # urllib 사용 
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        },
        method="POST"
    )

    with urllib.request.urlopen(req) as res:
        res_data = json.loads(res.read().decode("utf-8"))
        result_text = res_data['choices'][0]['message']['content'].strip()

    if result_text.startswith("```json"):
        result_text = result_text.replace("```json", "").replace("```", "").strip()

    return json.loads(result_text)

def lambda_handler(event, context):
    try:
        for record in event['Records']:
            bucket = record['s3']['bucket']['name']
            key = urllib.parse.unquote_plus(record['s3']['object']['key'])
            
            key_parts = key.split('/')
            user_id = key_parts[1] if len(key_parts) >= 3 else 'anonymous'
            receipt_id = key_parts[2].replace('.jpg', '') if len(key_parts) >= 3 else key

            ai_result = analyze_receipt_with_ai(bucket, key)

            # 💡 DynamoDB 저장 시 createdAt 추가
            table.put_item(
                Item={
                    'userId': user_id,
                    'receiptId': receipt_id,
                    'status': 'COMPLETED',
                    'aiResult': json.dumps(ai_result, ensure_ascii=False),
                    'createdAt': datetime.now().isoformat()  # 💡 현재 시간을 ISO 형식으로 저장
                }
            )

        return {'statusCode': 200, 'body': json.dumps('Success')}
    except Exception as e:
        print(f"Error processing receipt: {str(e)}")
        raise e