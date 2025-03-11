import numpy as np
import math
import os
import json
import requests
from datetime import datetime, timedelta
import subprocess
import base64
import stat
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization
from cryptography.fernet import Fernet



class PeakDetector:
    @staticmethod
    def find_peaks(data, height=50, distance=1, max_num=10):
        peak_indices = []
        candidate_indices = []

        for i in range(1, len(data) - 1):
            if data[i] > data[i - 1] and data[i] > data[i + 1]:
                candidate_indices.append(i)

        candidate_indices = [idx for idx in candidate_indices if data[idx] > height]
        candidate_indices.sort(key=lambda x: data[x], reverse=True)

        for idx in candidate_indices:
            if all(abs(idx - peak) >= distance for peak in peak_indices):
                peak_indices.append(idx)
                if len(peak_indices) == max_num:
                    break

        return sorted(peak_indices)

class PolynomialDetrendProcessor:
    def __init__(self, ppg_array, window_size, window_interval, order):
        self.ppg_array = ppg_array
        self.window_size = window_size
        self.window_interval = window_interval
        self.order = order
        self.ppg_array_without_dc = []

    def process(self):
        x_values = np.arange(1, self.window_size + 1)
        y_values = self.ppg_array[:self.window_size]
        vandermonde_matrix = np.vander(x_values, N=self.order + 1, increasing=True)
        x_transposed = vandermonde_matrix.T
        x_transposed_x = x_transposed @ vandermonde_matrix
        x_transposed_y = x_transposed @ y_values
        coefficients = np.linalg.solve(x_transposed_x, x_transposed_y)
        for i in range(self.window_size):
            trend = sum(coefficients[j] * (x_values[i] ** j) for j in range(self.order + 1))
            detrended_value = y_values[i] - trend
            self.ppg_array_without_dc.append(round(detrended_value, 4))
        return self.ppg_array_without_dc

class HeartRateAnalyzer:
    def __init__(self, cal_hr_time):
        self.hr_graph_elapsed = 0.0
        self.ppg_array = [0.0] * 50
        self.check_hr_count = 0
        self.hr_error_count = 0
        self.peak_error_count = 0
        self.result_hr = 0.0
        self.peak_bpm_values = []
        self.cal_hr_time = cal_hr_time

    def calculate_stddev(self, values):
        mean = np.mean(values)
        variance = np.mean((values - mean) ** 2)
        return math.sqrt(variance)

    def update_hr(self, interpolated_ppg, interpolated_acc):
        self.ppg_array.extend(interpolated_ppg)

        if len(self.ppg_array) >= 100:
            detrend_processor = PolynomialDetrendProcessor(self.ppg_array, 100, 10, 2)
            detrend_value = detrend_processor.process()

            is_ppg_zero = sum(self.ppg_array)
            if is_ppg_zero == 0:
                self.check_hr_count = 0
                self.result_hr = 0.0
                self.peak_bpm_values.clear()


            x_std = self.calculate_stddev([entry[0] for entry in interpolated_acc])
            y_std = self.calculate_stddev([entry[1] for entry in interpolated_acc])
            z_std = self.calculate_stddev([entry[2] for entry in interpolated_acc])

            # print("x_std, y_std, z_std", x_std, y_std, z_std)
            noise_threshold = x_std + y_std + z_std
            # print("noise_threshold", noise_threshold)

            mean = np.mean(detrend_value)
            std_dev = self.calculate_stddev(detrend_value)

            threshold_height = mean + (0.5 * std_dev)
            peak_indices = PeakDetector.find_peaks(detrend_value, height=threshold_height, distance=12)

            peak_intervals = []
            sampling_interval = 0.02

            for i in range(1, len(peak_indices)):
                index_diff = peak_indices[i] - peak_indices[i - 1]
                time_diff = index_diff * sampling_interval

                if 0.25 <= time_diff <= 1.5:
                    temp_hr = 60 / time_diff
                    if len(self.peak_bpm_values) >= 15:
                        if (self.result_hr != 0):
                            if abs((self.result_hr - temp_hr) / self.result_hr) < 0.20:
                                self.peak_bpm_values.append(temp_hr)
                                self.result_hr = np.mean(self.peak_bpm_values)
                    else:
                        self.peak_bpm_values.append(temp_hr)
                        self.result_hr = np.mean(self.peak_bpm_values)

            if len(self.peak_bpm_values) > 15:
                self.peak_bpm_values.pop(0)

        self.ppg_array = self.ppg_array[-50:]
        return [self.result_hr, detrend_value]


