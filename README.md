# VitalTrack-SDK_PC
VitalTrack SDK의 PC 버전 저장소
Windows, macOS, Linux에서 사용 가능</br>
</br>
</br>

## 프로그램 사용 방법

### 1. VitalTrack 장비 블루투스 연결
프로그램이 실행되면 좌측 상단의 'BLE 장치 검색' 버튼을 클릭하여 연결할 장비를 검색합니다.</br>
잠시 후 목록에 장비가 나타나면, 원하는 ID를 가진 장비를 선택하고 목록 아래 '연결' 버튼을 클릭합니다.</br>
연결이 성공하면 메시지상자가 표시됩니다.

### 2. 측정 시작과 종료
장비가 연결되면 우측 상단에 연결된 장비 이름이 표시됩니다.</br>
하단의 '측정 시작' 버튼을 클릭하여 측정을 시작하면 장비로부터 발생한 데이터가 표시됩니다.</br>
'측정 종료'버튼을 클릭하면 측정을 종료할 수 있습니다.</br>

### 3. 블루투스 연결 해제
좌측 하단의 '연결 해제' 버튼을 클릭하여 장비와의 연결을 해제할 수 있습니다.</br>
</br>
</br>

## SDK가 제공하는 결과 데이터
장비에서 측정한 결과 데이터를 SDK에서 확인할 수 있습니다.</br>
다음과 같은 결과 데이터 항목들이 제공됩니다.
<ol>
<li>PPG: PPG(Photoplethysmography)의 raw data</li> 
<li>9 Axis IMU data</li>   
 <ul>
   <li>
     ACC: 가속도(Acceleration) 데이터
   </li>
   <li>
     GYRO: 자이로스코프(Gyroscope) 데이터
   </li>
   <li>
     MAG: 지자기(Magnetometer) 데이터
   </li>   
 </ul>
</ol>
</br>
</br>

---
### 개발 환경
python >= 3.22.2(stable)
</br>
</br>
### 문의 및 지원
자세한 내용은 공식 웹사이트(www.newert.co.kr) 에서 확인할 수 있습니다.
