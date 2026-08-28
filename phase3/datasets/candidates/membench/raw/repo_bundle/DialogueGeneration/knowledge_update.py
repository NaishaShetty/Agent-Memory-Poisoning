import json
import numpy as np
import sys
sys.path.append('..')
import random
from utils import chatgpt, TimeClock, rewrite_message, formulate_QA, rewrite_question, rewrite_message_event, rewrite_question_translate, make_noise_time
import string

outpath_pre = '../OutData/ThirdAgent/LowLevel/'
trajectory_per_graph = 1

def generate_simple_role(graph_list):
    key_features = ['name', 'age', 'height', 'birthday', 'hometown', 'work_location', 'education', 'occupation', 'position', 'company_name', 'hobby', 'contact_number', 'email_address']
    b1_attrs_num = len(key_features)
    question_num = 1
    def generate_single_01a(graph):
        time_clock = TimeClock()
        charact = graph['user_profile']['character']
        message_list = []
        noise_message_list = []
        question_list = []

        role_list = graph['relation_profiles'] + graph['colleague_profiles']
        role_b1_id = np.random.choice(range(len(role_list)), size=1, replace=False)[0]
        role_b1 = role_list[role_b1_id]
        relation = role_b1['relationship']
        attrs = np.random.choice(key_features, size=b1_attrs_num, replace=False)

        while attrs[1] == 'name':
            attrs = np.random.choice(key_features, size=b1_attrs_num, replace=False)
            
        for k in attrs:
            v = role_b1[k]
            text = "My {}'s {} is {}.".format(relation, k, v)
            message_list.append({
                'rel': relation,
                'name': role_b1['name'],
                'attr': (k, v),
                'message': text,
                # 'time': time_clock.get_current_time(),
                'place': graph['user_profile']['work_location']
            })
            # time_clock.update_time()

        for qid in range(question_num):
            inx = np.random.choice(range(len(message_list)), size=1, replace=False)[0]
            real_attr = message_list[inx]
            question = "What is my {}'s {}?".format(relation, real_attr['attr'][0])
            answer = real_attr['attr'][1]

            for noise_role_id in range(len(role_list)):
                if noise_role_id != role_b1_id:
                    rel, k = role_list[noise_role_id]['relationship'], real_attr['attr'][0]
                    v = role_list[noise_role_id][k]
                    text = "My {}'s {} is {}.".format(rel, k, v)

                    noise_message_list.append({
                        'message': text,
                        # 'time': time_clock.get_current_time(),
                        'place': graph['user_profile']['work_location'],
                        'rel': rel,
                        'attr': (k, v)
                    })
                    # time_clock.update_time()
            
            question, choices, ground_truth = formulate_QA(question, answer)

            noise_answer_id = random.choice(['A', 'B', 'C', 'D'])
            while noise_answer_id == ground_truth:
                noise_answer_id = random.choice(['A', 'B', 'C', 'D'])
            
            noise_answer = choices[noise_answer_id]
            true_message = {
                'rel': message_list[inx]['rel'],
                'name': message_list[inx]['name'],
                'attr': message_list[inx]['attr'],
                'message': 'Sorry, I need to correct what I said earlier. ' + message_list[inx]['message'],
                # 'time': time_clock.get_current_time(),
                'place': message_list[inx]['place']
            }

            message_list[inx]['message'] = message_list[inx]['message'].replace(answer, noise_answer)

            target_id = random.sample(range(0, len(noise_message_list) + 1), 1)[0]
            noise_message_list.insert(target_id, true_message)
            question_list.append({
                'qid': qid,
                'question': rewrite_question(question),
                'answer': answer,
                'target_step_id': [int(inx), len(message_list) + target_id],
                'choices': choices,
                'ground_truth': ground_truth,
                # 'time': time_clock.get_current_time()
            })
            # time_clock.update_time()
        
        message_list_all = []
        for mid, m in enumerate(message_list + noise_message_list):
            message_list_all.append({
                'mid': mid,
                'message': rewrite_message(m['message'], charact),
                'time': time_clock.get_current_time(),
                'place': m['place'],
                'rel': m['rel'],
                'attr': m['attr'][0],
                'value': m['attr'][1]
            })
            time_clock.update_time()
        
        for q in question_list:
            q['time'] = time_clock.get_current_time()
            time_clock.update_time()
        
        return message_list_all, question_list

    data_list = []
    output_path = outpath_pre + '07_knowledgerenew_roles.json'
    with open(output_path) as f:
        data_list = json.load(f)
    for index, graph in enumerate(graph_list):
        if index < len(data_list):
            continue
        print('--- %d graph ---' % index)
        for trj in range(trajectory_per_graph):
            message_list, question_list = generate_single_01a(graph)
            data_list.append({
                'tid': len(data_list),
                'message_list': message_list,
                'question_list': question_list,
            })
            print(len(data_list)-1, 'finish!')
    
        with open(output_path,'w', encoding='utf-8') as f:
            json.dump(data_list, f, indent=4, ensure_ascii=False)


