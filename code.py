import board
import time
from supervisor import ticks_ms
from time import sleep
from digitalio import DigitalInOut, Pull
from busio import I2C

_TICKS_PERIOD = const(1<<29)

# NCI protocol definitions

# Header Message Type (MT) & Packet Boundary Flag (PBF)
# byte 0, MSB nibble
_HEADER_PBF_SEG_MASK     = const(0x10)
_HEADER_MT_CTRL_DATA     = const(0x00)
_HEADER_MT_CTRL_DATA_SEG = _HEADER_MT_CTRL_DATA &  _HEADER_PBF_SEG_MASK
_HEADER_MT_CTRL_REQ      = const(0x20)
_HEADER_MT_CTRL_REQ_SEG  = _HEADER_MT_CTRL_DATA & _HEADER_PBF_SEG_MASK
_HEADER_MT_CTRL_RSP      = const(0x40)
_HEADER_MT_CTRL_RSP_SEG  = _HEADER_MT_CTRL_RSP & _HEADER_PBF_SEG_MASK

# Group Identifier (GID) for control packets
# byte 0, LSB nibble
_GID_CORE = const(0x00)
_GID_RF   = const(0x01)

# Opcode Identifier for control packets
# byte 1, 6 LSBs
_OID_RF_DISCOVER_MAP = const(0x00)
_OID_RF_DISCOVER     = const(0x03)

_STATUS_OK       = const(0x00)
_STATUS_REJECTED = const(0x01)
_STATUS_FAILED   = const(0x03)

def status(nr: int):
    if nr == 0x00:
        return "OK"
    elif nr == 0x01:
        return "REJECTED"
    elif nr == 0x03:
        return "FAILED"
    else:
        return "0x{:02x}".format(nr)

def dump_package(buf: bytes, end: int, prefix: str = ""):
    fst, snd = buf[0], buf[1]
    if fst == 0x20 and snd == 0x00:
        print("{}CORE_RESET_CMD({}) Reset Configuration: {}".format(prefix, end, buf[3]))
    elif fst == 0x40 and snd == 0x00:
        print("{}CORE_RESET_RSP({}) Status: {} NCI Version: 0x{:02x} Configuration Status: 0x{:02x}".format(
            prefix, end, status(buf[3]), buf[4], buf[5]))
    elif fst == 0x20 and snd == 0x01:
        print("{}CORE_INIT_CMD({})".format(prefix, end))
    elif fst == 0x40 and snd == 0x01:
        # 3    Status
        # 4    NFCC Features
        #      ..
        # 8    #RF Interfaces
        #      RF Interfaces
        # 9+n  Max Logical Connections
        # 10+n Max Routing Table
        #      ..
        # 12+n Max Control Packet Payload Size
        # 13+n Max Size for Large Parameters
        #      ..
        # 15+n Manufacturer ID
        # 16+n Manufacturer Specific Information
        n = buf[8]
        print("{}CORE_INIT_RSP({}) Status: {} #RF Interfaces: {} Max Payload Size: {}".format(
            prefix, end, status(buf[3]), n, buf[12+n]))
    elif fst == 0x21 and snd == 0x00:
        print("{}RF_DISCOVER_MAP_CMD({}) #Mapping Configurations: {}".format(prefix, end, buf[3]))
    elif fst == 0x41 and snd == 0x00:
        print("{}RF_DISCOVER_MAP_RSP({}) Status: {}".format(prefix, end, status(buf[3])))
    elif fst == 0x21 and snd == 0x03:
        print("{}RF_DISCOVER_CMD({}) #Configurations: {}".format(prefix, end, status(buf[3])))
    elif fst == 0x41 and snd == 0x03:
        print("{}RF_DISCOVER_RSP({}) Status: {}".format(prefix, end, status(buf[3])))
    elif fst == 0x61 and snd == 0x05:
        # 3    RF Discovery ID
        # 4    RF Interface
        # 5    RF Protocol
        # 6    Activation RF Technology and Mode
        # 7    Max Data Packet Payload Size
        # 8    Initial Number of Credits
        # 9    #RF Technology Specific Parameters
        #      RF Technology Specific Parameters
        # 10+n Data Exchange RF Technology and Mode
        # 11+n Data Exchange Transmit Bit Rate
        # 12+n Data Exchange Receive Bit Rate
        # 13+n #Activation Parameters
        #      Activation Parameters
        print("{}RF_INTF_ACTIVATED_NTF({}) ID: {} Interface: {}{} Protocol: {}{} Mode: 0x{:02x}{} Max PL: {} Credits: {} RFTS length: {}".format(
            prefix, end, buf[3]
            , buf[4], " (Frame RF Interface)"      if buf[4] == 0x01 else ""
            , buf[5], " (PROTOCOL_T2T)"            if buf[5] == 0x02 else ""
            , buf[6], " (NFC_A_PASSIVE_POLL_MODE)" if buf[6] == 0x00 else ""
            , buf[7], buf[8], buf[9]))
        rtfs_length = buf[9]
        rfts_offset = 9+1
        # dump raw rfts
        for i in range(rtfs_length):
            print("{}RF_INTF_ACTIVATED_NTF({}) RFTS[{:02}]: {}".format(prefix, end, i, buf[rfts_offset+i]))
        # decode NFCID1 of rfts for NFC_A_PASSIVE_POLL_MODE
        if buf[6] == 0x00:
            nfcid1_length = buf[rfts_offset+2]
            print("  NFCID1 Length: {}".format(nfcid1_length))
            if nfcid1_length > 0:
                print("  NFCID1: ",end="")
                for id_byte_offset in range(nfcid1_length):
                    id_byte = "{}{:02x}".format(":" if id_byte_offset>0 else "", buf[rfts_offset+3+id_byte_offset])
                    print(id_byte, end="")
                print("")
        # dump DE
        de_offset = 9+rtfs_length+1
        print("{}RF_INTF_ACTIVATED_NTF({}) DE Mode: {} DE TX rate: {} DE RX rate: {} DE Act. Params: {}".format(prefix, end, buf[de_offset], buf[de_offset+1], buf[de_offset+2], buf[de_offset+3]))
    elif fst == 0x2f and snd == 0x02:
        print("{}PROPRIETARY_ACT_CMD({})".format(prefix, end))
    elif fst == 0x4f and snd == 0x02:
        print("{}PROPRIETARY_ACT_RSP({}) Status: {}".format(
            prefix, end, status(buf[3])))
    else:
        print("{}{} bytes".format(prefix, end))

