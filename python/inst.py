import pyvisa
import numpy

class Instrument:
    __rm = pyvisa.ResourceManager()
    def __init__(self, address, termination='\n'):
        self.inst = self.__rm.open_resource(address, write_termination=termination)
        self.inst.timeout = 900000 # 900 seconds
        print("Initialized " + self.inst.query("*IDN?"))
    
    def opc(self):
        return self.inst.query("*OPC?")

    # need some more methods here for sending and receiving different types of data

class NoiseFigure_8970B(Instrument):
    """Note that this instrument predates SCPI, and so there will be some oddities for controlling it."""
    """HPIB code summary on page 3-47 and on. """
    def __init__(self, address):
        super(NoiseFigure_8970B, self).__init__(address, '\r\n')

    k = 1.380649e-23

    avg_factor = {
        1 : 'F0',
        2 : 'F1',
        4 : 'F2',
        8 : 'F3', 
        16: 'F4',
        32: 'F5',
        64: 'F6',
        128:'F7',
        256:'F8',
        512:'F9'
    }

    # sets the RF input gain. The key '20 10 0' referres to the RF attenuator settings of +20dB, +10dB, and 0dB. See 3-69 for details. 
    input_gain = {
        '20 10 0'     : 'C0',
        '10 0 -10'    : 'C1',
        '0 -10 -20'   : 'C2',
        '-10 -20 -30' : 'C3'
    }

    def set_frequency(self, f):
        """frequency should be in MHz only."""
        self.inst.write('FR ' + str(f))

    def set_start_stop(self, fstart, fstop, fstep=100):
        """Sets the start, stop and step of the frequency sweep. Frequency should be in MHz only."""
        self.inst.write('FA ' + str(fstart) + ' EN FB ' + str(fstop) + ' EN')
        self.inst.write('SS ' + str(fstep) + ' EN')

    def set_avg_factor(self, factor):
        """factor: should be smooth code found from the avg_factor dictionary"""
        self.inst.write(factor)

    def set_input_gain(self, gain):
        """Only use this funciton if you get an error code like E22. If there is a large amount of gain external to
        the analyzer, E22 may be thrown. If this happens, try a lower setting like 10_0_n10."""
        self.inst.write(gain)

    def start_cal(self, fstart, fstop, fstep):
        """In order to calibrate, you have to send the CA command then manually trigger each measurement... because reasons... This function is not sufficient
        for calibrating in measurement modes 1.6-1.9."""
        self.inst.write('H2')
        self.inst.write('T1')
        self.set_start_stop(fstart, fstop, fstep)
        # self.inst.write('FA ' + str(fstart) + ' EN FB ' + str(fstop) + ' EN')
        # self.inst.write('SS ' + str(fstep) + ' EN')
        self.inst.write('Q2')
        self.inst.write('RS')

        self.inst.write('CA')

        # now trigger the measurement until all frequencies have been calibrated
        print('F (Hz)\tGkB\tTem')
        while (True):
            s = self.inst.query('T2')
            print(s, end='')

            # the first 2 bits are the important ones. bit 0 is the data ready bit, and bit 1 is the noise figure meter calibration complete.
            sb = self.inst.read_stb()
            # print('{0:b}'.format(sb))
            if sb & 2 == 2: # calibration complete bit
                break

        # now set to free run
        self.inst.write('T0')

    def meas_gain_nf(self, freq):
        """Measures the corrected gain and noise figure at the measurment frequency. Sets the output selection to be frequency, insertion gain, and noise figure."""
        self.set_frequency(freq)
        
        return [float(f) for f in self.inst.query('H1 EN M2').split(',')]

    """ 
    For controlling the system LO (for measurement mode e.g. 1.1 and others) you need to make sure the code is compatable with the synthesizer
    being used. See manual 3-220 through 3-221. 

    """

    """Detailed calibration starts on 3-59"""

    """Table of error messages starts on 3-95."""

    def meas_temp(self, freq, source_on=True, calibrated=True):
        """See section 3-200. This returns the CALIBRATED power density relative to 290K (-174dBm/Hz).
        If source_on, then the 28V output is set to on, off if false. This function returns the temperature."""
        self.set_frequency(freq)

        # set a status bit to trigger when data is complete
        self.inst.write('Q1')

        if source_on:
            if calibrated:
                f, _, db = (float(f) for f in self.inst.query('H1 EN N8').split(',')) # noise source on, calibrated
            else: 
                f, _, db = (float(f) for f in self.inst.query('H1 EN N6').split(',')) # noise source on, uncalibrated

        else:
            if calibrated:
                f, _, db = (float(f) for f in self.inst.query('H1 EN N7').split(',')) # noise source off, calibrated
            else:
                f, _, db = (float(f) for f in self.inst.query('H1 EN N5').split(',')) # noise source off, uncalibrated

        return (f, 290*numpy.power(10, db/10))


    def meas_power_density(self, source_on=True):
        return self.meas_temp(source_on)*self.k

    def load_enr(self, enr_pairs):
        """See the manual pages 3-87 to see ENR programming."""
        # iterate over the frequency ENR pairs in enr_pairs and program them into the meter
        # clear the ENR table and enter ENR programming mode
        self.inst.write('ND') # resets the ENR table to default values
        self.inst.write('NR')
        for r in enr_pairs:
            f = r[0]; enr = r[1]
            self.inst.write(str(f) + ' EN ' + str(enr) + ' EN') # the EN codes here literally mean the "enter" key, so enter frequency, then enter ENR, just as you would on the front panel
        self.inst.write('FR')


