"""
    File Name: main.py
    Project Name: SmartMirror+
    Team Members: Cortney Weints, Nathaniel Goenawan, Sheikh Srijon
    Date: 19 September 2019
    Description: This is the main.py file that runs on a SAM32 to execute SmartMirror+ functionality. Code was origionally sourced from Adafruit® and edited to fulfil our needs. SmartMirror+ takes imput data from a BME680 periferal sensor to monitor the room enviornment and fetches weather and time data from the internet using the ESP32 chip native to the SAM32. Information is processed and displayed on a 7" TFT diaplay driven by an RA8875.
    """

###################
# Import Packages #
###################

# Circuitboard
import time
import busio
from digitalio import DigitalInOut
import board

# Sensor
from busio import I2C
import adafruit_bme680

# Display
import adafruit_ra8875.ra8875 as ra8875
from adafruit_ra8875.ra8875 import color565
try:
    import struct
except ImportError:
    import ustruct as struct

# Wifi
import json
from adafruit_esp32spi import adafruit_esp32spi
import adafruit_esp32spi.adafruit_esp32spi_requests as requests

# SD Card Storage
import storage
import adafruit_sdcard

# Get wifi details and more from a secrets.py file
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise


#################################################
# Configuration of pins, ESP32, constants, etc. #
#################################################

# Configuration for CS and RST pins
cs_pin = DigitalInOut(board.D42)
rst_pin = DigitalInOut(board.D41)
int_pin = DigitalInOut(board.D37)

# Set up the sd card as a spi device
cs = DigitalInOut(board.xSDCS)
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)

# SAM32 board ESP32 Setup
dtr = DigitalInOut(board.DTR)
esp32_cs = DigitalInOut(board.TMS) #GPIO14
esp32_ready = DigitalInOut(board.TCK) #GPIO13
esp32_reset = DigitalInOut(board.RTS)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset, gpio0_pin=dtr, debug=False)
requests.set_interface(esp)

# Connect SAM32 to the card and mount the filesystem
sdcard = adafruit_sdcard.SDCard(spi, cs)
vfs = storage.VfsFat(sdcard)
storage.mount(vfs, "/sd")

# Set up BME680 as an I2C device
i2c = I2C(board.SCL, board.SDA)
bme680 = adafruit_bme680.Adafruit_BME680_I2C(i2c, debug=False)
bme680.sea_level_pressure = 1013.25

# Set commonly used fill colors as constants
WHITE = color565(255, 255, 255)
BLACK = color565(0, 0, 0)

# Config for display baudrate (default max is 6mhz)
BAUDRATE = 8000000

# Create and setup the RA8875 display
display = ra8875.RA8875(spi, cs=cs_pin, rst=rst_pin, baudrate=BAUDRATE)
display.init()
display.fill(BLACK)

# Create strings to hold weather and time URLs
LOCATION = "Palo Alto, US"
WEATHER_URL = "http://api.openweathermap.org/data/2.5/weather?q="+LOCATION
WEATHER_URL += "&appid="+secrets['openweather_token']
TIME_URL = "http://worldtimeapi.org/api/timezone/" + secrets['timezone']


#########################
# Function Definitions #
########################

# Converts 555 to 565
def convert_555_to_565(rgb):
    return (rgb & 0x7FE0) << 1 | 0x20 | rgb & 0x001F

# Class handles BMP objects
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

# Draws objects on screen
def draw(self, disp, x=0, y=0):
    print("{:d}x{:d} image".format(self.width, self.height))
    print("{:d}-bit encoding detected".format(self.bpp))
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

# Connects ESP32 to specified AP from secrets.py
def internetConnect():
    print("MAC addr:", [hex(i) for i in esp.MAC_address])
    print("Connecting to AP...")
    while not esp.is_connected:
        try:
            esp.connect_AP(secrets['ssid'], secrets['password'])
        except RuntimeError as e:
            print("could not connect to AP, retrying: ",e)
            continue
    print("Connected to", str(esp.ssid, 'utf-8'), "\tRSSI:", esp.rssi)

# Fetches time informaiton provided by worldtimeapi, parses json, formats string, and displays on screen
def updateTime(time_url):
    
    # get time info and format string
    print("\nFetching json from", time_url)
    r = requests.get(time_url)
    print('-'*40)
    print(r.json())
    print('-'*40)
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
    print(time_str)
    print('-'*40)
    
    # display info
    display.txt_set_cursor(530, 0)
    display.txt_trans(WHITE)
    display.txt_size(3)
    display.txt_write(time_str)

