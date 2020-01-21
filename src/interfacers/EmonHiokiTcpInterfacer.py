import socket
import time
import Cargo
import emonhub_coder as ehc
from emonhub_interfacer import EmonHubInterfacer
import struct
import errno

"""class EmonHiokiTcpInterfacer

Manages a socket on a HIOKI datalogger from ethernet link

"""

class EmonHiokiTcpInterfacer(EmonHubInterfacer):

    # Initialization
    def __init__(self, name, IP="192.168.1.11", port=8802):
        super().__init__(name)
        self._con = self._open_socket(IP,port)
        self._rNames = []
        if self._sopen :
            self._log.info("socket opened on HIOKI datalogger :-)")
        else:
            self._log.info("Impossible to open socket on HIOKI datalogger ;-( Will try again")

    # config check given a suffix (name,channel,voice)
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
            self._log.error("please provide a "+suffix+" or a list of "+suffix+"s")
            self._sopen=False
            return []
        result=[]
        if type(what) is list:
            result = what
        else:
            result.append(str(what))
        return result

    # Close connection
    def close(self):
        if self._con is not None:
            self._log.debug("Closing socket on HIOKI")
            self._con.close

    # read the runtime_settings from the interfacer section and store them in self._settings
    # they are  pubchannels, nodeId(s), interval
    def set(self, **kwargs):
        for key in kwargs:
            setting = kwargs[key]
            self._settings[key] = setting
            self._log.debug("Setting " + self.name + " %s: %s" % (key, setting) )

    # Open socket to HIOKI datalogger
    def _open_socket(self,IP,port):
        addr = (IP, int(port))
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            #s.setblocking(False)
            if s.connect_ex(addr) == 0:
                self._log.info("Opening socket on HIOKI datalogger: " + str(IP) + ":" + str(port))
                self._sopen = True
            else:
                self._log.debug("Connection to HIOKI failed: " +  str(IP) + ":" + str(port))
                self._sopen = False
        except Exception as e:
            self._log.error("socket opening failure : " + str(e))
            pass
        else:
            return s

    # using python socket
    # maybe could be simplier if using https://github.com/zeromq/pyzmq
    # see http://zguide.zeromq.org/page:all
    def read(self):
        f = []
        c = Cargo.new_cargo(rawdata="")
        
        if not self._sopen :
            self._con.close()
            self._log.info("Not connected, retrying connect" + str(self.init_settings))
            self._con = self._open_socket(self.init_settings["IP"],self.init_settings["port"])
            if self._rNames == [] :
                # connection is not open - we have to check the config
                # create 3 lists : self._rNames, self._channels and self._voices
                # if one this list is missing, then datas reading will not be done
                node = str(self._settings["nodeId"])
                rNames=self._check(node,'name')
                channels=self._check(node,'channel')
                voices=self._check(node,'voice')
                ln=len(rNames)
                lc=len(channels)
                lv=len(voices)
                lmin=min(ln,lc,lv)
                if lmin==0:
                    self._log.error("PLEASE REVIEW YOUR CONFIGURATION")
                    return
                del(rNames[lmin:ln])
                del(channels[lmin:lc])
                del(voices[lmin:lv])
                self._rNames=rNames
                self._channels=channels
                self._voices=voices
                self._log.debug(self._rNames)
                self._log.debug(self._channels)
                self._log.debug(self._voices)
                self._log.debug("*********config validated with success***********")
        
        if self._sopen and self._rNames == []:
            self._sopen = False

        if self._sopen :
            
            if 'interval' in self._settings:
                time.sleep(float(self._settings["interval"]))
            if 'nodeIds' in self._settings:
                nodes = self._settings["nodeIds"]
                # to develop later if needed
            elif 'nodeId' in self._settings:
                # we have only one node - work will be done by the classic process
                node = str(self._settings["nodeId"])

                # HIOKI interrogation
                for idx, rName in enumerate(self._rNames):
                    channel = self._channels[idx]
                    voice = self._voices[idx]
                    # using binary format
                    #msg=':MEMory:BREAl? CH'+channel+'_'+voice+'\r\n'
                    #self._con.send(msg)
                    #data = self._con.recv(1024)
                    #i = struct.unpack('>h', data)
                    #self._log.debug(i)
                    #t = ehc.encode('h',i[0])
                    #f.append(i[0])
                    # using ASCII format
                    msg=':MEMory:AREAl? CH'+channel+'_'+voice+'\r\n'
                    try:
                      self._con.sendall(msg)
                    except Exception as e:
                      self._log.error("Socket sending error : " + str(e))
                      if e.errno == errno.EPIPE:
                        self._log.error("FOUND BROKEN PIPE - REFRESHING SOCKET ..................")
                        self.close()
                        self._sopen=False
                        self._con = self._open_socket(self.init_settings["IP"],self.init_settings["port"])
                        if self._sopen :
                          self._con.sendall(msg)
                      else:
                        self._sopen=False
                        return
                    data = self._con.recv(1024)
                    if '\r\n' in data:
                      datap=data.replace('\r\n','')
                      self._log.debug(datap)
                      f.append(float(data)/100)
                if len(f)==len(self._rNames):
                    c.nodeid = node
                    c.realdata = f
                    self._log.debug("Return from read data: " + str(c.realdata))
                    return c
                else:
                    self._log.debug("missing data in the node - sending resumed !!!!!!!!!!!!!!!")
                    return
            else:
                self._log.error("please provide a nodeId or a list of nodeIds")
                return