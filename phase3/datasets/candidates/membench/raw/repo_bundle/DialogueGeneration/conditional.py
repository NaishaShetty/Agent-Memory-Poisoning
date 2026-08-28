import json
import numpy as np
import sys
sys.path.append('..')
from utils import chatgpt, TimeClock, rewrite_message, formulate_QA, rewrite_question, rewrite_message_event, rewrite_question_translate, formulate_QA_additional_judge
import string

outpath_pre = '../OutData/ThirdAgent/LowLevel/'
trajectory_per_graph = 1


def generate_condition_role(graph_list):
    key_features = ['name', 'age', 'height', 'birthday', 'hometown', 'work_location', 'education', 'occupation', 'position', 'company_name', 'hobby', 'contact_number', 'email_address']
    B1_attrs_num = len(key_features)
    question_num = 1
    def generate_single_01a(graph):
        time_clock = TimeClock()
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
            text = rewrite_message("My {}'s {} is {}.".format(relation, k, v), charact)
            message_list.append({
                'rel': relation,
                'name': role_B1['name'],
                'attr': (k,v),
                'message': text,
                'time': time_clock.get_current_time(),
                'place': graph['user_profile']['work_location']
            })
            time_clock.update_time()

        for qid in range(question_num):
            inx_01, inx_02 = np.random.choice(range(len(message_list)), size=2, replace=False)
            real_attr_01, real_attr_02 = message_list[inx_01], message_list[inx_02]
            question = "那个{}是{}的人，{}是什么？".format(real_attr_01['attr'][0], real_attr_01['attr'][1], real_attr_02['attr'][0])
            answer = real_attr_02['attr'][1]

            for noise_role_id in range(len(role_list)):
                if noise_role_id != role_B1_id:
                    rel, k = role_list[noise_role_id]['relationship'], real_attr_02['attr'][0]
                    v = role_list[noise_role_id][k]
                    text = rewrite_message("My {}'s {} is {}.".format(rel, k, v), charact)

                    noise_message_list.append({
                        'message': text,
                        'time': time_clock.get_current_time(),
                        'place': graph['user_profile']['work_location'],
                        'rel': rel,
                        'attr': (k,v)
                    })
                    time_clock.update_time()
            
            question, choices, groud_truth = formulate_QA(question, answer)
            question_list.append({
                'qid': qid,
                'question': rewrite_question_translate(question),
                'answer': answer,
                'target_step_id': [int(inx_01), int(inx_02)],
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

    data_list = []
    output_path = outpath_pre + '02_conditional_roles.json'
    for index, graph in enumerate(graph_list):
        print('--- %d Graph ---' % index)
        for trj in range(trajectory_per_graph):
            message_list, question_list = generate_single_01a(graph)
            data_list.append({
                'tid': len(data_list),
                'message_list': message_list,
                'question_list': question_list
            })
            print(len(data_list)-1, 'Finish!')
    
        with open(output_path,'w', encoding='utf-8') as f:
            json.dump(data_list, f, indent=4,ensure_ascii=False)

def generate_condition_event(graph_list):
    key_features = ['main_content', 'location', 'time', 'scale', 'duration']
    B1_attrs_num = len(key_features)
    question_num = 1
    def generate_single_01a(graph):
        time_clock = TimeClock()
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
            time_clock.update_time()

        inx_01, inx_02 = np.random.choice(range(len(message_list)), size=2, replace=False)
        real_attr_01, real_attr_02 = message_list[inx_01], message_list[inx_02]
        
        for qid in range(question_num):
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

            conditional_ans = real_attr_01['attr'][1]
            if real_attr_01['attr'][0] == 'time' and 'next' in real_attr_01['attr'][1]:
                abs_pre = real_attr_01['time'].rsplit(' ', 1)[0].replace("'", '')
                rel_pre = real_attr_01['attr'][1]
                rel_cur = time_clock.refine_rel_time(abs_pre, rel_pre, time_clock.get_current_timestamp())
                conditional_ans = rel_cur

            if real_attr_01['attr'][0] == 'main_content':
                question = "那个主要内容是{}的活动，{}是什么？".format(conditional_ans, real_attr_02['attr'][0])
            else:
                question = "那个{}是{}的活动，{}是什么？".format(real_attr_01['attr'][0], conditional_ans, real_attr_02['attr'][0])
            question = rewrite_question_translate(question)
            answer = real_attr_02['attr'][1]

            if real_attr_02['attr'][0] == 'time' and 'next' in answer:
                answer = time_clock.reltime_to_abstime(time_clock.get_current_timestamp(),answer)
            question, choices, groud_truth = formulate_QA(question, answer)
            question_list.append({
                'qid': qid,
                'question': question,
                'answer': answer,
                'target_step_id': [int(inx_01), int(inx_02)],
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
            'mid': mid+len(message_list),
            'message': m['message'],
            'time': m['time'],
            'place': m['place'],
            'rel': m['name'],
            'attr': m['attr'][0],
            'value': m['attr'][1]
        } for mid, m in enumerate(noise_message_list)] 
        
        return message_list, question_list

    data_list = []
    output_path = outpath_pre + '02_conditional_events.json'
    for index, graph in enumerate(graph_list):
        print('--- %d Graph ---' % index)
        for trj in range(trajectory_per_graph):
            message_list, question_list = generate_single_01a(graph)
            data_list.append({
                'tid': len(data_list),
                'message_list': message_list,
                'question_list': question_list
            })
            print(len(data_list)-1, 'Finish!')
    
        with open(output_path,'w', encoding='utf-8') as f:
            json.dump(data_list, f, indent=4,ensure_ascii=False)


trajectory_per_graph_new = 1


def generate_condition_addition(graph_list):

    def generate_condition_facts_01a_item(graph):
        time_clock = TimeClock()
        charact = graph['user_profile']['character']
        message_list = []
        noise_message_list = []
        question_list = []

        item = graph['items'][0]
        message_list.append({
            'message': rewrite_message("The {} of my {} is {}.".format(item['relationship'], item['item_type'], item['item_name']), charact),
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

        question = "What is my {}'s {}?".format(item['relationship'], item['item_type'])

        prompt = "Please summarize my comment concisely in two short sentences: {}\n".format(item['item_review'])
        prompt += "Only output the summary, do not repeat the question, and do not include any other descriptive information."
        prompt += "Example output: Strong performance, but battery life needs improvement."
        answer = chatgpt(prompt)

        noise_message_list = []
        place = graph['places'][0]
        noise_message_list.append({
            'message': rewrite_message("The {} of my {} is {}.".format(place['relationship'], place['place_type'], place['place_name']), charact),
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

        question, choices, ground_truth = formulate_QA_additional_judge(question, answer)

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

    def generate_condition_facts_01a_place(graph):
        time_clock = TimeClock()
        charact = graph['user_profile']['character']
        message_list = []
        noise_message_list = []
        question_list = []

        place = graph['places'][0]
        message_list.append({
            'message': rewrite_message("The {} of my {} is {}.".format(place['relationship'], place['place_type'], place['place_name']), charact),
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
            'message': rewrite_message("The {} of my {} is {}.".format(item['relationship'], item['item_type'], item['item_name']), charact),
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

        question = "What is my {} of {}?".format(place['relationship'], place['place_type'])

        prompt = "Please summarize my comment concisely in two short sentences: {}\n".format(place['place_review'])
        prompt += "Only output the summary, do not repeat the question, and do not include any other descriptive information."
        prompt += "Example output: Beautiful environment, but inconvenient transportation."
        answer = chatgpt(prompt)

        question, choices, ground_truth = formulate_QA_additional_judge(question, answer)

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

    output_path_item = outpath_pre + '02_conditional_items.json'
    output_path_place = outpath_pre + '02_conditional_places.json'
    data_list_item = []
    data_list_place = []
    for index, graph in enumerate(graph_list):
        print('--- {} Graph ---'.format(index))
        for trj in range(trajectory_per_graph_new):
            message_list, question_list = generate_condition_facts_01a_item(graph)
            data_list_item.append({
                'tid': len(data_list_item),
                'message_list': message_list,
                'question_list': question_list
            })
            print('{} Finish!'.format(len(data_list_item) - 1))
        for trj in range(trajectory_per_graph_new):
            message_list, question_list = generate_condition_facts_01a_place(graph)
            data_list_place.append({
                'tid': len(data_list_place),
                'message_list': message_list,
                'question_list': question_list
            })
            print('{} Finish!'.format(len(data_list_place) - 1))

        with open(output_path_item, 'w', encoding='utf-8') as f:
            json.dump(data_list_item, f, indent=4, ensure_ascii=False)
        with open(output_path_place, 'w', encoding='utf-8') as f:
            json.dump(data_list_place, f, indent=4, ensure_ascii=False)

def generate_memory_and_questions(demo_mode=False):
    profiles_path = '../graphs.json'
    with open(profiles_path, 'r', encoding='utf-8') as f:
        graph_list = json.load(f)

    # generate_condition_role(graph_list)
    generate_condition_event(graph_list)
    # if not demo_mode:
    #     generate_condition_addition(graph_list)
    # else:
    #     generate_condition_addition(graph_list[:50])
    generate_condition_addition(graph_list)


if __name__ == "__main__":
    generate_memory_and_questions(True)



