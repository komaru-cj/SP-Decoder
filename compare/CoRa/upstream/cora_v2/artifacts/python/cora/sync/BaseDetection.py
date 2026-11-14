import numpy as np
import scipy
import math

from cora.utils.lora import gen_discrete_lora_ref

class BaseDetection:
    def __init__(self, Fs, SF, BW, upsampling_factor=8, **kwargs):
        self.Fs = Fs
        self.SF = SF
        self.BW = BW

        self.upsampling_factor = upsampling_factor
        self.N = 2**SF
        self.PPS = self.upsampling_factor * self.N

        DL = np.conj(gen_discrete_lora_ref(np.arange(0,self.N), 0, M=self.N))
        self.DL = DL
        self.DL_up = scipy.signal.resample(DL, self.PPS)


    def synchronize(self, capture):
        return NotImplemented()

