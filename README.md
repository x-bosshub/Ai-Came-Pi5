# Ai-Came-Pi5
Ai Camera Pi5 และ Servo ควบคุม ขึ้นลงซ้ายขวา

```
sudo apt-get update
sudo apt-get install ffmpeg
pip install flask opencv-python gpiozero  --break-system-packages
```

sudo nano /etc/systemd/system/ai-cam-app.service
```
[Unit]
Description=AI App Auto Start Service
After=network-online.target
Wants=network-online.target
[Service]
# เปลี่ยน pi เป็น username ปัจจุบันของคุณถ้าจำเป็น
User=pi5
Group=pi5
# กำหนดโฟลเดอร์ที่รันสคริปต์
WorkingDirectory=/home/pi5/Ai-Came-Pi5
# คำสั่งที่ใช้รันโปรแกรม (แนะนำให้ใช้ Absolute Path ของ Python)
ExecStart=/usr/bin/python3 /home/pi5/Ai-Came-Pi5/app.py
# ตั้งค่าให้เริ่มทำงานใหม่เสมอถ้าโปรแกรมหยุดทำงาน
Restart=always
RestartSec=5
# เก็บ Log
StandardOutput=journal
StandardError=journal
[Install]
WantedBy=multi-user.target
```
