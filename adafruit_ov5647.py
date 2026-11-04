# SPDX-FileCopyrightText: Copyright (c) 2026 Liz Clark for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (C) 2016, Synopsys, Inc.
# SPDX-FileCopyrightText: Copyright (C) 2011 Sylwester Nawrocki
# SPDX-FileCopyrightText: Copyright (C) 2006-7 Jonathan Corbet
#
# SPDX-License-Identifier: GPL-2.0-only
"""
`adafruit_ov5647`
================================================================================

CircuitPython driver for the OV5647 camera module, as used on the
Raspberry Pi Camera v1.3. For use with `mipicsi.Camera`.

* Author(s): Liz Clark

Implementation Notes
--------------------

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://circuitpython.org/downloads


* Adafruit's Bus Device library: https://github.com/adafruit/Adafruit_CircuitPython_BusDevice

**Notes:**

* Register tables, power-up, mode and stream on/off sequences, and the
  controls follow the Linux kernel driver drivers/media/i2c/ov5647.c
"""

import time

import mipicsi
from adafruit_bus_device.i2c_device import I2CDevice
from digitalio import DigitalInOut
from micropython import const

try:
    from typing import Optional

    import busio
    from microcontroller import Pin
except ImportError:
    pass

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_OV5647.git"

_I2C_ADDRESS = const(0x36)
_CHIP_ID = const(0x5647)

_SW_STANDBY = const(0x0100)
_SW_RESET = const(0x0103)
_CHIP_ID_HIGH = const(0x300A)
_CHIP_ID_LOW = const(0x300B)
_PAD_OUT = const(0x300D)
_EXPOSURE = const(0x3500)  # 20 bits; the low 4 are fractions of a line
_AEC_AGC = const(0x3503)  # bit 0: manual exposure, bit 1: manual gain
_GAIN = const(0x350A)  # 10 bits
_HTS = const(0x380C)  # 16 bits
_VTS = const(0x380E)  # 16 bits
_OUTPUT_WIDTH = const(0x3808)  # 16 bits
_OUTPUT_HEIGHT = const(0x380A)  # 16 bits
_X_OFFSET = const(0x3810)  # 16 bits
_Y_OFFSET = const(0x3812)  # 16 bits
_TIMING_TC_V = const(0x3820)  # bit 1: vertical flip
_TIMING_TC_H = const(0x3821)  # bit 1: in-built horizontal mirror
_FRAME_OFF_NUMBER = const(0x4202)
_MIPI_CTRL00 = const(0x4800)
_MIPI_CTRL14 = const(0x4814)  # bits 7:6: virtual channel
_ISPCTRL3D = const(0x503D)  # test pattern

# MIPI_CTRL00 bits
_CLOCK_LANE_GATE = const(0x20)
_LINE_SYNC_ENABLE = const(0x10)
_BUS_IDLE = const(0x04)
_CLOCK_LANE_DISABLE = const(0x01)

# Register tables from the Linux ov5647 driver, unchanged.
_REGS_OE_ENABLE = (
    (0x3000, 0x0F),
    (0x3001, 0xFF),
    (0x3002, 0xE4),
)

_REGS_OE_DISABLE = (
    (0x3000, 0x00),
    (0x3001, 0x00),
    (0x3002, 0x00),
)

_REGS_COMMON = (
    (0x0100, 0x00),
    (0x0103, 0x01),
    (0x3034, 0x1A),
    (0x3035, 0x21),
    (0x303C, 0x11),
    (0x3106, 0xF5),
    (0x3827, 0xEC),
    (0x370C, 0x03),
    (0x5000, 0x06),
    (0x5003, 0x08),
    (0x5A00, 0x08),
    (0x3000, 0x00),
    (0x3001, 0x00),
    (0x3002, 0x00),
    (0x3016, 0x08),
    (0x3017, 0xE0),
    (0x3018, 0x44),
    (0x301C, 0xF8),
    (0x301D, 0xF0),
    (0x3A18, 0x00),
    (0x3A19, 0xF8),
    (0x3C01, 0x80),
    (0x3B07, 0x0C),
    (0x3630, 0x2E),
    (0x3632, 0xE2),
    (0x3633, 0x23),
    (0x3634, 0x44),
    (0x3636, 0x06),
    (0x3620, 0x64),
    (0x3621, 0xE0),
    (0x3600, 0x37),
    (0x3704, 0xA0),
    (0x3703, 0x5A),
    (0x3715, 0x78),
    (0x3717, 0x01),
    (0x3731, 0x02),
    (0x370B, 0x60),
    (0x3705, 0x1A),
    (0x3F05, 0x02),
    (0x3F06, 0x10),
    (0x3F01, 0x0A),
    (0x3A08, 0x01),
    (0x3A0F, 0x58),
    (0x3A10, 0x50),
    (0x3A1B, 0x58),
    (0x3A1E, 0x50),
    (0x3A11, 0x60),
    (0x3A1F, 0x28),
    (0x4001, 0x02),
    (0x4000, 0x09),
    (0x3503, 0x03),
)

