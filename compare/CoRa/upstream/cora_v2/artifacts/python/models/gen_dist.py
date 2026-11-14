import numpy as np
import matplotlib.pyplot as plt
import scipy.ndimage
import multiprocessing as mp
from scipy.interpolate import RegularGridInterpolator
np.random.seed(42)

#N = 256 #256
#MAX_POWER=4
#MIN_POWER=0.42
#MAX_CFO = 0.18
#M = 100000
#MAX_INT = 2
#BINS = 100
#SIGMA = 10  # Standard deviation for Gaussian kernel

# This one works!!!
N = 256 #256
MAX_POWER=8
MIN_POWER=0.3
MAX_CFO = 1/8
M = 100000
MAX_INT = 2
BINS = 200
SIGMA = 28  # Standard deviation for Gaussian kernel
k = 10

def generate_test_signal(M=M, MAX_INT=MAX_INT, MIN_POWER=MIN_POWER, MAX_POWER=MAX_POWER, MAX_CFO=MAX_CFO):
    true_freq = np.random.randint(0,N,(M, 1))
    true_power = np.random.uniform(MIN_POWER, MAX_POWER, (M,1))
    true_cfo = np.random.normal(scale=MAX_CFO / 6, size=(M,1))
    
    t = np.linspace(0,1,N, endpoint=False)
    true_sines = true_power * np.exp(1j*2*np.pi*(true_freq + true_cfo)*t)
    
    # M, 2, N
    int_freq = np.random.uniform(0,N, (M, MAX_INT, 2, 1))
    int_power = np.random.uniform(MIN_POWER, MAX_POWER, (M, MAX_INT))[...,None,None]

    power_mask = np.random.randint(0,2,(M,MAX_INT,1,1))
    int_p = np.random.randint(0,N,(M, MAX_INT))
    int_upper_mask = np.cumsum(np.eye(N)[int_p], axis=2)[:,:,None,:]
    int_lower_mask = 1-int_upper_mask
    
    int_masks = np.concatenate([int_upper_mask, int_lower_mask], axis=2)
    int_sines = (power_mask * int_power * np.exp(1j*2*np.pi*(int_freq)*t) * int_masks).sum(2).sum(1)
    
    noise = np.random.randn(M,N) + 1j*np.random.randn(M,N)
    s = int_sines + true_sines + noise
    return s, true_freq.flatten(), true_power.flatten()*N

