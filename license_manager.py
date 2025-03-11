import requests
from datetime import datetime
import json


class LicenseManager:
    def __init__(self, api_url="http://211.118.82.103:8000/subscribe/device/"):
        self.api_url = api_url

    def subscribe_device(self, user_license, device_id):
        """
        서버에 라이선스와 device_id를 전달하고, 서버가 {valid, expiration_date} 정보를 리턴하면
        만료일이 현재보다 미래이면 그 정보를 offline 캐시로 저장하고 True를 반환합니다.
        """
        payload = {
            "license_id": user_license,
            "device_id": device_id
        }
        print("payload", payload)
        try:
            response = requests.post(self.api_url, json=payload)
            response.raise_for_status()  # 상태 코드가 200번대가 아니면 예외 발생
            resp_json = response.json()
            print("Response status code:", response.status_code)
            print("Response JSON:", resp_json)

            # 서버 응답에 valid와 expiration_date가 있다고 가정합니다.
            if resp_json.get("valid") and resp_json.get("expiration_date"):
                expiration_str = resp_json["expiration_date"]
                # 만료일은 "YYYY-MM-DD" 형식으로 온다고 가정
                expiration_date = datetime.strptime(expiration_str, "%Y-%m-%d")
                if expiration_date > datetime.now():
                    # 캐시 파일에 offline으로 저장
                    cache_data = {
                        "user_license": user_license,
                        "expiration_date": expiration_str
                    }
                    with open("license_cache.json", "w") as f:
                        json.dump(cache_data, f)
                    return True
            return False
        except requests.exceptions.HTTPError as http_err:
            print("HTTP error occurred:", http_err)
            return False
        except Exception as err:
            print("Other error occurred:", err)
            return False
