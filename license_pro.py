
import os
import json
import requests
import subprocess
import stat
from datetime import datetime, timedelta
from cryptography.fernet import Fernet


class EncryptedCacheManager:
    def __init__(self, cache_filename="license_cache.json"):
        # 캐시 파일 경로만 계산 (디렉토리는 나중에 온라인 인증 시 생성)
        self.cache_dir = os.path.join(os.path.expanduser("~"), ".my_app")
        self.cache_file = os.path.join(self.cache_dir, cache_filename)
        # 고정된 암호화 키 사용 (운영 환경에서는 이 값을 안전하게 보관)
        self.key = b"39dqFhShnJIh0iIArAnknapNCzwwlcYhtXciGZf5rtw="
        self.cipher_suite = Fernet(self.key)

    def save_cache(self, cache_data):
        """온라인 인증이 확인된 후에 암호화된 JSON 데이터를 캐시 파일에 저장"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)

        json_data = json.dumps(cache_data).encode('utf-8')
        encrypted_data = self.cipher_suite.encrypt(json_data)

        # Windows: 캐시 파일이 존재하면 읽기 전용 속성을 제거
        if os.name == "nt" and os.path.exists(self.cache_file):
            try:
                os.chmod(self.cache_file, stat.S_IWRITE)
            except Exception as e:
                print("Error using os.chmod:", e)
            try:
                subprocess.run("attrib -r " + self.cache_file, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print("Error using attrib command:", e)

        try:
            with open(self.cache_file, "wb") as f:
                f.write(encrypted_data)
        except PermissionError as pe:
            print("PermissionError encountered. Attempting to remove existing file.")
            try:
                os.remove(self.cache_file)
                with open(self.cache_file, "wb") as f:
                    f.write(encrypted_data)
            except Exception as e:
                print("Failed to remove and rewrite cache file:", e)
                raise pe

        if os.name != "nt":
            try:
                os.chmod(self.cache_file, 0o600)
            except Exception as e:
                print("Could not set file permissions:", e)
        else:
            print("Skipping os.chmod on Windows.")

        print("Encrypted cache saved.")

    def load_cache(self):
        """캐시 파일이 존재하면 복호화하여 JSON 데이터로 반환"""
        if not os.path.exists(self.cache_file):
            print("No cache file found.")
            return None
        try:
            with open(self.cache_file, "rb") as f:
                encrypted_data = f.read()
            decrypted_data = self.cipher_suite.decrypt(encrypted_data)
            cache_data = json.loads(decrypted_data.decode('utf-8'))
            print("Encrypted cache loaded successfully.")
            return cache_data
        except Exception as e:
            print("Error loading cache file:", e)
            return None


class LicenseManager:
    def __init__(self, api_url="https://api.biosignal-datahub.com/subscribe/device/"):
        self.api_url = api_url
        # device_id와 user_license는 온라인 인증 시 설정됨.
        self.device_id = None
        self.user_license = None
        self.cache_manager = None

    def subscribe_device(self, user_license, device_id):
        """
        1. POST API를 통해 라이선스와 device_id의 유효성을 확인합니다.
        2. 온라인 권한이 획득되면, 서버의 sub_end_date를 기준으로
           오프라인 사용 한도를 현재 시각부터 최대 1개월로 제한한 effective_expiration_str를 산출합니다.
        3. 해당 정보를 암호화된 캐시 파일(디바이스별 파일)에 저장하고,
           PUT API를 호출하여 offline 만료 일자를 서버에 전송합니다.
        4. 만약 온라인 요청 실패 시, 캐시 파일을 이용해 최종 인증을 시도합니다.
        """
        # 온라인 인증 시 device_id와 user_license를 전달받아 저장
        self.device_id = device_id
        self.user_license = user_license
        # device_id를 이용하여 캐시 파일명을 정하고 cache_manager를 초기화
        cache_filename = f"license_cache_{device_id}.json"
        self.cache_manager = EncryptedCacheManager(cache_filename)

        post_payload = {
            "license_id": user_license,
            "device_id": self.device_id
        }
        print("POST Payload:", post_payload)
        try:
            post_response = requests.post(self.api_url, json=post_payload)
            post_response.raise_for_status()
            post_resp_json = post_response.json()
            print("POST Server Response:", post_resp_json)

            if post_resp_json.get("Result") and post_resp_json.get("sub_end_date"):
                expiration_str = post_resp_json["sub_end_date"]
                server_expiration = datetime.strptime(expiration_str, "%Y-%m-%d")
                if server_expiration > datetime.now():
                    one_month_later = datetime.now() + timedelta(days=30)
                    effective_expiration = min(server_expiration, one_month_later)
                    effective_expiration_str = effective_expiration.strftime("%Y-%m-%d")

                    # 캐시 데이터에 device_id와 user_license도 저장합니다.
                    cache_data = {
                        "user_license": user_license,
                        "device_id": self.device_id,
                        "sub_end_date": effective_expiration_str
                    }
                    self.cache_manager.save_cache(cache_data)

                    if os.name == "nt":
                        try:
                            subprocess.call(["attrib", "+h", self.cache_manager.cache_file])
                        except Exception as e:
                            print("Error setting hidden attribute on Windows:", e)

                    put_payload = {
                        "license_id": user_license,
                        "device_id": self.device_id,
                        "end_date": effective_expiration_str
                    }
                    print("PUT Payload:", put_payload)
                    put_response = requests.put(self.api_url, json=put_payload)
                    if put_response.status_code == 200:
                        print("Offline expiration date updated successfully via PUT.")
                    else:
                        print("Failed to update offline expiration date via PUT:", put_response.text)

                    return True
            return False
        except requests.exceptions.ConnectionError as conn_err:
            print("Connection error occurred (offline mode assumed):", conn_err)
            return self.final_authenticate()
        except requests.exceptions.HTTPError as http_err:
            error_detail = ""
            if http_err.response is not None:
                try:
                    error_json = http_err.response.json()
                    error_detail = error_json.get("detail", "")
                except Exception:
                    error_detail = http_err.response.text
            print("HTTP error occurred:", error_detail)
            return False
        except Exception as err:
            print("Other error occurred:", err)
            return False

    def final_authenticate(self):
        """
        캐시 파일에 저장된 user_license, device_id, 그리고 sub_end_date를 확인하여,
        user_license와 device_id가 현재와 일치하고, sub_end_date가 현재 시각보다 미래이면
        최종 인증 성공으로 판단합니다.
        """
        if not self.cache_manager:
            print("Final authentication failed: No cache manager initialized.")
            return False
        cache_data = self.cache_manager.load_cache()
        if cache_data:
            if cache_data.get("device_id") != self.device_id:
                print("Final authentication failed: Device mismatch.")
                return False
            if cache_data.get("user_license") != self.user_license:
                print("Final authentication failed: License mismatch.")
                return False
            expiration_str = cache_data.get("sub_end_date", "")
            if expiration_str:
                effective_expiration = datetime.strptime(expiration_str, "%Y-%m-%d")
                if effective_expiration > datetime.now():
                    print("Final authentication passed. Offline license is valid until:", expiration_str)
                    return True
                else:
                    print("Final authentication failed: Cached license has expired.")
            else:
                print("Final authentication failed: Incomplete cache data.")
        else:
            print("Final authentication failed: No cached license found.")
        return False


# 테스트용 실행 코드
if __name__ == "__main__":
    # 예시: DEVICE123로 온라인 인증 후 캐시 파일 생성
    lm1 = LicenseManager()
    if lm1.subscribe_device("SAMPLE_LICENSE", "DEVICE123"):
        print("License subscription successful on DEVICE123.")
    else:
        print("License subscription failed on DEVICE123.")

    # 예시: 다른 디바이스 (DEVICE456)로 오프라인 인증 시도
    lm2 = LicenseManager()
    # 여기서는 online subscribe_device를 호출하지 않으므로 cache_manager는 None인 상태입니다.
    # 최종 인증 호출 시, DEVICE456에 해당하는 캐시 파일은 없거나 device_id가 일치하지 않아 인증에 실패해야 합니다.
    if lm2.final_authenticate():
        print("Final authentication passed on DEVICE456.")
    else:
        print("Final authentication failed on DEVICE456.")
