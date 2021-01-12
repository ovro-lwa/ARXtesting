#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
arx commands

Created on Wed Jul  8 11:05:18 2020
using arxCommandDictionary from L. D'Addario as a guide

modified 20 Jul to make a class that can remember default address, etc.
modified 10 Aug to change analog translations
                use 6 bit field for attenuator and bit reverse
                Temperature is internally calibrated by processor
                Power and current now print EU values too.
modified 20210108 LRD: Fix reversal of SETA and SETS.

@author: jimlux
"""
import time  
import datetime
import arx
import numpy as np
from xlrd import open_workbook
import sys


class translateanalog():

    def __init__(self,filename="analogChannelCodes.xls"):
        self.chans=[]
        self.pins=[]
        self.names=[]
        self.convs=[]
        wb= open_workbook(filename)
        for sheet in wb.sheets():
            print(sheet.name)
            if sheet.name =="chanSel":
                #print("loading channel names")
                for row in range(0,10):
                    v = sheet.cell_value(row,0)
                    #print(v)
                    if v=='binary':
                        #print("found binary at row %d"%row)

                        newfmt = not("ARX" in sheet.cell_value(row,4))

                        break
                if row>8:
                    print("Excel file does not appear to be correctly formatted")
                    return
                #nchans = sheet.nrows-row-1
                #print ("%d channels defined")
                for row in range(row+1,sheet.nrows):
                    r = sheet.row_values(row)
                    #print(r)
                    n = int(r[1])
                    pin = r[3]
                    if newfmt:
                        conv=r[4]
                        sig = r[5]+":"+r[6]+":"+r[7]
                    else:
                        conv=""
                        sig = r[4]+":"+r[5]+":"+r[6]
                    self.chans.append(n)
                    self.pins.append(pin)
                    self.names.append(sig)
                    self.convs.append(conv)
            if sheet.name == 'reading':
                #print("TODO:extract coefficients")
                self.LSB = 4.0000       #TODO: find this in the spreadsheet
                self.Vgnd = 100
                self.Vddbeta= 4750
                self.tempcal = -3484
                
    def dump(self):
        print(self.chans)
        print(self.pins)
        print(self.convs)
        print(self.names)
        
    def name(self,channel):
        
        try:
            idx = self.chans.index(channel)
        except ValueError:

            return("Unknown channel")

        return (self.names[idx])

    """ series of functions to translate a value in range 0-4095 into
        engineering units.
    """

    def mV(self,DN):
        return(DN*self.LSB)
    
    def I1(self,DN):
        return(self.mV(DN)/500.0)
    
    def I2(self,DN):
        return(self.mV(DN)/1000.0)
    
    def P(self,DN):
        return((self.mV(DN)/7.5)**2/50000.)
    
    def R(self,DN):
        if DN==25:
            return(None)
        
        t1 = (self.mV(DN)-self.Vgnd)/self.Vddbeta
        return( 10.0/(1.0/t1-1.0))
        """ might be able to recode a bit...
            flip t1 over, and then it would be 10/(t1-1), saving a divide
        """
        
    def T(self,DN):
        return(float(DN) * 0.1)

""" reverse bits """

def reverse_bit(num):
    result = 0
    while num:
        result = (result << 1) + (num & 1)
        num >>= 1
    return result

def decodechannelconfig(v):
    """
        The configuration number is decoded as follows.
    b0    lowpass filter selection 1=wide, 0=narrow.
    b1    ==b0 for normal operation, !=b0 for signal off.
    b2    highpass filter selection, 1=wide, 0=narrow.
    b3:8  first attenuator setting, 0:0.5:31.5 dB.
    b9:14 second attenuator setting, 0:0.5:31.5 dB.
    b15   input DC power (0=off, 1=on).


    """
    print ("Decode channel config")
    lowpass = v & 1
    sigon = (v & 2)>>1 == lowpass
    hipass = v & 4
    att1 = reverse_bit((v>>3) & 0x3F)
    att2 = reverse_bit((v>>8) & 0x3F)
    
    dcpwr = v & 0x80
    configstring = "ON" if dcpwr else "OFF"
    configstring += ", "
    configstring += "ATN2: %d"%att2 + " %4.1f"%(att2*0.5)
    configstring += ", "
    configstring += "ATN1: %d"%att1 + " %4.1f"%(att1*0.5)
    configstring += ", "
    configstring += "LP:" +"off" if not sigon else ("wide" if lowpass else "narrow")
    configstring += " "
    configstring += "HP:"+("wide" if hipass else "narrow")
    
    #print ("lowpass:",lowpass)
    #print ("sigoff:",sigoff)
    #print ("hipass:", hipass)
    #print ("att1:",att1)
    #print("att2:",att2)
    #print ("dcpwr:",dcpwr)
    #print (configstring)
    return(configstring)


def bintohex(n):
    """ returns hex digit corresponding to number from 0-15"""
    if n<0 or n>15:
        print("invalid number to convert")
        return("0")
    return("0123456789ABCDEF"[n])


class arxcmd():

    def __init__(self,addr=None,bus=None,dneu="analogChannelCodes-modLux.xls"):
        if addr:
            self.addr = addr
        if bus:
            self.bus = bus
        self.t = translateanalog(dneu)
        self.errorfile = sys.stderr
        self.human = sys.stdout
        self.outfile = None
    
    def setAddr(self,addr):
        self.addr = addr
        
    def setBus(self,bus):
        self.bus = bus
        
    def setHumanOutput(self,outputfile=None):
        self.human=outputfile
        
    def setFileOutput(self,outputfile=None):
        self.outfile=outputfile
        
    def setErrorOutput(self,errorfile=None):
        self.errorfile = errorfile
        
    def debugprint(self,*args,**kwargs):
        print(*args, file=self.errorfile, **kwargs)
    
    def sendtoarx(self,string):

        self.debugprint("send to arx %x,"%self.addr)
        for c in string:
            self.debugprint(" %x"%ord(c))
        self.bus.clear_buffers()
        self.bus.send(self.addr,string)
    
    def getfromarx(self,nchars=80):
        resp = self.bus.read(nchars)
        self.debugprint(resp)
        return (resp)
    
    def sendarxrecv(self,string,nchars=80):
        self.debugprint("sendarxrecv:",self.addr,string)
        self.bus.send(self.addr,string)
        r = self.bus.receive(nchars)
        self.debugprint("receive",r)
        return(r)    
        
    
    
    
    def echo(self,anystring):
        """
        ECHO  reply with a copy of the argument string.
        
        syntax:
        <a>ECHO<anystring><CR>
        
        <anystring> is a sequence of up to 58 printable ASCII characters other than <CR>.
        
        response:
        <ACK><anystring><CR>
        
        This command should never fail.
        """
        if len(anystring)>58:
            print ("string too long, max 58: %d"%len(anystring))
            return(False)
        r=self.sendarxrecv('ECHO'+anystring,len(anystring)+9)
        tf,r = arx.checkack(r)
        if tf:
            print ("ECHO returns:",r[1:])
        return(tf)
    
    def arxn(self):
        """
        ARXN  reply with the serial number of the ARX board
        
        syntax:
        <a>ARXN<CR>
        
        response:
        <ACK>hh<CR>
        
        hh is two HEX digits representing the serial number (00 to FF).
        
        This commmand should never fail.
        """
        r= self.sendarxrecv('ARXN',nchars=7)
        n=-1
        tf,r=arx.checkack(r)
        if tf:
            s = r[1:3]
            n = arx.hextoint(s)
            print("ARX serial number %d %s"%(n,s))
        return(n)
    
    
    def anlg(self,channel):
        """
        ANLG  reply with 16b digitized voltage from a specified analog channel
        
        syntax:
        <a>ANLGhh<CR>
        
        hh is the desired microcontroller analog channel number in hex (2 digits, 0-255).
        (See separate list of valid channel numbers.)
        
        response:
        <ACK>hhhh<CR>
        
        hhhh is the 16b value in HEX (4 digits).
        
        failure:
        <NAK>31<CR>
        
        Invalid channel number.
        """
        r= self.sendarxrecv('ANLG'+"%02X"%channel)
        tf,r=arx.checkack(r)
        n=-1
        if tf:
            
            s = r[1:5]
            n = arx.hextoint(s)
    
            print("Chan:%d DN:%d %6.0f mV"%(channel,n,self.t.mV(n)))
        return(n)
    
    
    def comm(self,newaddr,config=None):
        """
        COMM   set RS485 address and baud rate
        
        syntax:
        <a>COMMa[<B>]<CR>
        
        where a is a single ASCII character (anything other than NULL=0)
              B is a 4-digit hex number giving an unsigned 16b value (optional).
        The RS485 address is set to 0x80+a, so that future commands must start with that value to be recognized.  The baud rate is set to 16*B.  If the second argument is absent, the baud rate is unchanged.
        
        CAUTION:  No check is made of the reasonableness of the arguments.
        
        response:
        <ACK><CR>
        
        This command cannot fail, but giving unreasonable arguments may make future communication impossible until the processor is reset.  Normally this command is used only in the laboratory for inital setup of the board.
        """
        if config:
            cmd = "COMM"+chr(newaddr)+"%04X"%config
        else:
            cmd = "COMM"+chr(newaddr)
        print("DEBUG, Comm command:%s"%cmd)
        
        #r = self.sendarxrecv(cmd)
        #tf,r=arx.checkack(r)
        #return(tf)
        return(True)
    
    def gtim(self):
        r= self.sendarxrecv('GTIM')
        tf,r=arx.checkack(r)
        if tf:
            if len(r)<10:
                print("response to GTIM too short 10 expected, %d received: %s"%(len(r),r))
                return -1
            if len(r)>10:
                print("response to GTIM too long 10 expected, %d received: %s"%(len(r),r))
                return -1
            n  = arx.hextoint(r[1:9])
            print("time returned: %d %s"%(n,
                    datetime.datetime.utcfromtimestamp(n).strftime('%Y-%m-%d %H:%M:%S')))
            return n
        
          
    def stim(self,newtime=None):
        """
        GTIM   get time (seconds)
        STIM   set time (seconds)
        
        syntax:
        <a>GTIM<CR>
        <a>STIMhhhhhhhh<CR>
        
        response:
        <ACK>hhhhhhhh<CR>  (GTIM)
        <ACK><CR>          (STIM)
        
        where hhhhhhhh is 8 hex digits giving a 32b unsigned number.  This is the
        integer part of the internal clock and is incremented once per second. 
        For GTIM, the value is returned in the response.  For STIM, the fractional
        part of the internal clock is cleared and the integer part is set to the
        given number.  It is recommended that the value be Unix time,
        seconds since Jan 0 1970.
        
        These commands cannot fail, but if fewer than 8 hex digits are given
        for STIM then the clock is set to an unpredictable value.
        
        If no parameter is provided, the current system time is used.
        
        """
        if not newtime:
            newtime = int(time.time())
        if newtime<0:
            """    current time is 5f06 188d, so high bit not set. """
            print("negative time is not allowed: %d"%newtime)
            return(False)
        #print(newtime)
        r= self.sendarxrecv("STIM%08X"%newtime)
        tf,r=arx.checkack(r)
        return(tf)
        
    def last(self):
        """
        LAST    return a copy of last valid command received
        
        syntax:
        <a>LAST<CR>
        
        response:
        <ACK>tttttttt<string>CR>
        
        where 
        tttttttt is a 32b unsigned integer as 8 hex digits giving the time on the board's clock at which the last valid command was received (see GTIM, STIM); and
        <string> is the entire content of the last valid command, excluding only the final <CR>, so it can be up to 63 characters long.  It includes the address byte <a> from that command with its MSB cleared; this allows distinguishing a broadcast command (a=0x80) from an individual-board command.  If there was no previous valid command (e.g., if LAST was the first valid command after a power cycle or reset) then <string> is empty and the time is zero.
        
        This command can be used to verify that a broadcast command was actually received, since the broadcast provides no acknowledgment.
        """
        r=self.sendarxrecv('LAST')
        print("LAST",r)
        tf,r=arx.checkack(r)
        if len(r)<11:
            print("response too short")
            return(False)
        if tf:
            t1 = r[1:9]
            last=r[9:]
            n  = arx.hextoint(t1)
            try:
                print("time returned: %d %s"%(n,
                        datetime.datetime.utcfromtimestamp(n).strftime('%Y-%m-%d %H:%M:%S')))
            except:
                print("problem with decoding date code")
            print("last cmd:%s"%last)
            
    def setc(self,channel,config):
        """
        SETC      configure one signal channel to given value
        
        syntax:
        <a>SETCnvvvv<CR>
        
        where n is the channel number within this board as one hex digit (0:F);
              vvvv is the 16b configuration number of the channel, as 4 hex digits.
        
        The configuration number is decoded as follows.
        b0    lowpass filter selection 1=wide, 0=narrow.
        b1    =b0 for normal operation, !=b0 for signal off.
        b2    highpass filter selection, 1=wide, 0=narrow.
        b3:7  first attenuator setting, 0:0.5:31.5 dB.
        b8:15 second attenuator setting, 0:0.5:31.5 dB.
        
        response:
        <ACK><CR>    Success.
        <NAK>31<CR>  The number of argument characters was not 5.
        """
        if channel<0 or channel>15:
            print ("invalid channel number %d"%channel)
            return(False)
        if config<0 or config>0xffff:
            print("invalid config %04X"%config)
            return(False)
        r=self.sendarxrecv('SETC'+"%01X%04X"%(channel,config))
        tf,r=arx.checkack(r)
        return(tf)

    def getc(self,channel):
        """
        GETC      return the configuration of one signal channel

        syntax:
        <a>GETCn<CR>
        
        where n is the channel number within this board as one hex digit (0:F);
        
        response:
        <ACK>vvvv<CR>    Success.  See SETC command for decoding of vvvv.
        <NAK>31<CR>  Invalid argument
        <NAK>32<CR>  Channel number out of range
        <NAK>33<CR>  I2C bus timeout
        <NAK>34<CR>  I2C bus slave failed to acknowledge
        
                Parameters
                ----------
                channel : TYPE
                    DESCRIPTION.
        
                Returns
                -------
                None.

        """
        if channel<0 or channel>15:
            print ("invalid channel number %d"%channel)
            return([])
        r=self.sendarxrecv('GETC'+"%01X"%channel)
        templist = []
        tf,r=arx.checkack(r)
        if tf:
            
            s = r[1:5]
            n = arx.hextoint(s)
            templist.append(n)
            sdecode=decodechannelconfig(n)
            print("%d %s %s"%(n,s,sdecode))
        return(templist)

    
    def sets(self,config):
        """
        SETS     configure all signal channels to the same given value
        
        syntax:
        <a>SETAvvvv<CR>
        
        where vvvv is the 16b configuration number (same meaning as in SETC).  The same configuration is  applied to all 16 channels of the board.  If this command is broadcast, all channels of the entire array are set to the same configuration.
        
        response:
        <ACK><CR>    Success.
        <NAK>31<CR>  The number of argument characters was not 4.
        """
        r=self.sendarxrecv('SETS'+"%04X"%(config))
        tf,r=arx.checkack(r)
        return(tf)


    def geta(self):
        """
        GETA      return configurations of all channels
        
        syntax:
        <a>GETA<CR>
        
        response:
        <ACK>vvvv....vvvv<CR>
        where the response string is 48 characters long, in 16 fields of 4-digit hex values, where each is the 16b configuration number of one channel, starting with channel 0.  Decoding is the same as for SETC.
        
        This command cannot fail.
        """
        r=self.sendarxrecv('GETA')
        templist = []
        tf,r=arx.checkack(r)
        if tf:
                
            for i in range(16):
                if i*4+4+1 > len(r):
                    print ("response too short at channel %d"%i)
                    break
                s = r[i*4+1:i*4+4+1]
                n = arx.hextoint(s)
                templist.append(n)
                sdecode=decodechannelconfig(n)
                print("%d %s %s"%(n,s,sdecode))
            
        return(templist)


    
    def seta(self,configs):
        """
        SETA     configure all signal channels to different given values
        
        syntax:
        <a>SETSvvvv...vvvv<CR>
        
        where the argument string is 48 characters in 16 fields of 4 each, giving the configuration numbers for each of the 16 channels of the board, starting with channel 0.  Each configuration number has the same meaning as in SETC.
        
        response:
        <ACK><CR>    Success.
        <NAK>31<CR>  The number of argument characters was not 48.
        
        TODO: maybe this should be an array of config?
        """
        if len(configs) != 16:
            print ("must be an array or list of 16 configuration values")
            return(False)
        cc = ""
        for c in configs:
            cc += "%04X"%c
            
        r=self.sendarxrecv('SETA'+cc)
        tf,r=arx.checkack(r)
        return(tf)

    
    def load(self):
        """
        LOAD       configure all signal channels to previously stored settings
        
        syntax:
        <a>LOAD<CR>
        
        Read the configuration numbers for all 16 channels from on-board non-volatile memory and configure all channels accordingly.  This command can be broadcast.
        
        response:
        <ACK><CR>
        
        This command cannot fail.
        """
        r= self.sendarxrecv('LOAD')
    
        tf,r=arx.checkack(r)
        if tf:
            print("loaded")
    
    def save(self):
        """
        SAVE      save settings of all signal channels
        
        syntax:
        <a>SAVE<CR>
        
        Write the current configuration numbers of all channels to on-board non-volatile memory.  This command can be broadcast.  These values will be automatically loaded at the next power cycle or reset.
        
        response:
        <ACK><CR>
        
        This command cannot fail.
        """
        r= self.sendarxrecv('SAVE')
    
        tf,r=arx.checkack(r)
        if tf:
            print("saved")
    
    
    
    def powc(self,channel):
        """
        POWC    return total power at output of given chnanel
        
        syntax:
        <a>POWCn<CR>
        where n is the channel number as one hex digit.
        
        response:
        <ACK>vvvv<CR>
        where vvvv is a 16b unsigned integer as 4 hex digits, proportional to the
        total power at the ouput of channel n.  See separate documentaion on
        converting the number to power units.
        
        This command cannot fail.
        """
        if channel<0 or channel>16:
            print("invalid channel number %d"%channel)
            return([])
        r= self.sendarxrecv('POWC'+bintohex(channel))
        powerlist = []
        tf,r=arx.checkack(r)
        if tf:
            
            s = r[1:5]
            n = arx.hextoint(s)
            powerlist.append(n)
            print("%d %5.2f (DN:%d)"%(channel,self.t.P(n),n))

        return(powerlist)
    
    def powa(self):
        """
        POWA     return total power at output of all channels
        
        syntax:
        <a>POWA<CR>
        
        response:
        <ACK>vvvv....vvvv<CR>
        where the response string is 48 characters long, in 16 fields of 4-digit
        hex values, where each is a 16b unsigned integer proportional to the total
        power at the output of one channel, starting with channel 0.
        
        This command cannot fail.
        """
        r= self.sendarxrecv('POWA')
        powerlist = []
        tf,r=arx.checkack(r)
        if tf:
            print ("chan pwr string")
            for i in range(16):
                if i*4+4+1 > len(r):
                    print("Response too short at channel %d"%i)
                    break
                s = r[i*4+1:i*4+4+1]
                n = arx.hextoint(s)
                powerlist.append(n)
                print("%d %5.2f (DN:%d)"%(i,self.t.P(n),n))
        
        return(powerlist)
    
    def curc(self,channel):
        """
        CURC      return FE or PD current for given channel
        
        syntax:
        <a>CURCn<CR>
        where n is the channel number as one hex digit.
        
        response:
        <ACK>vvvv<CR>
        where vvvv is a 16b unsigned integer as 4 hex digits, proportional to the DC current at the input of channel n.  For coax-connected antennas, this is the current drawn by the FEE; a value of 4095 corresponds to 500 mA.  For fiber-connected antnnas, this is the photodiode current at the ARX board; 4095 corresponds to 5 mA.  This current comes from the external 15V power supply.
        
        This command cannot fail.
        """
        if channel<0 or channel>15:
            print("invalid channel number %d"%channel)
            return([])
        r= self.sendarxrecv('CURC'+bintohex(channel))
        currlist = []
        tf,r=arx.checkack(r)
        if tf:
            
            s = r[1:5]
            n = arx.hextoint(s)
            currlist.append(n)
            print("chan: %d %f5.2 A (DN:%d)"%(channel,self.t.I1(n),n))
        return(currlist)

    
    def cura(self):
        """
        CURA       return FE or PD current for all channels
        
        syntax:
        <a>CURA<CR>
        
        response:
        <ACK>vvvv....vvvv<CR>
        where the response string is 48 characters long, in 16 fields of 4-digit hex values, where each is a 16b unsigned integer proportional to the current at the input of one channel, starting with channel 0.  Scaling is the same as for CURC.
        
        This command cannot fail.
        """
        r= self.sendarxrecv('CURA')
        currlist = []
        tf,r=arx.checkack(r)

        if tf:
            
            for i in range(16):
                if i*4+4+1 > len(r):
                    print("Response too short at channel %d"%i)
                    break
                s = r[i*4+1:i*4+4+1]
                n = arx.hextoint(s)
                currlist.append(n)
                print("chan: %d %5.2f A (DN:%d)"%(i,self.t.I1(s),n))

        return(currlist)
    
    def curb(self):
        """
        CURB       return dc current drawn by circuitry on this ARX board
        
        syntax:
        <a>CURB<CR>
        
        response:
        <ACK>vvvvCR>
        where vvvv is a 16b unsigned number as 4 hex digits, proportional the total DC current drawn by circuitry on this ARX board.  A value of 4096 corresponds to 10A.  This current comes from the external 6V power supply, regulated to 5V on the board.
        """
        r= self.sendarxrecv('CURB')
        currlist = []
        tf,r=arx.checkack(r)
        if tf:
            
            s = r[1:5]
            n = arx.hextoint(s)
            currlist.append(n)
            print("Board %5.2f A (DN:%d)"%(self.t.I2(n),n))
        return(currlist)
    
    
    def temp(self):
        """
        TEMP        return processor's chip temperature
        
        syntax:
        <a>TEMP<CR>
        
        response:
        <a>vvvv<CR>
        where vvvv is a 16b unsigned integer as 4 hex digits, representing the internal chip temperature of the microcontroller on the board.  See separate documentation on converting this number to temperature units.
        """
        r= self.sendarxrecv('TEMP')
        templist = []
        tf,r=arx.checkack(r)
        if tf:
            
            s = r[1:5]
            n = arx.hextoint(s)
            templist.append(n)
            print("%d %f"%(n,self.t.T(n)))
        return(templist)
    
    
if __name__ == "__main__":
    print("arxcmds main")
    t=translateanalog("analogChannelCodes-modLux.xls")
    t.dump()
    print("------------")
    print(t.name(1))
    print(t.name(2))
    print(t.name(99))
    print(t.name(63))
    
    print("------")
    print(" test conversions ")
    print("DN hex mV I1 I2 P R T ")
    for testcase in ("0	0000	0	0	0	0	-0.206185567	",
                    "21	0540	84	0.168	0.084	0.0025088	-0.033571129	#NUM!",
                    "25	0640	100	0.2	0.1	0.003555556	#DIV/0!	#DIV/0!",
                    "26	0680	104	0.208	0.104	0.003845689	0.00842815	483.15",
                    "256	4000	1024	2.048	1.024	0.372827022	2.415	66.2712827",    
                    "530	8480	2120	4.24	2.12	1.598008889	7.399	32.89",
                    "750	BB80	3000	6	3	3.2	15.676	13.96",
                    "1011	FCC0	4044	8.088	4.044	5.8147328	48.933	-10.67",
                    "1023	FFC0	4092	8.184	4.092	5.9535872		"):
                    
        DN = int(testcase.split()[0])
        print(testcase.split())
        print(DN,"%04x"%(DN*0x40),t.mV(DN),t.I1(DN),t.I2(DN),t.P(DN),t.R(DN),t.T(DN))
        print()
        
    