import json
import numpy as np
import sys
sys.path.append('..')
from utils import chatgpt, TimeClock, get_choices, rewrite_message_event, rewrite_message_role
import string

outpath_pre = '../OutData/ThirdAgent/LowLevel/'

trajectory_per_graph = 1

def formulate_QA(question, answer, nameB1, nameB2):
    if answer == 'Unable to determine':
        other_answers = [nameB1, nameB2, 'Both incorrect']
    elif answer == nameB1:
        other_answers = [nameB2, 'Both the same', 'Both incorrect']
    elif answer == nameB2:
        other_answers = [nameB1, 'Both the same', 'Both incorrect']
    elif answer == 'Both the same':
        other_answers = [nameB1, nameB2, 'Unable to determine']
    else:
        other_answers = ['Both the same', 'Both incorrect', 'Obtuse angle']

    ground_truth, choices = get_choices(answer, other_answers)
    return question, choices, ground_truth

def get_role_data(graph, time_clock):
    """
    Obtain the message and QA from role entities.
    """
    key_features = ['age', 'height', 'birthday', 'education']
    question_num = 1
    character = graph['user_profile']['character']
    message_list = []
    noise_message_list = []
    question_list = []

    role_list = graph['relation_profiles'] + graph['colleague_profiles']
    role_B_ids = np.random.choice(range(len(role_list)), size=2, replace=False)
    role_B1, role_B2 = role_list[role_B_ids[0]], role_list[role_B_ids[1]]
    relationB1, relationB2 = role_B1['relationship'], role_B2['relationship']

    compare_attrs = np.random.choice(key_features, size=question_num, replace=False)
    for compare_attr_k in compare_attrs:
        vB1, vB2 = role_B1[compare_attr_k], role_B2[compare_attr_k]
        GB_1 = 'his'
        if role_B1['gender'] == 'Female':
            GB_1 = 'her'

        text = rewrite_message_role("{} is my {}, {} {} is {}.".format(role_B1['name'], relationB1, GB_1, compare_attr_k, vB1), character)
        message_list.append({
            'rel': relationB1,
            'name': role_B1['name'],
            'attr': (compare_attr_k, vB1),
            'message': text,
            'time': time_clock.get_current_time(),
            'place': graph['user_profile']['work_location']
        })
        time_clock.update_time()

        GB_2 = 'his'
        if role_B2['gender'] == 'Female':
            GB_2 = 'her'

        text = rewrite_message_role("{} is my {}, {} {} is {}.".format(role_B2['name'], relationB2, GB_2, compare_attr_k, vB2), character)
        message_list.append({
            'rel': relationB2,
            'name': role_B2['name'],
            'attr': (compare_attr_k, vB2),
            'message': text,
            'time': time_clock.get_current_time(),
            'place': graph['user_profile']['work_location']
        })
        time_clock.update_time()

    for qid in range(question_num):
        compare_attr_k = compare_attrs[qid]
        vB1, vB2 = role_B1[compare_attr_k], role_B2[compare_attr_k]
        nameB1, nameB2 = role_B1['name'], role_B2['name']

        for noise_role_id in range(len(role_list)):
            if noise_role_id not in role_B_ids:
                v = role_list[noise_role_id][compare_attr_k]
                r = role_list[noise_role_id]['relationship']
                n = role_list[noise_role_id]['name']
                GB = 'his'
                if role_list[noise_role_id]['gender'] == 'Female':
                    GB = 'her'


                text = rewrite_message_role("{} is my {}, {} {} is {}.".format(n, r, GB, compare_attr_k, v), character)
                message_list.append({
                    'rel': r,
                    'name': n,
                    'attr': (compare_attr_k, v),
                    'message': text,
                    'time': time_clock.get_current_time(),
                    'place': graph['user_profile']['work_location']
                })
                time_clock.update_time()

        prompt = '[Info] {}\'s {} is {}; {}\'s {} is {}.\n'.format(nameB1, compare_attr_k, vB1, nameB2, compare_attr_k, vB2)
        prompt += 'Based on the information of the two individuals, please help me generate a question that compares {}.'.format(compare_attr_k)
        prompt += ' The answer to the question should be {}, {} or both the same.\n'.format(nameB1, nameB2)
        prompt += 'Only output the generated question, do not output the answer, do not output other descriptive information.\n'
        prompt += 'Output example: Who has a higher position, Zhang San or Li Si?'
        question = chatgpt(prompt)
    
        prompt = '[Info] {}\'s {} is {}; {}\'s {} is {}.\n'.format(nameB1, compare_attr_k, vB1, nameB2, compare_attr_k, vB2)
        prompt += 'Based on the information of the two individuals, please help me answer the question: {}.\n'.format(question)
        prompt += 'If you cannot determine based on the information, please output Unable to determine; if both are the same, please output Both the same; otherwise, the answer should be {} or {}.\n'.format(nameB1, nameB2)
        prompt += 'Only output the answer to this question, do not output other descriptive information.'
        prompt += 'Output example: Unable to determine'

        ans_pre = chatgpt(prompt)
        ans_ex = chatgpt('RandomSeed({})\n{}'.format(np.random.randint(1, 100), prompt))
        max_try = 0
        while ans_ex != ans_pre:
            ans_pre = ans_ex
            ans_ex = chatgpt('RandomSeed({})\n{}'.format(np.random.randint(1, 100), prompt))
            max_try += 1
            if max_try >= 10:
                ans_ex = None
        
        if ans_ex:
            answer = ans_ex
        else:
            answer = None
        
        if answer:
            question, choices, ground_truth = formulate_QA(question, answer, nameB1, nameB2)
        else:
            choices, ground_truth = '[ERRORC]', '[ERRORG]'

        question_list.append({
            'qid': qid,
            'question': question,
            'answer': answer,
            'target_step_id': [qid * 2, qid * 2 + 1],
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
    key_features = ['scale', 'duration']
    question_num = 1
    character = graph['user_profile']['character']
    message_list = []
    noise_message_list = []
    question_list = []

    event_list = graph['work_events'] + graph['rest_events']
    event_C_ids = np.random.choice(range(len(event_list)), size=2, replace=False)
    event_C1, event_C2 = event_list[event_C_ids[0]], event_list[event_C_ids[1]]

    compare_attrs = np.random.choice(key_features, size=question_num, replace=False)
    for compare_attr_k in compare_attrs:
        vC1, vC2 = event_C1[compare_attr_k], event_C2[compare_attr_k]
        nC1, nC2 = event_C1['event_name'], event_C2['event_name']

        text = rewrite_message_event("I will attend the {}, its {} is {}.".format(nC1, compare_attr_k, vC1), character)
        message_list.append({
            'name': nC1,
            'attr': (compare_attr_k, vC1),
            'message': text,
            'time': time_clock.get_current_time(),
            'place': graph['user_profile']['work_location']
        })
        time_clock.update_time()

        text = rewrite_message_event("I will attend the {}, its {} is {}.".format(nC2, compare_attr_k, vC2), character)
        message_list.append({
            'name': nC2,
            'attr': (compare_attr_k, vC2),
            'message': text,
            'time': time_clock.get_current_time(),
            'place': graph['user_profile']['work_location']
        })
        time_clock.update_time()

    for qid in range(question_num):
        compare_attr_k = compare_attrs[qid]
        vC1, vC2 = event_C1[compare_attr_k], event_C2[compare_attr_k]
        nC1, nC2 = event_C1['event_name'], event_C2['event_name']

        for noise_event_id in range(len(event_list)):
            if noise_event_id not in event_C_ids:
                v = event_list[noise_event_id][compare_attr_k]
                n = event_list[noise_event_id]['event_name']

                text = rewrite_message_event("{}'s {} is {}.".format(n, compare_attr_k, v), character)
                message_list.append({
                    'name': n,
                    'attr': (compare_attr_k, v),
                    'message': text,
                    'time': time_clock.get_current_time(),
                    'place': graph['user_profile']['work_location']
                })
                time_clock.update_time()

        prompt = '[Info] {}\'s {} is {}; {}\'s {} is {}.\n'.format(nC1, compare_attr_k, vC1, nC2, compare_attr_k, vC2)
        prompt += 'Based on the information of the two events, please help me generate a question that contains a comparison from the perspective of {}.'.format(compare_attr_k)
        prompt += ' Only output the generated question, do not output other descriptive information.\n'
        prompt += 'Output example: Which event, Innovation Competition or Food Festival, has a larger scale?'
        question = chatgpt(prompt)
    
        prompt = '[Info] {}\'s {} is {}; {}\'s {} is {}.\n'.format(nC1, compare_attr_k, vC1, nC2, compare_attr_k, vC2)
        prompt += 'Based on the information of the two events, please help me answer the question: {}.\n'.format(question)
        prompt += 'If you cannot determine based on the information, please output Unable to determine; if both are the same, please output Both the same; otherwise, the answer should be {} or {}.\n'.format(nC1, nC2)

        prompt += 'Only output the answer to this question, do not output other descriptive information, do not output reasoning or explanation.\n'
        prompt += 'Output example: Unable to determine'

        ans_pre = chatgpt(prompt)
        ans_ex = chatgpt('RandomSeed({})\n{}'.format(np.random.randint(1, 100), prompt))
        max_try = 0
        while ans_ex != ans_pre:
            ans_pre = ans_ex
            ans_ex = chatgpt('RandomSeed({})\n{}'.format(np.random.randint(1, 100), prompt))
            max_try += 1
            if max_try >= 10:
                ans_ex = None
        
        if ans_ex:
            answer = ans_ex
        else:
            answer = None
        
        if answer:
            question, choices, ground_truth = formulate_QA(question, answer, nC1, nC2)
        else:
            choices, ground_truth = '[ERRORC]', '[ERRORG]'
        
        question_list.append({
            'qid': qid,
            'question': question,
            'answer': answer,
            'target_step_id': [qid * 2, qid * 2 + 1],
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


def get_single_type_data(graph, time_clock, type):
    if type == 'role':
        return get_role_data(graph, time_clock)
    elif type == 'event':
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
        'value': m['value'][1]
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
        if q['choices'] == '[ERRORC]':
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
    output_path = outpath_pre +  '03_comparative_hybrid.json'
    for index, graph in enumerate(graph_list):
        print('--- {} Graph ---'.format(index))
        for trj in range(trajectory_per_graph):
            message_list, question_list = generate_single_02_combination(graph)
            data_list.append({
                'tid': len(data_list),
                'message_list': message_list,
                'question_list': question_list
            })
            print(len(data_list) - 1, 'Finish!')

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data_list, f, indent=4, ensure_ascii=False)

def generate_memory_and_questions(demo_mode=False):
    profiles_path = '../graphs.json'
    with open(profiles_path, 'r', encoding='utf-8') as f:
        graph_list = json.load(f)

    generate_simple_facts_addition(graph_list)

if __name__ == '__main__':
    generate_memory_and_questions(demo_mode=True)