def generate_simple_events(graph_list):
    key_features = ['main_content', 'location', 'time', 'scale', 'duration']
    key_features_noise = ['location', 'time', 'scale', 'duration']
    b1_attrs_num = len(key_features)
    question_num = 1
    
    def generate_single_01a(graph):
        time_clock = TimeClock()
        charact = graph['user_profile']['character']
        message_list = []
        noise_message_list = []
        question_list = []

        event_list = graph['work_events'] + graph['rest_events']
        event_c1_id = np.random.choice(range(len(event_list)), size=1, replace=False)[0]
        event_c1 = event_list[event_c1_id]

        text = "I will attend {}.".format(event_c1['event_name'])
        message_list.append({
            'name': event_c1['event_name'],
            'attr': ('The event I will attend', event_c1['event_name']),
            'message': text,
            'time': time_clock.get_current_time(),
            'place': graph['user_profile']['work_location']
        })
        time_clock.update_time()

        attrs = np.random.choice(key_features, size=b1_attrs_num, replace=False)
        noise_attr = np.random.choice(key_features_noise, size=1, replace=False)
        if 'time' in attrs and noise_attr == 'time':
            noise_answer = make_noise_time(event_c1['time'])

        for k in attrs:
            v = event_c1[k]

            if noise_attr == 'time' and k == 'time':
                text = "{}'s {} is {}.".format(event_c1['event_name'], k, noise_answer)
            else:
                text = "{}'s {} is {}.".format(event_c1['event_name'], k, v)

            message_list.append({
                'name': event_c1['event_name'],
                'attr': (k, v),
                'message': text,
                'time': time_clock.get_current_time(),
                'place': graph['user_profile']['work_location']
            })
            time_clock.update_time()
        
        if 'time' in attrs and noise_attr == 'time':
            text = "Sorry, I need to correct what I said earlier. {}'s {} is {}.".format(event_c1['event_name'], 'time', event_c1['time'])
            message_list.append({
                'name': event_c1['event_name'],
                'attr': ('time', event_c1['time']),
                'message': text,
                'time': time_clock.get_current_time(),
                'place': graph['user_profile']['work_location']
            })
            time_clock.update_time()

        # 不再考虑question_num的设定

        if noise_attr != 'time':
            inx = np.random.choice(range(1, len(message_list)), size=1, replace=False)[0]
            while message_list[inx]['attr'][0] == 'time':
                inx = np.random.choice(range(1, len(message_list)), size=1, replace=False)[0]
        else:
            inx = len(message_list) - 1

        real_attr = message_list[inx]
        question = "{}的{}是什么?".format(event_c1['event_name'], real_attr['attr'][0])
        question = rewrite_question_translate(question)
        answer = real_attr['attr'][1]

        for noise_event_id in range(len(event_list)):
            if noise_event_id != event_c1_id:
                name, k = event_list[noise_event_id]['event_name'], real_attr['attr'][0]
                if k == 'The event I will attend':
                    v = event_list[noise_event_id]['event_name']
                    text = rewrite_message_event("I will attend {}.".format(name), charact)
                else:
                    v = event_list[noise_event_id][k]
                    text = rewrite_message_event("{}'s {} is {}.".format(name, k, v), charact)

                noise_message_list.append({
                    'message': text,
                    # 'time': time_clock.get_current_time(),
                    'place': graph['user_profile']['work_location'],
                    'name': name,
                    'attr': (k, v)
                })
                # time_clock.update_time()

        if real_attr['attr'][0] == 'time' and 'next' in answer:
            answer = time_clock.reltime_to_abstime(time_clock.get_current_timestamp(), answer)
        question, choices, ground_truth = formulate_QA(question, answer)

        if noise_attr != 'time':
            noise_answer_id = random.choice(['A', 'B', 'C', 'D'])
            while noise_answer_id == ground_truth:
                noise_answer_id = random.choice(['A', 'B', 'C', 'D'])
            
            noise_answer = choices[noise_answer_id]
            true_message = {
                'name': message_list[inx]['name'],
                'attr': message_list[inx]['attr'],
                'message': 'Sorry, I need to correct what I said earlier. ' + message_list[inx]['message'],
                # 'time': time_clock.get_current_time(),
                'place': message_list[inx]['place']
            }
            message_list[inx]['message'] = message_list[inx]['message'].replace(answer, noise_answer)

            target_id = random.sample(range(0, len(noise_message_list) + 1), 1)[0]
            noise_message_list.insert(target_id, true_message)
        
        else:

            target_id = - 1

        question_list.append({
            'qid': 0,
            'question': question,
            'answer': answer,
            'target_step_id': [len(message_list) + target_id],
            'choices': choices,
            'ground_truth': ground_truth,
            'time': time_clock.get_current_time()
        })
        time_clock.update_time()

        for n in noise_message_list:
            n['time'] = time_clock.get_current_time()
            time_clock.update_time()

        message_list = [{
            'mid': mid,
            'message': rewrite_message_event(m['message']),
            'time': m['time'],
            'place': m['place'],
            'rel': m['name'],
            'attr': m['attr'][0],
            'value': m['attr'][1]
        } for mid, m in enumerate(message_list)] + [{
            'mid': mid + len(message_list),
            'message': rewrite_message_event(m['message']),
            'time': m['time'],
            'place': m['place'],
            'rel': m['name'],
            'attr': m['attr'][0],
            'value': m['attr'][1]
        } for mid, m in enumerate(noise_message_list)] 
        
        return message_list, question_list

    data_list = []
    output_path = outpath_pre + '07_knowledgerenew_events.json'
    for index, graph in enumerate(graph_list):
        print('--- {} Graph ---'.format(index))
        for trj in range(trajectory_per_graph):
            message_list, question_list = generate_single_01a(graph)
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
    with open(profiles_path,'r', encoding='utf-8') as f:
        graph_list = json.load(f)
    generate_simple_role(graph_list)
    generate_simple_events(graph_list)


if __name__ == "__main__":
    generate_memory_and_questions()

