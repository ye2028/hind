import os
import glob
import time
import random
import threading
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response, redirect, url_for, session
from twilio.rest import Client
import cv2

RECORDINGS_PATH = '/home/pi/projects/project/recordings/'
DB_PATH = '/home/pi/projects/project/orders.db'
os.makedirs(RECORDINGS_PATH, exist_ok=True)

app = Flask(__name__)
app.secret_key = 'ordbox_123' 

system_status = {
    "status": "IDLE",
    "video_filename": None,
    "otp_sent": False,
    "delivery_code": None
}

current_barcode = None
current_otp = None
otp_expiry_time = None
keypad_input_buffer = ""

def find_order_by_barcode(barcode):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, delegate_phone, delivery_code FROM orders WHERE barcode = ?", (barcode,))
    result = cursor.fetchone()
    conn.close()
    return result


def record_video():
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    video_filename = f'barcode_{timestamp}.avi'
    video_path = os.path.join(RECORDINGS_PATH, video_filename)

    video_files = sorted(glob.glob(os.path.join(RECORDINGS_PATH, '*.avi')), key=os.path.getmtime)
    if len(video_files) >= 20:
        os.remove(video_files[0])

    print(f"[-] بدء التسجيل إلى {video_path}")

    cap = cv2.VideoCapture(0)
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(video_path, fourcc, 20.0, (640, 480))

    start_time = time.time()
    while time.time() - start_time < 10:
        ret, frame = cap.read()
        if ret:
            out.write(frame)

    cap.release()
    out.release()
    print(f"[-] تم حفظ الفيديو: {video_filename}")

    system_status["video_filename"] = video_filename


def simulate_scan_process():
    global system_status, current_barcode, current_otp, otp_expiry_time
    system_status["status"] = "SCANNING"
    record_video()
    time.sleep(2)

    detected_barcode = random.choice(["12", "999999"])
    current_barcode = detected_barcode
    order = find_order_by_barcode(detected_barcode)

    if order:
        order_id, phone, delivery_code = order
        current_otp = str(random.randint(1000, 9999))
        otp_expiry_time = time.time() + 60

        try:
            # account_sid = 'xxxxxxxx'
            # auth_token = 'xxxxxxx'
            client = Client(account_sid, auth_token)
            message = client.messages.create(
                from_='whatsapp:+14155238886',
                body=f"أهلا OrdBox يرحب بك، رمز التحقق هو: {current_otp}",
                to=f'whatsapp:{phone}'
            )
            print(f"[-] OTP {current_otp} تم إرساله إلى {phone}")
        except Exception as e:
            print(f"[--] فشل إرسال OTP {current_otp}: {e}")

        system_status["status"] = "OTP_SENT"
        system_status["delivery_code"] = delivery_code
        system_status["otp_sent"] = True

        wait_start = time.time()
        while time.time() - wait_start < 60:
            if system_status["status"] != "OTP_SENT":
                break
            time.sleep(1)

        if system_status["status"] == "OTP_SENT":
            print("[--] لم يتم إدخال OTP خلال دقيقة، إعادة تعيين.")
            reset_status()
    else:
        print("[--] لم يتم العثور على الطلب")
        system_status["status"] = "NOT_FOUND"
        time.sleep(5)
        reset_status()


def reset_status():
    global system_status, current_barcode, current_otp, otp_expiry_time, keypad_input_buffer
    system_status = {
        "status": "IDLE",
        "video_filename": None,
        "otp_sent": False,
        "delivery_code": None
    }
    current_barcode = None
    current_otp = None
    otp_expiry_time = None
    keypad_input_buffer = ""


def send_open_box_signal():
    global system_status
    import requests
    try:
        requests.post("http://192.168.8.111/open_box")
        print("[-] تم إرسال إشارة لفتح الباب")

        if system_status["delivery_code"]:
            delivery_code = system_status["delivery_code"]
            phone = find_order_by_barcode(current_barcode)[1]
            try:
                # account_sid = 'xxxxxxxxx'
                # auth_token = 'xxxxxxxx'
                client = Client(account_sid, auth_token)
                message = client.messages.create(
                    from_='whatsapp:+14155238886',
                    body=f"شكرا لتسليمك الطلب، هذا هو رمز التسليم المرتبط بالطلب من الشركة: {delivery_code} .. نتمنى لك وقتا سعيدا،،",
                    to=f'whatsapp:{phone}'
                )
                print(f"[-] تم إرسال رمز التسليم إلى {phone}")
            except Exception as e:
                print(f"[--] فشل إرسال رمز التسليم: {e}")
    except Exception as e:
        print("[--] فشل إرسال الإشارة:", e)