_REGS_2592X1944 = (
    (0x3036, 0x69),
    (0x3821, 0x02),
    (0x3820, 0x00),
    (0x3612, 0x5B),
    (0x3618, 0x04),
    (0x5002, 0x41),
    (0x3814, 0x11),
    (0x3815, 0x11),
    (0x3708, 0x64),
    (0x3709, 0x12),
    (0x3800, 0x00),
    (0x3801, 0x00),
    (0x3802, 0x00),
    (0x3803, 0x00),
    (0x3804, 0x0A),
    (0x3805, 0x3F),
    (0x3806, 0x07),
    (0x3807, 0xA3),
    (0x3808, 0x0A),
    (0x3809, 0x20),
    (0x380A, 0x07),
    (0x380B, 0x98),
    (0x3811, 0x10),
    (0x3813, 0x06),
    (0x3A09, 0x28),
    (0x3A0A, 0x00),
    (0x3A0B, 0xF6),
    (0x3A0D, 0x08),
    (0x3A0E, 0x06),
    (0x4004, 0x04),
    (0x4837, 0x19),
    (0x4800, 0x24),
    (0x0100, 0x01),
)

_REGS_1920X1080 = (
    (0x3036, 0x69),
    (0x3821, 0x02),
    (0x3820, 0x00),
    (0x3612, 0x5B),
    (0x3618, 0x04),
    (0x5002, 0x41),
    (0x3814, 0x11),
    (0x3815, 0x11),
    (0x3708, 0x64),
    (0x3709, 0x12),
    (0x3800, 0x01),
    (0x3801, 0x5C),
    (0x3802, 0x01),
    (0x3803, 0xB2),
    (0x3804, 0x08),
    (0x3805, 0xE3),
    (0x3806, 0x05),
    (0x3807, 0xF1),
    (0x3808, 0x07),
    (0x3809, 0x80),
    (0x380A, 0x04),
    (0x380B, 0x38),
    (0x3811, 0x04),
    (0x3813, 0x02),
    (0x3A09, 0x4B),
    (0x3A0A, 0x01),
    (0x3A0B, 0x13),
    (0x3A0D, 0x04),
    (0x3A0E, 0x03),
    (0x4004, 0x04),
    (0x4837, 0x19),
    (0x4800, 0x34),
    (0x0100, 0x01),
)

_REGS_1296X972 = (
    (0x3036, 0x69),
    (0x3821, 0x03),
    (0x3820, 0x41),
    (0x3612, 0x59),
    (0x3618, 0x00),
    (0x5002, 0x41),
    (0x3800, 0x00),
    (0x3801, 0x00),
    (0x3802, 0x00),
    (0x3803, 0x00),
    (0x3804, 0x0A),
    (0x3805, 0x3F),
    (0x3806, 0x07),
    (0x3807, 0xA3),
    (0x3808, 0x05),
    (0x3809, 0x10),
    (0x380A, 0x03),
    (0x380B, 0xCC),
    (0x3811, 0x0C),
    (0x3813, 0x06),
    (0x3814, 0x31),
    (0x3815, 0x31),
    (0x3A09, 0x28),
    (0x3A0A, 0x00),
    (0x3A0B, 0xF6),
    (0x3A0D, 0x08),
    (0x3A0E, 0x06),
    (0x4004, 0x04),
    (0x4837, 0x16),
    (0x4800, 0x24),
    (0x350A, 0x00),
    (0x350B, 0x10),
    (0x3500, 0x00),
    (0x3501, 0x1A),
    (0x3502, 0xF0),
    (0x3212, 0xA0),
    (0x0100, 0x01),
)