# MT=1 GID=0 OID=0 PL=1 ResetType=1 (Reset Configuration)
NCI_CORE_RESET_CMD = b"\x20\x00\x01\x01"
# MT=1 GID=0 OID=1 PL=0
NCI_CORE_INIT_CMD  = b"\x20\x01\x00"
# MT=1 GID=f OID=2 PL=0
NCI_PROP_ACT_CMD   = b"\x2f\x02\x00"
# MT=1 GID=1 OID=0
NCI_RF_DISCOVER_MAP_RW = b"\x21\x00\x10\x05\x01\x01\x01\x02\x01\x01\x03\x01\x01\x04\x01\x02\x80\x01\x80"
# MT=1 GID=1 OID=3
NCI_RF_DISCOVER_CMD_RW = b"\x21\x03\x09\x04\x00\x01\x02\x01\x01\x01\x06\x01"
# MODE_POLL | TECH_PASSIVE_NFCA,
# MODE_POLL | TECH_PASSIVE_NFCF,
# MODE_POLL | TECH_PASSIVE_NFCB,
# MODE_POLL | TECH_PASSIVE_15693,

class PN7150:
    def __init__(self, i2c: I2C, irq: Pin, ven: Pin, addr: int = 0x28, debug: bool = False):
        self._i2c = i2c
        self._irq = DigitalInOut(irq)
        self._ven = DigitalInOut(ven)
        self._addr = addr
        self._debug = debug
        self._buf = bytearray(3 + 255)
        self._ven.switch_to_output(False)
        self._irq.switch_to_input(Pull.DOWN)

    def off(self):
        self._ven.value = 0

    def reset(self):
        self._ven.value = 0
        sleep(.001)
        self._ven.value = 1
        sleep(.003)

    def __read(self):
        self._i2c.readfrom_into(self._addr, self._buf, start=0, end=3);
        end = 3 + self._buf[2]
        if end > 3:
            self._i2c.readfrom_into(self._addr, self._buf, start=3, end=end)
        if self._debug:
            dump_package(self._buf, end, prefix="< ")
        return end

    def _read(self, timeout: int = 5):
        base = _TICKS_PERIOD - ticks_ms()
        while self._irq.value == 0:
            if (base + ticks_ms()) % _TICKS_PERIOD >= timeout:
                return 0
        return self.__read()

    def _write(self, cmd: bytes):
        # discard incoming messages
        while self._irq.value == 1:
            self.__read()
        if self._debug:
            dump_package(cmd, len(cmd), prefix="> ")
        return self._i2c.writeto(self._addr, cmd)

    def _connect(self):
        self.reset()
        self._write(NCI_CORE_RESET_CMD)
        end = self._read(15)
        if (end < 6 or self._buf[0] != 0x40 or self._buf[1] != 0x00
                or self._buf[3] != _STATUS_OK or self._buf[5] != 0x01):
            return False
        self._write(NCI_CORE_INIT_CMD)
        end = self._read()
        if end < 20 or self._buf[0] != 0x40 or self._buf[1] != 0x01 or self._buf[3] != _STATUS_OK:
            return False

        nRFInt = self._buf[8]
        self.fw_version = self._buf[17 + nRFInt:20 + nRFInt]
        print("Firmware version: 0x{:02x} 0x{:02x} 0x{:02x}".format(
            self.fw_version[0], self.fw_version[1], self.fw_version[2]))

        self._write(NCI_PROP_ACT_CMD)
        end = self._read()
        if end < 4 or self._buf[0] != 0x4F or self._buf[1] != 0x02 or self._buf[3] != _STATUS_OK:
            return False

        print("FW_Build_Number:", self._buf[4:8])

        return True

    def connect(self):
        assert self._i2c.try_lock()
        try:
            ok = self._connect()
        finally:
            self._i2c.unlock()
        return ok

    def modeRW(self):
        assert self._i2c.try_lock()
        self._write(NCI_RF_DISCOVER_MAP_RW)
        end = self._read(10)
        self._i2c.unlock()
        return end >= 4 and (self._buf[0] & 0xf0) == _HEADER_MT_CTRL_RSP and (self._buf[0] & 0x0f) == _GID_RF and self._buf[1] == _OID_RF_DISCOVER_MAP and self._buf[3] == _STATUS_OK

    def startDiscoveryRW(self):
        assert self._i2c.try_lock()
        self._write(NCI_RF_DISCOVER_CMD_RW)
        end = self._read()
        self._i2c.unlock()
        return end >= 4 and (self._buf[0] & 0xf0) == _HEADER_MT_CTRL_RSP and (self._buf[0] & 0x0f) == _GID_RF and self._buf[1] == _OID_RF_DISCOVER and (self._buf[3] == _STATUS_OK)

    def waitForDiscovery(self):
        assert self._i2c.try_lock()
        end = 0
        while end == 0:
            end = self._read()
        self._i2c.unlock()
        return end

