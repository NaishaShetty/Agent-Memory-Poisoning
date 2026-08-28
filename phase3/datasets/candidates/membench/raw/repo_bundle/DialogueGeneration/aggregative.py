import json
import numpy as np
import sys
sys.path.append('..')
from utils import chatgpt, TimeClock, formulate_QA, rewrite_message_event, rewrite_message_role
import string

outpath_pre = '../OutData/ThirdAgent/LowLevel/'

trajectory_per_graph = 1


def generate_aggr_role_04a(graph_list):
    key_features = ['age', 'height', 'birthday', 'hometown', 'work_location', 'education']
    question_num = 1

    def get_QA_info(whole_message_str, aggr_attr_k):
        prompt = '[User Information] {}\n'.format('\n'.join(whole_message_str))
        prompt += 'Based on the above user information, for the aspect of {}, please generate a counting question starting with "How many people...?", in a casual first-person style.\n'.format(aggr_attr_k)
        prompt += 'Only output the generated question, do not provide any other descriptive information.\n'
        prompt += 'Example output: How many people are aged 35 or below?'

        question = chatgpt(prompt)

        prompt = '[Question] {}\n'.format(question)
        prompt += 'Please modify the above question into a judgment question for an individual, for example, change "How many people are aged 35 or below?" to "Is his age 35 or below?"\n'
        prompt += 'Only output the modified question, do not provide any other descriptive information.\n'
        prompt += 'Example output: Is his age 35 or below?'

        question_single = chatgpt(prompt)

        ans_count = 0
        for m in whole_message_str:
            prompt = '[User Information] {}\n'.format(m)
            prompt += '[Question] {}\n'.format(question_single)
            prompt += 'Please answer the question based on the user information. If yes, output 1; if no, output 0; if unable to judge, output 2.\n'
            prompt += 'Please note the difference between "above" and "inclusive", for example, "above 35" means older than 35, while "35 or below" includes 35.\n'
            prompt += 'Please note that if not specified, the first half of the year refers to January to June, and the second half refers to July to December.\n'
            prompt += 'Only output the corresponding number of the answer, do not output any other descriptions or explanations, and do not include phrases like "output:".\n'
            prompt += 'Example output: 1'

            ans_single = chatgpt(prompt)
            max_try = 0
            while ans_single not in ['0', '1', '2']:
                print("Single Answer Parse Error: {}".format(ans_single))
                ans_single = chatgpt(prompt)
                if max_try >= 10:
                    ans_single = 0
            if ans_single == '1':
                ans_count += 1
            if ans_single == '2':
                return None, None
        answer = '{} people'.format(ans_count)
        print(question, answer)

        return question, answer

    def generate_single(graph):
        time_clock = TimeClock()
        charact = graph['user_profile']['character']
        message_list = []
        noise_message_list = []
        question_list = []

        role_list = graph['relation_profiles'] + graph['colleague_profiles']
        aggr_attrs = np.random.choice(key_features, size=question_num, replace=False)
        for qid, aggr_attr_k in enumerate(aggr_attrs):
            whole_message_str = []
            for role in role_list:
                r = role['relationship']
                v = role[aggr_attr_k]
                n = role['name']
                g = 'his'
                if role['gender'] == 'Female':
                    g= 'her'

                text = rewrite_message_role("{} is my {}, and {} {} is {}.".format(n, r, g, aggr_attr_k, v), charact)
                whole_message_str.append(text)
                message_list.append({
                    'rel': r,
                    'name': n,
                    'attr': (aggr_attr_k, v),
                    'message': text,
                    'time': time_clock.get_current_time(),
                    'place': graph['user_profile']['work_location']
                })
                time_clock.update_time()

            noise_attrs_list = np.random.choice(list(role_list[0].keys()), size=1, replace=False)
            for noise_attr in noise_attrs_list:
                if noise_attr not in aggr_attrs:
                    for role in role_list:
                        r = role['relationship']
                        v = role[noise_attr]
                        n = role['name']
                        g = 'his'
                        if role['gender'] == 'Female':
                            g= 'her'

                        text = rewrite_message_role("{} is my {}, and {} {} is {}.".format(n, r, g, noise_attr, v), charact)
                        message_list.append({
                            'rel': r,
                            'name': n,
                            'attr': (noise_attr, v),
                            'message': text,
                            'time': time_clock.get_current_time(),
                            'place': graph['user_profile']['work_location']
                        })
                        time_clock.update_time()

            question, answer = get_QA_info(whole_message_str, aggr_attr_k)
            if question is None:
                question, choices, ground_truth = '[ERRORQ]', '[ERRORC]', '[ERRORG]'
            else:
                question, choices, ground_truth = formulate_QA(question, answer)
            question_list.append({
                'qid': qid,
                'question': question,
                'answer': answer,
                'target_step_id': [qid * len(role_list) + k for k in range(len(role_list))],
                'choices': choices,
                'ground_truth': ground_truth,
                'time': time_clock.get_current_time()
            })
            time_clock.update_time()

        message_list = [{
            'mid': mid,
            'message': m['message'],
            'time': m['time'],
            'place': m['place'],
            'rel': m['rel'],
            'attr': m['attr'][0],
            'value': m['attr'][1]
        } for mid, m in enumerate(message_list)] + [{
            'mid': mid + len(message_list),
            'message': m['message'],
            'time': m['time'],
            'place': m['place'],
            'rel': m['rel'],
            'attr': m['attr'][0],
            'value': m['attr'][1]
        } for mid, m in enumerate(noise_message_list)]

        return message_list, question_list

    data_list = []
    output_path = outpath_pre + '04_aggregative_roles.json'
    for graph in graph_list:
        for trj in range(trajectory_per_graph):
            message_list, question_list = generate_single(graph)
            data_list.append({
                'tid': len(data_list),
                'message_list': message_list,
                'question_list': question_list
            })
            print(len(data_list) - 1, 'Finish!')

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data_list, f, indent=4, ensure_ascii=False)

