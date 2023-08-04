MAKEFLAGS += rR

PYTHON = python3
MCOPY  = mcopy

CIRCUITPYTHON_LABEL = CIRCUITPY
RP2040_LABEL = RPI-RP2

upload: PN7150.py NT3H2.py code.py
	$(PYTHON) checker.py code.py
	$(MCOPY) -voQi /dev/disk/by-label/$(CIRCUITPYTHON_LABEL) $^ ::

upload-circuitpython: firmware.uf2
	$(MCOPY) -vQi /dev/disk/by-label/$(RP2040_LABEL) $< ::
