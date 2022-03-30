import time
import tables as tb
import numpy as np
import threading
import nidaqmx
from nidaqmx.constants import AcquisitionType


class NIGrabber:
    def __init__(self,
                 complevel = 5,
                 expectedrows = 500,
                 samples_per_scan = 1000,
                 rate = 1000,
                 filename = 'datafile.h5',
                 ):

        self.samples_per_scan = samples_per_scan
        self.rate = rate
        self.fileh = tb.open_file(filename, mode='w')

        # Array that holds timestanps for each scan
        self.array_ts = self.fileh.create_earray(self.fileh.root,
                                                 'array_ts',
                                                 tb.FloatAtom(),
                                                 (1, 0),
                                                 "Times",
                                                 expectedrows=expectedrows)

        # Recorded preamp output
        filters = tb.Filters(complevel=complevel, complib='blosc')
        self.array_scans = self.fileh.create_earray(self.fileh.root,
                                                    'array_scans',
                                                    tb.FloatAtom(),
                                                    (self.samples_per_scan, 0),
                                                    "Scans", filters=filters,
                                                    expectedrows=expectedrows)
        # Recorded command voltage
        self.array_command = self.fileh.create_earray(self.fileh.root,
                                                      'array_command',
                                                      tb.FloatAtom(),
                                                      (self.samples_per_scan, 0),
                                                      "Command",
                                                      filters=filters,
                                                      expectedrows=expectedrows)

    def start_grab(self):
        self.task = nidaqmx.Task()

        self.task.ai_channels.add_ai_voltage_chan("PXI1Slot4_2/ai0:1")

        #self.task.timing.cfg_samp_clk_timing(1000, sample_mode=AcquisitionType.CONTINUOUS)
        self.task.timing.cfg_samp_clk_timing(rate=self.rate,
                                             sample_mode=AcquisitionType.FINITE)

        #samples = []

        def callback(task_handle, every_n_samples_event_type,
                     number_of_samples, callback_data):
            print('Every N Samples callback invoked.')

            #self.samples.extend(self.task.read(number_of_samples_per_channel=1000))
            data = np.array(self.task.read(number_of_samples_per_channel=self.samples_per_scan))

            # Append new data to data storage

            self.array_ts.append(np.array([time.time()])[np.newaxis])
            self.array_command.append(data[0][:, np.newaxis])
            self.array_scans.append(data[1][:, np.newaxis])

            return 0

        self.task.register_every_n_samples_acquired_into_buffer_event(
            self.samples_per_scan, callback)

        self.task.triggers.start_trigger.cfg_dig_edge_start_trig(
            "/PXI1Slot4_2/PFI0")

        self.task.triggers.start_trigger.retriggerable = True

        self.task.start()

    def stop_grab(self):
        self.task.close()
        self.fileh.close()
        print(self.fileh.filename)

class MyGui:
    def __init__(self, grabber):
        self.grabber = grabber

    def doMeasurement(self):
        for i in range(5):
            print('Gui', self.grabber.array_ts.shape)
            time.sleep(1)

        self.grabber.stop_grab()

if __name__ == '__main__':
    grabber = NIGrabber()
    grab_thread = threading.Thread(target=grabber.start_grab)
    grab_thread.start()

    my_gui = MyGui(grabber)
    gui_thread = threading.Thread(target=my_gui.doMeasurement)
    gui_thread.start()
