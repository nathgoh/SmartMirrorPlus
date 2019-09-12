"""
Helper file for pyportal sensor station
"""

import board
import displayio
from adafruit_display_text.label import Label
from adafruit_bitmap_font import bitmap_font

cwd = ("/"+__file__).rsplit('/', 1)[0] # the current working directory (where this file is)

# Fonts within /fonts folder
medium_font = cwd+"/fonts/Arial-16.bdf"
header_font = cwd+"/fonts/Arial-16.bdf"
glyphs = b'0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-,.: '

class SensorStation_GFX(displayio.Group):

    def __init__(self, celsius=True):
        # root displayio group
        root_group = displayio.Group(max_size=20)
        board.DISPLAY.show(root_group)
        super().__init__(max_size=20)
        self._celsius = celsius

        # create background icon group
        self._icon_group = displayio.Group(max_size=1)
        self.append(self._icon_group)
        board.DISPLAY.show(self._icon_group)

        # create text object group
        self._text_group = displayio.Group(max_size=8)
        self.append(self._text_group)

        self._icon_sprite = None
        self._icon_file = None
        self._cwd = cwd
        self.set_icon(self._cwd+"/icons/pyportal_splash.bmp")

        print('loading fonts...')
        self.medium_font = bitmap_font.load_font(medium_font)
        self.c_font = bitmap_font.load_font(header_font)
        self.medium_font.load_glyphs(glyphs)
        self.c_font.load_glyphs(glyphs)

        print('setting up Labels...')
        self.title_text = Label(self.c_font, text = "PyPortal Sensor Station")
        self.title_text.x = 50
        self.title_text.y = 10
        self._text_group.append(self.title_text)

        self.io_status_text = Label(self.c_font, max_glyphs=30)
        self.io_status_text.x = 65
        self.io_status_text.y = 190
        self._text_group.append(self.io_status_text)

        # Set up Labels to label sensor data
        self.bme_temp_humid_text = Label(self.medium_font, max_glyphs = 50)
        self.bme_temp_humid_text.x = 0
        self.bme_temp_humid_text.y = 70
        self._text_group.append(self.bme_temp_humid_text)

        self.bme_pres_alt_text = Label(self.medium_font, max_glyphs=50)
        self.bme_pres_alt_text.x = 0
        self.bme_pres_alt_text.y = 110
        self._text_group.append(self.bme_pres_alt_text)
        board.DISPLAY.show(self._text_group)

        self.bme_gas_text = Label(self.medium_font, max_glyphs=50)
        self.bme_gas_text.x = 0
        self.bme_gas_text.y = 150
        self._text_group.append(self.bme_gas_text)
        board.DISPLAY.show(self._text_group)

    def display_io_status(self, status_text):
        """Displays the current IO status.
        :param str status_text: Description of Adafruit IO status
        """
        self.io_status_text.text = status_text
        board.DISPLAY.refresh_soon()
        board.DISPLAY.wait_for_frame()

    def display_data(self, bme_data):
        """Displays the data from the sensors attached
        to the weathermeter pyportal and sends the data to Adafruit IO.

        :param list bme_data: List of env. data from the BME680 sensor.
        """
        temperature = round(bme_data[0], 1)
        print('Temperature: {0} C'.format(temperature))
        humidity = round(bme_data[2], 1)
        print('Humidity: {0}%'.format(humidity))
        if not self._celsius:
            temperature = (temperature * 9 / 5) + 32
            self.bme_temp_humid_text.text = 'Temp: {0} °F, Humid: {1}%'.format(temperature, humidity)
        else:
            self.bme_temp_humid_text.text = 'Temp: {0} °C, Humid: {1}%'.format(temperature, humidity)

        pressure = round(bme_data[3], 3)
        altitude = round(bme_data[4], 1)
        print('Altitude: %0.3f meters, Pressure: %0.2f hPa'%(altitude, pressure))
        self.bme_pres_alt_text.text = 'Alt: {0}m, Pres: {1} hPa'.format(altitude, pressure)

        gas = bme_data[1]
        print("Gas: {0} ohm".format(gas))
        self.bme_gas_text.text = 'Gas: {0}ohm'.format(gas)

        board.DISPLAY.refresh_soon()
        board.DISPLAY.wait_for_frame()

    def set_icon(self, filename):
        """Sets the background image to a bitmap file.

        :param filename: The filename of the chosen icon
        """
        print("Set icon to ", filename)
        if self._icon_group:
            self._icon_group.pop()

        if not filename:
            return  # we're done, no icon desired
        if self._icon_file:
            self._icon_file.close()
        self._icon_file = open(filename, "rb")
        icon = displayio.OnDiskBitmap(self._icon_file)
        try:
            self._icon_sprite = displayio.TileGrid(icon,
                                                   pixel_shader=displayio.ColorConverter())
        except TypeError:
            self._icon_sprite = displayio.TileGrid(icon,
                                                   pixel_shader=displayio.ColorConverter(),
                                                   position=(0,0))

        self._icon_group.append(self._icon_sprite)
        board.DISPLAY.refresh_soon()
        board.DISPLAY.wait_for_frame()