import json
import numpy as np
import sys
sys.path.append('..')
from utils import TimeClock,rewrite_message, rewrite_question, formulate_QA, rewrite_message_event, rewrite_question_translate

trajectory_per_graph = 1 # 10
outpath_pre = '../OutData/ThirdAgent/LowLevel/'


def get_role_data(graph, time_clock):
    """
    Obtain the message and QA from role entities.
    """
    key_features = ['name', 'age', 'height', 'birthday', 'hometown', 'work_location', 'education', 'occupation', 'position', 'company_name', 'hobby', 'contact_number', 'email_address']
    B1_attrs_num = len(key_features)
    question_num = 1

    charact = graph['user_profile']['character']
    message_list = []
    noise_message_list = []
    question_list = []

    role_list = graph['relation_profiles'] + graph['colleague_profiles']
    role_B1_id = np.random.choice(range(len(role_list)), size=1, replace=False)[0]
    role_B1 = role_list[role_B1_id]
    relation = role_B1['relationship']
    attrs = np.random.choice(key_features, size=B1_attrs_num, replace=False)
    while attrs[1] == 'name':
        attrs = np.random.choice(key_features, size=B1_attrs_num, replace=False)
    for k in attrs:
        v = role_B1[k]
        text = rewrite_message("my {}'s {} is {}.".format(relation, k, v), charact)
        message_list.append({
            'rel': relation,
            'name': role_B1['name'],
            'attr': (k, v),
            'message': text,
            'time': time_clock.get_current_time(),
            'place': graph['user_profile']['work_location']
        })
        time_clock.update_time()

    for qid in range(question_num):
        inx_01, inx_02 = np.random.choice(range(len(message_list)), size=2, replace=False)
        real_attr_01, real_attr_02 = message_list[inx_01], message_list[inx_02]
        question = "我的{}的{}是什么?".format(relation, real_attr_02['attr'][0])
        question = rewrite_question_translate(question)
        answer = real_attr_02['attr'][1]

        for noise_role_id in range(len(role_list)):
            if noise_role_id != role_B1_id:
                rel, k = role_list[noise_role_id]['relationship'], real_attr_02['attr'][0]
                v = role_list[noise_role_id][k]
                text = rewrite_message("my {}'s {} is {}.".format(rel, k, v), charact)

                noise_message_list.append({
                    'message': text,
                    'time': time_clock.get_current_time(),
                    'place': graph['user_profile']['work_location'],
                    'rel': relation,
                    'attr': (k, v),
                })
                time_clock.update_time()
            
        question, choices, groud_truth = formulate_QA(question, answer)
        question_list.append({
            'qid': qid,
            'question': rewrite_question(question),
            'answer': answer,
            'target_step_id': [int(inx_02)],
            'choices': choices,
            'ground_truth': groud_truth,
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
        'mid': mid+len(message_list),
        'message': m['message'],
        'time': m['time'],
        'place': m['place'],
        'rel': m['rel'],
        'attr': m['attr'][0],
        'value': m['attr'][1]
    } for mid, m in enumerate(noise_message_list)] 
    
    return message_list, question_list

