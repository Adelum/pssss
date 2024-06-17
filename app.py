from flask import Flask, render_template, jsonify
import serial
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import os
from azure.iot.device import IoTHubDeviceClient, Message

load_dotenv()

app = Flask(__name__)
ser = serial.Serial('COM4', 9600, timeout=0.1)

# Azure IoT Hub connection string
CONNECTION_STRING = os.getenv('IOT_HUB_CONNECTION_STRING')

# Initialize IoT Hub client
client = IoTHubDeviceClient.create_from_connection_string(CONNECTION_STRING)

MAX_COMMANDS = 10
last_temperature = ''
last_water_status = ''
reading_from_eeprom = False
flood_detected = False  # Flag to stop reading temperature and water status during a flood
last_flood_state = '0'  # Initialize the last flood state as '0'

# Email configuration from environment variables
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT'))
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
TO_EMAIL_ADDRESS = os.getenv('TO_EMAIL_ADDRESS')

def send_email(subject, body):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = TO_EMAIL_ADDRESS
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, TO_EMAIL_ADDRESS, msg.as_string())
        print("Email sent successfully")
    except Exception as e:
        print(f"Failed to send email: {e}")

def send_to_azure(message):
    try:
        msg = Message(message)
        client.send_message(msg)
        print("Message sent to Azure IoT Hub")
    except Exception as e:
        print(f"Failed to send message to Azure IoT Hub: {e}")

@app.route('/')
def index():
    if not flood_detected:
        temperature = get_temperature_from_microcontroller()
        water_status = get_water_status_from_microcontroller()
    else:
        temperature = last_temperature
        water_status = last_water_status

    last_10_led_states = get_last_10_led_states_from_microcontroller()
    return render_template('index.html', temperature=temperature, water_status=water_status,
                           last_10_led_states=last_10_led_states)

def get_water_status_from_microcontroller():
    global last_water_status, flood_detected, last_flood_state

    ser.write(b'W')
    time.sleep(2)
    response_water = ser.readline().decode('UTF-8').strip()
    print(f"Water status response: {response_water}")  # Debugging statement
    last_water_status = response_water

    # Check for transition from '0' to '1'
    if last_flood_state == '0' and response_water == '1':
        flood_detected = True
        print("Flood detected!")  # Debugging statement
        send_email("Flood Alert", "Senzorul de inundație a detectat apă!")
        send_to_azure('{"event": "flood_detected"}')
    elif response_water == '0':
        flood_detected = False

    last_flood_state = response_water
    send_to_azure(f'{{"water_status": "{response_water}"}}')
    return response_water

def get_temperature_from_microcontroller():
    global last_temperature

    if not flood_detected:
        ser.write(b'T')
        time.sleep(2)
        response_temp = ser.readline().decode('UTF-8').strip()
        print(f"Temperature response: {response_temp}")  # Debugging statement
        last_temperature = response_temp
        send_to_azure(f'{{"temperature": "{response_temp}"}}')

    return last_temperature

def get_last_10_led_states_from_microcontroller():
    global reading_from_eeprom
    reading_from_eeprom = True
    ser.write(b'E')  # Send command to Arduino to read the last 10 LED states from EEPROM
    time.sleep(2)
    led_states = []
    for _ in range(MAX_COMMANDS):
        response = ser.readline().decode('UTF-8').strip()
        if response:
            led_states.append(response)
    reading_from_eeprom = False  # Add response directly to the list of LED states
    return led_states

@app.route('/turn-on', methods=['POST'])
def turn_on():
    ser.write(b'A')
    time.sleep(2)  # Wait a bit to update the LED state
    send_to_azure('{"led_state": "on"}')
    return '', 204

@app.route('/turn-off', methods=['POST'])
def turn_off():
    ser.write(b'S')
    time.sleep(2)  # Wait a bit to update the LED state
    send_to_azure('{"led_state": "off"}')
    return '', 204

@app.route('/get_temperature')
def get_temperature():
    if not reading_from_eeprom and not flood_detected:
        temperature = get_temperature_from_microcontroller()
    else:
        temperature = last_temperature
    return temperature

@app.route('/get_water_status')
def get_water_status():
    if not reading_from_eeprom:
        water_status = get_water_status_from_microcontroller()
    else:
        water_status = last_water_status
    return water_status

@app.route('/read-eeprom', methods=['POST'])
def read_eeprom():
    last_10_led_states = get_last_10_led_states_from_microcontroller()
    return jsonify(last_10_led_states)

@app.route('/delete-message', methods=['POST'])
def delete_message():
    ser.write(b'D')  # Send command to Arduino to delete the oldest message from EEPROM
    time.sleep(2)  # Wait a bit to update the state
    return '', 204

if __name__ == '__main__':
    app.run(debug=True)
