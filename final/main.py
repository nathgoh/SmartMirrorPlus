import time
import busio
import digitalio
import board
import json

# Sensors
from busio import I2C
import adafruit_bme680
import adafruit_apds9960.apds9960

# Button
from adafruit_debouncer import Debouncer

# Display
import adafruit_ra8875.ra8875 as ra8875
from adafruit_ra8875.ra8875 import color565

# Wifi
from adafruit_esp32spi import adafruit_esp32spi
import adafruit_esp32spi.adafruit_esp32spi_requests as requests

# SD card storage
import storage
import adafruit_sdcard

# Get WiFi info
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

try:
    import struct
except ImportError:
    import ustruct as struct

####################################################################################################################################
# Configuration of pins, esp32, etc.
####################################################################################################################################

# Colors for display
BLACK = color565(0, 0, 0)
RED = color565(255, 0, 0)
BLUE = color565(0, 255, 0)
GREEN = color565(0, 0, 255)
YELLOW = color565(255, 255, 0)
CYAN = color565(0, 255, 255)
MAGENTA = color565(255, 0, 255)
WHITE = color565(255, 255, 255)

# Configuration for CS and RST pins:
cs_pin = digitalio.DigitalInOut(board.D37)
rst_pin = digitalio.DigitalInOut(board.D41)
int_pin = digitalio.DigitalInOut(board.D42)

# Button configuration
button = digitalio.DigitalInOut(board.D59)
button.direction = digitalio.Direction.INPUT
button.pull = digitalio.Pull.UP
switch = Debouncer(button)

# Config for display baudrate (default max is 6mhz):
BAUDRATE = 6000000

# Setup SPI bus using hardware SPI:
spi = busio.SPI(clock=board.SCK, MOSI=board.MOSI, MISO=board.MISO)

# Setup I2C bus for using hardware sensors
i2c = I2C(board.SCL, board.SDA)
bme680 = adafruit_bme680.Adafruit_BME680_I2C(i2c, debug=False)
apds = adafruit_apds9960.apds9960.APDS9960(i2c)
apds.enable_proximity = True
apds.enable_gesture = False

# Set location's pressure (hPa) at sea level
bme680.sea_level_pressure = 1015.25

# Create and setup the RA8875 display:
# Display is 800 x 480
display = ra8875.RA8875(spi, cs=cs_pin, rst=rst_pin, baudrate=BAUDRATE)
display.init()

# SAM32 board ESP32 Setup
dtr = digitalio.DigitalInOut(board.DTR)
esp32_cs = digitalio.DigitalInOut(board.TMS)
esp32_ready = digitalio.DigitalInOut(board.TCK)
esp32_reset = digitalio.DigitalInOut(board.RTS)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset, gpio0_pin=dtr, debug=False)
requests.set_interface(esp)

# Touchscreen
# display.touch_init(int_pin)
# display.touch_enable(False)

# Setup SD card
cs = digitalio.DigitalInOut(board.xSDCS)

# Connect to the card and mount the filesystem
sdcard = adafruit_sdcard.SDCard(spi, cs)
vfs = storage.VfsFat(sdcard)
storage.mount(vfs, "/sd")

# Config for display baudrate (default max is 6mhz):
BAUDRATE = 8000000

####################################################################################################################################
# Get WiFi connection
####################################################################################################################################
if esp.status == adafruit_esp32spi.WL_IDLE_STATUS:
    print("ESP32 found and in idle mode")

print("Firmware vers.", esp.firmware_version)
print("MAC addr:", [hex(i) for i in esp.MAC_address])

for ap in esp.scan_networks():
    print("\t%s\t\tRSSI: %d" % (str(ap['ssid'], 'utf-8'), ap['rssi']))

print("Connecting to AP...")

while not esp.is_connected:
    try:
        esp.connect_AP(b'mayB', b'notlikely')
    except RuntimeError as e:
        print("could not connect to AP, retrying: ",e)
        continue

print("Connected to", str(esp.ssid, 'utf-8'), "\tRSSI:", esp.rssi)
print("My IP address is", esp.pretty_ip(esp.ip_address))

