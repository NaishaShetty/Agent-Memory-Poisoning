class BaseAgent():
    def __init__(self, config):
        self.config = config

    def reset(self):
        raise NotImplementedError()

    def response(self, observation, reward, terminated, info):
        raise NotImplementedError()

    def train(self, env):
        raise NotImplementedError()