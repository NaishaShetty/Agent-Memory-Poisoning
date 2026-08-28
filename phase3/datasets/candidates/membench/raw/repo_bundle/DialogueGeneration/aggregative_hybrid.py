import json
import numpy as np
import sys
sys.path.append('..')
from utils import chatgpt, TimeClock, formulate_QA, rewrite_message_event, rewrite_message_role
import string

outpath_pre = '../OutData/ThirdAgent/LowLevel/'
trajectory_per_graph = 1

def get_role_data(graph, time_clock):
    """
    Obtain the message and QA from role entities.
    """
    key_features = ['age', 'height', 'birthday', 'hometown', 'work_location', 'education']
    question_num = 1
    noise_attrs_nums = 1

    def get_QA_info(whole_message_str, aggr_attr_k):
        prompt = '[User Info] {}\n'.format('\n'.join(whole_message_str))
        prompt += 'Based on the above user information, please generate a counting question about {} starting with "How many people...?" in a conversational first-person style.'.format(aggr_attr_k)
        prompt += 'Only output the generated question, do not include any other descriptive information.\n'
        prompt += 'Example output: How many people are aged 35 or below?'

        question = chatgpt(prompt)

        prompt = '[Question] {}\n'.format(question)
        prompt += 'Please modify the above question to a judgment question for a single person, for example, change "How many people are aged 35 or below?" to "Is their age 35 or below?"\n'
        prompt += 'Only output the modified question, do not include any other descriptive information.\n'
        prompt += 'Example output: Is their age 35 or below?'

        question_single = chatgpt(prompt)

        ans_count = 0
        for m in whole_message_str:
            prompt = '[User Info] {}\n'.format(m)
            prompt += '[Question] {}\n'.format(question_single)
            prompt += 'Please answer the question based on the user information. If yes, output 1; if no, output 0; if unable to judge, output 2.\n'
            prompt += 'Note the distinction between "above" and "including," e.g., "above 35" means older than 35, while "35 or above" includes 35.\n'
            prompt += 'If not specified, the first half of the year refers to January to June, and the second half refers to July to December.\n'
            prompt += 'Only output the corresponding number, do not include any other descriptions or explanations, and do not output phrases like "Output:".\n'
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
                g = 'her'

            text = rewrite_message_role("{} is my {}, {} {} is {}.".format(n, r, g, aggr_attr_k, v), charact)
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
                        g = 'her'

                    text = rewrite_message_role("{} is my {}, {} {} is {}.".format(n, r, g, noise_attr, v), charact)
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


def get_event_data(graph, time_clock):
    key_features = ['location', 'scale', 'duration']
    cand_noise_attrs = ['main_content', 'time', 'location', 'scale', 'duration']
    question_num = 1
    noise_attrs_nums = 1

    def get_QA_info(whole_message_str, aggr_attr_k):
        prompt = '[Event Info] {}\n'.format('\n'.join(whole_message_str))
        prompt += 'Based on the above event information, please generate a counting question about {} starting with "How many events...?" in a conversational first-person style.'.format(aggr_attr_k)
        prompt += 'Only output the generated question, do not include any other descriptive information.\n'
        prompt += 'Example output: How many events are located in Shanghai?'

        question = chatgpt(prompt)

        prompt = '[Question] {}\n'.format(question)
        prompt += 'Please modify the above question to a judgment question for a single event, for example, change "How many events are located in Shanghai?" to "Is this event located in Shanghai?"\n'
        prompt += 'Only output the modified question, do not include any other descriptive information.\n'
        prompt += 'Example output: Is this event located in Shanghai?'

        question_single = chatgpt(prompt)

        ans_count = 0
        for m in whole_message_str:
            prompt = '[Event Info] {}\n'.format(m)
            prompt += '[Question] {}\n'.format(question_single)
            prompt += 'Please answer the question based on the event information. If yes, output 1; if no, output 0; if unable to judge, output 2.\n'
            prompt += 'Only output the corresponding number, do not include any other descriptions or explanations, and do not output phrases like "Output:".\n'
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
            if ans_count == '2':
                return None, None
        answer = '{} events'.format(ans_count)
        print(question, answer)
        return question, answer
    
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


def get_single_type_data(graph, time_clock, data_type):
    if data_type == 'role':
        return get_role_data(graph, time_clock)
    elif data_type == 'event':
        return get_event_data(graph, time_clock)
    else:
        raise ValueError("None Type of QA.")

