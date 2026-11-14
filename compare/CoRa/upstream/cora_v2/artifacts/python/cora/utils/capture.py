import numpy as np
import os

class Capture:
    def __init__(self, input_file, complex_64):
        self._arr = None
        self.complex_64 = complex_64
        self.file = os.path.abspath(input_file)

    def _load_file(self, file, long):
        if not long:
            print("Using complex32")
            arr = np.fromfile(file, dtype=np.int16)
            return arr[::2] + 1j*arr[1::2]
        else:
            print("Using complex64")
            arr = np.fromfile(file, dtype=np.complex64)
            return arr

    @property
    def arr(self):
        if self._arr is None:
            self._arr = self._load_file(self.file, self.complex_64)
        return self._arr
    
    @arr.setter
    def arr(self, value):
        self._arr = value
