import numpy as np
from functools import reduce

class LoRaDecoder:
    # Assuming the necessary methods and properties are defined in the class
    def __init__(self, sf):
        self.ldr = 0
        self.sf = sf
        self.has_header = True
        self.hamming_decoding_en = True
        self.header_checksum_matrix = np.array([
            [1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
            [1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 1],
            [0, 1, 0, 0, 1, 0, 0, 1, 1, 0, 1, 0],
            [0, 0, 1, 0, 0, 1, 0, 1, 0, 1, 1, 1],
            [0, 0, 0, 1, 0, 0, 1, 0, 1, 1, 1, 1]
        ])
        self.whitening_seq = [0xff, 0xfe, 0xfc, 0xf8, 0xf0, 0xe1,
            0xc2, 0x85, 0xb, 0x17, 0x2f, 0x5e, 0xbc, 0x78, 0xf1, 0xe3,
            0xc6, 0x8d, 0x1a, 0x34, 0x68, 0xd0, 0xa0, 0x40, 0x80, 0x1, 0x2,
            0x4, 0x8, 0x11, 0x23, 0x47, 0x8e, 0x1c, 0x38, 0x71, 0xe2, 0xc4,
            0x89, 0x12, 0x25, 0x4b, 0x97, 0x2e, 0x5c, 0xb8, 0x70, 0xe0,
            0xc0, 0x81, 0x3, 0x6, 0xc, 0x19, 0x32, 0x64, 0xc9, 0x92, 0x24,
            0x49, 0x93, 0x26, 0x4d, 0x9b, 0x37, 0x6e, 0xdc, 0xb9, 0x72,
            0xe4, 0xc8, 0x90, 0x20, 0x41, 0x82, 0x5, 0xa, 0x15, 0x2b, 0x56,
            0xad, 0x5b, 0xb6, 0x6d, 0xda, 0xb5, 0x6b, 0xd6, 0xac, 0x59,
            0xb2, 0x65, 0xcb, 0x96, 0x2c, 0x58, 0xb0, 0x61, 0xc3, 0x87,
            0xf, 0x1f, 0x3e, 0x7d, 0xfb, 0xf6, 0xed, 0xdb, 0xb7, 0x6f,
            0xde, 0xbd, 0x7a, 0xf5, 0xeb, 0xd7, 0xae, 0x5d, 0xba, 0x74,
            0xe8, 0xd1, 0xa2, 0x44, 0x88, 0x10, 0x21, 0x43, 0x86, 0xd,
            0x1b, 0x36, 0x6c, 0xd8, 0xb1, 0x63, 0xc7, 0x8f, 0x1e, 0x3c,
            0x79, 0xf3, 0xe7, 0xce, 0x9c, 0x39, 0x73, 0xe6, 0xcc, 0x98,
            0x31, 0x62, 0xc5, 0x8b, 0x16, 0x2d, 0x5a, 0xb4, 0x69, 0xd2,
            0xa4, 0x48, 0x91, 0x22, 0x45, 0x8a, 0x14, 0x29, 0x52, 0xa5,
            0x4a, 0x95, 0x2a, 0x54, 0xa9, 0x53, 0xa7, 0x4e, 0x9d, 0x3b,
            0x77, 0xee, 0xdd, 0xbb, 0x76, 0xec, 0xd9, 0xb3, 0x67, 0xcf,
            0x9e, 0x3d, 0x7b, 0xf7, 0xef, 0xdf, 0xbf, 0x7e, 0xfd, 0xfa,
            0xf4, 0xe9, 0xd3, 0xa6, 0x4c, 0x99, 0x33, 0x66, 0xcd, 0x9a,
            0x35, 0x6a, 0xd4, 0xa8, 0x51, 0xa3, 0x46, 0x8c, 0x18, 0x30,
            0x60, 0xc1, 0x83, 0x7, 0xe, 0x1d, 0x3a, 0x75, 0xea, 0xd5, 0xaa,
            0x55, 0xab, 0x57, 0xaf, 0x5f, 0xbe, 0x7c, 0xf9, 0xf2, 0xe5,
            0xca, 0x94, 0x28, 0x50, 0xa1, 0x42, 0x84, 0x9, 0x13, 0x27,
            0x4f, 0x9f, 0x3f, 0x7f]
      

    def decode(self, symbols):
        return [self.decode_single(symbols[i][:, np.newaxis] + 1) for i in range(symbols.shape[0])]

    def decode_single(self, symbols_m):
        data_m = []
        checksum_m = []

        for pkt_num in range(symbols_m.shape[1]):
            # Gray coding
            symbols_g = self.gray_coding(symbols_m[:, pkt_num])
            # Deinterleave
            codewords = self.diag_deinterleave(symbols_g[:8], self.sf - 2)
            if not self.has_header:
                nibbles = self.hamming_decode(codewords, 8)
            else:
                # Parse header
                nibbles = self.hamming_decode(codewords, 8)
                self.payload_len = int(nibbles[0] * 16 + nibbles[1])
                self.crc = int(nibbles[2] & 1)
                self.cr = int(nibbles[2] >> 1)
                if self.payload_len == 0:
                    return [], False

                # Extract the LSB of the fourth element in 'nibbles'
                lsb_of_fourth = nibbles[3] & 1

                # Convert the fifth element of 'nibbles' to a 4-bit binary representation, with the MSB on the left
                binary_of_fifth = [int(i) for i in '{:04b}'.format(nibbles[4])]

                # The MATLAB function seems to combine these two into a single column vector. 
                # In Python, we can create a combined list (or use numpy array for more complex operations).
                header_checksum = [lsb_of_fourth] + binary_of_fifth
                def decimal_to_binary_array(decimals, bits):
                    """Convert an array of decimal numbers to a binary matrix."""
                    binary_matrix = ((decimals[:, None] & (1 << np.arange(bits)[::-1])) > 0).astype(int)
                    return binary_matrix

                # Convert the first three nibbles to binary, with 4 bits per nibble, left-MSB
                binary_matrix = decimal_to_binary_array(nibbles[0:3], 4)

                # Reshape the binary matrix into a flat array
                flat_binary_array = binary_matrix.reshape(-1)
                #nibbles_binary = np.concatenate([np.binary_repr(n, width=4) for n in nibbles[:3]]).astype(int)
                #header_checksum_calc = self.header_checksum_matrix @ nibbles_binary  # Placeholder for actual calculation           
                header_checksum_calc = np.bitwise_and(self.header_checksum_matrix, flat_binary_array.T).sum(axis=1) % 2
                
                if not np.array_equal(header_checksum, header_checksum_calc):
                    #raise ValueError('Invalid header checksum!')
                    return [], False
                nibbles = nibbles[5:]
            
            rdd = self.cr + 4
            ii = 8
            if (rdd not in [5,6,7,8]):
                return [], False
            while ii < len(symbols_g) - rdd + 1:
                codewords = self.diag_deinterleave(symbols_g[ii:ii + rdd], self.sf - 2 * self.ldr)
                # Hamming decode
                nibbles = np.hstack([nibbles, self.hamming_decode(codewords, rdd)])
                ii += rdd

            # Combine nibbles to bytes
            bytes_list = [((nibbles[i+1] << 4) | nibbles[i]) for i in range(0, len(nibbles)-1, 2)]
            bytes_array = np.array(bytes_list, dtype=np.uint8)
            # Dewhitening
            crc_ok = False
            if self.crc:
                data = self.dewhiten(bytes_array[:self.payload_len])
                data = np.append(data, bytes_array[self.payload_len:self.payload_len + 2])
                crc = self.crc16(data[:-4])
                if (self.payload_len >= 2):
                    xor = int.from_bytes(bytes([data[-3], data[-4]]),'little')
                    calc_crc = crc ^ xor
                    exp_crc = int.from_bytes(bytes([data[-2], data[-1]]),'little')
                    crc_ok = calc_crc == exp_crc
            else:
                data = self.dewhiten(bytes_array[:self.payload_len])
                checksum = []

            data_m.append(data)
            #checksum_m.append(checksum)

        return data_m[0], crc_ok

    def gray_coding(self, din):
        """
        Applies Gray coding to the input digital symbols.
        
        Parameters:
        din : array-like
            Input symbols with binary drift.
        
        Returns:
        symbols : numpy.ndarray
            Symbols after bin calibration using Gray coding.
        """
        import numpy as np

        # Adjust the first 8 symbols
        din[:8] = np.floor(din[:8] / 4)
        
        # Adjust the remaining symbols based on LDR
        if self.ldr:
            din[8:] = np.floor(din[8:] / 4)
        else:
            din[8:] = np.mod(din[8:] - 1, 2 ** self.sf)
        
        # Apply Gray coding
        s = np.uint16(din)
        symbols = np.bitwise_xor(s, np.right_shift(s, 1))
        
        
        return symbols
    
    def diag_deinterleave(self, symbols, ppm):
        """
        Diagonal deinterleaving of symbols.

        Parameters:
        symbols : numpy.ndarray
            Symbols after Gray coding.
        ppm : int
            Size with parity bits.

        Returns:
        codewords : numpy.ndarray
            Codewords after deinterleaving.
        """
        # Convert symbols to binary representation
        b = np.array([np.binary_repr(np.mod(symbol, 2**ppm), width=ppm) for symbol in symbols], dtype=str)
        # Convert string array to a 2D array of integers (0s and 1s)
        b_matrix = np.array([list(row) for row in b], dtype=int)
        
        b = b_matrix
        # Apply circular shift to each row of 'b'
        shifted_rows = [np.roll(b[x, :], 1 - x) for x in range(len(symbols))]

        # Convert list of arrays back into a 2D NumPy array
        result_matrix = np.array(shifted_rows)

        # If you need the result to be transposed (as suggested by the trailing `'` in MATLAB),
        # simply transpose the resulting matrix
        result_matrix = np.roll(result_matrix.T,-1,axis=0)
        decimal_values = np.dot(result_matrix, 2**np.arange(result_matrix.shape[-1]))
        return decimal_values[::-1]

    @staticmethod
    def bit_reduce(fn, w, pos):
        bits = [(w >> (p - 1)) & 1 for p in pos]
        return reduce(fn, bits)

    @staticmethod
    def parity_fix(p):
        """Determines the bit position that may need correction."""
        mapping = {
            3: 4,  # 011: error in bit 3 (position 4)
            5: 8,  # 101: error in bit 4 (position 8)
            6: 1,  # 110: error in bit 1 (position 1)
            7: 2,  # 111: error in bit 2 (position 2)
        }
        return mapping.get(p, 0)

    def hamming_decode(self, codeword, rdd):
        p1 = self.bit_reduce(lambda x, y: x ^ y, codeword, [8, 4, 3, 1])
        p2 = self.bit_reduce(lambda x, y: x ^ y, codeword, [7, 4, 2, 1])
        p3 = self.bit_reduce(lambda x, y: x ^ y, codeword, [5, 3, 2, 1])
        p4 = self.bit_reduce(lambda x, y: x ^ y, codeword, [5, 4, 3, 2, 1])
        p5 = self.bit_reduce(lambda x, y: x ^ y, codeword, [6, 4, 3, 2])
        if hasattr(self, 'hamming_decoding_en') and self.hamming_decoding_en:
            if rdd in {5, 6}:
                nibble = codeword % 16
            elif rdd in {7, 8}:
                parity = p2*4 + p3*2 + p5
                pf = np.vectorize(self.parity_fix)
                correction = pf(parity)
                corrected_codeword = codeword ^ correction
                nibble = corrected_codeword % 16
            else:
                raise ValueError('Invalid Code Rate!')
        else:
            nibble = codeword % 16

        return nibble
        
    def dewhiten(self, data):
        return np.bitwise_xor(data, self.whitening_seq[0:len(data)])
    
    def crc16(self, data):
        crc = 0x0000  # Initial value of CRC
        for newByte in data:
            newByte = int(newByte)  # Ensure the byte is treated as an unsigned number
            for _ in range(8):  # Process each bit in the byte
                if (((crc & 0x8000) >> 8) ^ (newByte & 0x80)):
                    crc = (crc << 1) ^ 0x1021
                else:
                    crc = (crc << 1)
                crc &= 0xFFFF  # Ensure CRC remains within 16 bits
                newByte <<= 1  # Move to the next bit
        return crc

