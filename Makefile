MAKEFLAGS += rR

PYTHON = python3
MCOPY  = mcopy

CIRCUITPYTHON_LABEL = CIRCUITPY
RP2040_LABEL = RPI-RP2

upload: code.py
	$(PYTHON) checker.py code.py
	$(MCOPY) -voQi /dev/disk/by-label/$(CIRCUITPYTHON_LABEL) $< ::

upload-circuitpython: firmware.uf2
	$(MCOPY) -vQi /dev/disk/by-label/$(RP2040_LABEL) $< ::
