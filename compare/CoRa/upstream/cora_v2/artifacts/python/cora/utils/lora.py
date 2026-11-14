import numpy as np
import math

# Generate a discrete reference symbol
def gen_discrete_lora_ref(n,m, M=128):
    s = np.exp(1j*2*np.pi*(n*n/(2*M) + (m/M - 1/2)*n))
    return s

def dechirp(sig, uc=True, M=128):
    """
    Dechirp the signal
    """
    UL = gen_discrete_lora_ref(np.linspace(0,M,sig.shape[-1],endpoint=False), 0, M)
    DL = np.conj(UL)
    if uc:
        return sig * DL
    else:
        return sig * UL

def _gen_packet_wrapper(t, data, N=256):
    preamble = 8*[0] + [8] + [16] + 3*[0]
    m = np.array(np.hstack([preamble, data])) / N

    iq_invert = np.ones(t.size)
    iq_invert[(t>=10) & (t < 13)] = -1

    t0 = np.floor(t)
    valid_region = (t >= 0) * (t < len(m))
    idx = (t0 * valid_region).astype(int)

    # Delta phase
    dp = np.array([0] + list(m[:len(m)-1]))
    dp = np.random.uniform(-np.pi, np.pi) + np.pi*(2*dp-1)
    dp = np.cumsum(dp)
    dp = dp[idx]
    dp = dp * iq_invert * 0
    
    # Calculate arrays of m
    m = m[idx]

    ip = iq_invert*(np.pi*(t-t0)**2 + np.pi*(2*m-1)*(t-t0) + dp)
    phase = ip*N
 
    return np.exp(1j*phase)*valid_region

# Aligns symbol boundary to the unit
def gen_lora_packet(t, data, N, SF, BW):
    TS = 2**SF/BW
    t_ = t / TS
    t_[t_ > 12.25] = t_[t_ > 12.25] + 0.75

    return _gen_packet_wrapper(t_, data, N)

def generate_hi(N, t, fd):
    #t = np.arange(0, 1, 1/Fs) # time vector. (start, stop, step)
    x = np.zeros(len(t))
    y = np.zeros(len(t))
    alpha = (np.random.rand(N) - 0.5) * 2 * np.pi
    phi = (np.random.rand(N) - 0.5) * 2 * np.pi
    r = np.random.randn(N)
    sines_x = r[:,None] * np.cos(2 * np.pi * fd * t * np.cos(alpha[:,None]) + phi[:,None])
    sines_y = r[:,None] * np.sin(2 * np.pi * fd * t * np.cos(alpha[:,None]) + phi[:,None])

    # z is the complex coefficient representing channel, you can think of this as a phase shift and magnitude scale
    z = (1/np.sqrt(N)) * (sines_x.sum(0) + 1j*sines_y.sum(0)) # this is what you would actually use when simulating the channel
    return z

def lte_etu_channel(signal):
    delays = np.array([0, 50, 120, 200, 230, 500, 1600, 2300, 5000]) * 1e-9
    relative_powers = np.array([-1, -1, -1, 0, 0, 0, -3, -5, -7])
    mults = np.sqrt(10**(relative_powers / 10))
    DL = np.conj(gen_discrete_lora_ref(np.arange(0,256), 0, M=256))
    fd = 5
    #signal = gen_discrete_lora_ref(np.arange(0,256), 40, M=256)
    Ts = 1e-3
    t = np.arange(signal.size) / signal.size * Ts
    # z = generate_hi(N, np.arange(256) / 256, 5)
    # Generate the taps

    taps = np.vstack([generate_hi(100, t, fd) for i in range(delays.size)])
    taps = taps / np.abs(taps[:,0:1])
    shift = np.exp(1j*2*np.pi*-delays[:,None]*t)

    # Calculate FFT of signal
    fft = np.fft.fft(signal)
    noise =  (np.random.randn(256,2)*np.array([1,1j])*1/np.sqrt(2)).sum(1)
    return np.fft.ifft(np.sum(fft*taps*shift*mults[:,None],axis=0))