class PSA_E4448A(Instrument):
    """ 
    Instrument noise figure manual: https://www.keysight.com/us/en/assets/9018-02592/user-manuals/9018-02592.pdf?success=true 
    """
    def __init__(self, address):
        super(PSA_E4448A, self).__init__(address)

        # set the format and byte order of the data
        self.inst.write(':FORMAT:BORDER NORMAL; :FORMAT:DATA:REAL,32')
        # disable continuous acquisition mode
        self.inst.write(':INITIATE:CONTINUOUS OFF')

    def init_nf_meas(self, avg=1):
        cmd = ''
        if avg > 1: 
            cmd += ':SENSE:NFIGURE:AVERAGE:STATE ON;:SENSE:NFIGURE:AVERAGE:COUNT ' + str(avg) + ';'
        else:
            cmd += ':SENSE:NFIGURE:AVERAGE:STATE OFF;'
        
        cmd += ':INITIATE:NFIG'
        self.inst.write(cmd)
        print('[Started] noise figure measurement')
        self.inst.query('*OPC?')
        print('[Finished] noise figure measurement')

    def __strlist2numpy(self, s):
        return numpy.asarray([float(f) for f in s.split(',')])

    def get_noise_figure(self):
        """Returns the frequency [Hz], gain [dB], and noise figure [dB]"""
        # For most noise figure measurement, the only things that are actually needed are the noise factor, and gain. 

        # despite being programmed in the binary format, the noise figure data comes out as ASCII
        fstart = float(self.inst.query(':SENSE:NFIGURE:FREQUENCY:START?'))
        fstop = float(self.inst.query(':SENSE:NFIGURE:FREQUENCY:STOP?'))
        # """This function returns 13 measurements."""
        # use the :FETCH:NFIGURE command

        # Reutnrs the following (from manual)
        # Returns the following scalar results, in order.
        # 1. Tcold scalar value
        # tcold = self.__strlist2numpy(self.inst.query(":FETCH:NFIGURE:ARRAY:DATA:TCOLD?"))
        # tcold = self.inst.query(":FETCH:NFIGURE:ARRAY:DATA:TCOLD?")

        # 2. Corrected scalar result for Noise Figure
        corrected_noise_figure = self.__strlist2numpy(self.inst.query(":FETCH:NFIGURE:ARRAY:DATA:CORRECTED:NFIGURE?"))
        # 3. Corrected scalar result for Noise Factor
        # corrected_noise_factor = self.inst.query(":FETCH:NFIGURE:ARRAY:DATA:CORRECTED:NFACTOR?")
        # 4. Corrected scalar result for Gain
        corrected_gain = self.__strlist2numpy(self.inst.query(":FETCH:NFIGURE:ARRAY:DATA:CORRECTED:GAIN?"))
        # 5. Corrected scalar result for Effective Temperature
        # corrected_effective_temperature = self.inst.query(":FETCH:NFIGURE:ARRAY:DATA:CORRECTED:TEFFECTIVE?")
        # 6. Corrected scalar result for Hot Power Density
        # corrected_hot_power_density = self.inst.query(":FETCH:NFIGURE:ARRAY:DATA:CORRECTED:PHOT?")
        # 7. Corrected scalar result for Cold Power Density
        # corrected_cold_power_density = self.inst.query(":FETCH:NFIGURE:ARRAY:DATA:CORRECTED:PCOLD?")

        # 8. Uncorrected scalar result for Noise Figure
        uncorrected_noise_figure = self.__strlist2numpy(self.inst.query(":FETCH:NFIGURE:ARRAY:DATA:UNCORRECTED:NFIGURE?"))
        # 9. Uncorrected scalar result for Noise Factor
        # uncorrected_noise_factor = self.inst.query(":FETCH:NFIGURE:ARRAY:DATA:UNCORRECTED:NFACTOR?")
        # 10. Uncorrected scalar result for Gain (apparently this doesn't have its own SCPI command to fetch, the following line doesn't work )
        # uncorrected_gain = self.inst.query(":FETCH:NFIGURE:ARRAY:DATA:UNCORRECTED:GAIN?")
        # 11. Uncorrected scalar result for Effective Temperature
        # uncorrected_effective_temperature = self.inst.query(":FETCH:NFIGURE:ARRAY:DATA:UNCORRECTED:TEFFECTIVE?")
        # 12. Uncorrected scalar result for Hot Power Density
        # uncorrected_hot_power_density = self.inst.query(":FETCH:NFIGURE:ARRAY:DATA:UNCORRECTED:PHOT?")
        # 13. Uncorrected scalar result for Cold Power Density
        # uncorrected_cold_power_density = self.inst.query(":FETCH:NFIGURE:ARRAY:DATA:UNCORRECTED:PCOLD?")

        # data = tcold, corrected_noise_figure, corrected_noise_factor, corrected_gain, corrected_effective_temperature, corrected_hot_power_density, corrected_cold_power_density, uncorrected_noise_figure, uncorrected_noise_factor, uncorrected_gain, uncorrected_effective_temperature, uncorrected_hot_power_density, uncorrected_cold_power_density

        # data = tcold, corrected_noise_figure, corrected_noise_factor, corrected_gain, corrected_effective_temperature, corrected_hot_power_density, corrected_cold_power_density, uncorrected_noise_figure, uncorrected_noise_factor, uncorrected_effective_temperature, uncorrected_hot_power_density, uncorrected_cold_power_density
        # print(len(corrected_gain))
        f = numpy.linspace(fstart, fstop, len(corrected_gain))
        return f, corrected_gain, corrected_noise_figure, uncorrected_noise_figure


