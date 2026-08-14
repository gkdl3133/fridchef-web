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
# deploy test
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
      {"name": "해표참기름", "category": "식용유/참기름", "quantity": 1},
      {"name": "대파", "category": "채소", "quantity": 1}
    ]

    카테고리는 반드시 아래 27개 중분류 중 정확히 하나로만 분류해줘:
    ['가루/분말류', '간편조리식품', '건과류', '건어물', '견과류', '계란/알류', '과일', '과자/떡/베이커리', '김치', '라면/면류', '밀키트', '반찬', '생수/탄산수', '소스/드레싱', '수산물', '식용유/참기름', '쌀/잡곡', '우유/두유/요거트', '음료', '장류', '잼/시럽', '정육', '조미료', '채소', '치즈/유가공품', '커피/차류', '통조림/캔']

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
            
            print(f"Processing S3 Key: {key}") # 디버깅용 로그

            key_parts = key.split('/')
            
            # 💡 [핵심 수정] S3 경로 구조가 어떻게 들어오든 안전하게 파싱하도록 개선
            # 예: 'uploads/kakao_123/uuid.jpg' 이거나 'kakao_123/uuid.jpg' 모두 대응
            user_id = 'anonymous'
            receipt_id = key.replace('/', '_').replace('.jpg', '') # 최후의 보완책

            if 'uploads' in key_parts and len(key_parts) >= 3:
                # 'uploads/유저ID/고유ID.jpg' 형태인 경우
                user_idx = key_parts.index('uploads') + 1
                if len(key_parts) > user_idx:
                    user_id = key_parts[user_idx]
                if len(key_parts) > user_idx + 1:
                    receipt_id = key_parts[user_idx + 1].replace('.jpg', '')
            elif len(key_parts) >= 2:
                # '유저ID/고유ID.jpg' 형태인 경우
                user_id = key_parts[0]
                receipt_id = key_parts[1].replace('.jpg', '')

            ai_result = analyze_receipt_with_ai(bucket, key)

            table.put_item(
                Item={
                    'userId': user_id,
                    'receiptId': receipt_id,
                    'status': 'COMPLETED',
                    'aiResult': json.dumps(ai_result, ensure_ascii=False),
                    'createdAt': datetime.now().isoformat()
                }
            )

        return {'statusCode': 200, 'body': json.dumps('Success')}
    except Exception as e:
        print(f"Error processing receipt: {str(e)}")
        raise e