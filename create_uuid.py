import uuid

def generate_subscription_uuid():
    """
    구독을 위한 UUID v4 생성 함수
    :return: 문자열 형태의 UUID v4
    """
    return str(uuid.uuid4())

if __name__ == '__main__':
    # 결제 성공 후 UUID 생성 및 출력
    subscription_uuid = generate_subscription_uuid()
    print("Generated Subscription UUID:", subscription_uuid)