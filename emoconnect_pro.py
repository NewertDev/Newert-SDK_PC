import math
import numpy as np


#########################################
# PeakDetector 클래스
#########################################
class PeakDetector:
    @staticmethod
    def find_peaks(data, height=50, distance=1, max_num=10):
        """
        data: 실수형 리스트
        height: 피크 최소 높이 기준
        distance: 피크 간 최소 인덱스 차이
        max_num: 반환할 최대 피크 개수

        반환: 오름차순 정렬된 피크 인덱스 리스트
        """
        candidate_indices = []
        # 1. 모든 피크 후보 (양쪽 이웃보다 큰 값)
        for i in range(1, len(data) - 1):
            if data[i] > data[i - 1] and data[i] > data[i + 1]:
                candidate_indices.append(i)

        # 2. height 기준 필터링
        candidate_indices = [idx for idx in candidate_indices if data[idx] > height]

        # 3. 값이 큰 순으로 정렬 후, distance 기준 필터링
        candidate_indices.sort(key=lambda idx: data[idx], reverse=True)
        peak_indices = []
        for idx in candidate_indices:
            is_peak = True
            for existing in peak_indices:
                if abs(idx - existing) < distance:
                    is_peak = False
                    break
            if is_peak:
                peak_indices.append(idx)
                if len(peak_indices) == max_num:
                    break
        # 4. 오름차순 정렬하여 반환
        return sorted(peak_indices)

    @staticmethod
    def detect_peaks(data):
        """
        1차 및 2차 미분을 이용하여 피크 감지.

        data: 실수형 리스트
        반환: 피크 인덱스 리스트
        """
        if len(data) < 3:
            return []

        # 1차 미분
        first_derivative = [data[i] - data[i - 1] for i in range(1, len(data))]
        # 2차 미분
        second_derivative = [first_derivative[i] - first_derivative[i - 1] for i in range(1, len(first_derivative))]

        peak_indices = []
        for i in range(1, len(second_derivative)):
            if second_derivative[i - 1] > 0 and second_derivative[i] < 0:
                peak_indices.append(i)
        return peak_indices


#########################################
# PolynomialDetrendProcessor 클래스
#########################################
class PolynomialDetrendProcessor:
    def __init__(self, ppg_array, window_size, window_interval, order):
        """
        ppg_array: PPG 데이터 리스트
        window_size: 분석에 사용할 데이터 포인트 수 (여기서는 100, 즉 2초 데이터 @50Hz)
        window_interval: (현재 구현에서는 사용되지 않음)
        order: 다항식 차수
        """
        self.ppg_array = ppg_array
        self.window_size = window_size
        self.window_interval = window_interval
        self.order = order
        self.ppg_array_without_dc = []

    def process(self):
        """
        ppg_array의 앞 window_size 개 데이터를 사용하여 다항식 피팅 후,
        추세(DC 성분)를 제거한 데이터를 반환.
        """
        # x 값: 1부터 window_size까지
        x_values = np.array([i + 1 for i in range(self.window_size)], dtype=float)
        y_values = np.array(self.ppg_array[:self.window_size], dtype=float)

        # Vandermonde 행렬 생성 (열: 1, x, x^2, ..., x^order)
        X = np.vander(x_values, N=self.order + 1, increasing=True)

        # Normal Equation: (X^T * X) * a = X^T * y 를 풀어 계수 계산
        XtX = np.dot(X.T, X)
        Xty = np.dot(X.T, y_values)
        coefficients = np.linalg.solve(XtX, Xty)

        detrended = []
        for i in range(self.window_size):
            # 추세 계산: 각 항에 계수를 곱해 합산
            trend = sum(coefficients[j] * (x_values[i] ** j) for j in range(self.order + 1))
            detrended_value = y_values[i] - trend
            detrended.append(round(detrended_value, 4))

        self.ppg_array_without_dc = detrended
        return self.ppg_array_without_dc