class EncryptedCacheManager:
    def __init__(self, cache_filename="license_cache.json"):
        # 사용자 홈 디렉토리 아래 숨김 폴더(~/.my_app) 생성
        self.cache_dir = os.path.join(os.path.expanduser("~"), ".my_app")
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)
        self.cache_file = os.path.join(self.cache_dir, cache_filename)

        # 고정된 암호화 키 (운영 환경에서는 이 값을 안전하게 보관하세요)
        self.key = b"39dqFhShnJIh0iIArAnknapNCzwwlcYhtXciGZf5rtw="
        self.cipher_suite = Fernet(self.key)

    def save_cache(self, cache_data):
        """암호화된 JSON 데이터를 캐시 파일에 저장"""
        json_data = json.dumps(cache_data).encode('utf-8')
        encrypted_data = self.cipher_suite.encrypt(json_data)

        # Windows 환경에서 캐시 파일이 이미 존재하면 읽기 전용 속성을 제거
        if os.name == "nt" and os.path.exists(self.cache_file):
            try:
                os.chmod(self.cache_file, stat.S_IWRITE)
            except Exception as e:
                print("Error using os.chmod:", e)
            try:
                subprocess.run("attrib -r " + self.cache_file, shell=True, check=True)
            except Exception as e:
                print("Error using attrib command:", e)

        # 파일 쓰기 시도, PermissionError 발생 시 파일 삭제 후 재시도
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

        # Linux/Unix 계열에서는 파일 권한을 소유자 전용 읽기/쓰기(0o600)로 설정
        if os.name != "nt":
            try:
                os.chmod(self.cache_file, 0o600)
            except Exception as e:
                print("Could not set file permissions:", e)
        else:
            print("Skipping os.chmod on Windows.")

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
        # 암호화된 캐시 파일 관리를 위한 EncryptedCacheManager 사용
        self.cache_manager = EncryptedCacheManager("license_cache.json")

    def subscribe_device(self, user_license, device_id):
        """
        1. POST API를 호출하여 라이선스와 device_id의 유효성을 확인합니다.
        2. 온라인 권한이 획득되면, 서버의 sub_end_date를 기준으로
           오프라인 사용 한도를 현재 시각부터 최대 1개월로 제한한 effective_expiration_str를 산출합니다.
        3. 암호화된 캐시 파일에 저장한 후, PUT API를 호출하여 offline 만료 일자를 서버에 전송합니다.
        4. 만약 POST/PUT 요청에 실패(예: 인터넷 연결 없음)하면, 캐시 파일을 이용해 최종 인증을 시도합니다.
        """
        post_payload = {
            "license_id": user_license,
            "device_id": device_id
        }
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

                    cache_data = {
                        "user_license": user_license,
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
                        "device_id": device_id,
                        "end_date": effective_expiration_str
                    }
                    put_response = requests.put(self.api_url, json=put_payload)
                    if put_response.status_code == 200:
                        print("Offline expiration date updated successfully.")
                    else:
                        print("Failed to update offline expiration date via PUT:", put_response.text)

                    return True
            return False
        except requests.exceptions.ConnectionError as conn_err:
            print("Connection error occurred (offline mode assumed):", conn_err)
            # 연결 오류 발생 시, 이미 존재하는 캐시 파일로 최종 인증 시도
            return self.final_authenticate()
        except requests.exceptions.HTTPError as http_err:
            # 서버 응답에서 "detail" 필드 추출
            error_detail = ""
            if http_err.response is not None:
                try:
                    error_json = http_err.response.json()
                    error_detail = error_json.get("detail", "")
                except Exception:
                    error_detail = http_err.response.text
            print("HTTP error occurred:", error_detail)
            return False

    def final_authenticate(self):
        """
        최종 인증을 캐시 파일을 통해 진행합니다.
        캐시 파일에 저장된 sub_end_date가 현재 시각보다 미래이면 최종 인증 성공으로 판단합니다.
        """
        cache_data = self.cache_manager.load_cache()
        if cache_data:
            expiration_str = cache_data.get("sub_end_date", "")
            user_license = cache_data.get("user_license", "")
            if expiration_str and user_license:
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
