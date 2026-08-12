import json
import boto3
import os
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ.get('TABLE_NAME', 'Receipts')
table = dynamodb.Table(TABLE_NAME)
# deploy test
def lambda_handler(event, context):
    # 브라우저 CORS 허용 헤더
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': '*',
        'Access-Control-Allow-Methods': 'OPTIONS,GET,POST,PUT,DELETE'
    }

    # Preflight(OPTIONS) 요청 처리
    http_method = event.get('requestContext', {}).get('http', {}).get('method') or event.get('httpMethod')
    if http_method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': headers,
            'body': ''
        }

    try:
        query_params = event.get('queryStringParameters') or {}
        body = {}
        if event.get('body'):
            try:
                body = json.loads(event.get('body'))
            except:
                body = {}

        # 1. DELETE (직접 삭제 요청)
        if http_method == 'DELETE':
            user_id = query_params.get('userId')
            receipt_id = query_params.get('receiptId')

            if not user_id or not receipt_id:
                return {'statusCode': 400, 'headers': headers, 'body': json.dumps({'error': 'userId와 receiptId가 필요합니다.'}, ensure_ascii=False)}

            table.delete_item(Key={'userId': user_id, 'receiptId': receipt_id})

            return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'message': '삭제 성공'}, ensure_ascii=False)}

        # 2. PUT / POST (수정, 자동 삭제, 레시피 재료 자동 차감 로직 통합)
        elif http_method in ['PUT', 'POST']:
            u_id = body.get('userId') or query_params.get('userId')
            r_id = body.get('receiptId') or query_params.get('receiptId')
            action = body.get('action')

            if not u_id:
                return {'statusCode': 400, 'headers': headers, 'body': json.dumps({'error': 'userId가 필요합니다.'}, ensure_ascii=False)}

            # 💡 [개선된 레시피 사용 시 냉장고 재료 자동 차감 로직]
            if action == 'use_recipe':
                print(f"=== [DEBUG] use_recipe 진입 성공! userId: {u_id} ===")
                ingredients_used = body.get('ingredientsUsed', []) 
                print(f"=== [DEBUG] 전달받은 사용 재료 목록: {ingredients_used} ===")
                
                if not ingredients_used:
                    return {'statusCode': 400, 'headers': headers, 'body': json.dumps({'error': '차감할 재료 목록이 없습니다.'}, ensure_ascii=False)}

                # 해당 유저의 모든 영수증 조회
                response = table.query(
                    KeyConditionExpression=Key('userId').eq(u_id)
                )
                items = response.get('Items', [])
                print(f"=== [DEBUG] DB에서 조회된 영수증 개수: {len(items)}개 ===")

                # 전달받은 사용 재료들을 하나씩 처리
                for recipe_item in ingredients_used:
                    target_name = str(recipe_item.get('name', '')).strip()
                    used_qty = float(recipe_item.get('quantity', 1))

                    # 수량이 0 이하인 재료는 차감 대상에서 제외
                    if used_qty <= 0:
                        continue

                    # 각 영수증을 돌며 해당 재료가 있는지 탐색
                    for receipt in items:
                        raw_ai_result = receipt.get('aiResult', '[]')
                        
                        # aiResult가 문자열 형태라면 리스트로 변환
                        if isinstance(raw_ai_result, str):
                            try:
                                ai_result = json.loads(raw_ai_result)
                            except:
                                ai_result = []
                        else:
                            ai_result = raw_ai_result

                        receipt_updated = False
                        for ingredient in ai_result:
                            db_name = str(ingredient.get('name', '')).strip()
                            
                            # 이름이 일치하는 경우 수량 차감
                            if db_name == target_name:
                                current_qty = float(ingredient.get('quantity', 1))
                                if current_qty > 0:
                                    current_qty -= used_qty
                                    ingredient['quantity'] = max(0.0, round(current_qty, 2))
                                    receipt_updated = True
                                    print(f"=== [MATCH & SUBTRACT] '{db_name}' 수량 갱신: 남은 수량 {ingredient['quantity']} ===")

                        # 이 영수증에서 실제로 재료가 깎였다면 즉시 DB에 반영 후 해당 재료 처리 완료
                        if receipt_updated:
                            print(f"=== [DB UPDATE] 영수증 ID {receipt['receiptId']} 갱신 실행 ===")
                            table.update_item(
                                Key={
                                    'userId': u_id,
                                    'receiptId': receipt['receiptId']
                                },
                                UpdateExpression="SET aiResult = :val",
                                ExpressionAttributeValues={
                                    ':val': json.dumps(ai_result, ensure_ascii=False)
                                }
                            )
                            break # 다음 차감 재료로 이동

                return {
                    'statusCode': 200,
                    'headers': headers,
                    'body': json.dumps({'message': '레시피에 사용된 재료가 냉장고에서 성공적으로 차감되었습니다!'}, ensure_ascii=False)
                }

            ai_result = body.get('aiResult') or body.get('items')

            if not r_id:
                return {'statusCode': 400, 'headers': headers, 'body': json.dumps({'error': 'receiptId가 필요합니다.'}, ensure_ascii=False)}

            # 품목이 비어있으면 DB에서 물리적으로 삭제
            if ai_result is None or (isinstance(ai_result, list) and len(ai_result) == 0):
                table.delete_item(
                    Key={
                        'userId': u_id,
                        'receiptId': r_id
                    }
                )
                return {
                    'statusCode': 200, 
                    'headers': headers, 
                    'body': json.dumps({'message': '품목이 없어 영수증 레코드가 삭제되었습니다.'}, ensure_ascii=False)
                }

            # 일반 정상 업데이트
            table.update_item(
                Key={
                    'userId': u_id,
                    'receiptId': r_id
                },
                UpdateExpression="SET aiResult = :val",
                ExpressionAttributeValues={
                    ':val': json.dumps(ai_result, ensure_ascii=False) if isinstance(ai_result, (list, dict)) else ai_result
                }
            )

            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({'message': '업데이트 성공'}, ensure_ascii=False)
            }
            
        return {
            'statusCode': 400,
            'headers': headers,
            'body': json.dumps({'error': f'지원하지 않는 메서드입니다: {http_method}'}, ensure_ascii=False)
        }

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)}, ensure_ascii=False)
        }