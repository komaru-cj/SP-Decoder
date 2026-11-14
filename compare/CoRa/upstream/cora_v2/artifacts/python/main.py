import argparse
import numpy as np
import pickle


from cora.utils.capture import Capture
from cora.sync import get_sync_backend
from cora.demod import get_demod_backend
from cora.decode import get_decode_backend

from cora import config

def main():
    # Main parser setup
    parser = argparse.ArgumentParser(description="Orchestrator CLI for LoRa decoding pipeline stages")
    subparsers = parser.add_subparsers(dest="stage", help="Pipeline stage to run", required=True)
    parser.add_argument("-S", "--spreading_factor", type=int, help="Spreading Factor", required=True)
    parser.add_argument("-l", "--long_complex", action="store_true", help="Enable parsing complex64 input data")

    # Sync subcommand
    sync_parser = subparsers.add_parser("sync", help="Run the sync stage")
    sync_parser.add_argument("--backend", help="Sync backend to use", default="CoRa")
    sync_parser.add_argument("-B", "--bandwidth", type=int, help="Bandwidth", required=True)
    sync_parser.add_argument("input", help="Input file")
    sync_parser.add_argument("output", help="Output file")

    # Demod subcommand
    demod_parser = subparsers.add_parser("demod", help='Run the demodulation stage')
    demod_parser.add_argument("--backend", help="Demod backend to use", default="CoRa")
    demod_parser.add_argument('input', type=str, help='Input file')
    demod_parser.add_argument('sync', type=str, help='Sync file')
    demod_parser.add_argument('output', type=str, help='Output file')
    demod_parser.add_argument("-B", "--bandwidth", type=int, help="Bandwidth", required=True)
    demod_parser.add_argument('--num_syms', '-n', type=int, help='Payload Length', required=True)

    decode_parser = subparsers.add_parser("decode", help='Run the decode stage')
    decode_parser.add_argument("--backend", help="Decode backend to use", default="LoRa")
    decode_parser.add_argument('input', type=str, help='Input file')
    decode_parser.add_argument('output', type=str, help='Output file')

    
    # Parse arguments
    args = parser.parse_args()
    SF = args.spreading_factor
    
    if args.stage == "sync":
        sync = get_sync_backend(args.backend)
        print(sync)
        BW = args.bandwidth
        input_file = args.input
        output_file = args.output
        capture = Capture(input_file, args.long_complex)
        res = (sync(1e6, SF, BW).synchronize(capture))

        print("Saving sync file")
        with open(output_file, 'wb') as handle:
            pickle.dump(res, handle)

    elif args.stage == "demod":
        demod = get_demod_backend(args.backend)
        BW = args.bandwidth
        input_file = args.input
        output_file = args.output
        sync_file = args.sync
        num_syms = args.num_syms
        capture = Capture(input_file, args.long_complex)
        with open(sync_file, 'rb') as handle:
            res = pickle.load(handle)

        demodulator = demod(SF)
        print(res)
        if len(res[0]) == 0:
            out = np.array([])
            with open(output_file, 'wb') as handle:
                pickle.dump([out, None], handle)
            print("Nothing to do")
            exit()

        total_frames = res[0].shape[0]
        frames_split = np.array_split(np.arange(total_frames), max(total_frames // config.DEMOD_BATCH_SIZE, 1))
        outs = []
        for samples in frames_split:
            out = (demodulator.demodulate(res[0][samples], capture, res[3][samples], res[2][samples], res[1][samples], 8, res[4][samples], num_syms))
            print(out[1])
            outs.append(out[0])

        out = np.vstack(outs)
        total_symbols = out.size

        with open(output_file, 'wb') as handle:
            pickle.dump([out, None], handle)

        print("Done")
    elif args.stage == "decode":
        decode = get_decode_backend(args.backend)
        input_file = args.input
        output_file = args.output
        SF = args.spreading_factor
        with open(input_file, 'rb') as handle:
            out = pickle.load(handle)
        
        dec = decode(SF)
        print("Decoding")
        print(out[0].astype(int))
        decoded = dec.decode(out[0])
        print(decoded)
        print("Decoded packets: ", np.sum([d[1] for d in decoded]))

        with open(output_file, 'wb') as handle:
            pickle.dump(decoded, handle)
        print("Done")

if __name__ == "__main__":
    main()
