# app.py
# sudo apt-get update
# sudo apt-get install ffmpeg
# pip install flask opencv-python gpiozero  --break-system-packages
# AIzaSyBR_hlWlch69U35ps0SLvffEwVz6J1n9Oc
import os
import time
import threading
import subprocess
import cv2
from flask import Flask, render_template, Response, request, jsonify
from gpiozero import AngularServo

# เริ่มต้น Flask App
app = Flask(__name__)

# ==========================================
# 1. การตั้งค่า Hardware และตัวแปร Servo
# ==========================================
PAN_PIN = 12
TILT_PIN = 13

# การตั้งค่าและจูนระยะพัลส์ของ Servo
PAN_MIN_PULSE = 0.0005
PAN_MAX_PULSE = 0.0025
TILT_MIN_PULSE = 0.0005  
TILT_MAX_PULSE = 0.0025  

# ค่าเริ่มต้นของมุมองศา (0 - 180)
current_pan = 90
current_tilt = 90
target_pan = 90
target_tilt = 90

# ตัวแปรควบคุมความเร็วการเคลื่อนที่ (ค่าเริ่มต้นคือความเร็วปกติ 0.015 วินาทีต่อก้าว)
movement_delay = 0.015

# การตั้งค่า Servo ต่อตรงผ่าน GPIO ของ Raspberry Pi
try:
    pan_servo = AngularServo(PAN_PIN, min_angle=0, max_angle=180, min_pulse_width=PAN_MIN_PULSE, max_pulse_width=PAN_MAX_PULSE)
    tilt_servo = AngularServo(TILT_PIN, min_angle=0, max_angle=180, min_pulse_width=TILT_MIN_PULSE, max_pulse_width=TILT_MAX_PULSE)
    
    # สั่งให้ไปที่ตำแหน่งเริ่มต้น
    pan_servo.angle = current_pan
    tilt_servo.angle = current_tilt
    
    servo_available = True
    print("GPIO Servos Initialized successfully with independent pulse tuning.")
except Exception as e:
    print(f"[Warning] ไม่สามารถเชื่อมต่อ Servo ผ่าน GPIO ได้: {e}")
    servo_available = False

# ฟังก์ชัน Thread สำหรับคุมความสมูทของ Servo (ทำงานแบบไม่หยุด)
def smooth_servo_loop():
    global current_pan, current_tilt, target_pan, target_tilt, movement_delay
    while True:
        if servo_available:
            # ตรวจสอบและปรับ Pan แบบสมูท
            if current_pan != target_pan:
                step = 1 if target_pan > current_pan else -1
                current_pan += step
                pan_servo.angle = current_pan
            else:
                # ถ้าหันไปถึงองศาเป้าหมายแล้ว ให้ตัดสัญญาณ PWM เพื่อหยุดอาการสั่นคราง
                if pan_servo.value is not None:
                    pan_servo.value = None
            
            # ตรวจสอบและปรับ Tilt แบบสมูท
            if current_tilt != target_tilt:
                step = 1 if target_tilt > current_tilt else -1
                current_tilt += step
                tilt_servo.angle = current_tilt
            else:
                # ถ้าหันไปถึงองศาเป้าหมายแล้ว ให้ตัดสัญญาณ PWM เพื่อหยุดอาการสั่นคราง
                if tilt_servo.value is not None:
                    tilt_servo.value = None
                
        # ปรับค่า sleep ตามความเร็วที่ผู้ใช้เลือกผ่านหน้าเว็บ
        time.sleep(movement_delay)

# เริ่มต้น Thread คุม Servo
servo_thread = threading.Thread(target=smooth_servo_loop, daemon=True)
servo_thread.start()

# ==========================================
# 2. ระบบค้นหาอุปกรณ์อัตโนมัติ (Auto-Detect)
# ==========================================
def auto_detect_hardware():
    hardware = {
        'camera_index': -1
    }
    
    # ค้นหากล้อง
    for i in range(4):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            hardware['camera_index'] = i
            cap.release()
            break
            
    return hardware

detected_hw = auto_detect_hardware()
print(f"Detected Hardware: {detected_hw}")

# ==========================================
# 3. ระบบสตรีมมิ่งภาพ
# ==========================================
def generate_video():
    if detected_hw['camera_index'] == -1:
        return
        
    cap = cv2.VideoCapture(detected_hw['camera_index'])
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    while True:
        success, frame = cap.read()
        if not success:
            break
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    cap.release()

# ==========================================
# 4. ฟังก์ชัน Recording (เฉพาะภาพ)
# ==========================================
recording_process = None

def start_recording():
    global recording_process
    filename = f"record_{time.strftime('%Y%m%d_%H%M%S')}.mp4"
    cmd = [
        'ffmpeg', '-y',
        '-f', 'v4l2', '-video_size', '640x480', '-i', f'/dev/video{detected_hw["camera_index"]}',
        '-c:v', 'libx264',
        filename
    ]
    recording_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ==========================================
# 5. Flask Routes
# ==========================================
@app.route('/')
def index():
    return render_template('index.html', hw=detected_hw)

@app.route('/video_feed')
def video_feed():
    return Response(generate_video(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/set_servo', methods=['POST'])
def set_servo():
    global target_pan, target_tilt
    data = request.json
    if 'pan' in data:
        target_pan = int(data['pan'])
    if 'tilt' in data:
        target_tilt = int(data['tilt'])
    return jsonify({"status": "ok", "pan": target_pan, "tilt": target_tilt})

@app.route('/set_speed', methods=['POST'])
def set_speed():
    global movement_delay
    data = request.json
    speed_level = int(data.get('speed', 3))
    
    # แปลงระดับความเร็ว 1-5 เป็นค่า Delay เวลาของการเคลื่อนที่ (หน่วยวินาที)
    if speed_level == 1:
        movement_delay = 0.06   # ช้ามาก (ค่อยๆ ขยับเนียนๆ)
    elif speed_level == 2:
        movement_delay = 0.03   # ช้า
    elif speed_level == 3:
        movement_delay = 0.015  # ความเร็วปกติ (ค่าเริ่มต้นเดิม)
    elif speed_level == 4:
        movement_delay = 0.008  # เร็ว
    elif speed_level == 5:
        movement_delay = 0.002  # เร็วมาก (หมุนทันที)
        
    return jsonify({"status": "ok", "delay": movement_delay})

@app.route('/record_control', methods=['POST'])
def record_control():
    global recording_process
    data = request.json
    action = data.get('action')
    
    if action == 'start':
        start_recording()
        return jsonify({"status": "recording"})
    elif action == 'stop':
        if recording_process:
            recording_process.terminate()
            recording_process = None
        return jsonify({"status": "stopped"})
    return jsonify({"status": "error"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