@app.route("/")
def index():
    return render_template("home.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'admin' and password == 'password':
            session['logged_in'] = True
            return redirect(url_for('orders'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/add-order', methods=['GET', 'POST'])
def add_order():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form['name']
        barcode = request.form['barcode']
        delegate_name = request.form['delegate_name']
        delegate_phone = request.form['delegate_phone']
        delegate_email = request.form['delegate_email']
        company = request.form['company']
        delivery_code = request.form['delivery_code']
        status = "Pending"
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''INSERT INTO orders 
            (name, barcode, delegate_name, delegate_phone, delegate_email, company, status, created_at, delivery_code) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (name, barcode, delegate_name, delegate_phone, delegate_email, company, status, created_at, delivery_code))
        conn.commit()
        conn.close()
        return redirect(url_for('orders'))
    return render_template('add_order.html')

@app.route('/orders')
def orders():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM orders ORDER BY created_at DESC")
    orders_list = c.fetchall()
    conn.close()
    return render_template('orders.html', orders=orders_list)

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/monitor')
def monitor():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('monitor.html')

@app.route('/update-order/<int:order_id>', methods=['POST'])
def update_order(order_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    name = request.form.get('name')
    barcode = request.form.get('barcode')
    delegate_name = request.form.get('delegate_name')
    delegate_phone = request.form.get('delegate_phone')
    delegate_email = request.form.get('delegate_email')
    shipping_company = request.form.get('company')
    delivery_code = request.form.get('delivery_code')

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        UPDATE orders SET 
            name=?, 
            barcode=?, 
            delegate_name=?, 
            delegate_phone=?, 
            delegate_email=?, 
            company=?, 
            delivery_code=? 
        WHERE id=?
    ''', (name, barcode, delegate_name, delegate_phone, delegate_email, shipping_company, delivery_code, order_id))
    conn.commit()
    conn.close()
    return redirect(url_for('orders'))


@app.route("/status")
def get_status():
    return jsonify({
        **system_status,
        "keypad_input": keypad_input_buffer
    })


@app.route("/start_scan", methods=["POST"])
def start_scan():
    if system_status["status"] == "IDLE":
        threading.Thread(target=simulate_scan_process).start()
        return jsonify({"message": "Scan started"})
    else:
        return jsonify({"message": "Scan already in progress"}), 400


@app.route("/simulate_motion", methods=["POST"])
def simulate_motion():
    return start_scan()


@app.route('/keypad_input', methods=['POST'])
def receive_keypad_input():
    global keypad_input_buffer, system_status
    data = request.get_json()

    if not data or 'key' not in data:
        return jsonify({'status': 'error', 'message': 'No key provided'}), 400

    key = data['key']
    print(f"Received key from keypad: {key}")

    if key == 'B' and system_status["status"] == "IDLE":
        print("[-] B key pressed — starting scan process")
        return start_scan()

    if key == 'D':
        print("Full OTP entered:", keypad_input_buffer)
        if keypad_input_buffer == current_otp and time.time() <= otp_expiry_time:
            system_status["status"] = "WAITING_CONFIRMATION"
            print("[-] OTP صحيح")
            send_open_box_signal()
        else:
            system_status["status"] = "OTP_INCORRECT"
            print("[--] OTP غير صحيح أو منتهي")
            time.sleep(3)
            reset_status()
        keypad_input_buffer = ""
    else:
        keypad_input_buffer += key

    return jsonify({'status': 'ok'}), 200

@app.route("/verify_otp", methods=["POST"])
def verify_otp():
    global system_status, current_barcode
    data = request.get_json()
    otp = data.get("otp")
    order = find_order_by_barcode(current_barcode)
    if order:
        _, expected_otp, delivery_code = order
        if otp == expected_otp:
            system_status["status"] = "WAIT_DELIVERY_CODE"
            return jsonify({"status": "OTP_CORRECT", "code": delivery_code})
    return jsonify({"status": "OTP_INCORRECT"}), 400

@app.route("/get_delivery_code", methods=["GET"])
def get_delivery_code():
    global current_barcode
    if current_barcode:
        order = find_order_by_barcode(current_barcode)
        if order:
            _, _, delivery_code = order
            current_barcode = None
            return jsonify({"code": delivery_code})
    return jsonify({"code": None}), 404

@app.route("/confirm_delivery", methods=["POST"])
def confirm_delivery():
    global system_status
    data = request.get_json()
    code = data.get("code")
    order = find_order_by_barcode(current_barcode)
    if order:
        _, _, delivery_code = order
        if code == delivery_code:
            system_status["status"] = "DELIVERED"
            return jsonify({"message": "Delivery confirmed"})
    return jsonify({"message": "Invalid code"}), 400

if __name__ == "__main__":
    print("?? Starting Flask app...")
    app.run(host="0.0.0.0", port=5000, debug=True)

