def get_demod_backend(backend="CoRa"):
    try:
        if backend == "Baseline":
            from cora.demod.BaselineDemodulator import BaselineDemodulator
            cls = BaselineDemodulator
        elif backend == "CoRa":
            from cora.demod.CoRaDemodulator import CoRaDemodulator
            cls = CoRaDemodulator
        else:
            raise ValueError("Unknown backend")
    except ImportError as e:
        raise ImportError(f'Backend {backend} requires additional dependencies')

    return cls
