import json
import numpy as np
import sys
sys.path.append('..')
from utils import TimeClock, rewrite_message, formulate_QA, rewrite_question, rewrite_message_event,rewrite_question_translate

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
            text = rewrite_message("My {}'s {} is {}.".format(relation, k, v), charact)
            message_list.append({
                'rel': relation,
                'name': role_b1['name'],
                'attr': (k, v),
                'message': text,
                'time': time_clock.get_current_time(),
                'place': graph['user_profile']['work_location']
            })
            time_clock.update_time()

        for qid in range(question_num):
            inx_01, inx_02 = np.random.choice(range(len(message_list)), size=2, replace=False)
            real_attr_01, real_attr_02 = message_list[inx_01], message_list[inx_02]
            question = "What is my {}'s {}?".format(relation, real_attr_02['attr'][0])
            answer = real_attr_02['attr'][1]

            for noise_role_id in range(len(role_list)):
                if noise_role_id != role_b1_id:
                    rel, k = role_list[noise_role_id]['relationship'], real_attr_02['attr'][0]
                    v = role_list[noise_role_id][k]
                    text = rewrite_message("My {}'s {} is {}.".format(rel, k, v), charact)

                    noise_message_list.append({
                        'message': text,
                        'rel': relation,
                        'attr': (k, v),
                        'time': time_clock.get_current_time(),
                        'place': graph['user_profile']['work_location']
                    })
                    time_clock.update_time()
            
            question, choices, ground_truth = formulate_QA(question, answer)
            question_list.append({
                'qid': qid,
                'question': rewrite_question(question),
                'answer': answer,
                'target_step_id': [int(inx_02)],
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
            'mid': mid+len(message_list),
            'message': m['message'],
            'time': m['time'],
            'place': m['place'],
            'rel': m['rel'],
            'attr': m['attr'][0],
            'value': m['attr'][1]
        } for mid, m in enumerate(noise_message_list)] 
        
        return message_list, question_list

    data_list = []
    output_path = outpath_pre + '01_simple_roles.json'
    for index, graph in enumerate(graph_list):
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

        text = rewrite_message_event("I will attend {}.".format(event_c1['event_name']), charact)
        message_list.append({
            'name': event_c1['event_name'],
            'attr': ('The event I will attend', event_c1['event_name']),
            'message': text,
            'time': time_clock.get_current_time(),
            'place': graph['user_profile']['work_location'],
        })
        time_clock.update_time()

        attrs = np.random.choice(key_features, size=b1_attrs_num, replace=False)
        for k in attrs:
            v = event_c1[k]
            text = rewrite_message_event("{}'s {} is {}.".format(event_c1['event_name'], k, v), charact)
            message_list.append({
                'name': event_c1['event_name'],
                'attr': (k, v),
                'message': text,
                'time': time_clock.get_current_time(),
                'place': graph['user_profile']['work_location']
            })
            if k == 'time' and 'next' in v:
                pre_time = time_clock.get_current_timestamp()
            time_clock.update_time()

        for qid in range(question_num):
            inx_01, inx_02 = np.random.choice(range(1, len(message_list)), size=2, replace=False)
            real_attr_01, real_attr_02 = message_list[inx_01], message_list[inx_02]
            question = "{}的{}是什么?".format(event_c1['event_name'], real_attr_02['attr'][0])
            question = rewrite_question_translate(question)
            answer = real_attr_02['attr'][1]

            for noise_event_id in range(len(event_list)):
                if noise_event_id != event_c1_id:
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

            if real_attr_02['attr'][0] == 'time' and  'next' in answer:
                answer = time_clock.reltime_to_abstime(pre_time, answer)
            question, choices, ground_truth = formulate_QA(question, answer)
            question_list.append({
                'qid': qid,
                'question': question,
                'answer': answer,
                'target_step_id': [int(inx_02)],
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
    output_path = outpath_pre + '01_simple_events.json'
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


trajectory_per_graph_item_place = 1


def generate_simple_item_place(graph_list):
    
    def generate_single_01a_item(graph):
        time_clock = TimeClock()
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

        noise_message_list = []
        place = graph['places'][0]
        noise_message_list.append({
            'message': rewrite_message("My {}'s {} is {}.".format(place['relationship'], place['place_type'], place['place_name']), charact),
            'time': time_clock.get_current_time(),
            'place': graph['user_profile']['work_location'],
            'rel': place['relationship'],
            'attr': place['place_type'],
            'value': place['place_name']
        })
        time_clock.update_time()

        noise_message_list.append({
            'message': rewrite_message("I think {} is {}.".format(place['place_name'], place['place_review']), charact),
            'time': time_clock.get_current_time(),
            'place': graph['user_profile']['work_location'],
            'rel': place['relationship'],
            'attr': place['place_type'],
            'value': place['place_review']
        })
        time_clock.update_time()

        question = "我{}的{}是什么？".format(item['relationship'], item['item_type'])
        question = rewrite_question_translate(question)
        answer = item['item_name']

        question, choices, ground_truth = formulate_QA(question, answer)

        question_list.append({
            'qid': 0,
            'question': rewrite_question(question),
            'answer': answer,
            'target_step_id': [0, 1],
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

    def generate_single_01a_place(graph):
        time_clock = TimeClock()
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
            'message': rewrite_message("I think {} is {}.".format(place['place_name'], place['place_review']), charact),
            'time': time_clock.get_current_time(),
            'place': graph['user_profile']['work_location'],
            'rel': place['relationship'],
            'attr': place['place_type'],
            'value': place['place_review']
        })
        time_clock.update_time()

        item = graph['items'][0]
        noise_message_list.append({
            'message': rewrite_message("My {}'s {} is {}.".format(item['relationship'], item['item_type'], item['item_name']), charact),
            'time': time_clock.get_current_time(),
            'place': graph['user_profile']['work_location'],
            'rel': item['relationship'],
            'attr': item['item_type'],
            'value': item['item_name']
        })
        time_clock.update_time()

        noise_message_list.append({
            'message': rewrite_message("I think {} is {}.".format(item['item_name'], item['item_review']), charact),
            'time': time_clock.get_current_time(),
            'place': graph['user_profile']['work_location'],
            'rel': item['relationship'],
            'attr': item['item_type'],
            'value': item['item_review']
        })
        time_clock.update_time()

        question = "我{}的{}是什么？?".format(place['relationship'], place['place_type'])
        question = rewrite_question_translate(question)
        answer = place['place_name']

        question, choices, ground_truth = formulate_QA(question, answer)

        question_list.append({
            'qid': 0,
            'question': rewrite_question(question),
            'answer': answer,
            'target_step_id': [0, 1],
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

    output_path_item = outpath_pre + '01_simple_items.json'
    output_path_place = outpath_pre + '01_simple_places.json'
    data_list_item = []
    data_list_place = []
    for index, graph in enumerate(graph_list):
        print('--- {} Graph ---'.format(index))
        for trj in range(trajectory_per_graph_item_place):
            message_list, question_list = generate_single_01a_item(graph)
            data_list_item.append({
                'tid': len(data_list_item),
                'message_list': message_list,
                'question_list': question_list
            })
            print(len(data_list_item) - 1, 'Finish!')
        for trj in range(trajectory_per_graph_item_place):
            message_list, question_list = generate_single_01a_place(graph)
            data_list_place.append({
                'tid': len(data_list_place),
                'message_list': message_list,
                'question_list': question_list
            })
            print(len(data_list_place) - 1, 'Finish!')
    
        with open(output_path_item, 'w', encoding='utf-8') as f:
            json.dump(data_list_item, f, indent=4, ensure_ascii=False)

        with open(output_path_place, 'w', encoding='utf-8') as f:
            json.dump(data_list_place, f, indent=4, ensure_ascii=False)


def generate_memory_and_questions():
    profiles_path = '../graphs.json'
    with open(profiles_path,'r', encoding='utf-8') as f:
        graph_list = json.load(f)
    generate_simple_role(graph_list)
    generate_simple_events(graph_list)
    generate_simple_item_place(graph_list)


if __name__ == "__main__":
    generate_memory_and_questions()

