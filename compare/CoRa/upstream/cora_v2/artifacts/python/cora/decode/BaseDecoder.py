import numpy as np
import functools
import scipy
import uuid
import os
import tempfile
import subprocess
from cora import config

class BaseMATLABDecoder:
    def __init__(self, sf):
        self.SF = sf

    def decode(self, symbols_m):
        tmpfile_name = f"tnb_{uuid.uuid4().hex}"
        path = os.path.join(tempfile.gettempdir(), f"{tmpfile_name}.mat")
        target = os.path.join(tempfile.gettempdir(), f"{tmpfile_name}.out.mat")
        scipy.io.savemat(path, {"syms": symbols_m})
        subprocess.run(["matlab", "-batch", f"[pkts,CRC]=TnBDecode(\"{path}\", {self.SF}, {self.decoder});save(\"{target}\", \"pkts\", \"CRC\")"],
                       cwd=config.TNB_FOLDER)
        mat = scipy.io.loadmat(target)
        os.remove(path)
        os.remove(target)
        return [(i, j) for i,j in zip(mat["pkts"][0], mat["CRC"][0])]
