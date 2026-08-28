class BaseMemory():
    def __init__(self, config) -> None:
        self.config = config

    def reset(self) -> None:
        raise NotImplementedError()

    def store(self, observation) -> None:
        raise NotImplementedError()
    
    def recall(self, observation) -> object:
        raise NotImplementedError()

    def retri(self, observation) -> object:
        raise NotImplementedError()
    
    def manage(self) -> None:
        raise NotImplementedError()
    
    def train(self, **kwargs) -> None:
        raise NotImplementedError()