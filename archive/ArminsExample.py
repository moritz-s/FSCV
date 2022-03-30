# -*- coding: utf-8 -*-
import nidaqmx
def start_scanning(self):

if self.shared.scanning_configuration_only_scan_test_patterns.value == 0:
    written = int32()

    # move the galvos to the right starting position, so they dont have to fly there from (0,0) and might cause a delay shift
    self.galvo_output = TaskHandle()

    data = np.r_[self.current_waveform.full_x[0] * self.shared.galvo_scanning_pixel_galvo_factor.value,
                 self.current_waveform.full_y[0] * self.shared.galvo_scanning_pixel_galvo_factor.value]
    DAQmxCreateTask("AO", byref(self.galvo_output))
    DAQmxCreateAOVoltageChan(self.galvo_output, "Dev1/ao0:1", "AO", -5.0, 5.0, DAQmx_Val_Volts, "")
    DAQmxWriteAnalogF64(self.galvo_output, 1, 1, 10.0, DAQmx_Val_GroupByChannel, data, byref(written), None)

    DAQmxStopTask(self.galvo_output)
    DAQmxClearTask(self.galvo_output)

    # and sleep a bit to let the galvo settle
    time.sleep(0.1)

    # now start the scanning
    self.galvo_output = TaskHandle()
self.pmt_input = TaskHandle()

DAQmxCreateTask("AI", byref(self.pmt_input))
DAQmxCreateAIVoltageChan(self.pmt_input, "Dev1/ai0:3", "AI", DAQmx_Val_Cfg_Default, float64(-self.shared.galvo_scanning_expected_pmt_signal_range.value),
                         float64(self.shared.galvo_scanning_expected_pmt_signal_range.value), DAQmx_Val_Volts, None)

DAQmxCfgSampClkTiming(self.pmt_input, "", float64(self.shared.galvo_scanning_AIrate.value), DAQmx_Val_Rising, DAQmx_Val_ContSamps,
                      int(self.numScans)) # buffer size is important! play with the factor if overflows occur! However, in generell if the data aquation cannot keep up with that buffer, timing of the 2p images might be off
DAQmxSetAIDataXferMech(self.pmt_input, "Dev1/ai0:3", DAQmx_Val_DMA)  # imporoves buffering problems
"""
Direct Memory Access (DMA)
DMA is a mechanism to transfer data between the device and computer memory without the involvement of the CPU.
This mechanism makes DMA the fastest available data transfer mechanism.
National Instruments uses DMA hardware and software technology to achieve high throughput rates and to increase system utilization.
DMA is the default method of data transfer for DAQ devices that support it.
"""

DAQmxCfgDigEdgeStartTrig(self.pmt_input, "ao/StartTrigger", DAQmx_Val_Rising)

# galvo output
data = np.r_[self.current_waveform.full_x * self.shared.galvo_scanning_pixel_galvo_factor.value,
             self.current_waveform.full_y * self.shared.galvo_scanning_pixel_galvo_factor.value]

DAQmxCreateTask("AO", byref(self.galvo_output))

DAQmxCreateAOVoltageChan(self.galvo_output, "Dev1/ao0:1", "AO", -5.0, 5.0, DAQmx_Val_Volts, "")
DAQmxCfgSampClkTiming(self.galvo_output, "", float64(self.shared.galvo_scanning_AOrate.value), DAQmx_Val_Rising,
                      DAQmx_Val_ContSamps, int(self.numPixels))
DAQmxWriteAnalogF64(self.galvo_output, int(self.numPixels), 0, 10.0, DAQmx_Val_GroupByChannel, data,
                    byref(written), None)

# needed?
#DAQmxSetAIDataXferMech(self.galvo_output, "Dev1/ao0:1", DAQmx_Val_DMA)


# open the uniblitz shuttter

#self.shutter_handle = TaskHandle()
#DAQmxCreateTask("Shutter", byref(self.shutter_handle))
#DAQmxCreateDOChan(self.shutter_handle, "Dev1/port0/line0", "", DAQmx_Val_ChanForAllLines)

if self.shared.laser_configuration_manual_shutter_override.value == 0:
    data = np.ones(1).astype(np.uint8)
    DAQmxWriteDigitalU8(self.shutter_handle, 1, 1, 10, DAQmx_Val_GroupByChannel, data, byref(written), None)
#DAQmxStartTask(self.shutter_handle) # can we couple this to the galvo thing?

# start the galvos and the scanning
DAQmxStartTask(self.pmt_input)
DAQmxStartTask(self.galvo_output)

self.shared.currently_scanning.value = 1

# Then read
DAQmxReadAnalogF64(self.pmt_input, int(self.numScans), 30.0, DAQmx_Val_GroupByChannel, self.pmt_buffer_data, int(4 * self.numScans), byref(read), None)