def gen_lora_packet_burst(t, locs, data, cfo, fto, SF=8, BW=250000, Fs=2e6, SNR=10, SNR_dev=1, channel_model=False):
    assert locs.shape[0] == data.shape[0]
    assert locs.shape[0] == cfo.size
    assert locs.shape[0] == fto.size

    N = 2**SF
    SNR_min = SNR - SNR_dev
    SNR_max = SNR + SNR_dev
    upsample_factor = int(Fs / BW)
    sample_period = 1/Fs

    packet_samples = int((8 + 2 + 2 + 0.25 + data.shape[1]) * N)
    # Generate noise
    noise_raw = (np.random.randn(t.size) + 1j*np.random.randn(t.size)) / np.sqrt(2)

    phase = np.zeros_like(t).astype(np.complex64)
    t_local = np.arange(packet_samples * upsample_factor) * sample_period
    for i in range(data.shape[0]):
        offset = locs[i] / Fs
        cp = gen_lora_packet(t_local + fto[i]*sample_period, data[i], N, SF, BW) * np.exp(1j*2*np.pi*(t_local / (sample_period * N * upsample_factor))*-cfo[i])
        loc = locs[i] + np.arange(packet_samples * upsample_factor)
        target_noise = noise_raw[loc]
        if channel_model:
            target_signal = lte_etu_channel(cp)
        else:
            target_signal = cp

        power_signal = (np.mean(target_signal*target_signal.conj()))
        power_noise = (np.mean(target_noise*target_noise.conj()))
        A = np.sqrt(10**((np.random.uniform(SNR_min, SNR_max))/10) * power_noise / power_signal)

        phase[loc] += cp * A

    signal = phase + noise_raw

    # Calculate peak amplitude
    preamble_indices = locs[:, np.newaxis] + (np.arange(8 * N * upsample_factor))[np.newaxis, ::upsample_factor]
    preamble_indices = preamble_indices.reshape(data.shape[0], 8, N)
    preambles = signal[preamble_indices]
    dechirped = preambles * gen_discrete_lora_ref(np.arange(N), 0,N).conj()
    ffts = np.abs(np.fft.fft(dechirped, axis=2))
    a = ffts[:,:,0]

    Peak_amp = np.vstack([np.mean(a,axis=1), np.var(a, axis=1, ddof=1), np.std(a, axis=1, ddof=1)]).T

    indices = np.mod(locs, upsample_factor).astype(int)
    # Generate the symbol boundaries
    locs = locs[:, np.newaxis] + np.arange(8) * N * upsample_factor

    # Store the downsampled symbol boundaries
    pream_ind = np.floor(locs / upsample_factor).astype(int)

    return [signal, pream_ind, indices, Peak_amp]


def sym_to_data_ang(symbols,N):
    data = []
    accumulator = 0

    ip = (-math.pi + (np.array(symbols)-1)*(2*math.pi/N))[:,np.newaxis]
    phase = ip + (2*math.pi/N)*np.arange(N).flatten()
    accumulator = np.cumsum(phase)
    return np.array(np.exp(1j*accumulator))

def get_bounded_max(arr,up_thresh,low_thresh):
    (pnts_up,) = (arr < up_thresh).nonzero()
    (pnts_low,) = (arr > low_thresh).nonzero()
    pnts = np.intersect1d(pnts_up, pnts_low)
    return pnts

def stft_v2(Buffer, f_n):
    w_n = f_n
    Buff_len = Buffer.size
    # Frequency axis
    f_n = math.ceil(f_n/2) * 2+1
    Lf = (f_n - 1)/2
    # Time axis
    w_n = math.ceil(w_n/2) * 2+1
    Lw = (w_n - 1)/2
    # Initialize Spectrum to zero with appropriate size
    Spec = np.zeros((f_n,Buff_len), dtype=np.complex64) 
    ## Sliding window over signal
    for iterr in range(Buff_len):
        i_l = min([iterr, Lw, Lf])
        i_r = min([Buff_len-iterr - 1, Lw, Lf])
        iter_ind = np.arange(-i_l, i_r+1)
        ind1 = (iter_ind + iterr).astype('int')   # Time Indexing of the original signal
        ind = (iter_ind + Lf).astype('int')     # Frequency Indexing of the martix
        Spec[ind, iterr] = Buffer[ind1]
    # Computing FFT of stacked Windows
    Spec = np.fft.fft(Spec.T).T
    Spec = Spec*2/f_n # normalizing the FFTs
    return Spec

def stft_v1(Rx_Buffer,N,DC):
    # This function produces a spectrogram of LoRa signal using Dechirping
    # operation to get the best frequency Resolution
    Spec = np.zeros((N,Rx_Buffer.shape[0]))
    buff = np.zeros(Rx_Buffer.size + N - 1, dtype=Rx_Buffer.dtype)
    buff[:Rx_Buffer.size] = Rx_Buffer
    for i in range(len(Rx_Buffer)):
        Spec[:,i] = np.roll(np.abs(np.fft.fft(buff[i:i+N] * DC)) / math.sqrt(N), -(i))
    return Spec


def get_max(arr,threshold,num_pnts):
    out = []
    if len(arr) == 0:
        return np.array(out)
    for i in range(num_pnts):
        [a, b] = arr.max(0), arr.argmax(0)
        if(a<threshold):
            return np.array(out)
        else:
            out.append(b)
            arr[b] = 0
    return np.array(out)

def length(arr):
    return max(arr.shape)