class NT3H2:
    def __init__(self, i2c: I2C, addr: int = 0x55):
        self._i2c = i2c
        self._addr = addr
        self._buf = bytearray(17)

    def _readpage(self, page: int):
        self._buf[0] = page
        self._i2c.writeto_then_readfrom(self._addr, self._buf, self._buf, out_end = 1, in_start = 1)

    def readpage(self, page: int):
        assert self._i2c.try_lock()
        self._readpage(page)
        self._i2c.unlock()
        print('Page {:02}:{}'.format(page, ''.join(' {:02x}'.format(x) for x in self._buf[1:])))

    def set_addr(self, addr: int):
        assert self._i2c.try_lock()
        self._readpage(0x00)
        self._buf[1] = 2 * addr
        self._i2c.writeto(self._addr, self._buf)
        self._addr = addr
        self._i2c.unlock()

if __name__ == '__main__':
    if True:
        # Fast 400KHz I2C
        i2c = I2C(board.SCL, board.SDA, frequency = 400000)
    else:
        # Regular 100kHz I2C
        i2c = board.I2C()

    try:
        #nt = NT3H2(i2c)
        #nt.readpage(0)
        #nt.readpage(58)

        nfc = PN7150(i2c, board.IRQ, board.VEN, debug=True)

        while True:
            print("\n------ Initiating NFC discovery ------")
            assert nfc.connect()
            print("Connected.")

            assert nfc.modeRW()
            print("Switched to read/write mode.")

            assert nfc.startDiscoveryRW()
            print("Started read/write discovery.")

            nfc.waitForDiscovery()
            time.sleep(2)
    finally:
        i2c.deinit()
