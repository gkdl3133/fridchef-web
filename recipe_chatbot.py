import json
import os
import urllib.request

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
# deploy test1
def lambda_handler(event, context):
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'OPTIONS,POST'
    }

    # Preflight OPTIONS 요청에 대해 즉시 200 OK 응답 반환
    http_method = event.get('requestContext', {}).get('http', {}).get('method') or event.get('httpMethod')
    if http_method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': headers,
            'body': ''
        }

    try:
        body = json.loads(event.get('body', '{}'))
        user_id = body.get('userId')
        ingredients = body.get('ingredients', [])
        user_message = body.get('message', '이 재료들로 뭐 만들어 먹을까?')

        if not user_id:
            return {'statusCode': 400, 'headers': headers, 'body': json.dumps({'error': 'userId가 필요합니다.'}, ensure_ascii=False)}

        system_prompt = f"""
        너는 대한민국 최고의 베테랑 가정식 프로 AI 셰프야. 유저의 냉장고 재료와 요청사항을 바탕으로 누구나 따라 할 수 있고 실제로 맛있는 현실적인 집밥 요리를 추천해줘.
        
        [현재 유저의 냉장고 재료 목록]
        {json.dumps(ingredients, ensure_ascii=False)}

        [절대 규칙]
        1. **맛있는 요리만 추천:** 절대 상식에 어긋나거나 맛이 이상할 것 같은 조합(괴식)은 만들지 마세요. 냉장고에 있는 재료만으로 맛있는 조합이 안 나온다면, 차라리 "기본적인 집에 있을 법한 양념(소금, 간장, 식용유 등)"은 추가해도 된다고 가정하고 평범하고 검증된 레시피를 추천해줘.
        2. **핵심 재료 선별:** 재료 목록에 있는 것 중 **실제로 그 요리에 어울리는 주재료 1~3개와 필수 부재료만 선택**해서 사용하세요. 목록에 있다고 해서 상관없는 재료를 억지로 다 갖다 붙이면 절대 안 됩니다.
        3. **현실적인 계량:** 각 재료의 사용량은 실제 요리할 때 들어가는 **현실적인 적정량(예: 대파 1/2대, 다진 마늘 1스푼, 고춧가루 1큰술 등)**으로만 정확히 표기해줘.
        4. **조리 순서 명확화:** 레시피를 추천할 때는 1) 요리 이름, 2) 사용된 냉장고 재료, 3) 간단한 조리 순서(1, 2, 3단계)를 보기 좋게 정리해서 친절하고 먹음직스러운 어조로 대답해줘.
        """

        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "max_tokens": 800,
            "temperature": 0.7
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

        with urllib.request.urlopen(req, timeout=9) as res:
            res_data = json.loads(res.read().decode("utf-8"))
            ai_reply = res_data['choices'][0]['message']['content'].strip()

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({'reply': ai_reply}, ensure_ascii=False)
        }

    except Exception as e:
        print(f"Chatbot Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)}, ensure_ascii=False)
        }