####################################################################################################################################
# Get images displayed on display
####################################################################################################################################
class BMP(object):
    def __init__(self, filename):
        self.filename = filename
        self.colors = None
        self.data = 0
        self.data_size = 0
        self.bpp = 0
        self.width = 0
        self.height = 0
        self.read_header()

    def convert_555_to_565(rgb):
        return (rgb & 0x7FE0) << 1 | 0x20 | rgb & 0x001F

    def read_header(self):
        if self.colors:
            return
        with open(self.filename, 'rb') as f:
            f.seek(10)
            self.data = int.from_bytes(f.read(4), 'little')
            f.seek(18)
            self.width = int.from_bytes(f.read(4), 'little')
            self.height = int.from_bytes(f.read(4), 'little')
            f.seek(28)
            self.bpp = int.from_bytes(f.read(2), 'little')
            f.seek(34)
            self.data_size = int.from_bytes(f.read(4), 'little')
            f.seek(46)
            self.colors = int.from_bytes(f.read(4), 'little')

    def draw(self, disp, x=0, y=0):
            line = 0
            line_size = self.width * (self.bpp//8)
            if line_size % 4 != 0:
                line_size += (4 - line_size % 4)
            current_line_data = b''
            with open(self.filename, 'rb') as f:
                f.seek(self.data)
                disp.set_window(x, y, self.width, self.height)
                for line in range(self.height):
                    current_line_data = b''
                    line_data = f.read(line_size)
                    for i in range(0, line_size, self.bpp//8):
                        if (line_size-i) < self.bpp//8:
                            break
                        if self.bpp == 16:
                            color = convert_555_to_565(line_data[i] | line_data[i+1] << 8)
                        if self.bpp == 24 or self.bpp == 32:
                            color = color565(line_data[i+2], line_data[i+1], line_data[i])
                        current_line_data = current_line_data + struct.pack(">H", color)
                    disp.setxy(x, self.height - line + y)
                    disp.push_pixels(current_line_data)
                disp.set_window(0, 0, disp.width, disp.height)

####################################################################################################################################
# Get current local time and display on screen
####################################################################################################################################
# Time
TIME_URL = "http://worldtimeapi.org/api/timezone/" + secrets['timezone']

def time():
    r = requests.get(TIME_URL)
    time = json.loads(r.text)
    datetime = time['datetime']
    times = datetime.split(":")
    hour = int(times[0][-2:])
    minute = int(times[1])
    r.close()

    format_str = "%d:%02d"
    if hour >= 12:
        hour = hour - 12
        format_str = format_str+" PM"
    else:
        format_str = format_str+" AM"
    if hour == 0:
        hour = 12
    time_str = format_str % (hour, minute)

    # Time
    display.txt_set_cursor(530, 0)
    display.txt_trans(WHITE)
    display.txt_size(3)
    display.txt_write(time_str)

####################################################################################################################################
# Display room environment info on screen
####################################################################################################################################
def room():
    # Room environment data
    bme_data = [bme680.temperature, bme680.gas, bme680.humidity, bme680.pressure, bme680.altitude]

    # Title
    display.txt_set_cursor(15, 0)
    display.txt_size(3)
    display.txt_write("Room")

    display.txt_set_cursor(0, 80)
    display.txt_size(2)
    display.txt_write("Temperature: {0}".format(round((bme_data[0] * 9 / 5) + 32, 2)) + "°F")

    display.txt_set_cursor(0, 130)
    display.txt_size(2)
    display.txt_write("Humidity: {0}".format(round(bme_data[2], 2)) + "%")

    display.txt_set_cursor(0, 180)
    display.txt_size(2)
    display.txt_write("Pressure: {0}".format(round(bme_data[3], 2)) + " hPa")

    display.txt_set_cursor(0, 230)
    display.txt_size(2)
    display.txt_write("Gas: {0}".format(round(bme_data[3], 2)) + " Ohms")

    display.txt_set_cursor(0, 280)
    display.txt_size(2)
    display.txt_write("Altitude: {0}".format(round(bme_data[4], 2)) + "m")

####################################################################################################################################
# Display weather info on screen
####################################################################################################################################
def weather():
    # Location
    LOCATION = "Palo Alto, US"

    # Grabbing weather data
    DATA_SOURCE = "http://api.openweathermap.org/data/2.5/weather?q=" + LOCATION
    DATA_SOURCE += "&appid=" + secrets['openweather_token']
    DATA_LOCATION = []

    # Parse JSON file
    r = requests.get(DATA_SOURCE)
    print(r.json())
    weather = json.loads(r.text)
    city_name = weather['name']
    country = weather['sys']['country']
    weather_desc = weather['weather'][0]['icon']
    main = weather['weather'][0]['main']
    main = main[0].upper() + main[1:]
    weather_info = weather['weather'][0]['description']
    description_words = weather_info.split(" ")
    weather_info = ""
    for word in description_words:
        word = word[0].upper() + word[1:]
        weather_info += word + " "
    min_temp = weather['main']['temp_min']
    max_temp = weather['main']['temp_max']
    cur_temp = weather['main']['temp']
    humidity = weather['main']['humidity']
    r.close()

    fp = open("/sd/icons/" + weather_desc + ".bmp", 'r')
    weather_icon = BMP("/sd/icons/" + weather_desc + ".bmp")

    # Location
    display.txt_set_cursor(15, 0)
    display.txt_size(3)
    display.txt_write(city_name + ", " + country)

    # Main
    display.txt_set_cursor(15, 360)
    display.txt_trans(WHITE)
    display.txt_size(3)
    display.txt_write(main)

    # Weather description
    display.txt_set_cursor(15, 430)
    display.txt_size(1)
    display.txt_write(weather_info)

    # Current temp
    display.txt_set_cursor(610, 360)
    display.txt_size(3)
    display.txt_write("{0}".format(round(((cur_temp- 273 )* 9 / 5) + 32, 1)) + "°F")

    # Min and max temp
    display.txt_set_cursor(610, 430)
    display.txt_size(1)
    display.txt_write("{0}".format(round(((min_temp- 273 )* 9 / 5) + 32, 1))  + "°/" +
    "{0}".format(round(((max_temp - 273 )* 9 / 5) + 32, 1)) + "°")

    # Icon
    weather_icon.draw(display, (display.width - weather_icon.width)// 2, (display.height - weather_icon.height) // 2)

####################################################################################################################################
# Main loop:
####################################################################################################################################
display.txt_trans(WHITE)
display_toggle = False

while True:
    # Update switch state
    switch.update()
    if switch.fell:
        display_toggle = not display_toggle
        display.init()

    if not display_toggle:
        room()
        time()
    elif display_toggle:
        time()
        weather()