import numpy as np
import time
import pickle
import numexpr as ne

from cora.demod.BaseDemodulator import BaseDemodulator

class CoRaDemodulator(BaseDemodulator):
    name = "CoRaDemodulator"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        with open("models/dist.pkl", "rb") as handle:
            z = pickle.load(handle)
        self.z = z
        self.antialias = False

    def demodulate(self, Pream_ind_stack_base, capture, Peak_amp_base,FFO_base, indexes, upsampling_factor, bin_offsets, num_data_sym):
        SF = self.SF
        N = int(2**SF)
        Rx_Buffer_Base = capture.arr

        # LORA pkt variables
        num_preamble = 8
        num_sync = 2
        num_DC = 2.25
        self.num_data_sym = num_data_sym
        
        PS = num_data_sym + 1

        PPS = N * 8
        print(upsampling_factor, Pream_ind_stack_base[:,0], indexes)
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
        print("Creating data")
        out = {}
        start = time.perf_counter()
        data = self.dechirp(Rx_Buffer_Base, SF, PS, packet_starts + int(11.25*PPS), cfos)
        end = time.perf_counter()
        out["Dechirp"] = (end - start) / (data.shape[0] * data.shape[1])
        print("Done")
        #del Rx_Buffer_Base
        power_stats = Peak_amp_base
        power_shape = data.shape + (PS,)
        power_stats = power_stats[:,0:1]
        print("Creating new features")
        start = time.perf_counter()
        features = (self.calculate_features(data, power_stats)).astype(np.float32)
        end = time.perf_counter()
        out["Features"] = (end - start) / (data.shape[0] * data.shape[1])
        start = time.perf_counter()
        #del data
        threshold = 1 - 1 / 200

        # Thresholding
        features = np.minimum(features, threshold)

        print("Interpolation")

        features = (ne.evaluate('features * 200')).astype(int)
        vals_1 = features[:,1:,:,:]
        vals_2 = features[:,0:-1,:,:]

        p1 = self.z[vals_1[...,0], vals_1[...,1]]
        p2 = self.z[vals_2[...,0], vals_2[...,1]]

        print("Demodulation")
        bayes = ne.evaluate('(p1 * (1-p2))')
        end = time.perf_counter()
        out["Interpolation"] = (end - start) / (vals_1.shape[0] * vals_1.shape[1])
        start = time.perf_counter()
        demod_sym_stack = np.mod(bayes.argmax(2), N)
        #bo = bin_offsets[:, np.newaxis]
        demod =  np.mod(ne.evaluate('demod_sym_stack  - 1'), N)
        end = time.perf_counter()
        out["Argmax"] = (end - start) / (demod_sym_stack.shape[0] * demod_sym_stack.shape[1])
        return demod, out


    def calculate_features(self, data_raw, power_stats):
        #h = self.h_operator(data_raw).min(1)
        SF = self.SF
        N = int(2**SF)

        #h = self.h_operator(data_raw)
        # Precompute the indices
        indices = np.arange(N)
        mod_indices = np.zeros(N,dtype=int)
        mod_indices[1::2] = 1
        mod_indices_plus_one = ne.evaluate('1-mod_indices')
        
        mask = np.ones(8*N)
        mask[(8*N)//2:] = -1

        # Using broadcasting to create the combined data array
        extended_data = np.empty((2,) + data_raw.shape, dtype=data_raw.dtype)
        extended_data[0,...] = data_raw
        extended_data[1,...] = data_raw * mask

        if self.antialias:
            fft = np.fft.fft(extended_data)
            ho = np.abs(fft[...,:N] + fft[..., -N:]) / 8
        else:
            ho = np.abs(np.fft.fft(extended_data[...,::8]))

        data_fft = ho[0]
        h = ho[1]

        # Get the shape of data_raw and add the new dimension
        shape_with_new_dim = data_raw[...,::8].shape + (2,)

        # Create the zero-initialized array with the new shape
        out = np.zeros(shape_with_new_dim)
        #out[...,0] = ne.evaluate('h / data_fft')
        out[...,0] = ne.evaluate('h / data_fft')
        ps = power_stats[:,None]
        out[...,1] = ne.evaluate('abs(data_fft - ps) / ps')
        print("Done")
        return out

    def h_operator(self, x):
        res = np.zeros((2,) + x.shape, dtype=x.dtype)
        half = x.shape[-1] // 2
        v1 = x[...,:half]
        v2 = x[...,half:]

        res[0,...,:half] = ne.evaluate('v1 + v2')
        res[1,...,:half] = ne.evaluate('v1 - v2')
        res = np.ascontiguousarray(res)
        start = time.perf_counter()
        fft = np.abs(np.fft.fft(res, axis=-1))
        end = time.perf_counter()
        print(fft.shape)
        print((end - start) * 1e6 / (x.shape[0] * x.shape[1]))
        return fft