def h_operator(x):
    x = x[:,np.newaxis,:]
    v2 = np.roll(x, x.shape[2]//2,axis=2)
    res = np.concatenate([x + v2, x - v2],axis=1)
    res[:,:,x.shape[2]//2:] = 0
    res = np.abs(np.fft.fft(res,axis=2))
    return res

def calculate_features(data_raw, power_stats):
    h = h_operator(data_raw).min(1)
    data_fft = np.abs(np.fft.fft(data_raw))
    h_stats = h / data_fft
    pow_stats = np.abs(data_fft - power_stats[:,0:1]) / power_stats[:,0:1]
    #pow_stats = (data_fft / power_stats[:,0][:,None, None])# / power_stats[:,0][:,None, None]
    return np.concatenate([h_stats[...,None], pow_stats[...,None]], axis=len(data_raw.shape))

pools = 100
m = M // pools
ms = (np.ones(pools) * m).astype(int)
def gen_wrapper(m):
    print("Generating signal")
    s, true_freq, true_power = generate_test_signal(M=m)
    # Choose only the hard cases
    syms = np.abs(np.fft.fft(s)).argmax(1)
    hard = syms != true_freq
    s = s[hard,...]
    true_freq = true_freq[hard]
    true_power = true_power[hard]
    M = np.sum(hard)
    print("Hard symbols:", M)
    print("Calculating features")
    features = calculate_features(s, true_power[:,None])
    print(features.shape, true_freq.shape)
    return features, true_freq

with mp.Pool(processes=pools) as pool:
    res = pool.map(gen_wrapper, ms)

features = np.concatenate([r[0] for r in res])
true_freq = np.concatenate([r[1] for r in res])

M = true_freq.size
print(features.shape, true_freq.shape)
print("Calculating metrics")
m_good = np.zeros((M,N))
m_good[np.arange(M), true_freq] = 1
m_bad = np.zeros((M,N))
m_bad[np.arange(M), np.random.randint(0,N,M)] = 1

d = features[...,1]**2
d[:,true_freq] = 10000

print(features.shape)
print("DESHEIP", d.shape, k)
top_k = np.argpartition(-d, k,axis=1)[:,:k]  # Results are not sorted

bad = np.take_along_axis(features, top_k[...,None], axis=1).reshape(-1,2)

#m_bad = 1-m_good
m_good = m_good.astype(bool)
#m_bad = m_bad.astype(bool)

good = features[m_good,:]
#bad = features[m_bad,:]

good[good > 1] = 1
bad[bad > 1] = 1
print("SHEIP", good.shape, bad.shape)

xedges = np.linspace(0,1,BINS+1)
yedges = np.linspace(0,1,BINS+1)
print((xedges[0] + xedges[1]) / 2)
print("Calculating distribution")
hist_good, xedges_good, yedges_good = np.histogram2d(good[:,0], good[:,1], bins=[xedges, yedges], density=False)
hist_bad, xedges_bad, yedges_bad = np.histogram2d(bad[:,0], bad[:,1], bins=[xedges, yedges], density=False)

# Apply Gaussian filter
for i in range(1):
    hist_good = scipy.ndimage.gaussian_filter(hist_good, sigma=SIGMA)
    hist_bad = scipy.ndimage.gaussian_filter(hist_bad, sigma=SIGMA)

## Define the bin centers for interpolation
#xcenters_good = (xedges_good[:-1] + xedges_good[1:]) / 2
#ycenters_good = (yedges_good[:-1] + yedges_good[1:]) / 2
#
#xcenters_bad = (xedges_bad[:-1] + xedges_bad[1:]) / 2
#ycenters_bad = (yedges_bad[:-1] + yedges_bad[1:]) / 2
#
## Step 2: Create the interpolation function using RegularGridInterpolator
#f_good = RegularGridInterpolator((xcenters_good, ycenters_good), hist_good, method="nearest")
#f_bad = RegularGridInterpolator((xcenters_bad, ycenters_bad), hist_bad, method="nearest")
#
#x, y = np.meshgrid(np.linspace(0,1,100,endpoint=False), np.linspace(0,1,100,endpoint=False))
#x = x.flatten()
#y = y.flatten()
#print(x.max(), y.max(), xcenters_good, ycenters_good)
#P_c_t = f_good(np.vstack([x,y]).T).reshape(100,100)
#P_c_f = f_bad(np.vstack([x,y]).T).reshape(100,100)

H1 = hist_good
H2 = hist_bad
# Smoothing constant
alpha = 1

# Smooth the histograms
H1_smooth = H1 + alpha
H2_smooth = H2 + alpha

# Normalize smoothed histograms
H1_smooth = H1_smooth / np.sum(H1_smooth)
H2_smooth = H2_smooth / np.sum(H2_smooth)

# Number of samples in each class (example)
N1 = 1  # Number of samples in class 1
N2 = N-1  # Number of samples in class 2

# Prior probabilities
P_C1 = good.shape[0] / (good.shape[0] + bad.shape[0])
P_C2 = bad.shape[0] / (good.shape[0] + bad.shape[0])

def compute_posterior(H1, H2, P_C1, P_C2):
    # Likelihoods using smoothed histograms
    P_xy_C1 = H1#[x, y]
    P_xy_C2 = H2#[x, y]
    
    # Total probability
    P_xy = P_xy_C1 * P_C1 + P_xy_C2 * P_C2
    
    # Posterior probabilities
    P_C1_xy = (P_xy_C1 * P_C1) / P_xy# if P_xy != 0 else 0
    P_C2_xy = (P_xy_C2 * P_C2) / P_xy# if P_xy != 0 else 0

    P_C1_xy[np.isnan(P_C1_xy)] = 0
    P_C1_xy[np.isnan(P_C1_xy)] = 0
    
    return P_C1_xy, P_C2_xy

print("Generating posterior")
P_C1_xy, P_C2_xy = compute_posterior(H1_smooth, H2_smooth, P_C1, P_C2)

print("Saving file")
import pickle
with open("dist.pkl", "wb") as handle:
    pickle.dump(P_C1_xy / np.max(P_C1_xy), handle)

