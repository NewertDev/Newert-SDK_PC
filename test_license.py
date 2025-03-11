import os
import json
from cryptography.fernet import Fernet
from datetime import datetime, timedelta

# 암호화 키와 라이선스 파일 경로 설정
KEY_FILE = "license_key.key"
LICENSE_FILE = "license_info.lic"


# 암호화 키 생성 및 저장
def generate_key():
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as key_file:
            key_file.write(key)


# 암호화 키 로드
def load_key():
    if not os.path.exists(KEY_FILE):
        raise FileNotFoundError("Encryption key not found. Please run the online mode first.")
    with open(KEY_FILE, "rb") as key_file:
        return key_file.read()


# 라이선스 정보 저장
def save_license_info(license_data):
    """라이선스 정보를 암호화하여 로컬에 저장"""
    key = load_key()
    fernet = Fernet(key)
    encrypted_data = fernet.encrypt(json.dumps(license_data).encode())
    with open(LICENSE_FILE, "wb") as license_file:
        license_file.write(encrypted_data)


# 라이선스 정보 로드
def load_license_info():
    """로컬에 저장된 라이선스 정보를 복호화하여 로드"""
    if not os.path.exists(LICENSE_FILE):
        raise FileNotFoundError("License file not found. Please authenticate online first.")
    key = load_key()
    fernet = Fernet(key)
    with open(LICENSE_FILE, "rb") as license_file:
        encrypted_data = license_file.read()
    decrypted_data = fernet.decrypt(encrypted_data).decode()
    return json.loads(decrypted_data)


# 오프라인 라이선스 인증
def authenticate_license():
    """오프라인 모드에서 라이선스 인증"""
    try:
        license_info = load_license_info()

        # 인증 조건 1: 상태 확인
        if license_info.get("status") != "valid":
            print("Invalid license status.")
            return False

        # 인증 조건 2: 유효 기간 확인
        last_auth_date = datetime.strptime(license_info.get("last_auth_date"), "%Y-%m-%d")
        if datetime.now() > last_auth_date + timedelta(days=30):
            print("License expired. Please authenticate online.")
            return False

        print("License authenticated successfully.")
        return True
    except Exception as e:
        print(f"License authentication failed: {e}")
        return False


# 테스트
if __name__ == "__main__":
    # Step 1: 암호화 키 생성
    generate_key()

    # Step 2: 온라인 인증 후 라이선스 저장 (예시)
    # 마지막 웹 인증 날짜 포함
    license_data = {
        "user_id": "user123",
        "device_id": "device456",
        "status": "valid",  # valid or invalid
        "last_auth_date": datetime.now().strftime("%Y-%m-%d"),  # 현재 날짜 저장
    }
    save_license_info(license_data)
    print("License information saved successfully.")

    # Step 3: 오프라인 인증
    if authenticate_license():
        print("Accessing Pro mode features...")
    else:
        print("Access denied. Please authenticate online.")
