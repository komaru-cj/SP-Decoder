# CoRa Source Code

## Instructions

1. Install the required Python dependencies:
```
pip install -r requirements.txt
```

Consider using `venv` if you want an isolated Python environment. E.g
```
python -m venv venv
source venv/bin/activate
# ... run commands inside the isolated Python environment
```

2. Install MATLAB and the required TnB packages to run TnB
3. Clone TnB from the official [TnB repository](https://github.com/raghavrathi10/TnB.git).
4. Apply the `patches/TnB.patch` patch to TnB by using `git apply`. This exposes the synchronization and decoder blocks as MATLAB functions that will be used by the CoRa demodulator.
The patch was tested on top of commit:

```
commit bb33e98d596960b6f357142874bc0908f5a4e7dd (origin/main, origin/HEAD)
Author: zzhangcsfsu <116897936+zzhangcsfsu@users.noreply.github.com>
Date:   Mon Nov 21 19:19:06 2022 -0500

    Update README.md
```

5. Modify `cora/config.py` and set the `TNB_FOLDER` variable to the cloned TnB folder
6. Utilize main.py to run the synchronization, demodulation and decoding stages.

To decode LoRa packets using CoRa, run the following commands:

```
python main.py --spreading_factor <SF> sync --bandwidth <BW> --backend TnB <capture_file> <sync_file>
python main.py --spreading_factor <SF> demod --bandwidth <BW> --backend CoRa --num_syms <num_syms> <capture_file> <sync_file> <demod_file>
python main.py --spreading_factor <SF> decode --bandwidth <BW> --backend BEC <demod_file> <decode_file>
```

All intermediate files (`<sync_file>, <demod_file>, <decode_file>`) use the
Pickle format.

NOTE: By default, CoRa assumes `complex32` format for the capture file. For using
`complex64`, please use the `--long_complex` flag when invoking `main.py`