def generate_aggr_event_04b(graph_list):
    key_features = ['location', 'scale', 'duration']
    cand_noise_attrs = ['main_content', 'time', 'location', 'scale', 'duration']
    question_num = 1
    noise_attrs_nums = 1
    
    def get_QA_info(whole_message_str, aggr_attr_k):
        prompt = '[Event Information] {}\n'.format('\n'.join(whole_message_str))
        prompt += 'Based on the above event information, for the aspect of {}, please generate a counting question starting with "How many events...?", in a casual first-person style.\n'.format(aggr_attr_k)
        prompt += 'Only output the generated question, do not provide any other descriptive information.\n'
        prompt += 'Example output: How many events have their location in Shanghai?'

        question = chatgpt(prompt)

        prompt = '[Question] {}\n'.format(question)
        prompt += 'Please modify the above question into a judgment question for a single event, for example, change "How many events have their location in Shanghai?" to "Does this event have its location in Shanghai?"\n'
        prompt += 'Only output the modified question, do not provide any other descriptive information.\n'
        prompt += 'Example output: Does this event have its location in Shanghai?'

        question_single = chatgpt(prompt)

        ans_count = 0
        for m in whole_message_str:
            prompt = '[Event Information] {}\n'.format(m)
            prompt += '[Question] {}\n'.format(question_single)
            prompt += 'Please answer the question based on the event information. If yes, output 1; if no, output 0; if unable to judge, output 2.\n'
            prompt += 'Only output the corresponding number of the answer, do not output any other descriptions or explanations.\n'
            prompt += 'Example output: 1'

            ans_single = chatgpt(prompt)
            max_try = 0
            while ans_single not in ['0', '1', '2']:
                print("Single Answer Parse Error: {}".format(ans_single))
                ans_single = chatgpt(prompt)
                if max_try >= 10:
                    ans_single = 0
            if ans_single == '1':
                ans_count += 1
            if ans_single == '2':
                return None, None
        answer = '{} events'.format(ans_count)
        # print(question, answer)
        return question, answer

    def generate_single(graph):
        time_clock = TimeClock()
        charact = graph['user_profile']['character']
        message_list = []
        noise_message_list = []
        question_list = []

        event_list = graph['work_events'] + graph['rest_events']
        aggr_attrs = np.random.choice(key_features, size=question_num, replace=False)
        for qid, aggr_attr_k in enumerate(aggr_attrs):
            whole_message_str = []
            for event in event_list:
                v = event[aggr_attr_k]
                n = event['event_name']

                text = rewrite_message_event("{}'s {} is {}.".format(n, aggr_attr_k, v), charact)
                whole_message_str.append(text)
                message_list.append({
                    'name': n,
                    'attr': (aggr_attr_k, v),
                    'message': text,
                    'time': time_clock.get_current_time(),
                    'place': graph['user_profile']['work_location']
                })
                time_clock.update_time()
            
            noise_attrs_list = np.random.choice(cand_noise_attrs, size=1, replace=False)
            for noise_attr in noise_attrs_list:
                if noise_attr not in aggr_attrs:
                    for event in event_list:
                        v = event[noise_attr]
                        n = event['event_name']

                        text = rewrite_message_event("{}'s {} is {}.".format(n, noise_attr, v), charact)
                        message_list.append({
                            'name': n,
                            'attr': (noise_attr, v),
                            'message': text,
                            'time': time_clock.get_current_time(),
                            'place': graph['user_profile']['work_location']
                        })
                        time_clock.update_time()
            
            question, answer = get_QA_info(whole_message_str, aggr_attr_k)
            if question is None:
                question, choices, ground_truth = '[ERRORQ]', '[ERRORC]', '[ERRORG]'
            else:
                question, choices, ground_truth = formulate_QA(question, answer)
            question_list.append({
                'qid': qid,
                'question': question,
                'answer': answer,
                'target_step_id': [qid * len(event_list) + k for k in range(len(event_list))],
                'choices': choices,
                'ground_truth': ground_truth,
                'time': time_clock.get_current_time()
            })
            time_clock.update_time()

        message_list = [{
            'mid': mid,
            'message': m['message'],
            'time': m['time'],
            'place': m['place'],
            'rel': m['name'],
            'attr': m['attr'][0],
            'value': m['attr'][1]
        } for mid, m in enumerate(message_list)] + [{
            'mid': mid + len(message_list),
            'message': m['message'],
            'time': m['time'],
            'place': m['place'],
            'rel': m['name'],
            'attr': m['attr'][0],
            'value': m['attr'][1]
        } for mid, m in enumerate(noise_message_list)] 
        
        return message_list, question_list

    data_list = []
    output_path = outpath_pre + '04_aggregative_events.json'
    for graph in graph_list:
        for trj in range(trajectory_per_graph):
            message_list, question_list = generate_single(graph)
            data_list.append({
                'tid': len(data_list),
                'message_list': message_list,
                'question_list': question_list
            })
            print(len(data_list) - 1, 'Finish!')

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data_list, f, indent=4, ensure_ascii=False)


def generate_memory_and_questions():
    profiles_path = '../graphs.json'
    with open(profiles_path, 'r', encoding='utf-8') as f:
        graph_list = json.load(f)

    generate_aggr_role_04a(graph_list)
    generate_aggr_event_04b(graph_list)


if __name__ == '__main__':
    generate_memory_and_questions()

