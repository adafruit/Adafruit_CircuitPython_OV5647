# SPDX-FileCopyrightText: Copyright (c) 2026 Liz Clark for Adafruit Industries
# SPDX-License-Identifier: MIT
"""Press the boot button to save a photo from the OV5647 to the microSD card.

Photos are saved as 16-bit RGB565 BMP files: /sd/ov5647-0000.bmp,
/sd/ov5647-0001.bmp, etc.
"""

import os
import struct

import board
import keypad
import mipicsi
import sdioio
import storage
import videocore

import adafruit_ov5647

# microSD card over SDIO
sd = sdioio.SDCard(
    clock=board.SD_CLK,
    command=board.SD_CMD,
    data=(board.SD_DATA0, board.SD_DATA1, board.SD_DATA2, board.SD_DATA3),
    frequency=25000000,
)
storage.mount(storage.VfsFat(sd), "/sd")

sensor = adafruit_ov5647.OV5647(board.I2C(), reset_pin=board.CAMERA_RESET)
camera = mipicsi.Camera(sensor, output_format=mipicsi.PixelFormat.RGB565)
frame = bytearray(sensor.width * sensor.height * 2)
video = videocore.VideoBuffer(frame)
video.play(camera)

# the boot button reads low when pressed
buttons = keypad.Keys((board.BUTTON,), value_when_pressed=False, pull=True)


def next_filename():
    existing = os.listdir("/sd")
    number = 0
    while "ov5647-%04d.bmp" % number in existing:
        number += 1
    return "/sd/ov5647-%04d.bmp" % number


def save_bmp(path, pixels, width, height):
    """Save RGB565 pixels as a top-down 16-bit BMP."""
    image_size = width * height * 2  # even widths need no row padding
    offset = 14 + 40 + 12
    with open(path, "wb") as file:
        file.write(struct.pack("<2sIHHI", b"BM", offset + image_size, 0, 0, offset))
        file.write(
            struct.pack(
                "<IiiHHIIiiII", 40, width, -height, 1, 16, 3, image_size, 2835, 2835, 0, 0
            )
        )
        file.write(struct.pack("<III", 0xF800, 0x07E0, 0x001F))  # RGB565 masks
        file.write(pixels)


print("Camera running. Press the boot button to take a photo.")

while True:
    event = buttons.events.get()
    if event and event.pressed:
        video.stop()  # freeze the current frame while it is saved
        path = next_filename()
        save_bmp(path, frame, sensor.width, sensor.height)
        os.sync()  # make sure it's on the card before carrying on
        print("saved", path)
        video.play(camera)