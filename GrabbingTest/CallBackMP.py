import time
import threading
import nidaqmx
from nidaqmx.constants import AcquisitionType


class NIGrabber:
    def __init__(self):
        self.samples = []

    def grab(self):
        #with nidaqmx.Task() as task:
        self.task = task = nidaqmx.Task()
        if 1:
            task.ai_channels.add_ai_voltage_chan("PXI1Slot4_2/ai0")

            #task.timing.cfg_samp_clk_timing(1000, sample_mode=AcquisitionType.CONTINUOUS)
            task.timing.cfg_samp_clk_timing(1000, sample_mode=AcquisitionType.FINITE)

            #samples = []

            def callback(task_handle, every_n_samples_event_type,
                         number_of_samples, callback_data):
                print('Every N Samples callback invoked.')

                self.samples.extend(task.read(number_of_samples_per_channel=1000))

                return 0

            task.register_every_n_samples_acquired_into_buffer_event(
                1000, callback)

            task.triggers.start_trigger.cfg_dig_edge_start_trig(
                "/PXI1Slot4_2/PFI0")

            task.triggers.start_trigger.retriggerable = True

            task.start()

            #input('Running task. Press Enter to stop and see number of '
            #      'accumulated samples.\n')

            #print(len(self.samples))

    def stopgrab(self):
        print('stoooped')
        self.task.close()
        #self.task.stop()
        print('OK')

class MyGui:
    def __init__(self, grabber):
        self.grabber = grabber

    def doMeasurement(self):
        for i in range(3):
            print(len(self.grabber.samples))
            time.sleep(1)
        self.grabber.stopgrab()

grabber = NIGrabber()
grab_thread = threading.Thread(target=grabber.grab)
grab_thread.start()

for i in range(3):
    print(len(grabber.samples))
    time.sleep(1)
grabber.stopgrab()

#my_gui = MyGui(grabber)
#gui_thread = threading.Thread(target=my_gui.doMeasurement)
#gui_thread.start()

#grabber.grab()