class MULTI_METER_34401A(Instrument):
    def __init__(self, address):
        super(MULTI_METER_34401A, self).__init__(address)

    # def set_nplcycles(self, NPLCycles=100):
    #     self.inst.write('VOLT:DC:NPLCycles ' + str(NPLCycles))

    def get_meas_vdc(self, meter_range='DEF', resolution='DEF'):
        """meter range and resolution can be either MIN MAX or DEF"""
        return float(self.inst.query('MEAS:VOLT:DC? ' + meter_range + ',' + resolution))
    


class POWER_METER_N1913A(Instrument):
    """User Guide: https://www.keysight.com/us/en/assets/9018-02514/programming-guides/9018-02514.pdf?success=true"""
    def __init__(self, address):
        super(POWER_METER_N1913A, self).__init__(address)

    def set_zero(self, channel):
        if channel == 1 or channel == 2:
            self.inst.write('CALibration' + str(channel) + ':AUTO ONCE')
        else:
            raise ValueError("Channel " + str(channel) + " is out of bounds.")
    
    def set_init_cont(self, state):
        if type(state) is bool or type(state) is int:
            state = int(state)
            if state == 0:
                state = 'OFF'
            else:
                state = 'ON'

        self.inst.write('INITiate:CONTinuous ' + state) 


    def get_power(self, channel):
        if channel == 1 or channel == 2:
            return float(self.inst.query('READ' + str(channel) + ':POW:AC?'))
        else:
            raise ValueError("Channel " + str(channel) + " is out of bounds.")