def merge_message_and_QA(meta_message_list, meta_question_list, message_list, question_list):
    mid_prefix = len(meta_message_list)
    meta_message_list += [{
        'mid': mid_prefix + mid,
        'message': m['message'],
        'time': m['time'],
        'place': m['place'],
        'rel': m['rel'],
        'attr': m['attr'][0],
        'value': m['attr'][1]
    } for mid, m in enumerate(message_list)]

    qid_prefix = len(meta_question_list)
    meta_question_list += [{
        'qid': qid_prefix + q['qid'],
        'question': q['question'],
        'answer': q['answer'],
        'target_step_id': [mid_prefix + ref_id for ref_id in q['target_step_id']],
        'choices': q['choices'],
        'ground_truth': q['ground_truth'],
        'time': q['time']
    } for qid, q in enumerate(question_list)]
    

def get_new_question_list(meta_question_list):
    def get_choices(ans, other_ans):
        choices = {}

        cvt = {0: 'A', 1: 'B', 2: 'C', 3: 'D'}
        ans_tag = np.random.choice(range(4), size=1, replace=False)[0]
        ans_temp = [0 for _ in range(4)]
        ans_temp[ans_tag] = 1
        ground_truth = cvt[ans_tag]

        choices[ground_truth] = ans
        for i in range(3):
            for index, t in enumerate(ans_temp):
                if t == 0:
                    ans_temp[index] = 1
                    cur_tag = index
                    break
            choices[cvt[cur_tag]] = other_ans[i]
        choices = {k: choices[k] for k in sorted(choices)}
        return ground_truth, choices

    question_text = ''
    answer_text = ''
    confuse_choices_text_list = ['', '', '']
    target_step_id_list = []
    for qid, q in enumerate(meta_question_list):
        target_step_id_list += q['target_step_id']
        if q['question'] == '[ERRORQ]':
            return {
                'qid': 0,
                'question': '[ERRORQ]',
                'answer': '[ERRORA]',
                'target_step_id': target_step_id_list,
                'choices': '[ERRORC]',
                'ground_truth': '[ERRORG]',
                'time': meta_question_list[-1]['time']
            }
        if qid >= 1:
            question_text += 'Additionally, {}'.format(q['question'])
            answer_text += '; {}'.format(q['answer'])
            confuse_choices = [v for k, v in q['choices'].items() if k != q['ground_truth']]
            confuse_choices_text_list = [choice_text + '; {}'.format(confuse_choices[cid]) for cid, choice_text in enumerate(confuse_choices_text_list)]
        else:
            question_text += '{}'.format(q['question'])
            answer_text += '{}'.format(q['answer'])
            confuse_choices = [v for k, v in q['choices'].items() if k != q['ground_truth']]
            confuse_choices_text_list = confuse_choices

    ground_truth, choices = get_choices(answer_text, confuse_choices_text_list)
    return {
        'qid': 0,
        'question': question_text,
        'answer': answer_text,
        'target_step_id': target_step_id_list,
        'choices': choices,
        'ground_truth': ground_truth,
        'time': meta_question_list[-1]['time']
    }

def generate_simple_facts_addition(graph_list):
    B1_attrs_num = 5
    question_num = 1
    def generate_single_02_combination(graph):
        time_clock = TimeClock()
        combination_cand = ['role', 'event']
        p = [0.5, 0.5]
        combination_types = np.random.choice(combination_cand, size=2, replace=False, p=p)

        meta_message_list, meta_question_list = [], []

        for ct in combination_types:
            message_list, question_list = get_single_type_data(graph, time_clock, ct)
            merge_message_and_QA(meta_message_list, meta_question_list, message_list, question_list)

        meta_question_list = [get_new_question_list(meta_question_list)]
        
        return meta_message_list, meta_question_list
        
    data_list = []
    output_path = outpath_pre + '04_aggregative_hybrid.json'
    for index, graph in enumerate(graph_list):
        print('--- {} Graph ---'.format(index))
        for trj in range(trajectory_per_graph):
            message_list, question_list = generate_single_02_combination(graph)
            data_list.append({
                'tid': len(data_list),
                'message_list': message_list,
                'question_list': question_list
            })
            print('{} Finish!'.format(len(data_list) - 1))
    
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data_list, f, indent=4, ensure_ascii=False)

def generate_memory_and_questions(demo_mode=False):
    profiles_path = '../graphs.json'
    with open(profiles_path, 'r', encoding='utf-8') as f:
        graph_list = json.load(f)

    generate_simple_facts_addition(graph_list)

if __name__ == '__main__':
    generate_memory_and_questions(demo_mode=True)


