import time
import numpy as np
import nidaqmx
from nidaqmx import stream_writers # Required (!?)
from nidaqmx import stream_readers # Required (!?)

umax = 1.2
umin = -0.4
Tramp = 0.01
Tbase = 0.1
fs = 20000.0

base = np.ones(int(Tbase * fs)) * umin
ramp = np.linspace(umin, umax, int(Tramp * fs))
out = 5.0 * np.hstack([ramp, ramp[::-1], base])
nTotal = len(out)

taskI = nidaqmx.Task()
taskO = nidaqmx.Task()

# Configure out Channel
taskO.ao_channels.add_ao_voltage_chan("Dev2/ao0")
taskO.out_stream.regen_mode = nidaqmx.constants.RegenerationMode.ALLOW_REGENERATION
taskO.timing.cfg_samp_clk_timing(rate=fs,
                                 sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
                                 samps_per_chan=nTotal)
# Configure In Channels
taskI.ai_channels.add_ai_voltage_chan("PXI1Slot4_2/ai%i" % 0)
taskI.ai_channels.add_ai_voltage_chan("PXI1Slot4_2/ai%i" % 1)
taskI.ai_channels.add_ai_voltage_chan("PXI1Slot4_2/ai%i" % 2)
taskI.timing.cfg_samp_clk_timing(rate=fs,
                                 sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
                                 samps_per_chan=nTotal)

# create writer and reader
writer = nidaqmx.stream_writers.AnalogSingleChannelWriter(taskO.out_stream, auto_start=False)
writer.write_many_sample(out)
reader = nidaqmx.stream_readers.AnalogMultiChannelReader(taskI.in_stream)

try:
    for i in range(10):
        # Start
        taskI.start()
        taskO.start()

        # Acquire data
        data = np.zeros((3, nTotal))

        time.sleep(0.05)
        reader.read_many_sample(data, nidaqmx.constants.READ_ALL_AVAILABLE, timeout=((2+nTotal) / fs))
        print('Ok', data.max())
        time.sleep(0.005)

        # Start
        taskI.stop()
        taskO.stop()
finally:
    # Stop
    taskI.close()
    taskO.close()