class SYNTH_83620A(Instrument):
    """User Guide: https://www.keysight.com/us/en/assets/9018-01018/user-manuals/9018-01018.pdf?success=true"""
    def __init__(self, address):
        super(SYNTH_83620A, self).__init__(address)

    def set_cw_freq(self, frequency, units='GHZ'):
        """frequency: frequency given in 'units'"""
        self.inst.write('FREQuency:CW ' + str(frequency) + ' ' + units)
    
    def set_power(self, power, units='DBM'):
        self.inst.write('POWER:LEVEL ' + str(power) + ' ' + units)

    # def set_correction_flatness(self, frequency, power):
        # hstack the arrays, it is assumed that frequency and power are just linear arrays
        # correction_array = numpy.vstack((frequency, power)).T
        # print(numpy.ndarray.flatten(correction_array))
        # self.inst.write_ascii_values('CORRection:FLATness ', numpy.ndarray.flatten(correction_array).tolist())

    def set_correction_on(self, state):
        if type(state) is bool or type(state) is int:
            state = int(state)
            if state == 0:
                state = 'OFF'
            else:
                state = 'ON'

        self.inst.write('CORRection:STATe ' + state) 

    def set_rf_on(self, state):
        if type(state) is bool or type(state) is int:
            state = int(state)
            if state == 0:
                state = 'OFF'
            else:
                state = 'ON'

        self.inst.write('POWER:STATE ' + state)

class AWG_33250A(Instrument):
    """User Guide: https://www.keysight.com/us/en/assets/9018-03925/user-manuals/9018-03925.pdf?success=true quick command reference: https://www.keysight.com/us/en/assets/9018-40986/reference-guides/9018-40986.pdf?success=true"""
    def __init__(self, address):
        super(AWG_33250A, self).__init__(address)

    # phase locking commands
    def set_phase(self, phase):
        """Sets the phase offset for phase locking. Can either be a numeral, or MIN or MAX. In either degrees or radians depending on the units being used (UNIT:ANGLE?)."""
        if type(phase) is float or type(phase) is int:
            phase = str(phase)
        
        self.inst.write('PHASE ' + phase)


    def set_burst_cycles(self, cycles='INFINITY'):
        if type(cycles) is int:
            cycles = str(cycles)

        self.inst.write('BURST:NCYCLES ' + cycles)

    def set_burst(self, state):
        """Enable or disable burst state. Either ON or OFF, or 1, 0 or True False."""
        if type(state) is bool or type(state) is int:
            state = int(state)
            if state == 0:
                state = 'OFF'
            else:
                state = 'ON'

        self.inst.write('BURST:STATE ' + state)

    def set_burst_mode(self, mode):
        """Mode can be either TRIGGERED, GATED"""
        self.inst.write('BURST:MODE ' + mode)

    def trigger(self):
        self.inst.write('TRIG')

    def set_trigger_out(self, state, slope='POS'):
        """state can be either ON, OFF, 1, 0, or True, False. Slope must be either POSITIVE or NEGATIVE"""
        if type(state) is not str:
            state = int(state)
            if state == 1:
                state = 'ON'
            else:
                state = 'OFF'

        self.inst.write('OUTP:TRIG ' + state)
        self.inst.write('OUTP:TRIG:SLOP ' + slope)

    def set_trigger_source(self, source):
        """Source can be either BUS, IMMEDIATE, EXTERNAL"""
        self.inst.write('TRIG:SOUR ' + source)

    def set_output_state(self, state):
        """ON or OFF, or 1 or 0, or True, False"""
        if type(state) is bool or type(state) is int:
            if int(state) == 1:
                state = 'ON'
            else:
                state = 'OFF'
        
        self.inst.write('OUTP ' + state)

    def set_output_impedance(self, imped=50):
        """Sets the output load for the signal generator. Set the impedance in Ohms, or use INF for HIGHZ."""
        if type(imped) is str:
            self.inst.write('OUTP:LOAD ' + imped)
        else:
            self.inst.write("OUTP:LOAD " + str(imped))
    
    def get_output_impedance(self):
        return self.inst.query('OUTP:LOAD?')

    def set_function(self, func):
        """Sets the function of the AWG, valid funcs are SINUSOID, SQUARE, RAMP, PULSE, NOISE, DC, USER"""
        self.inst.write('FUNC ' + func)

    def get_function(self):
        self.inst.query('FUNC?')

    def __set_voltage_freq_hl(self, freq, lowvalue, highvalue):
        self.inst.write('VOLT:LOW '  + str(lowvalue))
        self.inst.write('VOLT:HIGH ' + str(highvalue))
        self.inst.write('FREQ ' + str(freq))
    
    def __set_voltage_freq_a(self, freq, amplitude, offset):
        self.inst.write('VOLT:OFFS '  + str(offset))
        self.inst.write('VOLT ' + str(amplitude))
        self.inst.write('FREQ ' + str(freq))

    def square_hl(self, freq=1e3, lowvalue=0, highvalue=3.3, duty=50):
        self.set_function('SQUARE')
        self.__set_voltage_freq_hl(freq=freq, lowvalue=lowvalue, highvalue=highvalue)    
        self.inst.write('FUNC:SQU:DCYC ' + str(duty))

    def square_a(self, freq=1e3, amplitude=1, offset=0, duty=50):
        self.set_function('SQUARE')
        self.__set_voltage_freq_a(freq=freq, amplitude=amplitude, offset=offset)
        self.inst.write('FUNC:SQU:DCYC ' + str(duty))

    def sine_a(self, freq=1e3, amplitude=1, offset=0):
        self.set_function('SINUSOIDE')
        self.__set_voltage_freq_a(freq=freq, amplitude=amplitude, offset=offset)

