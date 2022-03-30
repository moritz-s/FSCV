import time
import tables as tb
import numpy as np
import threading

try:
    import nidaqmx
    from nidaqmx.constants import AcquisitionType
    REAL_DATA = True
except ModuleNotFoundError:
    # If nidaqmx is not installed, random data is generated
    REAL_DATA = False


class NIGrabber:
    def __init__(self,
                 complevel = 5,
                 expectedrows = 500,
                 samples_per_scan = 1000,
                 rate = 100e3,
                 filename = 'datafile.h5',
                 ):

        self.samples_per_scan = samples_per_scan
        self.rate = rate
        self.last_data = None
        self.n_scans_acquired = 0
        self.running = False

        self.fileh = tb.open_file(filename, mode='w')
        # Array for timestanps
        self.array_ts = self.fileh.create_earray(self.fileh.root,
                                                 'array_ts',
                                                 tb.FloatAtom(),
                                                 (1, 0),
                                                 "Times",
                                                 expectedrows=expectedrows)

        # Array for signal
        filters = tb.Filters(complevel=complevel, complib='blosc')
        self.array_scans = self.fileh.create_earray(self.fileh.root,
                                                    'array_scans',
                                                    tb.FloatAtom(),
                                                    (self.samples_per_scan, 0),
                                                    "Scans", filters=filters,
                                                    expectedrows=expectedrows)
        # Array for command voltage
        self.array_command = self.fileh.create_earray(self.fileh.root,
                                                      'array_command',
                                                      tb.FloatAtom(),
                                                      (self.samples_per_scan, 0),
                                                      "Command",
                                                      filters=filters,
                                                      expectedrows=expectedrows)

    def callback(self, task_handle, every_n_samples_event_type,
                number_of_samples, callback_data):

        if REAL_DATA:
            data = np.array(self.task.read(number_of_samples_per_channel=self.samples_per_scan))
        else:
            data = np.random.normal(size=(2, self.samples_per_scan))

        # For access by gui thread
        self.last_data = data

        if not self.running:
            return 0

        # Append new data to data storage
        self.array_ts.append(np.array([time.time()])[np.newaxis])
        self.array_command.append(data[0][:, np.newaxis])
        self.array_scans.append(data[1][:, np.newaxis])

        self.n_scans_acquired += 1

        t_now = time.perf_counter()

        if self.n_scans_acquired > 1:
            self.delta_t = t_now - self.lastUpdate

        if self.n_scans_acquired == 2:
               self.delta_t_max = self.delta_t
               self.delta_t_min = self.delta_t
        elif self.n_scans_acquired > 2:
            if self.delta_t > self.delta_t_max:
               self.delta_t_max = self.delta_t
            if self.delta_t < self.delta_t_min:
               self.delta_t_min = self.delta_t

        self.lastUpdate = t_now

        #print('callback. ', self.n_scans_acquired)
        return 0

    def start_grabbing(self):
        self.running = True
        self.n_scans_acquired = 0

        if REAL_DATA:
            self.task = nidaqmx.Task()

            min_val = -10
            max_val = 10
            self.task.ai_channels.add_ai_voltage_chan("PXI1Slot4_2/ai0:1", min_val=min_val, max_val=max_val)

            #self.task.timing.cfg_samp_clk_timing(1000, sample_mode=AcquisitionType.CONTINUOUS)
            self.task.timing.cfg_samp_clk_timing(rate=self.rate,
                                                sample_mode=AcquisitionType.FINITE)

            self.task.register_every_n_samples_acquired_into_buffer_event(
                self.samples_per_scan, self.callback)

            self.task.triggers.start_trigger.cfg_dig_edge_start_trig(
                "/PXI1Slot4_2/PFI0")

            self.task.triggers.start_trigger.retriggerable = True

            self.task.start()
        else:
            class phantom_data_task:
                """Single use phantom data generator."""
                def __init__(self, callback_function, acuisition_period_sec=0.1):
                    self.callback_function = callback_function
                    self.acuisition_period_sec = acuisition_period_sec
                    self.generate = True

                def acquire_random_data(self):
                    """ This  continously calls the callback function """
                    while self.generate:
                        time.sleep(self.acuisition_period_sec)
                        if self.generate:
                            self.callback_function(None, None, None, None)

                def close(self):
                    """ Stop calling the callback function """
                    self.generate=False

            task_phantom = phantom_data_task(callback_function=self.callback,
                                             acuisition_period_sec=self.samples_per_scan/self.rate)

            phantom_thread = threading.Thread(target=task_phantom.acquire_random_data)
            phantom_thread.start()
            self.task = task_phantom

    def stop_grab(self):
        self.task.close()
        self.running = False
        time.sleep(0.005)
        self.fileh.flush()
        self.fileh.close()
        print('saved: ', self.fileh.filename)

class MyGui:
    def __init__(self, grabber):
        self.grabber = grabber

    def doMeasurement(self):
        for i in range(3):
            print('Gui update', self.grabber.n_scans_acquired)
            time.sleep(1)

        print(self.grabber.delta_t_min)
        print(self.grabber.delta_t)
        print(self.grabber.delta_t_max)

        self.grabber.stop_grab()

if __name__ == '__main__':
    grabber = NIGrabber()
    grab_thread = threading.Thread(target=grabber.start_grabbing)
    grab_thread.start()

    my_gui = MyGui(grabber)
    gui_thread = threading.Thread(target=my_gui.doMeasurement)
    gui_thread.start()
