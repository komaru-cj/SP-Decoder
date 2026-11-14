from cora.decode.BaseDecoder import BaseMATLABDecoder

class BECDecoder(BaseMATLABDecoder):
    def __init__(self, sf):
        super().__init__(sf)
        self.decoder = 1
