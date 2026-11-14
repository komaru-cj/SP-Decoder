import numpy as np
import time
import numexpr as ne

from cora.demod.BaseDemodulator import BaseDemodulator

class BaselineDemodulator(BaseDemodulator):
    name = "BaselineDemodulator"

    def demodulate(self, Pream_ind_stack_base, capture,Peak_amp_base,FFO_base, indexes, upsampling_factor, bin_offsets, num_data_sym):
        SF = self.SF
        N = int(2**SF)
        Rx_Buffer_Base = capture.arr

        # LORA pkt variables
        num_preamble = 8
        num_sync = 2
        num_DC = 2.25
        self.num_data_sym = num_data_sym
        
        PS = num_data_sym

        PPS = N * 8
        packet_starts = Pream_ind_stack_base[:,0] * upsampling_factor + indexes
        samples_per_packet = int((12.25 + num_data_sym) * PPS)
        print("Before", packet_starts.size)
        mask = packet_starts < Rx_Buffer_Base.size - samples_per_packet
        packet_starts = packet_starts[mask]
        print("After", packet_starts.size)
        # Update variables
        Pream_ind_stack_base = Pream_ind_stack_base[mask,...]
        Peak_amp_base = Peak_amp_base[mask,...]
        FFO_base = FFO_base[mask]
        indexes = indexes[mask]
        bin_offsets = bin_offsets[mask]
        cfos = FFO_base[:,None]
        out = {}
        print("Creating data")
        start = time.perf_counter()
        data = self.dechirp(Rx_Buffer_Base, SF, PS, packet_starts + int(12.25*PPS), cfos)
        end = time.perf_counter()
        out["Dechirp"] = (end - start) / (data.shape[0] * data.shape[1])
        print("Done")
        #del Rx_Buffer_Base
        print("Interpolation")
        start = time.perf_counter()
        fft = np.abs(np.fft.fft(data))
        end = time.perf_counter()
        out["FFT"] = (end - start) / (data.shape[0] * data.shape[1])
        start = time.perf_counter()
        demod_sym_stack = np.mod((fft).argmax(2), N)
        end = time.perf_counter()
        out["Argmax"] = (end - start) / (data.shape[0] * data.shape[1])

        return np.mod(ne.evaluate('demod_sym_stack - 1'), N), out
