#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jul  8 07:29:31 2020

@author: jimlux
"""

defaultaddress= 0x81
""" class to manage a 485 bus connected to arx boards
opens the serial port and provides methods to send and receive

one can instantiate multiple buses if desired

"""
import serial

class arx485:
    def __init__(self,name,port):
        self.name = name
        self.serial = serial.Serial(
            port = port,
            baudrate = 9600,
            parity = serial.PARITY_NONE,
            stopbits = serial.STOPBITS_ONE,
            bytesize = serial.EIGHTBITS,
            timeout = 30,
            writeTimeout = 0,
            readTimeout = 0.1
            )
        #self.clear_buffers()
        #self.incoming_data = ''
        #self.saved_data = []
    
    def send(self,addr,string):
        pass
    def receive(self,nchars):
        pass
    def sendrecv(self,addr,string,nchars):
        self.send(addr,string)
        r = self.receive(nchars)
        print(r)
    def clear_buffers(self):
        self.serial.flushInput()
        self.serial.flushOutput()
        
""" class for arx boards
I'm not sure we'll need this
"""

class arx:
    def __init__(self,addr,bus):
        self.addr = addr
        self.bus = bus
    def send(self,string):
        print("send to arx %x,"%self.addr)
        for c in string:
            print(" %x"%ord(c))
        self.bus.clear_buffers()
        self.bus.send(self.addr,string)
        
    def receive(self,nchars):
        r = bus.read(nchars)
        return r
    
"""
generic versions, using global variable, bus
"""

   
def sendtoarx(addr,string):
    if not addr:
        if debug:
            print("using default address %x"%defaultaddress)

        addr = defaultaddress
    print("send to arx %x,"%addr)
    for c in string:
        print(" %x"%ord(c))
    bus.clear_buffers()
    bus.send(addr,string)
    
def getfromarx(nchar=80):
    print ("simulated response")
    resp = bus.read(nchar)
    return (resp)


"""
useful utilities
"""
"""checkack - validates that first character is ACK
"""
def checkack(string):
    if len(string)<1:
        print("string zero length")
        return False
    if ord(string[0]) == 6:
        return True
    print("first char not ACK")
    return False

"""hextoint - checks validity too
"""
def hextoint(string):
    total = 0
    for c in string:
        cidx = "0123456789ABCDEF".find(c)
        if cidx == -1:
            print("invalid character %s in string %s"%(c,string))
            # should probably throw an exception here
        else:
            total = total * 16 + cidx
    return total

"""
commands and response handlers
See ARX ICD for more info
"""

"""
ECHO  reply with a copy of the argument string.

syntax:
<a>ECHO<anystring><CR>

<anystring> is a sequence of up to 58 printable ASCII characters other than <CR>.

response:
<ACK><anystring><CR>

This command should never fail.
"""

def echo(texttoecho,addr=None):
    print("echo called")
    print(texttoecho)
    sendtoarx(addr,"ECHO"+texttoecho)    

    resp=getfromarx(nchar=80)
    checkack(resp)
    print(resp)
    return(resp)

"""
ARXN  reply with the serial number of the ARX board

syntax:
<a>ARXN<CR>

response:
<ACK>hh<CR>

hh is two HEX digits representing the serial number (00 to FF).

This commmand should never fail.
"""

def arxn(addr=None):
    sendtoarx(addr,"ARXN")
    resp = getfromarx(4)
    checkack(resp)
    if len(resp)>=3:
        serno = hextoint(resp[1:3])
        print ("Serial number: %d"%serno)
    else:
        print("ARXN response too short")
    
    
""" initialization code
set up bus
"""


#ser = serial.Serial('dev/ttyUSB0',timeout=0.1)

bus = arx485('bus','/dev/ttyUSB0')
