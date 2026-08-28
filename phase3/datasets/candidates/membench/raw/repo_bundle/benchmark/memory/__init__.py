from .BaseMemory import BaseMemory
from .CommonMemory import FullMemory, MemoryBank, RetrievalMemory, RecentMemory, GAMemory, MGMemory, SCMemory, RFMemory


def create_memory_module(config):
    if config['type'] == 'FullMemory':
        return FullMemory(config)
    elif config['type'] == 'MemoryBank':
        return MemoryBank(config)
    elif config['type'] == 'RetrievalMemory':
        return RetrievalMemory(config)
    elif config['type'] == 'RecentMemory':
        return RecentMemory(config)
    elif config['type'] == 'GAMemory':
        return GAMemory(config)
    elif config['type'] == 'MGMemory':
        return MGMemory(config)
    elif config['type'] == 'SCMemory':
        return SCMemory(config)
    elif config['type'] == 'RFMemory':
        return RFMemory(config)
    else:
        raise "This memory type has not been implemented."