class DC_E3649A(Instrument):
    def __init__(self, address):
        super(DC_E3649A, self).__init__(address)
        self.set_supply_output(0)
    
    def set_channel(self, channel):
        """channel: which output to use sohuld be either OUT1 or OUT2"""
        self.inst.write('INST:SEL ' + channel)

    def set_supply_voltage(self, voltage, channel):
        self.set_channel(channel)
        self.inst.write('VOLT ' + str(voltage))

    def meas_supply_voltage(self, channel):
        self.set_channel(channel)
        return float(self.inst.query('MEAS:VOLT:DC?'))
    
    def meas_supply_current(self, channel):
        self.set_channel(channel)
        return float(self.inst.query('MEAS:CURR:DC?'))

    # state is either 0 (off) or 1 (on)
    def set_supply_output(self, state):
        self.inst.write('OUTP:STAT ' + str(state))


class DC_6033A(Instrument):
    def __init__(self, address):
        super(DC_6033A, self).__init__(address)
        self.set_supply_voltage(0)
    
    def set_supply_voltage(self, voltage):
        self.inst.write('VSET ' + str(voltage))

    def set_supply_current(self, current):
        self.inst.write('ISET ' + str(current))

    # state is either 0 (off) or 1 (on)
    # def set_supply_output(self, state):
        # self.inst.write('OUT ' + str(state)) 

