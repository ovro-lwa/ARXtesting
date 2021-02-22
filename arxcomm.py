#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Usage:
  arx [--logfile=<logfile>] [--input=<infile>] [--error=<errorfile>] [--port=<serialPort>]
  
Options:
  -l --logfile=<logfile>      CSV file to write results of commands 
  -i --input=<infile>         File to read commands from
  -e --error=<errorfile>
  -p --port=<serialPortName>  Default: COM4

Created on Wed Jul  8 07:29:31 2020
modified 15 Jul 2020 - jimlux - add wakeup function 
                              - allow both CR and CR/LF and LF as line terminators on responses
         12 Aug 2020 - jimlux - added parameter to !waitsec, allow 0-60 seconds.
	20210107 - LRD:  Changed final else: clause in parsecmd() to handle any command not known 
                         when the preceeding clauses were written.
	20210108 - LRD:  Changed timeout parameter in Serial.serial() call from 0.1 to 1.0.
        20210213 - LRD:  Simplified version, no parsing.

@author: jimlux
"""
import sys
arxmod=sys.modules[__name__]
arxmod.defaultaddress= 0x2
arxmod.currentaddr = arxmod.defaultaddress
debug = False

import serial
#import arxcmds

class arx485:
    """ class to manage a 485 bus connected to arx boards
    opens the serial port and provides methods to send and receive
    
    one can instantiate multiple buses if desired
    
    """
    def __init__(self,name,port):
        self.name = name
        self.serial=None
        try:
            self.serial = serial.Serial(
                port = port,
                baudrate = 19200,
                parity = serial.PARITY_NONE,
                stopbits = serial.STOPBITS_ONE,
                bytesize = serial.EIGHTBITS,
                timeout = 1.0,
                writeTimeout = 0
                )
        except serial.SerialException:
            print("Serial port not found: %s"%port)
        else:
            pass
        #self.clear_buffers()
        #self.incoming_data = ''
        #self.saved_data = []
    
    def send(self,addr,string):
        s = bytearray('\0'+string+chr(13),'utf-8')
        s[0]=addr+0x80       # put the address in.
        n = self.serial.write(s)
        if debug:
            print (s)
            print("%d characters sent"%n)
            
    def receive(self,nchars):
        s = self.serial.read_until(chr(13),nchars) #read until CR=13 or timeout.
        if debug:
            print('%d characters read'%len(s))
        return(s)
    
    def sendrecv(self,addr,string,nchars):
        self.send(addr,string)
        r = self.receive(nchars)
        print(r)
        
    def clear_buffers(self):
        self.serial.flushInput()
        self.serial.flushOutput()
        


    
"""
generic versions, using global variable, bus
"""
   
def sendtoarx(string):

    print("send to arx %x,"%arxmod.currentaddr)
    for c in string:
        print(" %x"%ord(c))
    arxmod.bus.clear_buffers()
    arxmod.bus.send(arxmod.currentaddr,string)
    
def getfromarx(nchars=80):
    print ("simulated response")
    resp = arxmod.bus.read(nchars)
    return (resp)

def sendarxrecv(string,nchars=80):
    arxmod.bus.send(arxmod.currentaddr,string)
    r = arxmod.bus.receive(nchars)
    return(r)


"""===================================================================
useful utilities
"""

def checkack(resparray):
    """checkack - validates that first character is ACK
    Response (success):  <ACK>[<reply>]<CR>
    where
    <ACK> = 0x06 indicates that the command was accepted.
    <reply> can be any ASCII string or the null string, and the detailed syntax is command-dependent. 

    Response (failure):  <NAK><e>[<f>]<CR>
    where
     <NAK>= 0x15 - ASCII NAK
     <e> is a 1-character generic error code with these meanings:
    1  the command code was not recognized and no action was taken;
    2  the command was too long (64 bytes were received and none was <CR>) and no action was taken (characters after the 64th are ignored until the next address byte is received);
    3  the command failed, in which case <f> is a 1-character reason code that is command-dependent.

    """
    """TODO: probably want to create a "dump string as string and hex formatting"
    """
    """ TODO: need to allow for line terminator variability?"""

    
    #print(resparray)
    if len(resparray)<1:
        print("Timeout - String zero length")
        return (False,resparray)
    
    while len(resparray)>0:
        
        if resparray[0] == 6:         #ASCII ACK
            return (True,resparray)
        if resparray[0] == 0x15:      #ASCII NAK
            if len(resparray)<2:
                print("Malformed NAK, only 1 char long")
                return (False,resparray)
         
            if resparray[1] == ord('1'):
                print("Invalid command received by arx")
            elif resparray[1] == ord('2'):
                print("command too long, ignored")
            elif resparray[1] == ord('3'):
                if len(resparray)<3:
                    print("malformed NAK, generic code 3, no remaining characters")
                    return (False,resparray)
                print("Command failed, reason: %s"%chr(resparray[2]))
                if resparray[2] == ord('1'):
                    print ("Invalid argument")
                elif resparray[2] == ord('2'):
                    print ("channel number out of range")
                elif resparray[2] == ord('3'):
                    print("I2C bus timeout")
                elif resparray[2] == ord('4'):
                    print("I2 bus device failed to acknowledge")
                else:
                    print("unknown reason")
            else:
                print("invalid generic error code as first char of NAK %s in string %s"%(resparray[1],resparray))

            return (False,resparray)
        #print("skipping character neither ack nor nak %d"%resparray[0])
        resparray=resparray[1:]
        
    print("no response")
    return (False,resparray)


def hextoint(string):
    """hextoint - checks validity too"""
    total = 0
    #print("hextoint:",string)
    for c in string:
        cidx = "0123456789ABCDEF".find(chr(c))
        if cidx == -1:
            print("invalid character %s in string %s"%(c,string))
            # should probably throw an exception here
        else:
            total = total * 16 + cidx
    return total


def arxhelp():
    print("ARX control utility")
    print("")
    print("# is a comment character, anything after # is ignored")
    print("* indicates the command is to be sent to all ARXes on the bus")
    print("a number on the beginning indicates the ARX address to send the command to")
    print("examples:")    
    print("   ARXN    - sends ARXN command to current default unit")
    print("   * ARXN   - sends ARXN command to address 0x80, the broadcast address")
    print("   21 ARXN  - sends ARXN command to address 0x95 = 0x80 + 0x15")
    print("   0x10 ARXN - sends ARXN command to address 0x90 ")
    print("? prints this help")
    print("!string  sends everything after the bang as a literal string")
    print("non printing characters can be entered as hex with a backslash escape")
    print(" \\x08 is the BEL character")
    
import datetime
from dateutil.parser import parse

    
""" initialization code
set up bus
"""
import os
import time
import sys
import docopt

if __name__ == "__main__":
    opts = docopt.docopt(__doc__)
    print (len(opts))
    print (opts)
    if opts['--error']:
        errfile = open(opts['--error'],'w')
    else:
        errfile = sys.stderr
    if opts['--port']:
        commname = opts['--port']
    else:
        commname = "COM4"

    arxmod.bus = arx485('bus',commname)
    
    if not arxmod.bus.serial:
        print("unable to open 485 interface at",commname)
        sys.exit(1)

    #------MAIN COMMAND LOOP-----#
    echo = True
    while True:
        promptstr = "%d>"%arxmod.currentaddr
        try:
            s = input(promptstr).upper()
        except EOFError:
            print("")
            print("end of input")
            break
        if echo:
            print(s)
        idx=s.find("#")
        if idx>-1:
            s=s[:idx]
        s=s.strip()
        if len(s)==0:
            continue

        # Check for exit or wait
        if s in ['!X', "!!"]:
            break
        if "!WAITSEC" in s:
            ss = s.split()
            if len(ss)>1:
                try:
                    nsec = float(ss[1])
                except ValueError:
                    print("invalid delay %s, using 1 second"%ss[1])
                    nsec = 1.0
                if nsec>60:
                    print ("max 60 second wait, setting to 60 seconds")
                    nsec = 60
                if nsec<0:
                    print ("no negative wait possible, using 1 second")
                    nsec = 1.0
            else:
                nsec = 1.0
            print("pausing %5.2f second"%nsec)
            time.sleep(nsec)
            continue

        # Check for non-default address
        ss = s.split()
        arxmod.currentaddr = arxmod.defaultaddress
        if ss[0][0] in '1234567890':
            try:
                temp = int(ss[0],0)
                ss=ss[1:]
            except ValueError:
                print ("Address field is not a valid number")
                continue
            if temp>128 or temp<0:
                print ("Not a valid address (1-127)")
                continue
            if temp==128 or temp==0:
                print("Setting broadcast. Prefer using *")
            arxmod.currentaddr = temp   
            if len(ss) == 0:  #address change only, no command
                arxmod.defaultaddress=temp
                continue

        # Check for broadcast    
        if ss[0][0] == "*":
            print("Setting broadcast")
            arxmod.currentaddr = 0
            ss=ss[1:]

        if len(ss) ==0:  
            continue

        cmd = ss[0]
        print("Address=",arxmod.currentaddr)
        r=sendarxrecv(cmd)
        #tf,r = checkack(r)
        s = str(r[1:])
        if r[0]==6:
            print("ACK",s)
            continue
        if r[0]==0x15:
            print("NAK",s)
        else:
            print(int(r[0]),s)
        
