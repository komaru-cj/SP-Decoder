import numpy as np
import math
import os
import tempfile
import uuid
import scipy

from cora.utils.lora import gen_discrete_lora_ref
from cora.sync.BaseDetection import BaseDetection
from cora import config

import subprocess

class TnBDetection(BaseDetection):
    def __init__(self, Fs, SF, BW, upsampling_factor=8):
        super().__init__(Fs, SF, BW, upsampling_factor)

    def synchronize(self, capture):
        print("Loading file")
        tmpfile_name = f"tnb_{uuid.uuid4().hex}"
        path = os.path.join(tempfile.gettempdir(), f"{tmpfile_name}.mat")
        subprocess.run(["matlab", "-batch", f"[loc,cfo]=TnBSync(\"{capture.file}\", {self.SF}, {self.BW});save(\"{path}\", \"loc\", \"cfo\")"],
                       cwd=config.TNB_FOLDER)
        mat = scipy.io.loadmat(path)
        os.remove(path)
        a,b = mat["loc"], mat["cfo"]
        # Load file
        start_time = np.asarray(a).flatten().astype(int)
        cfo = np.asarray(b).flatten()
        # Substract 1 due to Matlab indexing
        locs = start_time - 1
        upsample_factor = 8
        N = 2**self.SF
        signal = capture.arr
        preamble_indices = locs[:, np.newaxis] + (np.arange(8 * N * upsample_factor))[np.newaxis, ::upsample_factor]
        preamble_indices = preamble_indices.reshape(start_time.size, 8, N)
        preambles = signal[preamble_indices]
        dechirped = preambles * gen_discrete_lora_ref(np.arange(N), 0,N).conj() * np.exp(1j*2*np.pi*np.linspace(0,1,N,endpoint=False)*cfo[:,np.newaxis,np.newaxis])
        ffts = np.abs(np.fft.fft(dechirped, axis=2))
        a = ffts[:,:,0]

        Peak_amp = np.vstack([np.mean(a,axis=1), np.var(a, axis=1, ddof=1), np.std(a, axis=1, ddof=1)]).T

        indices = np.mod(locs, upsample_factor).astype(int)
        # Generate the symbol boundaries
        locs = locs[:, np.newaxis] + np.arange(8) * N * upsample_factor

        # Store the downsampled symbol boundaries
        Pream_ind = np.floor(locs / upsample_factor).astype(int)
        return Pream_ind, indices, cfo, Peak_amp, np.zeros_like(cfo)
