import time
import Cargo

try:
    from pymodbus.constants import Endian
    from pymodbus.payload import BinaryPayloadDecoder
    from pymodbus.client.sync import ModbusTcpClient as ModbusClient
    pymodbus_found = True
except ImportError:
    pymodbus_found = False

import emonhub_coder as ehc
from emonhub_interfacer import EmonHubInterfacer

"""class EmonModbusTcpInterfacer
Monitors Modbus devices using modbus tcp
At this stage, only read_holding_registers() is implemented in the read() method
for devices working only with integers, please change the function to read_inpu$
"""

def clean(str):
    if str.find(",")!=-1:
        str=str[0:str.find(",")]
    str=str.replace("[","")
    str=str.replace("]","")
    str=str.replace("'","")
    return str

class EmonModbusTcpInterfacer(EmonHubInterfacer):

    def __init__(self, name, modbus_IP='192.168.1.10', modbus_port=0):
        """Initialize Interfacer
        com_port (string): path to COM port
        """

        # Initialization
        super().__init__(name)

        if not pymodbus_found:
            self._log.error("PYMODBUS NOT PRESENT BUT NEEDED !!")
        # open connection
        if pymodbus_found:
            self._log.info("pymodbus installed")
            self._log.debug("EmonModbusTcpInterfacer args: " + str(modbus_IP) + " - " + str(modbus_port))
            self._con = self._open_modTCP(modbus_IP, modbus_port)
            if self._modcon:
                 self._log.info("Modbustcp client Connected")
            else:
                 self._log.info("Connection to ModbusTCP client failed. Will try again")

    def set(self, **kwargs):
        for key in kwargs:
            setting = kwargs[key]
            self._settings[key] = setting
            self._log.debug("Setting " + self.name + " %s: %s" % (key, setting))

    def close(self):
        # Close TCP connection
        if self._con is not None:
            self._log.debug("Closing tcp port")
            self._con.close()

    def _open_modTCP(self, modbus_IP, modbus_port):
        """ Open connection to modbus device """

        try:
            c = ModbusClient(modbus_IP, modbus_port)
            if c.connect():
                self._log.info("Opening modbusTCP connection: " + str(modbus_port) + " @ " + str(modbus_IP))
                self._modcon = True
            else:
                self._log.debug("Connection failed")
                self._modcon = False
        except Exception as e:
            self._log.error("modbusTCP connection failed" + str(e))
            #raise EmonHubInterfacerInitError('Could not open connection to host %s' %modbus_IP)
        else:
            return c


    def _read_node(self,node):
        """ Read registers from client and create a cargo for the specified node"""
        if pymodbus_found:
            f = []
            c = Cargo.new_cargo(rawdata="")
            # valid datacodes list and number of registers associated
            # in modbus protocol, one register is 16 bits or 2 bytes
            valid_datacodes = ({'h': 1, 'H': 1, 'i': 2, 'l': 2, 'I': 2, 'L': 2, 'f': 2, 'q': 4, 'Q': 4, 'd': 4})

            if not self._modcon:
                self._con.close()
                self._log.info("Not connected, retrying connect" + str(self.init_settings))
                self._con = self._open_modTCP(self.init_settings["modbus_IP"], self.init_settings["modbus_port"])

            if self._modcon :

                # check if node has a configuration
                if node not in ehc.nodelist:
                    self._log.error("node "+node+" not configured")
                    return
                if 'rx' not in ehc.nodelist[node]:
                    self._log.error("no rx section in configuration of node "+node)
                    return

                rx=ehc.nodelist[node]['rx']

                # store names
                rNames = rx['names']
                if 'names' in rx:
                    rNames = rx['names']
                elif 'name' in rx:
                    rNames={}
                    rNames[0] = clean(str(rx['name']))
                else:
                    print("please provide a name or a list of names")
                    return

                # fetch registers
                if 'registers' in rx:
                    registers = rx['registers']
                elif 'register' in rx:
                    registers = {}
                    registers[0] = clean(str(rx['register']))
                else:
                    self._log.error("please provide a register number or a list of registers")
                    return

                # check if number of registers and number of names are the same
                if len(rNames) != len(registers):
                    self._log.error("You have to define an equal number of registers and of names")
                    return

                # fetch unitId or unitIds
                unitIds = None
                if 'unitIds' in rx:
                    unitIds = rx['unitIds']
                elif 'unitId' in rx:
                    unitId = int(clean(str(rx['unitId'])))
                else:
                    unitId=1

                # check if number of names and number of unitIds are the same
                if unitIds is not None:
                    if len(unitIds) != len(rNames):
                        self._log.error("You are using unitIds. You have to define an equal number of UnitIds and of names")
                        return

                # fetch datacode or datacodes
                datacodes = None
                if 'datacodes' in rx:
                    datacodes = rx['datacodes']
                elif 'datacode' in rx:
                    datacode = clean(str(rx['datacode']))
                else:
                    self._log.error("please provide a datacode or a list of datacodes")
                    return

                # check if number of names and number of datacodes are the same
                if datacodes is not None:
                    if len(datacodes) != len(rNames):
                        self._log.error("You are using datacodes. You have to define an equal number of datacodes and of names")
                        return

                # calculate expected size in bytes and search for invalid datacode(s)
                expectedSize = 0
                if datacodes is not None:
                    for code in datacodes:
                        if code not in valid_datacodes:
                            self._log.debug("-" * 46)
                            self._log.debug("invalid datacode")
                            self._log.debug("-" * 46)
                            return
                        else:
                            expectedSize += valid_datacodes[code] * 2
                else:
                    if datacode not in valid_datacodes:
                        self._log.debug("-" * 46)
                        self._log.debug("invalid datacode")
                        self._log.debug("-" * 46)
                        return
                    else:
                        expectedSize = len(rNames) * valid_datacodes[datacode] * 2

                self._log.debug("expected bytes number after encoding: " + str(expectedSize))

                # at this stage, we don't have any invalid datacode(s)
                # so we can loop and read registers
                for idx, rName in enumerate(rNames):
                    register = int(registers[idx])

                    if unitIds is not None:
                        unitId = int(unitIds[idx])

                    if datacodes is not None:
                        datacode = datacodes[idx]

                    self._log.debug("datacode " + datacode)
                    qty = valid_datacodes[datacode]
                    self._log.debug("reading register # :" + str(register) + ", qty #: " + str(qty) + ", unit #: " + str(unitId))

                    try:
                        self.rVal = self._con.read_holding_registers(register - 1, qty, unit=unitId)
                        assert self.rVal.function_code < 0x80
                    except Exception as e:
                        self._log.error("Connection failed on read of register: " + str(register) + " : " + str(e))
                        self._modcon = False
                        #missing datas will lead to an incorrect encoding
                        #we have to drop the payload
                        return
                    else:
                        #self._log.debug("register value:" + str(self.rVal.registers) + " type= " + str(type(self.rVal.registers)))
                        #f = f + self.rVal.registers
                        decoder = BinaryPayloadDecoder.fromRegisters(self.rVal.registers, byteorder=Endian.Big, wordorder=Endian.Big)
                        if datacode == 'h':
                            rValD = decoder.decode_16bit_int()
                        elif datacode == 'H':
                            rValD = decoder.decode_16bit_uint()
                        elif datacode == 'i':
                            rValD = decoder.decode_32bit_int()
                        elif datacode == 'l':
                            rValD = decoder.decode_32bit_int()
                        elif datacode == 'I':
                            rValD = decoder.decode_32bit_uint()
                        elif datacode == 'L':
                            rValD = decoder.decode_32bit_uint()
                        elif datacode == 'f':
                            rValD = decoder.decode_32bit_float() * 10
                        elif datacode == 'q':
                            rValD = decoder.decode_64bit_int()
                        elif datacode == 'Q':
                            rValD = decoder.decode_64bit_uint()
                        elif datacode == 'd':
                            rValD = decoder.decode_64bit_float()*10
                        # some modbus IP gateways (eg Enless) work with radio sensors
                        # if a rssi is out of range, we could have incoherent values so we drop the whole payload
                        if rName[0:4] == "RSSI":
                            if rValD > 1500:
                                self._log.debug("RSSI out of range" + str(rValD))
                                return
                            elif rValD == 0:
                                self._log.debug("RSSI null")
                                return
                            else:
                                self._log.debug("RSSI OK")
                        t = ehc.encode(datacode,rValD)
                        f = f + list(t)
                        self._log.debug("Encoded value: " + str(t))
                        self._log.debug("value: " + str(rValD))

                #test if payload length is OK
                if len(f) == expectedSize:
                    self._log.debug("payload size OK (" + str(len(f)) + ")")
                    self._log.debug("reporting data: " + str(f))
                    c.nodeid = node
                    c.realdata = f
                    self._log.debug("Return from read data: " + str(c.realdata))
                    return c
                else:
                    self._log.error("incorrect payload size :" + str(len(f)) + " expecting " + str(expectedSize))
                    return

    def read(self):
        if 'interval' in self._settings:
            time.sleep(float(self._settings["interval"]))
        # fetch nodeid or nodeids
        if 'nodeIds' in self._settings:
            nodes = self._settings["nodeIds"]
            for idx, node in enumerate(nodes):
                if len(self._settings["pubchannels"]):
                    # Read the input and process data if available
                    rxc = self._read_node(node)
                    if rxc:
                        rxc = self._process_rx(rxc)
                        if rxc:
                            for channel in self._settings["pubchannels"]:
                                self._log.debug(str(rxc.uri) + " Sent to channel(start)' : " + str(channel))

                                # Initialize channel if needed
                                if not channel in self._pub_channels:
                                    self._pub_channels[channel] = []

                                # Add cargo item to channel
                                self._pub_channels[channel].append(rxc)

                                self._log.debug(str(rxc.uri) + " Sent to channel(end)' : " + str(channel))
            self._log.debug("all modbus 'simili' nodes processed")
            return
        elif 'nodeId' in self._settings:
            # we have only one node - work will be done by the classic process
            node = str(self._settings["nodeId"])
            return self._read_node(node)
        else:
            self._log.error("please provide a nodeId or a list of nodeIds")
            return
