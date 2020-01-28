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

"""class EmonModbusTcpInterfacer2
Monitors Modbus devices using modbus tcp
Implements 2 modbus functions : read_holding_registers (code x03) and read_input_registers (code x04)
To switch from function x03 to x04, just add fCode=4 in the section [[[init_settings]]] of the interfacer
"""

class EmonModbusTcpInterfacer2(EmonHubInterfacer):

    def __init__(self, name, modbus_IP='192.168.1.10', modbus_port=0, fCode=3):
        """Initialize Interfacer
        com_port and fCode
        """

        # Initialization
        super(EmonModbusTcpInterfacer2, self).__init__(name)
        
        if not pymodbus_found:
            self._log.error("PYMODBUS NOT PRESENT BUT NEEDED !!")
        # open connection
        if pymodbus_found:
            self._log.info("pymodbus installed")
            self._log.debug("EmonModbusTcpInterfacer2 args: " + str(modbus_IP) + " - " + str(modbus_port))
            self._con = self._open_modTCP(modbus_IP,modbus_port)
            if self._modcon :
                 self._log.info("Modbustcp client Connected")
            else:
                 self._log.info("Connection to ModbusTCP client failed. Will try again")

    # config check given a suffix
    def _check(self,node,suffix):
        # ehc.nodelist is a json object containing all datas from the [nodes] section of the emonhub.conf file
        if ehc.nodelist[node]['rx'] is None:
          self._log.error("!!!!!!!!!!!!!!!!!!!!!missing rx section in the node")
          return []
        else:
          rx=ehc.nodelist[node]['rx']
        if suffix+'s' in rx:
            what = rx[suffix+'s']
        elif suffix in rx:
            what = rx[suffix]
        else:
            self._log.debug("please provide a "+suffix+" or a list of "+suffix+"s")
            return []
        result=[]
        if type(what) is list:
            result = what
        else:
            result.append(str(what))
        return result

    def set(self, **kwargs):
        
        for key in kwargs.keys():
            setting = kwargs[key]
            self._settings[key] = setting
            self._log.debug("Setting " + self.name + " %s: %s" % (key, setting) )

    def close(self):

        # Close TCP connection
        if self._con is not None:
            self._log.info("Closing tcp port")
            self._con.close()

    def _open_modTCP(self,modbus_IP,modbus_port):
        """ Open connection to modbus device """

        try:
            c = ModbusClient(modbus_IP,modbus_port)
            if c.connect():
                self._log.info("Opening modbusTCP connection: " + str(modbus_port) + " @ " +str(modbus_IP))
                self._modcon = True
                self._rNames = {}
                self._datacodes = {}
                self._registers = {}
                self._unitIds = {}
                self._expectedSize = {}
            else:
                self._log.debug("Connection failed")
                self._modcon = False
        except Exception as e:
            self._log.error("modbusTCP connection failed" + str(e))
            #raise EmonHubInterfacerInitError('Could not open connection to host %s' %modbus_IP)
            pass
        else:
            return c


    def _read_node(self,node):
        """ Read registers from client and create a cargo for the specified node"""
        if pymodbus_found:
            f = []
            c = Cargo.new_cargo(rawdata="")
            # check if node has a configuration
            if node not in ehc.nodelist:
                self._log.error("node "+node+" not configured")
                return
            # valid datacodes list and number of registers associated
            # in modbus protocol, one register is 16 bits or 2 bytes
            valid_datacodes = ({'h': 1, 'H': 1, 'i': 2, 'l': 2, 'I': 2, 'L': 2, 'f': 2, 'q': 4, 'Q': 4, 'd': 4})
            
            # connection is not opened
            if not self._modcon :
                self._con.close()
                self._log.info("Not connected, retrying connect" + str(self.init_settings))
                self._con = self._open_modTCP(self.init_settings["modbus_IP"],self.init_settings["modbus_port"])
            
            # connection is opened but the node config has not been checked
            if self._modcon and node not in self._rNames :
                self._log.info("[node"+node+"]"+"*********checking the config***********")
                # create the lists
                # if one is missing, then datas reading will not be done
                rNames=self._check(node,'name')
                registers=self._check(node,'register')
                datacodes=self._check(node,'datacode')
                ln=len(rNames)
                lr=len(registers)
                ld=len(datacodes)
                # we can have the same datacode for all the registers 
                if ld == 1:
                    lmin=min(ln,lr)
                else:
                    lmin=lmin=min(ln,lr,ld)
                if lmin==0:
                    self._log.error("PLEASE REVIEW YOUR NODE "+node+" CONFIGURATION")
                    return
                del(rNames[lmin:ln])
                del(registers[lmin:lr])
                if ld > 1:
                    del(datacodes[lmin:ld])
                # at this stage, we know that rx section exists 
                rx=ehc.nodelist[node]['rx']
                # generate list of unitIds
                # if nothing is provided, we assume we have to interrogate slave 1
                unitIds =self._check(node,'unitId')
                if unitIds==[]:
                    unitIds.append("1")
                # check if number of names and number of unitIds are the same
                if len(unitIds)> 1 and len(unitIds) != len(rNames):
                    self._log.error("You are using unitIds. You have to define an equal number of UnitIds and of names")
                    return
                
                # calculate expected size in bytes and search for invalid datacode(s) 
                expectedSize=0
                if len(datacodes)==1:
                    if datacodes[0] not in valid_datacodes:
                        self._log.error("-" * 46)
                        self._log.error("invalid datacode")
                        self._log.error("-" * 46)
                        return
                    else:
                        expectedSize=len(rNames)*valid_datacodes[datacodes[0]]*2
                else:
                    for code in datacodes:
                        if code not in valid_datacodes:
                            self._log.error("-" * 46)
                            self._log.error("invalid datacode")
                            self._log.error("-" * 46)
                            return
                        else:
                            expectedSize+=valid_datacodes[code]*2
                self._rNames[node]=rNames
                self._registers[node]=registers
                self._datacodes[node]=datacodes
                self._unitIds[node]=unitIds
                self._expectedSize[node]=expectedSize
                # just for debug
                self._log.info(self._rNames[node])
                self._log.info(self._registers[node])
                self._log.info(self._datacodes[node])
                self._log.info(self._unitIds[node])
                self._log.info("[node"+node+"]"+"expected bytes number after encoding: "+str(self._expectedSize[node]))
                self._log.info("[node"+node+"]"+"*********config validated with success***********")

            # connection is opened, node config is valid and stored and we don't have any invalid datacode(s)
            if self._modcon and node in self._rNames:
                # so we can loop and read registers
                for idx, rName in enumerate(self._rNames[node]):
                    register = int(self._registers[node][idx])
                    
                    if len(self._unitIds[node]) > 1:
                        unitId = int(self._unitIds[node][idx])
                    else:
                        unitId = int(self._unitIds[node][0])
                    
                    if len(self._datacodes[node]) > 1:
                        datacode = self._datacodes[node][idx]
                    else:
                        datacode = self._datacodes[node][0]
                    
                    self._log.debug("datacode " + datacode)
                    qty = valid_datacodes[datacode]
                    self._log.debug("reading register # :" + str(register) + ", qty #: " + str(qty) + ", unit #: " + str(unitId))
                        
                    try:
                        if self._fCode==3:
                            self.rVal = self._con.read_holding_registers(register-1,qty,unit=unitId)
                        elif self._fCode==4:
                            self._log.info("we are reading input registers")
                            self.rVal = self._con.read_input_registers(register-1,qty,unit=unitId)
                        assert(self.rVal.function_code < 0x80)
                    except Exception as e:
                        self._log.error("Connection failed on read of register: " +str(register) + " : " + str(e))
                        self._modcon = False
                        #missing datas will lead to an incorrect encoding
                        #we have to drop the payload
                        return
                    else:
                        #self._log.debug("register value:" + str(self.rVal.registers)+" type= " + str(type(self.rVal.registers)))
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
                            rValD = decoder.decode_32bit_float()*10
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
                if len(f) == self._expectedSize[node]:
                    self._log.debug("payload size OK (" + str(len(f)) +")")
                    self._log.debug("reporting data: " + str(f))
                    c.nodeid = node
                    c.realdata = f      
                    self._log.debug("Return from read data: " + str(c.realdata))
                    return c
                else:
                    self._log.error("incorrect payload size :" + str(len(f)) + " expecting " + str(self._expectedSize[node]))
                    return
                    
    def read(self):
        if 'interval' in self._settings:
            time.sleep(float(self._settings["interval"]))
        # before the  config check for node(s), we fix the function code to 3 by default
        # if the user has defined something in the interfacer section, we modify fCode 
        # right now, we only accept fCode=3 and fCode=4
        if self._rNames == {} :
            self._fCode = 3
            if "fCode" in self.init_settings and int(self.init_settings["fCode"])==4 :
               self._fCode=4
            self._log.info("Using the modbus function code "+str(self._fCode))
        
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