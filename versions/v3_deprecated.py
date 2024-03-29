'''
Note that this code produces an inverted wave correctly but the output is
delayed as the indexing used is incorrect and this function is now deprecated.
Use v3.py instead as the correct u_storage is used.
'''

import sys
import signal
import os
import jack
import threading
import numpy as np
from numba import jit, njit
import numba
from scipy.io import wavfile as wf

class Version3:
    def __init__(self, taps, chunk):
        self.order = taps
        self.chunk = chunk
        self.h     = np.zeros(self.order)
        self.mics  = np.array([np.zeros(self.chunk, dtype=np.float32),
                                np.zeros(self.chunk, dtype=np.float32)])
        self.chans = 2
        self.rate  = 44100

        self.u = np.zeros(self.chunk, dtype=np.float32)
        self.d = np.zeros(self.chunk, dtype=np.float32)
        self.res_u = np.zeros(self.order, dtype=np.float32)
        self.res_d = np.zeros(self.order, dtype=np.float32)
################################################################
        self.u_rec = np.zeros(10*self.rate, dtype=np.float32)
        self.d_rec = np.zeros(10*self.rate, dtype=np.float32)
        self.index=0
################################################################
        self.init = True


    def process(self, frames):
        assert len(self.client.inports) == len(self.client.outports)
        assert frames == self.client.blocksize
        count =0
        for i in (self.client.inports):
            self.mics[count] = np.frombuffer(i.get_buffer(), dtype=np.float32)
            count+=1
        if (self.init):
            # Padded with zeros which wont get processed the first time
            self.init = False
            self.u[:self.chunk-self.order] = self.mics[0][:self.chunk-self.order]
            self.d[:self.chunk-self.order] = self.mics[1][:self.chunk-self.order]
        else:
            # After first time, filled with residual then current values then no space for padding
            self.u[:self.order] = np.array([i for i in self.res_u])
            self.u[self.order:] = self.mics[0][:self.chunk-self.order]
            self.d[:self.order] = np.array([j for j in self.res_d])
            self.d[self.order:] = self.mics[1][:self.chunk-self.order]

        self.res_u[:] = np.array([i for i in self.mics[0][self.chunk-self.order:]])
        self.res_d[:] = np.array([i for i in self.mics[1][self.chunk-self.order:]])

        self.u_rec[self.index:self.index+self.chunk] = np.array([i for i in self.u])
        self.d_rec[self.index:self.index+self.chunk] = np.array([i for i in self.d])

        self.index = self.index+self.chunk
        output=self.u
        for o in (self.client.outports):
            o.get_buffer()[:] = output.tobytes()
            output=self.d


    def shutdown(self, status, reason):
        print('JACK shutdown!')
        print('status:', status)
        print('reason:', reason)
        self.event.set()

    def begin(self):
        clientname = 'v3'
        servername = None
        self.client = jack.Client(clientname, servername=servername)
        self.client.set_process_callback(self.process)
        self.client.set_shutdown_callback(self.shutdown)
        if self.client.status.server_started:
            print('JACK server started')
        if self.client.status.name_not_unique:
            print('unique name {0!r} assigned'.format(client.name))

        self.event = threading.Event()

        # create two port pairs
        for number in 1, 2:
            self.client.inports.register('input_{0}'.format(number))
            self.client.outports.register('output_{0}'.format(number))


        with self.client:
        # When entering this with-statement, client.activate() is called.
        # This tells the JACK server that we are ready to roll.
        # Our process() callback will start running now.

            capture = self.client.get_ports(is_physical=True, is_output=True)
            if not capture:
                raise RuntimeError('No physical capture ports')

            for src, dest in zip(capture, self.client.inports):
                self.client.connect(src, dest)

            playback = self.client.get_ports(is_physical=True, is_input=True)
            if not playback:
                raise RuntimeError('No physical playback ports')

            for src, dest in zip(self.client.outports, playback):
                self.client.connect(src, dest)

            print('Press Ctrl+C to stop')
            try:
                self.event.wait()
            except KeyboardInterrupt:
                print('\nInterrupted by user')
                wf.write('U_is_blue.wav', 44100, self.u_rec)
                wf.write('D_is_red.wav', 44100, self.d_rec)
                print("Songs written?")
#________________________________End of Class______________________________#

@jit(nopython=True)
def filter(u, d, order, h):
    # Preparing output
    chunk = 128
    y = np.zeros(chunk, dtype=np.float32)
    # Filtering (This might take too long for a given sample rate)
    out_length = len(u)-order+1
    for n in range(out_length):
        x  = np.flipud(u[n:n+order])
        y[n]   = -1*(x*h).sum()
        e       = d[n+order-1] + y[n]
        h  = h + (1/((x*x).sum()+0.00001)) * x * e
    return h, y

def startCancelling():
    v3 = Version3(taps=32, chunk=128)
    v3.begin()

if __name__=='__main__':
    startCancelling()
