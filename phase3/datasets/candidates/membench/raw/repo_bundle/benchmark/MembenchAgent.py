from memory import create_memory_module
# from BaseAgent import BaseAgent
from benchutils import create_LLM
from langchain.prompts import PromptTemplate
import logging
import time
import json

INSTRUCTION_THIRD = """Please answer the following question based on past memories of the user's messages.
Past memory: {memory}
Question: (current time is {time}) {question}
Choices:
A. {choice_A}
B. {choice_B}
C. {choice_C}
D. {choice_D}
Please output the correct option for the question, only one corresponding letter, without any other messages.
Example: D
"""

INSTRUCTION_FIRST = """Please answer the following question based on past memories of your'conversation with the user.
Past memory: {memory}
Question: (current time is {time}) {question}
Choices:
A. {choice_A}
B. {choice_B}
C. {choice_C}
D. {choice_D}
Please output the correct option for the question, only one corresponding letter, without any other messages.
Example: D
"""

class MemBenchAgent():
    def __init__(self, config):
        self.config = config
        self.memory = create_memory_module(self.config['memory_config'])
        self.llm = create_LLM(config['LLM_config'])
        self.write_time = []
        self.read_time = []

    def reset(self):
        self.memory.reset()
        self.write_time = []
        self.read_time = []

    def response(self, observation, reward, terminated, info, mode, step):
        # if mode == 'ThirdAgent'  or step == 0:
        #     if 'message' in observation:
        #         self.memory.store("{}[|]{}".format(step, observation['message']))
        #         action = {'response': 'No Need Reply.'}  # 这里的action怎么改一下
        #     elif 'question' in observation:
        #         question, time, choices = observation['question'], observation['time'], observation['choices']
        #         memory_context = self.memory.recall('%s (%s)' % (question, time))
        #         prompt = PromptTemplate(
        #                 input_variables=['memory', 'question', 'time' 'choice_A', 'choice_B', 'choice_C', 'choice_D'],
        #                 template=INSTRUCTION_THIRD
        #             ).format(memory = memory_context, question = question, time = time, choice_A = choices['A'], choice_B = choices['B'], choice_C = choices['C'], choice_D = choices['D'])
        #         res = remove_space_and_ent(self.llm.fast_run(prompt))

        #         memory_id = self.memory.retri('{} ({})'.format(question, time))
        #         action = {'response': res, 'memory_index': memory_id}
        #     else:
        #         raise "Agent accepts unknown observations."
        # else:
        if 'message' in observation:
            if isinstance(observation['message'], dict):
                time_01 = time.perf_counter()
                # print("{}[|]'user': {}; 'agent': {}".format(step, observation['message']['user'], observation['message']['agent']))
                self.memory.store("{}[|]'user': {}; 'agent': {}".format(step, observation['message']['user'], observation['message']['agent']))
                # print('yes')
                time_02 = time.perf_counter()
                action = {'response': observation['message']['agent']}  
            else:
                time_01 = time.perf_counter()
                self.memory.store("{}[|]{}".format(step, observation['message']))
                time_02 = time.perf_counter()
                action = {'response': 'No Need Reply'}

            self.write_time.append(time_02  - time_01)

        elif 'question' in observation:
            question, time_, choices = observation['question'], observation['time'], observation['choices']
            time_03 = time.perf_counter()
            memory_context = self.memory.recall('%s (%s)' % (question, time_))
            time_04 = time.perf_counter()

            self.read_time.append(time_04 - time_03)
            # print(choices)
            prompt = PromptTemplate(
                    input_variables=['memory', 'question', 'time' 'choice_A', 'choice_B', 'choice_C', 'choice_D'],
                    template=INSTRUCTION_FIRST
                ).format(memory = memory_context, question = question, time = time_, choice_A = choices['A'], choice_B = choices['B'], choice_C = choices['C'], choice_D = choices['D'])
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": "choice",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "choice": {
                                "type": "string",
                                "description": "Your choice",
                                "enum": ["A", "B", "C", "D"]
                            }
                        },
                        "required": ["choice"],
                        "additionalProperties": False
                    },
                    "strict": True
                }
            }
            res = self.llm.fast_run(prompt, response_format=response_format)
            res = json.loads(res)['choice']
            # print(res)
            memory_id = self.memory.retri('{} ({})'.format(question, time_))
            if memory_id == None:
                action = {'response': res}

            action = {'response': res, 'memory_index': memory_id}
        else:
            raise "Agent accepts unknown observations."
        
        return action
    
    def response_cap(self, observation, reward, terminated, info, mode, step):
        # 因为在target_step_id之后每一步都要进行QA
        if isinstance(observation['message'], dict):
            self.memory.store("{}[|]'user': {}; 'agent': {}".format(step, observation['message']['user'], observation['message']['agent']))
            action = {'response': observation['message']['agent']}  # 这里的action怎么改一下
        else:
            self.memory.store("{}[|]{}".format(step, observation['message']))
            action = {'response': 'No Need Reply'}

        
        if 'question' in observation:
            question, time_, choices = observation['question'], observation['time'], observation['choices']
            memory_context = self.memory.recall('{} ({})'.format(question, time_))
            
            prompt = PromptTemplate(
                    input_variables=['memory', 'question', 'time' 'choice_A', 'choice_B', 'choice_C', 'choice_D'],
                    template=INSTRUCTION_FIRST
                ).format(memory = memory_context, question = question, time = time_, choice_A = choices['A'], choice_B = choices['B'], choice_C = choices['C'], choice_D = choices['D'])
            res = remove_space_and_ent(self.llm.fast_run(prompt))
            action['response'] = res
        
        return action

    

def remove_space_and_ent(s):
    return s.replace(" ", "").replace("\n", "")