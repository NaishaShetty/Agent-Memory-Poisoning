from .BaseMemory import BaseMemory
from .memutils import get_word_num, get_truncated_context
import json
import faiss, torch, math, random, re
from transformers import AutoModel, AutoTokenizer
import sys
sys.path.append('..')
from benchutils import create_LLM

def remove_space_and_ent(s):
    return s.replace(" ", "").replace("\n", "").replace('*', '')

class GAMemory(BaseMemory):
    """
    Memory mechanism of Generative Agents.
    """
    def __init__(self, config) -> None:
        super().__init__(config)

        self.current_time = None
        self.accmulated_importance = 0

        self.max_words = self.config['args']['max_words']
        self.recency_decay = self.config['args']['recency_decay']
        self.recency_coef = self.config['args']['recency_coef']
        self.importance_coef = self.config['args']['importance_coef']
        self.relevance_coef = self.config['args']['relevance_coef']
        self.reflect_threshold = self.config['args']['reflect_threshold']
        self.reflect_max_words = self.config['args']['reflect_max_words']
        self.reflect_question_num = self.config['args']['reflect_question_num']
        self.reflect_retrieval_topk = self.config['args']['reflect_retrieval_topk']
        self.reflect_insight_num = self.config['args']['reflect_insight_num']
        self.embedding_dim = self.config['args']['embedding_dim']
        self.reflector_LLM_config = self.config['args']['reflector_LLM_config']
        self.importance_LLM_config = self.config['args']['importance_LLM_config']

        model_path = self.config['args']['embedding_model_path']
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModel.from_pretrained(model_path)
        
        self.memorystore = {'text': [], 'source':[], 'importance':[], 'create_time': [], 'recency_time': []}
        self.vectorstore = faiss.IndexFlatIP(self.embedding_dim)
        self.reflector = create_LLM(self.reflector_LLM_config)
        self.important_judge = create_LLM(self.importance_LLM_config)
    
    def __add_memorystore__(self, observation, source, importance, time):
        self.memorystore['text'].append(observation)
        self.memorystore['source'].append(source)
        self.memorystore['importance'].append(importance)
        self.memorystore['create_time'].append(time)
        self.memorystore['recency_time'].append(time)

    def __convert_strings_to_vectors__(self,s):
        res = self.tokenizer(s, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            embeddings = self.model(**res).last_hidden_state[:, -1, :]
            norms = torch.linalg.norm(embeddings,dim=1,keepdim = True)
            embedding_normalized = embeddings / norms

        return embedding_normalized.numpy()

    def __get_size__(self):
        return len(self.memorystore['text'])

    def __is_empty__(self):
        return self.__get_size__() == 0

    def __calculate_importance__(self, observation):
        prompt = """
On the scale of 1 to 10, where 1 is purely unimportant and 10 is extremely important, rate the likely importance of the following piece of memory.
Memory: {}
Your should just output the rating number between from 1 to 10, and do not output any other texts.""" .format(observation)
        # score_response_format = {
        #     "type": "json_schema",
        #     "json_schema": {
        #         "name": "rating",
        #         "schema": {
        #             "type": "object",
        #             "properties": {
        #                 "rating": {
        #                     "type": "number",
        #                     "description": "Your rating",
        #                     "exclusiveMinimum": 1,
        #                     "exclusiveMaximum": 10
        #                 }
        #             },
        #             "required": ["rating"],
        #             "additionalProperties": False
        #         },
        #         "strict": True
        #     }
        # }
        score_response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "rating",
                "schema": {
                    "type": "object",
                    "properties": {
                        "rating": {
                            "type": "number",
                            "description": "Your rating"
                        }
                    },
                    "required": ["rating"],
                    "additionalProperties": False
                },
                "strict": True
            }
        }
        importance = remove_space_and_ent(self.important_judge.fast_run(prompt, response_format = score_response_format))
        importance = json.loads(importance)['rating']
        # print(importance)
        if importance < 1.0:
            importance = 1.0
        if importance > 10.0:
            importance = 10.0
        assert 1.0 <= float(importance) <= 10.0
        return float(importance)/10.0

    def __get_recency_list__(self):
        return [self.recency_decay ** (self.current_time - rt) for rt in self.memorystore['recency_time']]

    def __get_importance_list__(self):
        return self.memorystore['importance']

    def __get_relevance_list__(self, observation):

        query_emb = self.__convert_strings_to_vectors__(observation)
        dis, idx = self.vectorstore.search(query_emb,self.__get_size__())
        relevance_list = list(zip(dis[0],idx[0]))
        sorted_relevance_list = sorted(relevance_list, key=lambda x: x[1], reverse=False)
        return [rel for rel, mid in sorted_relevance_list]

    def __get_recursion_context__(self, mid):
        source = self.memorystore['source'][mid]
        text = self.memorystore['text'][mid]
        if not source:
            return text
    
        return '{} [{}]'.format(text, ';'.join([self.__get_recursion_context__(submid) for submid in source]))

    def __retention__(self, mid) -> None:
        self.memorystore['recency_time'][mid] = self.current_time

    def reset(self):
        self.current_time = None
        self.accmulated_importance = 0
        self.memorystore = {'text': [], 'source':[], 'importance':[], 'create_time': [], 'recency_time': []}
        self.vectorstore.reset()

    def __reflect__(self, importance, observation):
        self.accmulated_importance += importance
        if self.accmulated_importance >= self.reflect_threshold:
            recent_context = ''
            for mid in range(self.__get_size__()-1,-1,-1): 
                tmp = recent_context + '%s\n' % self.memorystore['text'][mid]
                residual_word = self.reflect_max_words - get_word_num(tmp)
                if residual_word < 0:
                    recent_context =  ' '.join((recent_context + self.memorystore['text'][mid]).split(' ')[:self.reflect_max_words])
                    print(get_word_num(recent_context))
                    break
                recent_context = tmp
            self.accmulated_importance = 0

            # The process below is the reflection process of Generative Agent.
            
            question_prompt = """
Information: {}
Given only the information above, what are 3 most salient highlevel questions we can answer about the subjects in the statements?
Please output each question in a single line, and do not output any other messages.""".format(recent_context)
            res = self.reflector.fast_run(question_prompt)
            question_list = [q for q in res.splitlines() if q.strip() != '']
            assert len(question_list) == 3
            
            ret_context = ''
            ret_evidence_list = []
            for question in question_list:
                question_emb = self.__convert_strings_to_vectors__(question)
                dis, idx = self.vectorstore.search(question_emb, self.reflect_retrieval_topk)
                for mid in idx[0]:
                    ret_context += '%s\n' % self.__get_recursion_context__(mid)
                    ret_evidence_list.append(mid)
                    if get_word_num(ret_context) > self.reflect_max_words:
                        ret_context =  ' '.join(ret_context.split(' ')[:self.reflect_max_words])
                        break

            insight_prompt = """
Statements:
{}
What {} high-level insights can you infer from the above statements?
Please output each insight in a single line, and do not output any other messages.
""" .format(ret_context, self.reflect_insight_num)
            res = self.reflector.fast_run(insight_prompt)
            insight_list = [q for q in res.splitlines() if q.strip() != '']

            max_try = 5
            if len(insight_list) != self.reflect_insight_num:
                tries = 0
                while max_try != 0:
                    print('{} tries'.format(tries))
                    res = self.reflector.fast_run(insight_prompt)
                    insight_list = [q for q in res.splitlines() if q.strip() != '']
                    if len(insight_list) == self.reflect_insight_num:
                        max_try = 0
                    else:
                        max_try -= 1

            for insight in insight_list:
                importance = self.__calculate_importance__(observation)
                self.__add_memorystore__(insight, ret_evidence_list , importance, self.current_time)
                self.vectorstore.add(self.__convert_strings_to_vectors__(insight))

    def store(self, observation, time = None) -> None:
        if time is None:
            if self.current_time is None:
                self.current_time = 0
            time = self.current_time + 1
        
        importance = self.__calculate_importance__(observation)

        self.__add_memorystore__(observation, None , importance, time)
        self.vectorstore.add(self.__convert_strings_to_vectors__(observation))

        self.__reflect__(importance, observation)
        
        self.current_time = time
    
    def recall(self, observation) -> object:
        if self.__is_empty__():
            return ''
        
        recency_list = self.__get_recency_list__()
        importance_list = self.__get_importance_list__()
        relevance_list = self.__get_relevance_list__(observation)

        score_list = [
            (self.recency_coef * recency_list[mid] + self.importance_coef * importance_list[mid] + self.relevance_coef * relevance_list[mid], mid)
            for mid in range(self.__get_size__())]
        sorted_score_list = sorted(score_list, key=lambda x: x[0], reverse=True)
        
        memory_context = ''
        for score, mid in sorted_score_list: 
            self.__retention__(mid)
            tmp = memory_context + '%s\n' % self.memorystore['text'][mid]
            residual_word = self.max_words - get_word_num(tmp)
            if residual_word < 0:
                return  ' '.join((memory_context + self.memorystore['text'][mid]).split(' ')[:self.max_words])
            memory_context = tmp
        return memory_context

    # 这里得写一个retri的函数
    def retri(self, observation):
        if self.__is_empty__():
            return ''
        
        recency_list = self.__get_recency_list__()
        importance_list = self.__get_importance_list__()
        relevance_list = self.__get_relevance_list__(observation)

        score_list = [
            (self.recency_coef * recency_list[mid] + self.importance_coef * importance_list[mid] + self.relevance_coef * relevance_list[mid], mid)
            for mid in range(self.__get_size__())]
        sorted_score_list = sorted(score_list, key=lambda x: x[0], reverse=True)
        
        memory_index = []
        for score, mid in sorted_score_list: 
            self.__retention__(mid)
            if self.memorystore['source'][mid] == None:
                memory_index.append(int(self.memorystore['text'][mid].split('[|]')[0]))  # 直接来源于observation
            else:
                for i in self.memorystore['source'][mid]:  # 因为这里会统计信息是直接来自observation还是来自它的总结
                    if i not in memory_index:
                        memory_index.append(i)
            
        return memory_index
        
    def manage(self) -> None:
        pass
    
    def train(self, **kwargs) -> None:
        pass
    