class PNA_E8364B(Instrument):
    """Programmers Reference: https://www.testworld.com/wp-content/uploads/user-guide-help-agilent-e8362b-e8363b-e8364b-e8361a-n5230a-n5242a-pna-series-microwave-network-analyzers.pdf"""
    # SCIP starts on 1873

    def __init__(self, address):
        super(PNA_E8364B, self).__init__(address)
        # set the PNA returned data measurement format (pg. 2000)
        self.inst.write("FORM:BORD NORM") # byte order, not sure what normal means
        self.inst.write("FORM REAL,64")
        # self.inst.write("FORM ASCII,0")

        # setup averaging (pg. 2017)
        self.inst.write("INIT:CONT ON")

        # self.avg_count = 128

        # self.inst.write("SENS:AVER:COUNT " + str(self.avg_count))
        self.inst.write("SENS:AVER:STAT OFF")

        self.inst.write("DISP:ARR QUAD")
        
        # delete measurements (pg. 1954)
        self.inst.write("CALC:PAR:DEL:ALL")

        # init measurement (pg. 1951)
        self.inst.write("CALC:PAR:DEF 'CH1_S11',S11")
        self.inst.write("DISP:WIND1:TRAC1:FEED 'CH1_S11'")
        self.inst.write("CALC:PAR:DEF 'CH1_S21',S21")
        self.inst.write("DISP:WIND3:TRAC1:FEED 'CH1_S21'")
        self.inst.write("CALC:PAR:DEF 'CH1_S22',S22")
        self.inst.write("DISP:WIND4:TRAC1:FEED 'CH1_S22'")
        self.inst.write("CALC:PAR:DEF 'CH1_S12',S12")
        self.inst.write("DISP:WIND2:TRAC1:FEED 'CH1_S12'")

    def get_start_stop(self):
        start = float(self.inst.query("SENS:FREQ:START?"))
        stop = float(self.inst.query("SENS:FREQ:STOP?"))

        # points = len(stop)

        # (pg 2181)
        # points = int(self.inst.query("SENS:GCS:SWE:FREQ:POIN?"))
        # print(points)

        return start, stop
        # return numpy.linspace(start, stop, points)

    def get_data(self, param):
        """param selects which parameters (e.g. S11, S21, etc..)"""

        # set the measurement selection (pg. 1950)
        self.inst.write("CALC:PAR:SEL 'CH1_"+param+"'")

        # start a sweep (pg. 2002)
        # turn off continous sweep, then start a new one
        self.inst.write("INIT:CONT OFF")
        
        # i = 0
        # for i in range(0, self.avg_count):
        self.inst.write("ABORT;INITIATE:IMMEDIATE")
        self.inst.query("*WAI;*OPC?")

        # get complex data from PNA (pg. 1889)
        data = self.inst.query_binary_values("CALC:DATA? SDATA", datatype='d', container=numpy.array, is_big_endian=True)
        real = data[0::2]
        imag = data[1::2]
        s = real + 1j*imag

        points = len(real)
        start, stop = self.get_start_stop()
        f = numpy.linspace(start, stop, points)

        return s, f