#########################################
# HeartRateAnalyzer 클래스
#########################################
class HeartRateAnalyzer:
    def __init__(self, cal_hr_time=0, threshold1=5.0, threshold2=10.0, threshold3=15.0):
        """
        cal_hr_time: 안정적인 심박수 계산을 위한 최소 분석 주기 횟수 (이제 0으로 설정하면 바로 계산)
        threshold1, threshold2, threshold3: 가속도 노이즈 임계값 기준
        """
        self.hr_graph_elapsed = 0.0
        self.ppg_array = [0.0] * 50  # 초기 PPG 버퍼
        self.hr_error_count = 0
        self.peak_error_count = 0
        self.result_hr = 0.0
        self.peak_bpm_values = []
        self.cal_hr_time = cal_hr_time
        self.threshold1 = threshold1
        self.threshold2 = threshold2
        self.threshold3 = threshold3

    def calculate_stddev(self, values):
        mean = np.mean(values)
        variance = np.mean((np.array(values) - mean) ** 2)
        return math.sqrt(variance)

    def update_hr(self, interpolated_ppg, interpolated_acc):
        """
        interpolated_ppg: 새로운 PPG 데이터 리스트
        interpolated_acc: 새로운 가속도 데이터 리스트, 각 항목은 [x, y, z]

        반환: (현재 HR, detrended 데이터 리스트)

        50Hz로 PPG 데이터를 수집하므로, 2초 데이터 = 100 샘플 기준으로 HR 계산
        """
        self.ppg_array.extend(interpolated_ppg)

        # 2초 데이터, 즉 100 샘플 이상이 모이면 HR 계산 수행
        if len(self.ppg_array) >= 100:
            # 초기 디트렌딩 (파라미터 2 사용)
            processor = PolynomialDetrendProcessor(self.ppg_array, 100, 10, 2)
            detrend_value = processor.process()

            # PPG 신호가 모두 0이면 센서 미착용 등으로 판단
            if sum(self.ppg_array) == 0:
                self.result_hr = 0.0
                self.peak_bpm_values.clear()
            else:
                # 가속도 노이즈 임계값 계산
                x_std = self.calculate_stddev([entry[0] for entry in interpolated_acc])
                y_std = self.calculate_stddev([entry[1] for entry in interpolated_acc])
                z_std = self.calculate_stddev([entry[2] for entry in interpolated_acc])
                noise_threshold = x_std + y_std + z_std

                # 디트렌딩 신호의 통계량 계산
                mean_val = np.mean(detrend_value)
                std_dev = self.calculate_stddev(detrend_value)
                threshold_height = mean_val + (0.5 * std_dev)

                # 기본 피크 검출 파라미터
                min_distance = 12
                max_num = 8
                sampling_interval = 0.02  # 초 단위

                # 노이즈에 따른 디트렌딩 파라미터 조정
                if self.threshold1 <= noise_threshold < self.threshold2:
                    processor = PolynomialDetrendProcessor(self.ppg_array, 100, 10, 5)
                    detrend_value = processor.process()
                    mean_val = np.mean(detrend_value)
                    std_dev = self.calculate_stddev(detrend_value)
                    threshold_height = mean_val + (0.5 * std_dev)
                elif noise_threshold >= self.threshold2:
                    if noise_threshold >= self.threshold3 and self.result_hr >= 140:
                        processor = PolynomialDetrendProcessor(self.ppg_array, 100, 10, 25)
                        detrend_value = processor.process()
                        mean_val = np.mean(detrend_value)
                        std_dev = self.calculate_stddev(detrend_value)
                        threshold_height = mean_val + (0.5 * std_dev)
                    else:
                        processor = PolynomialDetrendProcessor(self.ppg_array, 100, 10, 7)
                        detrend_value = processor.process()
                        mean_val = np.mean(detrend_value)
                        std_dev = self.calculate_stddev(detrend_value)
                        threshold_height = mean_val + (0.5 * std_dev)

                # 피크 검출
                peak_indices = PeakDetector.find_peaks(detrend_value,
                                                       height=threshold_height,
                                                       distance=min_distance,
                                                       max_num=max_num)
                peak_intervals = []
                for i in range(1, len(peak_indices)):
                    index_diff = peak_indices[i] - peak_indices[i - 1]
                    time_diff = index_diff * sampling_interval
                    if time_diff <= 0.20 or time_diff >= 1.5:
                        continue
                    temp_hr = 60 / time_diff
                    if self.result_hr > 0 and len(self.peak_bpm_values) >= 15:
                        if abs((self.result_hr - temp_hr) / self.result_hr) < 0.20:
                            self.hr_error_count = 0
                            peak_intervals.append(time_diff)
                        else:
                            if len(peak_indices) < 4:
                                self.hr_error_count += 1
                            if self.hr_error_count >= 10:
                                if self.peak_bpm_values:
                                    self.peak_bpm_values.pop(0)
                                self.peak_bpm_values.append(temp_hr)
                                self.result_hr = np.mean(self.peak_bpm_values)
                    else:
                        peak_intervals.append(time_diff)

                if len(self.peak_bpm_values) > 15:
                    self.peak_bpm_values.pop(0)

                if peak_intervals:
                    avg_peak_interval = np.mean(peak_intervals)
                    bpm = 60 / avg_peak_interval
                    if not self.peak_bpm_values:
                        self.peak_bpm_values.append(bpm)
                        self.result_hr = bpm
                    else:
                        self.peak_bpm_values.append(bpm)
                        self.result_hr = np.mean(self.peak_bpm_values)

            # 최신 50개 샘플만 유지 (오버랩하여 다음 2초 분석 시 1초의 중첩)
            self.ppg_array = self.ppg_array[-50:]
            return self.result_hr, detrend_value
        else:
            return self.result_hr, []


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
                subprocess.run("attrib -r " + self.cache_file, shell=True, check=True)
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
