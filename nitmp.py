import numpy as np
import nidaqmx
from nidaqmx import stream_writers # Required (!?)
from nidaqmx import stream_readers # Required (!?)

def doWriteRead(out, fs):
    """ Synchron output and aquisition """
    nTotal = len(out)
    with nidaqmx.Task() as taskI, nidaqmx.Task() as taskO:
        # Configure out Channel
        taskO.ao_channels.add_ao_voltage_chan("Dev2/ao0")
        taskO.out_stream.regen_mode = nidaqmx.constants.RegenerationMode.DONT_ALLOW_REGENERATION
        taskO.timing.cfg_samp_clk_timing(rate=fs,
                                         sample_mode = nidaqmx.constants.AcquisitionType.FINITE,
                                         samps_per_chan=nTotal)
        # Configure In Channels
        taskI.ai_channels.add_ai_voltage_chan("PXI1Slot4_2/ai%i"%0)
        taskI.ai_channels.add_ai_voltage_chan("PXI1Slot4_2/ai%i"%1)
        taskI.ai_channels.add_ai_voltage_chan("PXI1Slot4_2/ai%i"%2)
        taskI.timing.cfg_samp_clk_timing(rate=fs,
                                         sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
                                         samps_per_chan=nTotal)
        # create writter and reader
        writer = nidaqmx.stream_writers.AnalogSingleChannelWriter(taskO.out_stream, auto_start=False)
        reader = nidaqmx.stream_readers.AnalogMultiChannelReader(taskI.in_stream)
        writer.write_many_sample(out)
        # Start
        taskI.start()
        taskO.start()
        data = np.zeros((3, nTotal))
        # Aquire data
        reader.read_many_sample(data, nidaqmx.constants.READ_ALL_AVAILABLE, timeout=(1+nTotal/fs))
    return data

out = np.linspace(0,1,1000)
fs = 2000

data = doWriteRead(out, fs)
print(data.shape)