_REGS_640X480 = (
    (0x3036, 0x46),
    (0x3821, 0x03),
    (0x3820, 0x41),
    (0x3612, 0x59),
    (0x3618, 0x00),
    (0x3814, 0x35),
    (0x3815, 0x35),
    (0x3708, 0x64),
    (0x3709, 0x52),
    (0x3800, 0x00),
    (0x3801, 0x10),
    (0x3802, 0x00),
    (0x3803, 0x00),
    (0x3804, 0x0A),
    (0x3805, 0x2F),
    (0x3806, 0x07),
    (0x3807, 0x9F),
    (0x3808, 0x02),
    (0x3809, 0x80),
    (0x380A, 0x01),
    (0x380B, 0xE0),
    (0x3A09, 0x2E),
    (0x3A0A, 0x00),
    (0x3A0B, 0xFB),
    (0x3A0D, 0x02),
    (0x3A0E, 0x01),
    (0x4004, 0x02),
    (0x4800, 0x34),
    (0x0100, 0x01),
)


class _ModeInfo:
    """One sensor mode: native size, frame timing and MIPI lane bit rate"""

    def __init__(self, name, size, timing, lane_bit_rate_mbps, regs):
        self.name = name
        self.width, self.height = size
        self.hts, self.vts = timing  # total line length and frame height
        self.lane_bit_rate_mbps = lane_bit_rate_mbps
        self.regs = regs

    def __repr__(self):
        return "Mode." + self.name


class Mode:
    """Sensor modes. All send RAW10 over 2 MIPI data lanes."""

    R640X480 = _ModeInfo("R640X480", (640, 480), (1852, 504), 292, _REGS_640X480)
    """640 x 480, 2x2 binned and subsampled, full field of view, about 60
    frames per second. The default."""

    R1296X972 = _ModeInfo("R1296X972", (1296, 972), (1896, 1435), 438, _REGS_1296X972)
    """1296 x 972, 2x2 binned, full field of view"""

    R1920X1080 = _ModeInfo("R1920X1080", (1920, 1080), (2416, 1104), 438, _REGS_1920X1080)
    """1920 x 1080, center crop of the full resolution, 30 frames per second"""

    R2592X1944 = _ModeInfo("R2592X1944", (2592, 1944), (2844, 1968), 438, _REGS_2592X1944)
    """2592 x 1944, full 5 megapixel resolution. One RGB565 frame is about
    10 MB."""


class TestPattern:
    """Built-in test patterns, for `OV5647.test_pattern`"""

    NONE = 0x00
    """The camera image"""
    COLOR_BARS = 0x80
    """Vertical color bars"""
    COLOR_SQUARES = 0x82
    """A grid of colored squares"""
    RANDOM = 0x81
    """Random data"""


# Bayer order for each combination of [flip][mirror], as in the Linux
# driver's ov5647_get_mbus_code().
_BAYER_ORDERS = (
    (mipicsi.BayerOrder.GBRG, mipicsi.BayerOrder.BGGR),
    (mipicsi.BayerOrder.RGGB, mipicsi.BayerOrder.GRBG),
)