def get_event_data(graph, time_clock):
    key_features = ['main_content', 'location', 'time', 'scale', 'duration']
    B1_attrs_num = len(key_features)
    question_num = 1

    charact = graph['user_profile']['character']
    message_list = []
    noise_message_list = []
    question_list = []

    event_list = graph['work_events'] + graph['rest_events']
    event_C1_id = np.random.choice(range(len(event_list)), size=1, replace=False)[0]
    event_C1 = event_list[event_C1_id]

    text = rewrite_message_event("I will attend {}.".format(event_C1['event_name']), charact)
    message_list.append({
        'name': event_C1['event_name'],
        'attr': ('The event I will attend', event_C1['event_name']),
        'message': text,
        'time': time_clock.get_current_time(),
        'place': graph['user_profile']['work_location']
    })
    time_clock.update_time()

    attrs = np.random.choice(key_features, size=B1_attrs_num, replace=False)
    for k in attrs:
        v = event_C1[k]
        text = rewrite_message_event("{}'s {} is {}.".format(event_C1['event_name'], k, v), charact)
        message_list.append({
            'name': event_C1['event_name'],
            'attr': (k, v),
            'message': text,
            'time': time_clock.get_current_time(),
            'place': graph['user_profile']['work_location']
        })
        if k == 'time' and 'next' in v:
            pre_time = time_clock.get_current_timestamp()
        time_clock.update_time()

    for qid in range(question_num):
        inx_01, inx_02 = np.random.choice(range(1,len(message_list)), size=2, replace=False)
        real_attr_01, real_attr_02 = message_list[inx_01], message_list[inx_02]
        question = "{}的{}是什么？".format(event_C1['event_name'], real_attr_02['attr'][0])
        question = rewrite_question_translate(question)
        
        answer = real_attr_02['attr'][1]

        for noise_event_id in range(len(event_list)):
            if noise_event_id != event_C1_id:
                name, k = event_list[noise_event_id]['event_name'], real_attr_02['attr'][0]
                if k == 'The event I will attend':
                    v = event_list[noise_event_id]['event_name']
                    text = rewrite_message_event("I will attend {}.".format(name), charact)
                else:
                    v = event_list[noise_event_id][k]
                    text = rewrite_message_event("{}'s {} is {}.".format(name, k, v), charact)

                noise_message_list.append({
                    'message': text,
                    'time': time_clock.get_current_time(),
                    'place': graph['user_profile']['work_location'],
                    'name': name,
                    'attr': (k, v)
                })
                time_clock.update_time()

        if real_attr_02['attr'][0] == 'time' and 'next' in answer:
            answer = time_clock.reltime_to_abstime(pre_time, answer)

        question, choices, groud_truth = formulate_QA(question, answer)
        question_list.append({
            'qid': qid,
            'question': question,
            'answer': answer,
            'target_step_id': [int(inx_02)],
            'choices': choices,
            'ground_truth': groud_truth,
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

def get_item_data(graph, time_clock):
    charact = graph['user_profile']['character']
    message_list = []
    noise_message_list = []
    question_list = []

    item = graph['items'][0]
    message_list.append({
        'message': rewrite_message("My {}'s {} is {}.".format(item['relationship'], item['item_type'], item['item_name']), charact),
        'time': time_clock.get_current_time(),
        'place': graph['user_profile']['work_location'],
        'rel': item['relationship'],
        'attr': item['item_type'],
        'value': item['item_name']
    })
    time_clock.update_time()

    message_list.append({
        'message': rewrite_message("I think {} is {}.".format(item['item_name'], item['item_review']), charact),
        'time': time_clock.get_current_time(),
        'place': graph['user_profile']['work_location'],
        'rel': item['relationship'],
        'attr': item['item_type'],
        'value': item['item_review']
    })
    time_clock.update_time()

    question = "我{}的{}是什么？".format(item['relationship'], item['item_type'])
    rewrite_question_translate(question)
    answer = item['item_name']

    question, choices, groud_truth = formulate_QA(question, answer)

    question_list.append({
            'qid': 0,
            'question': rewrite_question(question),
            'answer': answer,
            'target_step_id': [0, 1],
            'choices': choices,
            'ground_truth': groud_truth,
            'time': time_clock.get_current_time()
        })
    time_clock.update_time()

    message_list = [{
        'mid': mid,
        'message': m['message'],
        'time': m['time'],
        'place': m['place'],
        'rel': m['rel'],
        'attr': m['attr'],
        'value': m['value']
    } for mid, m in enumerate(message_list)] + [{
        'mid': mid + len(message_list),
        'message': m['message'],
        'time': m['time'],
        'place': m['place'],
        'rel': m['rel'],
        'attr': m['attr'],
        'value': m['value']
    } for mid, m in enumerate(noise_message_list)] 
    
    return message_list, question_list

def get_place_data(graph, time_clock):
    charact = graph['user_profile']['character']
    message_list = []
    noise_message_list = []
    question_list = []

    place = graph['places'][0]
    message_list.append({
        'message': rewrite_message("My {}'s {} is {}.".format(place['relationship'], place['place_type'], place['place_name']), charact),
        'time': time_clock.get_current_time(),
        'place': graph['user_profile']['work_location'],
        'rel': place['relationship'],
        'attr': place['place_type'],
        'value': place['place_name']
    })
    time_clock.update_time()

    message_list.append({
        'message': rewrite_message("I think {} is {}.".format(place['place_name'], place['place_name']), charact),
        'time': time_clock.get_current_time(),
        'place': graph['user_profile']['work_location'],
        'rel': place['relationship'],
        'attr': place['place_type'],
        'value': place['place_review']
    })
    time_clock.update_time()

    question = "我{}的{}是什么？".format(place['relationship'], place['place_type'])
    question = rewrite_question_translate(question)
    answer = place['place_name']


    question, choices, groud_truth = formulate_QA(question, answer)

    question_list.append({
            'qid': 0,
            'question': rewrite_question(question),
            'answer': answer,
            'target_step_id': [0, 1],
            'choices': choices,
            'ground_truth': groud_truth,
            'time': time_clock.get_current_time()
        })
    time_clock.update_time()


    message_list = [{
        'mid': mid,
        'message': m['message'],
        'time': m['time'],
        'place': m['place'],
        'rel': m['rel'],
        'attr': m['attr'],
        'value': m['value']
    } for mid, m in enumerate(message_list)] + [{
        'mid': mid + len(message_list),
        'message': m['message'],
        'time': m['time'],
        'place': m['place'],
        'rel': m['rel'],
        'attr': m['attr'],
        'value': m['value']
    } for mid, m in enumerate(noise_message_list)]  
    
    return message_list, question_list

def get_single_type_data(graph, time_clock, type):
    if type == 'role':
        return get_role_data(graph, time_clock)
    elif type == 'event':
        return get_event_data(graph, time_clock)
    elif type == 'item':
        return get_item_data(graph, time_clock)
    else:
        return get_place_data(graph, time_clock)

def merge_message_and_QA(meta_message_list, meta_question_list, message_list, question_list):
    mid_prefix = len(meta_message_list)
    meta_message_list += [{
        'mid': mid_prefix + mid,
        'message': m['message'],
        'time': m['time'],
        'place': m['place'],
        'rel': m['rel'],
        'attr': m['attr'],
        'value': m['value']
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
    def get_choices(ans,other_ans):
        choices = {}

        cvt = {0:'A',1:'B',2:'C',3:'D'}
        ans_tag = np.random.choice(range(4),size=1,replace=False)[0]
        ans_temp = [0 for i in range(4)]
        ans_temp[ans_tag] = 1
        groud_truth = cvt[ans_tag]

        choices[groud_truth] = ans
        for i in range(3):
            for index, t in enumerate(ans_temp):
                if t == 0:
                    ans_temp[index] = 1
                    cur_tag = index
                    break
            choices[cvt[cur_tag]] = other_ans[i]
        choices = {k: choices[k] for k in sorted(choices)}
        return groud_truth,choices
    question_text = ''
    answer_text = ''
    confuse_choices_text_list = ['', '', '']
    target_step_id_list = []
    for qid, q in enumerate(meta_question_list):
        target_step_id_list += q['target_step_id']
        if qid >= 1:
            question_text += 'In addition, {}'.format(q['question'])
            answer_text += '; {}'.format(q['answer'])
            confuse_choices = [v for k,v in q['choices'].items() if k != q['ground_truth']]
            confuse_choices_text_list = [choice_text+'; {}'.format(confuse_choices[cid]) for cid, choice_text in enumerate(confuse_choices_text_list)]
        else:
            question_text += '{}'.format(q['question'])
            answer_text += '{}'.format(q['answer'])
            confuse_choices = [v for k,v in q['choices'].items() if k != q['ground_truth']]
            confuse_choices_text_list = confuse_choices

    groud_truth, choices = get_choices(answer_text, confuse_choices_text_list)
    return {
        'qid': 0,
        'question': question_text,
        'answer': answer_text,
        'target_step_id': target_step_id_list,
        'choices': choices,
        'ground_truth': groud_truth,
        'time': meta_question_list[-1]['time']
    }
    
def check_both(tp1, tp2):
    if tp1 == 'item' and tp2 == 'place':
        return False
    if tp1 == 'place' and tp2 == 'item':
        return False
    return True

def generate_simple_facts_addition(graph_list):
    B1_attrs_num = 5
    question_num = 1
    def generate_single_01_combination(graph):
        time_clock = TimeClock()
        combination_cand = ['role', 'event', 'item', 'place']
        p = [0.35, 0.35, 0.15, 0.15]
        combination_types = np.random.choice(combination_cand,size=2,replace=False,p = p)
        while combination_types[0] == 'event' or not check_both(combination_types[0], combination_types[1]):
            combination_types = np.random.choice(combination_cand,size=2,replace=False,p = p)

        meta_message_list, meta_question_list = [], []

        for ct in combination_types:
            message_list, question_list = get_single_type_data(graph, time_clock, ct)
            merge_message_and_QA(meta_message_list, meta_question_list, message_list, question_list)
        # print(meta_message_list,meta_question_list)

        meta_question_list = [get_new_question_list(meta_question_list)]
        
        return meta_message_list, meta_question_list
        

    data_list = []
    output_path = outpath_pre + '01_simple_hybrid.json'
    for index, graph in enumerate(graph_list):
        print('--- %d Graph ---' % index)
        for trj in range(trajectory_per_graph):
            message_list, question_list = generate_single_01_combination(graph)
            data_list.append({
                'tid': len(data_list),
                'message_list': message_list,
                'question_list': question_list
            })
            print(len(data_list)-1, 'Finish!')
    
        with open(output_path,'w', encoding='utf-8') as f:
            json.dump(data_list, f, indent=4,ensure_ascii=False)
            

def generate_memory_and_questions(demo_mode = False):
    profiles_path = '../graphs.json'
    with open(profiles_path,'r', encoding='utf-8') as f:
        graph_list = json.load(f)

    generate_simple_facts_addition(graph_list)
    


if __name__ == '__main__':
    generate_memory_and_questions(demo_mode=True)