class DSOX_OScope(Instrument):
    """Programmers Reference: https://www.keysight.com/us/en/assets/9018-06894/programming-guides/9018-06894.pdf"""

    def __init__(self, address):
        super(DSOX_OScope, self).__init__(address)

    # Root Commands
    def opc(self):
        return self.inst.query("*OPC?")

    def is_running(self):
        """Returns the running state of the oscilloscope. If running, returns True, False otherwise."""

        running = int(self.inst.query(":OPER:EVEN?")) & 8
        return True if running == 1 else False
    
    def run(self):
        self.inst.write(':RUN')

    def single(self):
        self.inst.write(':SING')

    def digitize(self, source, opt):
        """Starts an acquisition cycle according to the settings defined by :ACQuire commands, then stops the instrument. The instrument will block commands until the digitize cycle is complete. Can be checked by waiting for a '1' from opc."""
        
        digstr = ":DIG "

        if type(source) is list:
            # expect opt to also be a list of the same length
            if type(source) is not list:
                raise TypeError("digitize expected a list of options.")
            if len(source) != len(opt):
                raise IndexError("digitize source length must match options length.")
            
            for i in range(0, len(source)):
                s = source[i]
                o = opt[i]

                if s == 'CHAN':
                    if i != 0:
                        digstr += ','
                    digstr += s + str(o)
                    
                else:
                    raise ValueError("Source " + source + " has not been implemented.")
                    
        else:
            if source == "CHAN":
                digstr += source + str(opt)
            else:
                raise ValueError("Source " + source + " has not been implemented.")

        self.inst.write(digstr)

    # Channel Commands
    def set_coupling(self, channel, coupling):
        """Sets the channel coupling to either AC or DC. Channel should be an integer"""
        self.inst.write(':CHANNEL' + str(channel) + ':COUPLING ' + coupling)
    
    def set_scale_offset(self, channel, full_scale, offset=0):
        """Sets the channel scale and offset. Channel should be an integer. Offset and scale in volts. Scale is the full scale range."""
        self.inst.write(':CHANNEL' + str(channel) + ':RANGE ' + str(full_scale))
        self.inst.write(':CHANNEL' + str(channel) + ':OFFSET ' + str(offset))

    def autoscale(self):
        self.inst.write(':AUTOSCALE')

    # Trigger Commands
    def set_trigger_mode(self, mode, opt=0):
        """Sets the trigger mode. Most common is edge. There are several, see pg. 922 of reference manual."""
        
        if mode == 'SBUS':
            self.inst.write(':TRIGGER:MODE ' + mode + str(opt))
        else:
            self.inst.write(':TRIGGER:MODE ' + mode)

    # def set_trigger_level_auto(self):
        # """Automatically sets the trigger level """

    def set_trigger_edge(self, level, slope='POSITIVE', coupling='DC'):
        """Sets the trigger edge, level, slope and coupling. Slope can be either POSitive, NEGative, EITHer, ALTerate."""
        self.inst.write(':TRIGGER:EDGE:SLOPE ' + slope)
        self.inst.write(':TRIGGER:EDGE:COUPLING ' + coupling)
        self.inst.write(':TRIGGER:EDGE:LEVEL ' + str(level))

    def set_trigger_edge_source(self, source, opt=0):
        """Sets the trigger edge source. Can be CH, DIG, EXT, LINE, WGEN."""

        s = ':TRIGGER:EDGE:SOURCE ' + source
        if source == 'CH':
            s += str(opt)
        elif source == 'DIG':
            raise ValueError("Source " + source + " has not been implemented.")
        
        self.inst.write(s)



    # Timebase Commands
    def set_timebase_mode(self, mode):
        """Sets the timebase mode. Either MAIN, WINDOW, XY, or ROLL."""
        self.inst.write(':TIMEBASE:MODE ' + mode)
    
    def set_timebase_range_position(self, range, position=0):
        """Sets the timebase full scale range and position (offset/delay) in seconds."""
        self.inst.write('TIMEBASE:POSITION ' + str(position))
        self.inst.write('TIMEBASE:RANGE ' + str(range))

    # Acquire Commands (See page 241 of programmers reference)
    def set_acquire_count(self, count):
        """Sets how many acquisistions to take before stopping. count should be an integer from 2-65536."""
        self.inst.write(":ACQ:COUN " + str(count))
    
    def get_acquire_count(self):
        return self.inst.query(":ACQ:COUN?")

    def get_acquire_points(self):
        return int(self.inst.query(":ACQ:POIN?"))

    def get_acquire_sample_rate(self):
        return float(self.inst.query(":ACQ:SRAT?"))

    def set_acquire_type(self, acqtype):
        """Sets the acquisition type to one of 4 strings: NORMal, AVERage, HRESolution, PEAK"""
        self.inst.write(":ACQ:TYPE " + acqtype)

    def get_acquire_type(self):
        return self.inst.query(":ACQ:TYPE?")

    def set_acquire_mode(self, mode):
        "Sets the acquisition fode. Either realtime (RTIMe) or segmented (SEGMented)"
        self.inst.write(":ACQUIRE:MODE " + mode)

    def get_acquire_mode(self):
        return self.inst.query(":ACQUIRE:MODE?")

    # Segmented Commands
    def set_segmented_count(self, count):
        """count: the number of segments to acquire (50 max usually)"""
        if count > 1000:
            raise ValueError("Segmented Count " + count + " is > 1000.")
        else:
            self.inst.write(":WAVEFORM:SEGMENTED:COUNT " + str(int(count)))

    def set_segmented_index(self, index):
        if index > 1000:
            raise ValueError("Segment index " + index + " is > 1000.")
        else:
            self.inst.write(":ACQUIRE:SEGMENTED:INDEX " + str(index))
    
    def get_segmented_index(self):
        return self.inst.query(int(":ACQUIRE:SEGMENTED:INDEX?"))

    def get_segmented_count(self):
        return int(self.inst.query(":WAVEFORM:SEGMENTED:COUNT?"))


    # AWG commands
    def set_awg_freq(self, freq=1e3):
        """Sets the frequency of the AWG. freq in Hz."""
        self.inst.write(":WGEN:FREQ " + str(freq))

    def set_awg_func(self, func, opt):
        """Sets the function to use for the AWG. func is a string and can be SINusoid SQUare RAMP PULSe DC NOISe SINC EXPRise EXPFall CARDiac GAUSsian ARBitrary"""
        self.inst.write(":WGEN:FUNCTION " + func)

        if func == "SQUARE":
            # opt should be the duty cycle from 0-100%
            self.inst.write(":WGEN:FUNCTION:SQUARE:DCYCLE " + str(opt))
        elif func == "RAMP":
            # opt should be the ramp symmetry in 0-100%
            self.inst.write(":WGEN:FUNCTION:RAMP:SYMMETRY " + str(opt))
        elif func == "PULSE":
            # opt should be the pulse width in seconds
            self.inst.write(":WGEN:FUNCTION:PULSE:WIDTH " + str(opt))

    def set_awg_low_high(self, low=0, high=3.3):
        """Sets the AWG funciton high and low levels"""
        self.inst.write(":WGEN:VOLTAGE:LOW " + str(low))
        self.inst.write(":WGEN:VOLTAGE:HIGH " + str(high))

    def set_awg_output(self, state):
        """Enables or disables the AWG output. state should be either 1 or 0 or ON or OFF"""
        if type(state) is not str:
            state = int(state)
            if state == 1:
                state = 'ON'
            else:
                state = 'OFF'

        self.inst.write(":WGEN:OUTPUT " + str(state))

    # measurement commands (See page 417 of programmers reference)
    def __start_measure(self, s):
        self.inst.write(":MEAS:" + s)

    def __get_measure(self, s):
        # measurements should be in NR3 (floating point) format, not sure if they are returned as strings or binary
        return float(self.inst.query(":MEAS:" + s + "?"))
    
    def init_meas_amplitude(self, source, opt):
        """Configures an amplitude measurement. See page 482 of programmers guide."""
        
        s = "VAMP " + source
        if source == "CHAN":
            self.__start_measure(s + str(opt))
        else:
            raise ValueError("Source " + source + " has not been implemented.")
                
    def read_meas_amplitdue(self):
        return self.__get_measure("VAMP")

    def init_meas_vpp(self, source, opt):
        s = "VPP" + source
        if source == "CHAN":
            self.__start_measure(s + str(opt))
        else:
            raise ValueError("Source " + source + " has not been implemented.")
        
    def read_meas_vpp(self):
        return self.__get_measure("VPP")



    # Download waveform
    def set_source(self, source, opt):

        s = ":WAV:SOUR " + source
        if source == "CHAN":
            self.inst.write(s + str(opt))
        else:
            raise ValueError("Source " + source + " has not been implemented.")

    def __parse_preamble(self, preamble):
        values = [float(i) for i in preamble.split(',')]

        return tuple(values)

    def get_waveform(self, source, opt):
        self.set_source(source, opt)

        # configure waveform format
        self.inst.write(":WAV:BYT LSBF")
        self.inst.write(":WAV:UNS 0")
        self.inst.write(":WAV:FORM WORD")

        # start with the waveform preamble so that the time base and voltages can be confiugred
        _, _, points, _, xinc, xorigin, xref, yinc, yorigin, yref = self.__parse_preamble(self.inst.query(":WAV:PRE?"))

        # now read the data
        data = self.inst.query_binary_values(":WAV:DATA?", datatype='h', is_big_endian=False, container=numpy.array)

        # print(data)

        # values of 0x00 or 0x0000 are holes, which is where data hasn't been acquired
        # 0x01 or 0x0100 — Clipped low. These are locations where the waveform is clipped at the bottom of the oscilloscope display
        # 0xFF or 0xFF00 — Clipped high. These are locations where the waveform is clipped at the top of the oscilloscope display.

        # check for clipped high or clipped low
        clipped = False
        if numpy.any(data, where=0xFF) or numpy.any(data, where=0xFF00) or numpy.any(data, where=0x01) or numpy.any(data, where=0x0100):
            clipped=True

        # converted_data = (data - data[int(yref)]) * yinc + yorigin
        converted_data = (data) * yinc + yorigin

        xpoints = numpy.arange(0, points)
        time_values     = xorigin + xpoints*xinc

        return time_values, converted_data, clipped
    
    