class OV5647:
    """Driver for the OV5647 camera sensor.

    :param ~busio.I2C i2c: The I2C bus the sensor is connected to
    :param ~microcontroller.Pin reset_pin: The camera's enable/power-down pin,
        such as ``board.CAMERA_RESET``. It is pulsed low, then held high.
    :param Mode mode: The initial sensor mode
    :param int address: The sensor's I2C address
    """

    def __init__(
        self,
        i2c: busio.I2C,
        *,
        reset_pin: Optional[Pin] = None,
        mode: _ModeInfo = Mode.R640X480,
        address: int = _I2C_ADDRESS,
    ) -> None:
        self._reset = None
        if reset_pin is not None:
            self._reset = DigitalInOut(reset_pin)
            self._reset.switch_to_output(value=False)
            time.sleep(0.01)
            self._reset.value = True
            time.sleep(0.02)  # datasheet: 20 ms before the first I2C access
        self._device = I2CDevice(i2c, address)
        self._buf = bytearray(3)

        self._streaming = False
        self._mode = mode
        self._width = mode.width
        self._height = mode.height
        self._mirror = False
        self._flip = False
        self._test_pattern = TestPattern.NONE
        self._auto_exposure = True
        self._exposure = min(mode.vts - 4, 1000)
        self._analog_gain = 32

        # Power on: enable the outputs, then stop streaming so the MIPI lanes
        # rest in LP-11 until the camera starts playing.
        self._write_list(_REGS_OE_ENABLE)
        self._stop()

        # Detect
        self._write(_SW_RESET, 0x01)
        chip_id = (self._read(_CHIP_ID_HIGH) << 8) | self._read(_CHIP_ID_LOW)
        if chip_id != _CHIP_ID:
            raise RuntimeError(f"Expected OV5647, got chip ID 0x{chip_id:04X}")
        self._write(_SW_RESET, 0x00)

    def _read(self, reg: int) -> int:
        buf = self._buf
        buf[0] = reg >> 8
        buf[1] = reg & 0xFF
        with self._device as dev:
            dev.write_then_readinto(buf, buf, out_end=2, in_start=2)
        return buf[2]

    def _write(self, reg: int, value: int) -> None:
        buf = self._buf
        buf[0] = reg >> 8
        buf[1] = reg & 0xFF
        buf[2] = value
        with self._device as dev:
            dev.write(buf)

    def _write_list(self, regs) -> None:
        for reg, value in regs:
            self._write(reg, value)
            if reg == _SW_RESET and value == 0x01:
                time.sleep(0.005)  # let the software reset finish

    def _write16(self, reg: int, value: int) -> None:
        self._write(reg, value >> 8)
        self._write(reg + 1, value & 0xFF)

    def _read16(self, reg: int) -> int:
        return (self._read(reg) << 8) | self._read(reg + 1)

    def _update_bits(self, reg: int, mask: int, value: int) -> None:
        self._write(reg, (self._read(reg) & ~mask & 0xFF) | (value & mask))

    def _check_not_streaming(self) -> None:
        if self._streaming:
            raise RuntimeError("Stop the video before changing the sensor's mode")

    @property
    def mode(self) -> _ModeInfo:
        """The sensor mode, one of the `Mode` values. Setting it resets
        `width` and `height` to the mode's full size, and `exposure` to the
        mode's default. Can't be changed while streaming."""
        return self._mode

    @mode.setter
    def mode(self, mode: _ModeInfo) -> None:
        self._check_not_streaming()
        self._mode = mode
        self._width = mode.width
        self._height = mode.height
        self._exposure = min(mode.vts - 4, 1000)

    @property
    def width(self) -> int:
        """Frame width in pixels. Set it to crop a centered window narrower
        than the mode's full width (even values only). Can't be changed while
        streaming."""
        return self._width

    @width.setter
    def width(self, width: int) -> None:
        self._check_not_streaming()
        if not 2 <= width <= self._mode.width or width % 2:
            raise ValueError(f"width must be even and at most {self._mode.width}")
        self._width = width

    @property
    def height(self) -> int:
        """Frame height in pixels. Set it to crop a centered window shorter
        than the mode's full height (even values only). Can't be changed while
        streaming."""
        return self._height

    @height.setter
    def height(self, height: int) -> None:
        self._check_not_streaming()
        if not 2 <= height <= self._mode.height or height % 2:
            raise ValueError(f"height must be even and at most {self._mode.height}")
        self._height = height

    @property
    def pixel_format(self) -> mipicsi.PixelFormat:
        """The `mipicsi.PixelFormat` the sensor transmits: always RAW10"""
        return mipicsi.PixelFormat.RAW10

    @property
    def bayer_order(self) -> mipicsi.BayerOrder:
        """The `mipicsi.BayerOrder` of the RAW data, which depends on
        `mirror` and `flip`"""
        return _BAYER_ORDERS[self._flip][self._mirror]

    @property
    def data_lanes(self) -> int:
        """The number of MIPI data lanes: always 2"""
        return 2

    @property
    def lane_bit_rate_mbps(self) -> int:
        """The bit rate of each MIPI data lane in the current mode"""
        return self._mode.lane_bit_rate_mbps

    @property
    def mirror(self) -> bool:
        """True to mirror the image left to right. Can't be changed while
        streaming, because it changes the `bayer_order`."""
        return self._mirror

    @mirror.setter
    def mirror(self, value: bool) -> None:
        self._check_not_streaming()
        self._mirror = bool(value)

    @property
    def flip(self) -> bool:
        """True to flip the image upside down. `mirror` and `flip` together
        rotate the image 180 degrees. Can't be changed while streaming,
        because it changes the `bayer_order`."""
        return self._flip

    @flip.setter
    def flip(self, value: bool) -> None:
        self._check_not_streaming()
        self._flip = bool(value)

    @property
    def test_pattern(self) -> int:
        """A `TestPattern` value to send instead of the camera image, or
        `TestPattern.NONE` for the image"""
        return self._test_pattern

    @test_pattern.setter
    def test_pattern(self, value: int) -> None:
        self._test_pattern = value
        if self._streaming:
            self._write(_ISPCTRL3D, value)

    @property
    def auto_exposure(self) -> bool:
        """True (the default) for the sensor's automatic exposure and gain.
        When False, `exposure` and `analog_gain` set them directly."""
        return self._auto_exposure

    @auto_exposure.setter
    def auto_exposure(self, value: bool) -> None:
        self._auto_exposure = bool(value)
        if self._streaming:
            self._write_exposure()

    @property
    def exposure(self) -> int:
        """Exposure time in lines, 4 up to the mode's frame height plus
        blanking. With `auto_exposure` it is only the starting point."""
        return self._exposure

    @exposure.setter
    def exposure(self, value: int) -> None:
        if not 4 <= value <= self._mode.vts - 4:
            raise ValueError(f"exposure must be 4 to {self._mode.vts - 4} lines")
        self._exposure = value
        if self._streaming:
            self._write_exposure()

    @property
    def analog_gain(self) -> int:
        """Analog gain, 16 (1x) to 1023 (about 64x). The default is 32 (2x).
        With `auto_exposure` it is only the starting point."""
        return self._analog_gain

    @analog_gain.setter
    def analog_gain(self, value: int) -> None:
        if not 16 <= value <= 1023:
            raise ValueError("analog_gain must be 16 to 1023")
        self._analog_gain = value
        if self._streaming:
            self._write_exposure()

    def _write_exposure(self) -> None:
        lines = self._exposure << 4
        self._write(_EXPOSURE, (lines >> 16) & 0x0F)
        self._write(_EXPOSURE + 1, (lines >> 8) & 0xFF)
        self._write(_EXPOSURE + 2, lines & 0xFF)
        self._write16(_GAIN, self._analog_gain & 0x3FF)
        self._write(_AEC_AGC, 0x00 if self._auto_exposure else 0x03)

    @property
    def streaming(self) -> bool:
        """True while the sensor is streaming frames (read-only)"""
        return self._streaming

    def _start(self) -> None:
        """Program the current mode and start streaming. Called by
        `mipicsi.Camera`; user code should not call it."""
        if self._streaming:
            return  # idempotent, as mipicsi expects
        mode = self._mode

        # Set mode: common registers, mode registers, virtual channel 0
        self._write_list(_REGS_COMMON)
        self._write_list(mode.regs)
        self._update_bits(_MIPI_CTRL14, 0xC0, 0x00)
        if not self._read(_SW_STANDBY) & 0x01:
            self._write(_SW_STANDBY, 0x01)

        # Controls, as the Linux driver applies them at stream start
        self._write16(_HTS, mode.hts)
        self._write16(_VTS, mode.vts)
        self._write_exposure()
        self._write(_ISPCTRL3D, self._test_pattern)
        # The sensor's mirror bit is set for the unmirrored image
        self._update_bits(_TIMING_TC_H, 0x02, 0x00 if self._mirror else 0x02)
        self._update_bits(_TIMING_TC_V, 0x02, 0x02 if self._flip else 0x00)

        # Crop a centered window by shrinking the output size and moving the
        # window offset. Offsets stay even so the Bayer order doesn't change.
        if (self._width, self._height) != (mode.width, mode.height):
            x_offset = self._read16(_X_OFFSET) + ((mode.width - self._width) // 2 & ~1)
            y_offset = self._read16(_Y_OFFSET) + ((mode.height - self._height) // 2 & ~1)
            self._write16(_OUTPUT_WIDTH, self._width)
            self._write16(_OUTPUT_HEIGHT, self._height)
            self._write16(_X_OFFSET, x_offset)
            self._write16(_Y_OFFSET, y_offset)

        # Stream on: non-continuous clock with line sync, as on a Raspberry Pi
        self._write(_MIPI_CTRL00, _BUS_IDLE | _CLOCK_LANE_GATE | _LINE_SYNC_ENABLE)
        self._write(_FRAME_OFF_NUMBER, 0x00)
        self._write(_PAD_OUT, 0x00)
        self._streaming = True

    def _stop(self) -> None:
        """Stop streaming. Called by `mipicsi.Camera`; user code should not
        call it."""
        self._write(_MIPI_CTRL00, _CLOCK_LANE_GATE | _BUS_IDLE | _CLOCK_LANE_DISABLE)
        self._write(_FRAME_OFF_NUMBER, 0x0F)
        self._write(_PAD_OUT, 0x01)
        self._streaming = False

    def deinit(self) -> None:
        """Stop streaming, power the sensor down and release the reset pin"""
        try:
            self._stop()
            self._write_list(_REGS_OE_DISABLE)
            self._update_bits(_SW_STANDBY, 0x01, 0x00)
        except OSError:
            pass  # the sensor may already be powered off
        if self._reset is not None:
            self._reset.value = False
            self._reset.deinit()
            self._reset = None

    def __enter__(self) -> "OV5647":
        return self

    def __exit__(self, exception_type, exception_value, traceback) -> None:
        self.deinit()
