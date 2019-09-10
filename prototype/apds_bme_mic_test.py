import time
import board, neopixel, digitalio
import adafruit_bme680
import busio
from busio import I2C
from analogio import AnalogIn
import board
import busio
import adafruit_apds9960.apds9960


# Create library object using Bus I2C port
i2c = I2C(board.SCL, board.SDA)

# Sensors
bme680 = adafruit_bme680.Adafruit_BME680_I2C(i2c, debug=False)
apds9960 = adafruit_apds9960.apds9960.APDS9960(i2c)
mic_pin = AnalogIn(board.A9)

# Set location's pressure (hPa) at sea level
bme680.sea_level_pressure = 1013.25

# Set Adps9960 functionality
apds9960.enable_proximity = True
apds9960.enable_color = False
apds9960.enable_gesture = True


while True:

    n = (mic_pin.value / 65536) * 1000

    print("\nTemperature: %0.1f C" % bme680.temperature)
    print("Gas: %d ohm" % bme680.gas)
    print("Humidity: %0.1f %%" % bme680.humidity)
    print("Pressure: %0.3f hPa" % bme680.pressure)
    print("Altitude = %0.2f meters" % bme680.altitude)
    print((n,))

    print()
    print(apds9960.proximity())

    #gesture = apds9960.gesture()
    #while gesture == 0:
    #    gesture = apds9960.gesture()
    #if gesture == 1:
    #    print("UP")
    #elif gesture == 2:
    #    print("DOWN")
    #elif gesture == 3:
    #    print("LEFT")
    #elif gesture == 4:
    #    print("RIGHT")

    time.sleep(1)
