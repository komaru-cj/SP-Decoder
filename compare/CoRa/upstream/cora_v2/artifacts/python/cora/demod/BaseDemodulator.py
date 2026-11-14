import numpy as np
import time
from cora.utils.lora import gen_discrete_lora_ref
import scipy
import numexpr as ne

class BaseDemodulator:
    def __init__(self, SF, upsampling_factor=8):
        self.SF = SF
        self.upsampling_factor = upsampling_factor

    def demodulate(self, Pream_ind_stack_base, capture,Peak_amp_base,FFO_base, indexes, upsampling_factor, bin_offsets, num_data_sym):
        #DEMOD
        # CIC Demodulation
        # chirp variables
        SF = self.SF
        N = int(2**SF)
        Rx_Buffer_Base = capture.arr

        # Pream_ind: indices of the peaks of the preamble in relation to the Rx_Buffer
        # Rx_Buffer: received signal
        # Pream_ind_stack: indices of the peaks of the preamble in relation to the Rx_Buffer
        # for all the packets in the Rx_Buffer
        # Peak_amp: amplitude of the peaks of the preamble in relation to the Rx_Buffer
        # m: index of the packet in the Pream_ind_stack

        # LORA pkt variables
        num_preamble = 8
        num_sync = 2
        num_DC = 2.25
        self.num_data_sym = num_data_sym

        # Generate a list of arguments to be passed to the pool
        demod_sym_stack = np.zeros((Pream_ind_stack_base.shape[0], self.num_data_sym), dtype=int)
        times = np.zeros(Pream_ind_stack_base.shape[0])
        for m in range(demod_sym_stack.shape[0]):
            st = time.perf_counter()
            demod_sym_stack[m,:] = self.demod_callback(Pream_ind_stack_base[m,:], Peak_amp_base[m,:], FFO_base[m], indexes[m], upsampling_factor, Rx_Buffer_Base, Pream_ind_stack_base, m)
            times[m] = time.perf_counter() - st


        return np.mod(demod_sym_stack + bin_offsets[:, np.newaxis] - 2, N), times

    def demod_callback(self, Pream_ind, Peak_amp, FFO, index, upsampling_factor, Rx_Buffer_Base, Pream_ind_stack_base, m):
        raise NotImplementedError("Subclasses must implement this method")

    def dechirp(self, arr, sf, symbols, packet_start, cfo):

        N = 2**sf
        UL = gen_discrete_lora_ref(np.arange(0,N), 0, M=N)
        DL = ne.evaluate('conj(UL)')
        DL_up = scipy.signal.resample_poly(DL, 8, 1)
        PPS = N * 8
        preamble_samples = (packet_start[:,None] + np.arange(0,PPS*symbols)[None, :]).flatten()
        tgt = arr[preamble_samples].reshape(-1,symbols, PPS)
        lsp = np.linspace(0,1,8*N,endpoint=False)
        pi = np.pi
        shift = ne.evaluate('exp(1j*2*pi*cfo*lsp)')[:,None,:]
        preamble_raw = ne.evaluate('tgt * DL_up *  shift')

        return preamble_raw.astype(np.complex64)

