# SPDX-FileCopyrightText: Copyright (c) 2026 Liz Clark for Adafruit Industries
# SPDX-License-Identifier: MIT

import board
import mipicsi
import videocore
import adafruit_ov5647

sensor = adafruit_ov5647.OV5647(board.I2C(), reset_pin=board.CAMERA_RESET)
camera = mipicsi.Camera(sensor, output_format=mipicsi.PixelFormat.RGB565)
frame = bytearray(sensor.width * sensor.height * 2)
video = videocore.VideoBuffer(frame)
video.play(camera)

while True:
    pass