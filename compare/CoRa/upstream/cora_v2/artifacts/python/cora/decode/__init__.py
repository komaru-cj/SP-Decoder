def get_decode_backend(backend="LoRa"):
    try:
        if backend == "LoRa":
            from cora.decode.LoRaDecoder import LoRaDecoder
            cls = LoRaDecoder
        elif backend == "BEC":
            from cora.decode.BECDecoder import BECDecoder
            cls = BECDecoder
        elif backend == "TnBLoRa":
            from cora.decode.TnBLoRaDecoder import TnBLoRaDecoder
            cls = TnBLoRaDecoder
        else:
            raise ValueError("Unknown backend")
    except ImportError as e:
        raise ImportError(f'Backend {backend} requires additional dependencies')

    return cls