# Fetches weather informaiton provided by OpoenWeather, parses json, formats strings, and displays on screen
def updateWeather(weather_url):
    
    # get weather info and format strings
    print("\nFetching json from", weather_url)
    r = requests.get(weather_url)
    print('-'*40)
    print(r.json())
    print('-'*40)
    weather = json.loads(r.text)
    city_name =  weather['name'] # + ", " + weather['sys']['country']
    print("OpenWeather data for " + city_name)
    main = weather['weather'][0]['main']
    main = main[0].upper() + main[1:]
    print(main)
    description = weather['weather'][0]['description']
    description_words = description.split(" ")
    description = ""
    for word in description_words:
        word = word[0].upper() + word[1:]
        description += word + " "
    print(description)
    temp = (weather['main']['temp'] - 273.15) * 9 / 5 + 32 # it's...in kelvin
    print("Current temp: " + str(int(temp)) + " F")
    tempH = (weather['main']['temp_max'] - 273.15) * 9 / 5 + 32
    print("High: " + str(int(tempH)) + " F")
    tempL = (weather['main']['temp_min'] - 273.15) * 9 / 5 + 32
    print("Low: " + str(int(tempL)) + " F")
    icon = weather['weather'][0]['icon']
    print(icon)
    print('-'*40)
    r.close()
    
    # display parsed and prcessed informaiton on the screen
    display.txt_set_cursor(15, 0)
    display.txt_trans(WHITE)
    display.txt_size(3)
    display.txt_write(city_name)    # location
    
    display.txt_set_cursor(610, 360)
    display.txt_trans(WHITE)
    display.txt_size(3)
    display.txt_write("%d°F" % int(temp))   # temp
    
    display.txt_set_cursor(610, 430)
    display.txt_trans(WHITE)
    display.txt_size(1)
    display.txt_write("%d°" % int(tempH) + "/ %d°" % int(tempL))    # temp H/L
    
    display.txt_set_cursor(15, 360)
    display.txt_trans(WHITE)
    display.txt_size(3)
    display.txt_write(main)    # main
    
    display.txt_set_cursor(15, 430)
    display.txt_trans(WHITE)
    display.txt_size(1)
    display.txt_write(description)    # descrioption
    
    fp = open("/sd/icons/" + icon + ".bmp", "r")
    bitmap = BMP("/sd/icons/" + icon + ".bmp")
    bitmap.draw(display, (display.width - bitmap.width) // 2, (display.height - bitmap.height) // 2)    # icon

# Retrieves room informaiton from BME680, formats strings, and displays on screen
def updateRoom():
    
    # get room info
    roomTemp = int(bme680.temperature * 9 / 5 + 32)
    roomGas = int(bme680.gas)
    roomHumidity = int(bme680.humidity)
    roomPressure = int(bme680.pressure)
    roomAlt = int(bme680.altitude)
    
    # display sensor data on screen
    display.txt_set_cursor(0, 0)
    display.txt_trans(WHITE)
    display.txt_size(3)
    display.txt_write("Room Environment")    # Title
    
    display.txt_set_cursor(15, 100)
    display.txt_trans(WHITE)
    display.txt_size(2)
    display.txt_write("Temperature:     {0}".format(roomTemp) + "°F")   # Temperature
    
    display.txt_set_cursor(15, 170)
    display.txt_trans(WHITE)
    display.txt_size(2)
    display.txt_write("Humidity:        {0}".format(roomHumidity) + "%")    # Humidity
    
    display.txt_set_cursor(15, 240)
    display.txt_trans(WHITE)
    display.txt_size(2)
    display.txt_write("Pressure:        {0}".format(roomPressure) + " hPa")    # Pressure
    
    display.txt_set_cursor(15, 310)
    display.txt_trans(WHITE)
    display.txt_size(2)
    display.txt_write("Gas:             {0}".format(roomGas) + " Ohms")    # Gas
    
    display.txt_set_cursor(15, 380)
    display.txt_trans(WHITE)
    display.txt_size(2)
    display.txt_write("Altitude:        {0}".format(roomAlt) + "m")    # Altitude


##################
# Main Code Loop #
##################

internetConnect()
while True:
    updateTime(TIME_URL)
    updateWeather(WEATHER_URL)
    display.init()
    display.fill(BLACK)
    updateTime(TIME_URL)
    updateRoom()
    time.sleep(45)
    display.init()
    display.fill(BLACK)
