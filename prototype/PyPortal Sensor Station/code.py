import time
import board
import neopixel
import busio
import analogio
from simpleio import map_range
from digitalio import DigitalInOut
import adafruit_bme680

from adafruit_esp32spi import adafruit_esp32spi, adafruit_esp32spi_wifimanager
from adafruit_io.adafruit_io import IO_HTTP, AdafruitIO_RequestError

import sensor_station_helper

# Create library object using Bus I2C port
i2c = busio.I2C(board.SCL, board.SDA)

# Sensors
bme680 = adafruit_bme680.Adafruit_BME680_I2C(i2c, debug=False)
# apds9960 = adafruit_apds9960.apds9960.APDS9960(i2c)
# mic_pin = AnalogIn(board.A9)

# Set location's pressure (hPa) at sea level
bme680.sea_level_pressure = 1013.25

# Set Adps9960 functionality
# apds9960.enable_proximity = True
# apds9960.enable_color = False
# apds9960.enable_gesture = True

PYPORTAL_REFRESH = 5

# Get wifi details and more from a secrets.py file
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

# PyPortal ESP32 Setup
esp32_cs = DigitalInOut(board.ESP_CS)
esp32_ready = DigitalInOut(board.ESP_BUSY)
esp32_reset = DigitalInOut(board.ESP_RESET)
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)
status_light = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.2)
wifi = adafruit_esp32spi_wifimanager.ESPSPI_WiFiManager(esp, secrets, status_light)

# Set your Adafruit IO Username and Key in secrets.py
ADAFRUIT_IO_USER = secrets['aio_username']
ADAFRUIT_IO_KEY = secrets['aio_key']

# Create an instance of the Adafruit IO HTTP client
io = IO_HTTP(ADAFRUIT_IO_USER, ADAFRUIT_IO_KEY, wifi)
io = IO_HTTP(ADAFRUIT_IO_USER, ADAFRUIT_IO_KEY, wifi)

bme680 = adafruit_bme680.Adafruit_BME680_I2C(i2c)

# Change this to match the location's pressure (hPa) at sea level
bme680.sea_level_pressure = 1013.25

# Set up Adafruit IO Feeds
print('Getting Group data from Adafruit IO...')
station_group = io.get_group('pyportal-sensor-station')
feed_list = station_group['feeds']
altitude_feed = feed_list[0]
gas_feed = feed_list[1]
humidity_feed = feed_list[2]
pressure_feed = feed_list[3]
temperature_feed = feed_list[4]

gfx = sensor_station_helper.SensorStation_GFX()

def send_to_io():
    # handle sending sensor data to Adafruit IO
    io.send_data(temperature_feed['key'], bme680_data[0])
    io.send_data(gas_feed['key'], bme680_data[1])
    io.send_data(humidity_feed['key'], bme680_data[2])
    io.send_data(pressure_feed['key'], bme680_data[3])
    io.send_data(altitude_feed['key'], bme680_data[4])

while True:

    print('obtaining sensor data...')
    # Store bme280 data as a list
    bme680_data = [bme680.temperature, bme680.gas, bme680.humidity,
                   bme680.pressure, bme680.altitude]

    # Display sensor data on PyPortal using the gfx helper
    print('displaying sensor data...')
    gfx.display_data(bme680_data)
    print('sensor data displayed!')

    try:
        try:
            print('Sending data to Adafruit IO...')
            gfx.display_io_status('Sending data to IO...')
            send_to_io()
            gfx.display_io_status('Data Sent!')
            print('Data sent!')
        except AdafruitIO_RequestError as e:
            raise AdafruitIO_RequestError('IO Error: ', e)
    except (ValueError, RuntimeError) as e:
        print("Failed to get data, retrying\n", e)
        wifi.reset()
        continue

    time.sleep(PYPORTAL_REFRESH)