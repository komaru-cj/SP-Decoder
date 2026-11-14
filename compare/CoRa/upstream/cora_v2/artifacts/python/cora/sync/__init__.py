def get_sync_backend(backend="TnB"):
    try:
        if backend == "TnB":
            from cora.sync.TnBDetection import TnBDetection
            sync = TnBDetection
        else:
            raise ValueError("Unknown backend")
    except ImportError as e:
        raise ImportError(f'Backend {backend} requires additional dependencies')

    return sync