class MemoryBank(BaseMemory):
    """
    Memory mechanism of MemoryBank.
    We consider one step as one day in the original implementation.
    """
    def __init__(self, config) -> None:
        super().__init__(config)

        self.memory_base = {
            'history': {},
            'summary': {},
            'global': ''
        }
        
        self.current_time = None

        self.max_words = self.config['args']['max_words']
        self.use_forget = self.config['args']['use_forget']
        self.embedding_dim = self.config['args']['embedding_dim']
        self.summarizer_LLM_config = self.config['args']['summarizer_LLM_config']

        model_path = self.config['args']['embedding_model_path']
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModel.from_pretrained(model_path)
        
        self.memorystore = [] # (type, date, index, recency_t, memory_strength)
        self.vectorstore = faiss.IndexFlatIP(self.embedding_dim)
        self.summarizer = create_LLM(self.summarizer_LLM_config)
    
    def __get_memory_item__(self, mid):
        type, date, index, recency_t, memory_strength = self.memorystore[mid]
        if type == 'history':
            return self.memory_base['history'][date][index], recency_t, memory_strength
        elif type == 'summary':
            return self.memory_base['summary'][date], recency_t, memory_strength

    def __convert_strings_to_vectors__(self,s):
        # print(s)
        res = self.tokenizer(s, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            embeddings = self.model(**res).last_hidden_state[:, -1, :]
            norms = torch.linalg.norm(embeddings,dim=1,keepdim = True)
            embedding_normalized = embeddings / norms

        return embedding_normalized.numpy()

    def __get_size__(self):
        return len(self.memorystore)

    def __is_empty__(self):
        return self.__get_size__() == 0

    def __get_forgetting_flag__(self, recency_t, memory_strength):
        prob = math.exp(-(self.current_time-recency_t)/5*memory_strength)
        return random.random() > prob

    def __retention__(self, mid) -> None:
        type, date, index, recency_t, memory_strength = self.memorystore[mid]
        self.memorystore[mid] = (type, date, index, self.current_time, memory_strength+1)

    def reset(self) -> None:
        self.memory_base = {
            'history': {},
            'summary': {},
            'global': ''
        }
        
        self.current_time = None
        self.memorystore = []
        self.vectorstore.reset()

    def __summarize_history__(self, history) -> str:
        prompt = "Please summarize the following content as concisely as possible, extracting the main themes and key information. If there are multiple key events, you may summarize them separately. Content:\n"
        prompt += '%s' % '\n'.join(history)
        return self.summarizer.fast_run(prompt)

    def __update_global_memory__(self) -> str:
        prompt = "Please summarize the following content as concisely as possible, extracting the main themes and key information. If there are multiple key events, you may summarize them separately. Content:\n"
        prompt += '%s' % '\n'.join(list(self.memory_base['summary'].values()))
        self.memory_base['global'] = self.summarizer.fast_run(prompt)

    def store(self, observation, time = None) -> None:
        if time is None:
            if self.current_time is None:
                self.current_time = 0
            time = self.current_time + 1
        
            self.memory_base['history'][time] = [observation]
            self.memorystore.append(('history', time, 0, time, 1))
            self.vectorstore.add(self.__convert_strings_to_vectors__(observation))
            
            if time > 1:
                self.memory_base['summary'][self.current_time] = self.__summarize_history__(self.memory_base['history'][self.current_time])
                if self.memory_base['summary'][self.current_time] is None:
                    self.memory_base['summary'][self.current_time] = ' '
                # while self.memory_base['summary'][self.current_time] is None:
                #     self.memory_base['summary'][self.current_time] = self.__summarize_history__(self.memory_base['history'][self.current_time])
                 
                
                self.memorystore.append(('summary', self.current_time, None, self.current_time, 1))
                
                self.vectorstore.add(self.__convert_strings_to_vectors__(self.memory_base['summary'][self.current_time]))
                self.__update_global_memory__()
        else:
            if time not in self.memory_base['history']:
                self.memory_base['history'][time] = []
                if self.current_time is not None:
                    self.memory_base['summary'][self.current_time] = self.__summarize_history__(self.memory_base['history'][self.current_time])
                    self.memorystore.append(('summary', self.current_time, None, self.current_time, 1))
                    self.vectorstore.add(self.__convert_strings_to_vectors__(self.memory_base['summary'][self.current_time]))
                    self.__update_global_memory__()
            self.memory_base['history'][time].append(observation)
            self.memorystore.append(('history', time, 0, time, 1))
            self.vectorstore.add(self.__convert_strings_to_vectors__(observation))
        self.current_time = time

    def recall(self, observation) -> object:
        if self.__is_empty__():
            return ''

        query_emb = self.__convert_strings_to_vectors__(observation)
        dis, idx = self.vectorstore.search(query_emb,self.__get_size__())
        ranking_ids = idx[0]
        memory_context = '%s\n' % self.memory_base['global']
        for mid in ranking_ids:
            new_context, recency_t, memory_strength = self.__get_memory_item__(mid)
            forgetting_flag = self.__get_forgetting_flag__(recency_t, memory_strength)
            if forgetting_flag and self.use_forget:
                continue
            self.__retention__(mid)
            tmp = memory_context + '%s\n' % new_context
            residual_word = self.max_words - get_word_num(tmp)
            if residual_word < 0:
                return  ' '.join((memory_context + new_context).split(' ')[:self.max_words])
            memory_context = tmp
        return memory_context
    
    def retri(self, observation):
        return None
    
    def manage(self) -> None:
        pass
    
    def train(self, **kwargs) -> None:
        pass
    

class MGMemory(BaseMemory):
    """
    Memory mechanism of MemGPT.
    """

    FUNCTION_DESCRIPTIONS = """
----- Funtion Descriptions -----
def memory_retrieval(query: str):
    Description: retrieve query-related information from (external) archival storage, and add the result into working memory.
    Args: query is a string to retrieve relevant information (e.g., 'Alice's name').

def memory_recall(query: str):
    Descripton: retrieve query-related information from (external) recall storage, and add the result into FIFO memory.
    Args: query is a string to retrieve relevant information (e.g., 'Alice's name').

def memory_archive(memory_list: list):
    Description: archive some memory from FIFO memory into (external) archival storage.
    Args: the index list of FIFO memory (e.g., [0, 2, 3]).

def memory_transfer(memory_list: list):
    Description: transfer some memory from FIFO memory into working memory.
    Args: the index list of FIFO memory (e.g., [0, 2, 3]).

def memory_save(memory_list: list):
    Description: archive some memory from working memory into (external) archival storage.
    Args: the index list of working memory (e.g., [0, 2, 3]).
----- Funtion Description End -----
"""
    FEW_SHOTS = """
[EXAMPLE 1]
memory_retrieval('Alice's name')
memory_save([0, 1])
[EXAMPLE 2]
memory_recall('Bob's name')
memory_transfer([0])
[EXAMPLE 3]
memory_archive([0])
[EXAMPLE 4]
No Excuate"""

    def __init__(self, config):
        super().__init__(config)

        self.main_context = {
            'working_context': [],
            'recursive_summary': '',
            'FIFO_queue': []
        }

        self.archival_storage = self.ArchivalStorage(config['args']['archival_storage_config'])
        self.reacall_storage = self.RecallStorage(config['args']['recall_storage_config'])

        self.max_words = self.config['args']['max_words']
        self.working_memory_maximum = self.config['args']['working_memory_maximum']
        self.warning_count = int(self.max_words * self.config['args']['warning_threshold'])
        self.flush_count = int(self.max_words * self.config['args']['flush_threshold'])
        self.flush_evicted_count = int(self.max_words * self.config['args']['flush_evicted_percentage'])

        self.LLM_processor = create_LLM(self.config['args']['LLM_processor_config'])

    def __get_current_memory_context__(self):
        memory_context = '\n'.join(self.main_context['working_context'])
        memory_context += self.main_context['recursive_summary']
        memory_context += '\n'.join(self.main_context['FIFO_queue'])
        return memory_context
    
    def __get_current_memory_prompt(self):
        prompt = 'Total Capacity: %s words\n' % self.max_words
        prompt = 'Working Memory(capacity %s words):\n' % self.working_memory_maximum
        for wid, wtext in enumerate(self.main_context['working_context']):
            prompt += '[%d] %s\n' % (wid, wtext)
        prompt += 'Recursive Memory Summary:\n'
        prompt += '%s\n' % self.main_context['recursive_summary']
        prompt += 'FIFO Memory:\n'
        for fid, ftext in enumerate(self.main_context['FIFO_queue']):
            prompt += '[%d] %s\n' % (fid, ftext)

        return prompt

    def __get_current_memory_count__(self):
        return get_word_num(self.__get_current_memory_context__())

    def __flush_queue__(self):
        for mid in range(len(self.main_context['FIFO_queue'])):
            flush_context = '\n'.join(self.main_context['FIFO_queue'][:mid+1])
            if get_word_num(flush_context) >= self.flush_count:
                break
        prompt = 'Recursive Summary: %s\n' % self.main_context['recursive_summary']
        prompt += 'Recent Memory: %s\n' % flush_context
        prompt += 'Please update the Recursive Summary based on Recursive Summary and summarizing Recent Memory.\n'
        prompt += 'Just output the new Recursive Summary, without any other messages.'

        self.main_context['recursive_summary'] = self.LLM_processor.fast_run(prompt)
        self.reacall_storage.add_list(self.main_context['FIFO_queue'][:mid+1])
        if mid+1 == len(self.main_context['FIFO_queue']):
            self.main_context['FIFO_queue'] = []
        else:
            self.main_context['FIFO_queue'] = self.main_context['FIFO_queue'][mid+1:]

    def __truncate_working_context__(self):
        if len(self.main_context['working_context']) == 0:
            return 
        for mid in range(len(self.main_context['working_context'])):
            kept_working_context = '\n'.join(self.main_context['working_context'][:mid+1])
            if get_word_num(kept_working_context) >= self.flush_count:
                break
        self.main_context['working_context'] = self.main_context['working_context'][:mid]

    def __memory_retrieval__(self, query):
        retrieval_list = self.archival_storage.retrieve_list(query)
        self.main_context['working_context'] += retrieval_list
        self.__truncate_working_context__()
        return True
    
    def __memory_recall__(self, query):
        retrieval_list = self.reacall_storage.retrieve_list(query)
        self.main_context['FIFO_queue'] += retrieval_list
        return True

    def __memory_archive__(self, memory_list):
        try:
            text_list = [self.main_context['FIFO_queue'][mid] for mid in memory_list]
            self.reacall_storage.add_list(text_list)
            for mid in sorted(memory_list, reverse=True):
                self.main_context['FIFO_queue'].pop(mid)
            return True
        except Exception as e:
            print('Memory Archieve Function Error:',e)
            return False

    def __memory_transfer__(self, memory_list):
        try:
            text_list = [self.main_context['FIFO_queue'][mid] for mid in memory_list]
            self.main_context['working_context'] += text_list
            for mid in sorted(memory_list, reverse=True):
                self.main_context['FIFO_queue'].pop(mid)
            return True
        except Exception as e:
            print('Memory Transfer Function Error:',e)
            return False

    def __memory_save__(self, memory_list):
        try:
            text_list = [self.main_context['working_context'][mid] for mid in memory_list]
            self.archival_storage.add_list(text_list)
            for mid in sorted(memory_list, reverse=True):
                self.main_context['working_context'].pop(mid)
            return True
        except Exception as e:
            print('Memory Save Function Error:',e)
            return False
    
    def __parse_excuate_function__(self, res):
        if res.strip() == 'No Excuate':
            print('No Execuation Chosen.')
            return
        excuate_list = [q for q in res.splitlines() if q.strip() != '']
        for exe_text in excuate_list:
            pattern = r'(\w+)\((.*?)\)'
            match = re.search(pattern, exe_text)
            if match:
                try:
                    func_name, func_args = match.group(1), match.group(2)
                    execuate_command = 'self.__%s__(%s)' % (func_name, func_args)
                    signal = eval(execuate_command)
                    print('Execuate Function [%s(%s)]: %s' % (func_name, func_args, signal))
                except Exception as e:
                    print('Fail to ExecuateFunction [%s(%s)]: %s'% (func_name, func_args, e))
            else:
                print('Execuate Parse Fail.')

    def __trigger_function_call__(self, observation):
        warning_flag = self.__get_current_memory_count__() > self.warning_count

        prompt = 'Query: %s\n' % observation
        prompt += self.__get_current_memory_prompt()
        prompt += self.FUNCTION_DESCRIPTIONS
        prompt += 'Please choose some of the following functions to execute, and you should output each executed function in a single line.\n'
        if warning_flag:
            prompt += 'We suggest to execute memory_archive or memory_transfer.\n'
        prompt += 'If you do not execute any functions, just output No Excuate.\n'
        prompt += 'Your output should follow the following format in the examples, and do not output other messages.\n'
        prompt += self.FEW_SHOTS

        res = self.LLM_processor.fast_run(prompt)

        self.__parse_excuate_function__(res)
        
    def reset(self) -> None:
        self.main_context = {
            'working_context': [],
            'recursive_summary': '',
            'FIFO_queue': []
        }

        self.archival_storage.reset()
        self.reacall_storage.reset()

    def store(self, observation) -> None:
        self.main_context['FIFO_queue'].append(observation)
        if self.__get_current_memory_count__() > self.flush_count:
            self.__flush_queue__()
    
    def recall(self, observation) -> object:
        self.__trigger_function_call__(observation)
        return self.__get_current_memory_context__()

    def manage(self) -> None:
        raise NotImplementedError()
    
    def train(self, **kwargs) -> None:
        pass

    def retri(self, observation):
        return None

    class ArchivalStorage():
        def __init__(self, config):
            self.config =  config

            self.embedding_dim = config['embedding_dim']
            self.retrieval_num = config['retrieval_num']
            model_path = self.config['embedding_model_path']
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            self.model = AutoModel.from_pretrained(model_path)

            self.memorystore = []
            self.vectorstore = faiss.IndexFlatIP(self.embedding_dim)

        def __convert_strings_to_vectors__(self,s):
            res = self.tokenizer(s, return_tensors="pt", truncation=True, max_length=512)
            with torch.no_grad():
                embeddings = self.model(**res).last_hidden_state[:, -1, :]
                norms = torch.linalg.norm(embeddings,dim=1,keepdim = True)
                embedding_normalized = embeddings / norms

            return embedding_normalized.numpy()

        def reset(self):
            self.memorystore = []
            self.vectorstore.reset()
        
        def add_list(self, memory_list):
            for memory in memory_list:
                self.memorystore.append(memory)
                mem_encode = self.__convert_strings_to_vectors__(memory)
                self.vectorstore.add(mem_encode)
        
        def is_empty(self):
            return len(self.memorystore) == 0

        def retrieve_list(self, query):
            if self.is_empty():
                return ''
            query_emb = self.__convert_strings_to_vectors__(query)
            dis, idx = self.vectorstore.search(query_emb,self.retrieval_num)
            ranking_ids = idx[0]
            memory_list = []
            for mid in ranking_ids: 
                memory_list.append(self.memorystore[mid])
            return memory_list

    class RecallStorage():
        def __init__(self, config):
            self.config =  config

            self.embedding_dim = config['embedding_dim']
            self.retrieval_num = config['retrieval_num']
            model_path = self.config['embedding_model_path']
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            self.model = AutoModel.from_pretrained(model_path)

            self.memorystore = []
            self.vectorstore = faiss.IndexFlatIP(self.embedding_dim)

        def __convert_strings_to_vectors__(self,s):
            res = self.tokenizer(s, return_tensors="pt", truncation=True, max_length=512)
            with torch.no_grad():
                embeddings = self.model(**res).last_hidden_state[:, -1, :]
                norms = torch.linalg.norm(embeddings,dim=1,keepdim = True)
                embedding_normalized = embeddings / norms

            return embedding_normalized.numpy()

        def reset(self):
            self.memorystore = []
            self.vectorstore.reset()
        
        def add_list(self, memory_list):
            for memory in memory_list:
                self.memorystore.append(memory)
                mem_encode = self.__convert_strings_to_vectors__(memory)
                self.vectorstore.add(mem_encode)

        def is_empty(self):
            return len(self.memorystore) == 0

        def retrieve_list(self, query):
            if self.is_empty():
                return ''
            query_emb = self.__convert_strings_to_vectors__(query)
            dis, idx = self.vectorstore.search(query_emb,self.retrieval_num)
            ranking_ids = idx[0]
            memory_list = []
            for mid in ranking_ids: 
                memory_list.append(self.memorystore[mid])
            return memory_list

class SCMemory(BaseMemory):
    """
    Memory mechanism of SCM.
    """
    def __init__(self, config):
        super().__init__(config)

        self.current_time = None
        self.memory_stream = {
            'history': [],
            'summary': [],
            'recency_time': []
        }

        self.max_words = self.config['args']['max_words']
        self.embedding_dim = self.config['args']['embedding_dim']
        self.recency_decay = self.config['args']['recency_decay']
        self.retrieval_top_k = self.config['args']['retrieval_top_k']
        self.flash_memory_T = self.config['args']['flash_memory_T']
        self.summarizer_LLM_config = self.config['args']['summarizer_LLM_config']
        self.controller_LLM_config = self.config['args']['controller_LLM_config']

        model_path = self.config['args']['embedding_model_path']
        
        self.tokenizer = AutoTokenizer.from_pretrained("/data/tanhaoran/LocalLLM/multilingual-e5-small")
        self.model = AutoModel.from_pretrained("/data/tanhaoran/LocalLLM/multilingual-e5-small")
        
        self.vectorstore = faiss.IndexFlatIP(self.embedding_dim)
        self.summarizer = create_LLM(self.summarizer_LLM_config)
        self.controller = create_LLM(self.controller_LLM_config)

    def __get_size__(self):
        return len(self.memory_stream['history'])

    def __is_empty__(self):
        return self.__get_size__() == 0

    def __summarize_observation__(self, observation):
        prompt = """
Observation: %s
Please provide a summary of the above observation in one sentence, while preserving key information as much as possible. 
You should just output the summary, without any other messages.""" % observation
        return self.summarizer.fast_run(prompt)

    def __convert_strings_to_vectors__(self,s):
        res = self.tokenizer(s, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            embeddings = self.model(**res).last_hidden_state[:, -1, :]
            norms = torch.linalg.norm(embeddings,dim=1,keepdim = True)
            embedding_normalized = embeddings / norms

        return embedding_normalized.numpy()

    def __retention__(self, mid) -> None:
        self.memory_stream['recency_time'][mid] = self.current_time
    
    def __self_ask_require_activation__(self, observation, flash_memory):
        prompt = """
Query: %s
Memory: %s
Given the above memory, determine whether it requires other information to generate correct response for the query.
You should just output YES or NO, without any other messages.""" % (observation, flash_memory)
        res = self.controller.fast_run(prompt).strip()
        if res == 'YES':
            return True
        elif res == 'NO':
            return False
        else:
            raise "Activation Self-ask Parse Error: %s" % res

    def __self_ask_require_summary__(self, observation, activation_summary, flash_memory):
        prompt = """
Query: %s
Memory: %s
%s
Based on the memory, can the query be responsed correctly?
You should just output YES or NO, without any other messages.""" % (observation, activation_summary, flash_memory)
        res = self.controller.fast_run(prompt).strip()
        if res == 'YES':
            return True
        elif res == 'NO':
            return False
        else:
            raise "Summary Self-ask Parse Error: %s" % res

    def __get_recency_list__(self):
        return [self.recency_decay ** (self.current_time - rt) for rt in self.memory_stream['recency_time']]
    
    def __get_relevance_list__(self, observation):
        query_emb = self.__convert_strings_to_vectors__(observation)
        dis, idx = self.vectorstore.search(query_emb,self.__get_size__())
        relevance_list = list(zip(dis[0],idx[0]))
        sorted_relevance_list = sorted(relevance_list, key=lambda x: x[1], reverse=False)
        return [rel for rel, mid in sorted_relevance_list]

    def __retrieve__(self, observation):
        recency_list = self.__get_recency_list__()
        relevance_list = self.__get_relevance_list__(observation)

        score_list = [
            (recency_list[mid] + relevance_list[mid], mid)
            for mid in range(self.__get_size__())]
        sorted_score_list = sorted(score_list, key=lambda x: x[0], reverse=True)

        activation_memory_list = []
        for score, mid in sorted_score_list[:self.retrieval_top_k]: 
            self.__retention__(mid)
            activation_memory_list.append(mid)
        return activation_memory_list

    def __get_flash_memory__(self):
        return '\n'.join([self.memory_stream['history'][mid] for mid in range(max(0,self.__get_size__()-2), self.__get_size__())])

    def reset(self) -> None:
        self.current_time = None
        self.memory_stream = {
            'history': [],
            'summary': [],
            'recency_time': []
        }
        
        self.vectorstore.reset()

    def store(self, observation, time = None) -> None:
        if time is None:
            if self.current_time is None:
                self.current_time = 0
            time = self.current_time + 1

        self.memory_stream['history'].append(observation)
        self.memory_stream['summary'].append(self.__summarize_observation__(observation))
        self.memory_stream['recency_time'].append(time)

        mem_encode = self.__convert_strings_to_vectors__(observation)
        self.vectorstore.add(mem_encode)

        self.current_time = time

    def recall(self, observation) -> object:
        if self.__is_empty__():
            return ''
        
        flash_memory = self.__get_flash_memory__()
        if not self.__self_ask_require_activation__(observation, flash_memory):
            return get_truncated_context(flash_memory,self.max_words)
        else:
            activation_memory_list = self.__retrieve__(observation)
            print(activation_memory_list)
            activation_summary = '\n'.join([self.memory_stream['summary'][mid] for mid in activation_memory_list])
            if self.__self_ask_require_summary__(observation, activation_summary, flash_memory):
                memory_context = '%s\n%s' % (activation_summary, flash_memory)
            else:
                activation_history = '\n'.join([self.memory_stream['history'][mid] for mid in activation_memory_list])
                memory_context = '%s\n%s' % (activation_history, flash_memory)
            return get_truncated_context(memory_context, self.max_words)
    
    def retri(self, observation):
        return None
            
    def manage(self) -> None:
        pass
    
    def train(self, **kwargs) -> None:
        pass

class RFMemory(BaseMemory):
    """
    Memory mechanism of Reflexion.
    """

    REFLECTION_EXAMPLE = """
Question: The Rome Protocols were signed by three Prime Ministers one of which was assassinated as part of what?
Thought 1: I need to search Rome Protocols, find the three Prime Ministers, then find what they were assassinated as part of.
Action 1: Search[Rome Protocols]
Observation 1: The Rome Protocols were a series of three international agreements concluded in Rome on 17 March 1934 between the governments of Austria, Hungary and Italy. They were signed by Italian Prime Minister Benito Mussolini, Austrian Chancellor Engelbert Dollfuss and Hungarian Prime Minister Gyula Gömbös. All of the protocols went into effect on 12 July 1934 and were registered in League of Nations Treaty Series on 12 December 1934.
Thought 2: The three Prime Ministers were Benito Mussolini, Engelbert Dollfuss, and Gyula Gömbös. I need to search Benito Mussolini and find what he was assassinated as part of.
Action 2: Search[Benito Mussolini]
Observation 2: Benito Amilcare Andrea Mussolini (UK:  MU(U)SS-ə-LEE-nee, US:  MOOSS-, Italian: [beˈniːto aˈmilkare anˈdrɛːa mussoˈliːni]; 29 July 1883 – 28 April 1945) was an Italian politician and journalist who founded and led the National Fascist Party (PNF). He was Prime Minister of Italy from the March on Rome in 1922 until his deposition in 1943, as well as "Duce" of Italian fascism from the establishment of the Italian Fasces of Combat in 1919 until his summary execution in 1945 by Italian partisans. As dictator of Italy and principal founder of fascism, Mussolini inspired and supported the international spread of fascist movements during the inter-war period.Mussolini was originally a socialist politician and a journalist at the Avanti! newspaper. In 1912, he became a member of the National Directorate of the Italian Socialist Party (PSI), but he was expelled from the PSI for advocating military intervention in World War I, in opposition to the party's stance on neutrality. In 1914, Mussolini founded a new journal, Il Popolo d'Italia, and served in the Royal Italian Army during the war until he was wounded and discharged in 1917. Mussolini denounced the PSI, his views now centering on Italian nationalism instead of socialism, and later founded the fascist movement which came to oppose egalitarianism and class conflict, instead advocating "revolutionary nationalism" transcending class lines. On 31 October 1922, following the March on Rome (28–30 October), Mussolini was appointed prime minister by King Victor Emmanuel III, becoming the youngest individual to hold the office up to that time. After removing all political opposition through his secret police and outlawing labor strikes, Mussolini and his followers consolidated power through a series of laws that transformed the nation into a one-party dictatorship. Within five years, Mussolini had established dictatorial authority by both legal and illegal means and aspired to create a totalitarian state. In 1929, Mussolini signed the Lateran Treaty with the Holy See to establish Vatican City.
Mussolini's foreign policy aimed to restore the ancient grandeur of the Roman Empire by expanding Italian colonial possessions and the fascist sphere of influence. In the 1920s, he ordered the Pacification of Libya, instructed the bombing of Corfu over an incident with Greece, established a protectorate over Albania, and incorporated the city of Fiume into the Italian state via agreements with Yugoslavia. In 1936, Ethiopia was conquered following the Second Italo-Ethiopian War and merged into Italian East Africa (AOI) with Eritrea and Somalia. In 1939, Italian forces annexed Albania. Between 1936 and 1939, Mussolini ordered the successful Italian military intervention in Spain in favor of Francisco Franco during the Spanish Civil War. Mussolini's Italy initially tried to avoid the outbreak of a second global war, sending troops at the Brenner Pass to delay Anschluss and taking part in the Stresa Front, the Lytton Report, the Treaty of Lausanne, the Four-Power Pact and the Munich Agreement. However, Italy then alienated itself from Britain and France by aligning with Germany and Japan. Germany invaded Poland on 1 September 1939, resulting in declarations of war by France and the UK and the start of World War II.
On 10 June 1940, Mussolini decided to enter the war on the Axis side. Despite initial success, the subsequent Axis collapse on multiple fronts and eventual Allied invasion of Sicily made Mussolini lose the support of the population and members of the Fascist Party. As a consequence, early on 25 July 1943, the Grand Council of Fascism passed a motion of no confidence in Mussolini; later that day King Victor Emmanuel III dismissed him as head of government and had him placed in custody, appointing Pietro Badoglio to succeed him as Prime Minister. After the king agreed to an armistice with the Allies, on 12 September 1943 Mussolini was rescued from captivity in the Gran Sasso raid by German paratroopers and Waffen-SS commandos led by Major Otto-Harald Mors. Adolf Hitler, after meeting with the rescued former dictator, then put Mussolini in charge of a puppet regime in northern Italy, the Italian Social Republic (Italian: Repubblica Sociale Italiana, RSI), informally known as the Salò Republic, causing a civil war. In late April 1945, in the wake of near total defeat, Mussolini and his mistress Clara Petacci attempted to flee to Switzerland, but both were captured by Italian communist partisans and summarily executed by firing squad on 28 April 1945 near Lake Como. The bodies of Mussolini and his mistress were then taken to Milan, where they were hung upside down at a service station to publicly confirm their demise.
Thought 3: Benito Mussolini was assassinated as part of the collapse of the Axis powers during World War II. So the Rome Protocols were signed by three Prime Ministers one of which was assassinated as part of World War II.
Action 3: Finish[World War II]

Reflection: I searched one of the prime ministers involved in the signing, then attemted to answer right away. I should have searched each of the prime ministers, then looked up 'death' on each of their pages in order to get more information before answering.
"""

    def __init__(self, config):
        super().__init__(config)

        self.memory_reflection = ''

        self.max_words = self.config['args']['max_words']
        self.train_config = self.config['train_config']

        self.reflector = create_LLM(self.config['reflector_LLM_config'])

        self.memory_list = []

    def reset(self, reset_reflection=False) -> None:
        self.memory_list = []
        if reset_reflection:
            self.memory_reflection = ''

    def __reflection__(self, last_trial):
        prompt = """
Past reflection result: %s
Previous trial: %s
You are an advanced agent that can improve based on self refection. You have been given the previous trial in which you have interacted with the environment.
Based on the past reflection result and the previous trial, please generate a new reflection text.
You may diagnose a possible reason for failure and devise a new, concise, high level plan that aims to mitigate the same failure. Use complete sentences.  
Example: %s
You should just output the text of your reflection, without any other messages.""" % ( self.memory_reflection,self.REFLECTION_EXAMPLE, last_trial)
        res = self.reflector.fast_run(prompt)
        self.memory_reflection = res

    def store(self, observation) -> None:
        self.memory_list.append(observation)
    
    def recall(self, observation) -> object:
        if self.memory_reflection:
            memory_context =  '%s\n' % self.memory_reflection
        else:
            memory_context = ''
        
        memory_context += '\n'.join(self.memory_list)
        return ' '.join(memory_context.split(' ')[:self.max_words])
    
    def retri(self, observation):
        return None
    
    def manage(self) -> None:
        raise NotImplementedError()
    
    def train(self, **kwargs) -> None:
        agent, env = kwargs['agent'], kwargs['env']
        for i in range(self.train_config['trajectory_num']):
            agent.reset()
            observation, reward, terminated, info = env.reset_train()

            while not terminated:
                action = agent.response(observation, reward, terminated, info)
                observation, reward, terminated, info = env.step(action)
            self.__reflection__('\n'.join(self.memory_list))
            print(self.memory_reflection)

class FullMemory(BaseMemory):
    """
    Memory mechanism with full storage and recalling.
    """
    def __init__(self, config) -> None:
        super().__init__(config)

        self.max_words = self.config['args']['max_words']
        self.memory_list = []
    
    def reset(self):
        self.memory_list = []

    def store(self, observation) -> None:
        self.memory_list.append(observation)
    
    def recall(self, observation) -> object:
        memory_context = '\n'.join(self.memory_list)
        return ' '.join(memory_context.split(' ')[:self.max_words])
    
    def retri(self, observation):
        memory_index = []
        for memory in self.memory_list:
            memory_index.append(int(memory.split('[|]')[0]))
        return memory_index
    
    def manage(self) -> None:
        pass
    
    def train(self, **kwargs) -> None:
        pass

class RetrievalMemory(BaseMemory):
    """
    Memory mechanism with vanilla retrieval mechanism (vanilla RAG), a.k.a, long-term memory.
    """
    def __init__(self, config) -> None:
        super().__init__(config)

        self.max_words = self.config['args']['max_words']
        self.embedding_dim = self.config['args']['embedding_dim']

        model_path = self.config['args']['embedding_model_path']
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModel.from_pretrained(model_path)
        
        self.memorystore = []
        self.vectorstore = faiss.IndexFlatIP(self.embedding_dim)

    def reset(self):
        self.memorystore = []
        self.vectorstore.reset()
    
    def __convert_strings_to_vectors__(self,s):
        res = self.tokenizer(s, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            embeddings = self.model(**res).last_hidden_state[:, -1, :]
            norms = torch.linalg.norm(embeddings,dim=1,keepdim = True)
            embedding_normalized = embeddings / norms

        return embedding_normalized.numpy()

    def store(self, observation) -> None:
        self.memorystore.append(observation)
        mem_encode = self.__convert_strings_to_vectors__(observation)
        # print("Expected dimension (Faiss index):", self.vectorstore.d)
        # print("Actual vector dimension:", mem_encode.shape)
        self.vectorstore.add(mem_encode)

    def is_empty(self):
        return len(self.memorystore) == 0
    
    def recall(self, observation) -> object:
        if self.is_empty():
            return ''
        query_emb = self.__convert_strings_to_vectors__(observation)
        dis, idx = self.vectorstore.search(query_emb,len(self.memorystore))
        ranking_ids = idx[0]
        memory_context = ''
        for mid in ranking_ids: 
            tmp = memory_context + '%s\n' % self.memorystore[mid]
            residual_word = self.max_words - get_word_num(tmp)
            if residual_word < 0:
                return  ' '.join((memory_context + self.memorystore[mid]).split(' ')[:self.max_words])
            memory_context = tmp
        return memory_context
    
    def retri(self, observation):
        if self.is_empty():
            return []
        query_emb = self.__convert_strings_to_vectors__(observation)
        dis, idx = self.vectorstore.search(query_emb,len(self.memorystore))
        ranking_ids = idx[0]
        memory_index = []
        memory_context = ''
        for mid in ranking_ids: 
            tmp = memory_context + '%s\n' % self.memorystore[mid]
            memory_index.append(int(self.memorystore[mid].split('[|]')[0]))
            residual_word = self.max_words - get_word_num(tmp)
            if residual_word < 0:
                # return  ' '.join((memory_context + self.memorystore[mid]).split(' ')[:self.max_words])
                return memory_index
            memory_context = tmp
        return memory_index[:10]
    
    def manage(self) -> None:
        pass
    
    def train(self, **kwargs) -> None:
        pass

class RecentMemory(BaseMemory):
    """
    Memory mechanism with the latest observations.
    """
    def __init__(self, config) -> None:
        super().__init__(config)

        self.max_words = self.config['args']['max_words']
        self.memory_list = []
    
    def reset(self):
        self.memory_list = []

    def store(self, observation) -> None:
        self.memory_list.append(observation)
    
    def recall(self, observation) -> object:
        memory_context = '\n'.join(self.memory_list)
        return ' '.join(memory_context.split(' ')[-self.max_words:])
    
    def retri(self, observation):
        memory_index = []
        for memory in self.memory_list:
            memory_index.append(int(memory.split('[|]')[0]))
        return memory_index
    
    def manage(self) -> None:
        pass
    
    def train(self, **kwargs) -> None:
        pass