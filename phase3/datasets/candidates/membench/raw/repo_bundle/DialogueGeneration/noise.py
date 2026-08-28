import json
import numpy as np
import sys
sys.path.append('..')
from utils import chatgpt, TimeClock, rewrite_message, formulate_QA, rewrite_message_event, formulate_QA_additional_judge, rewrite_question_translate

# noise是在question上加noise
trajectory_per_graph = 1
outpath_pre = '../OutData/ThirdAgent/LowLevel/'


def rewrite_question_noise(noise, question):
    noise_adj_list = [
        "Oops, actually what I wanted to ask was: ",
        "Actually, my real question is: ",
        "Wait, what I really want to know is: ",
        "Hold on, what I actually wanted to understand is: ",
        "I got it wrong, what I really meant to ask is: ",
        "Sorry, what I truly wanted to ask is: ",
        "Oh, what I truly wanted to clarify is,",
        "Hmm, actually my question was this: ",
        "Wait a minute, what I wanted to ask is,",
        "Oh no, I actually wanted to figure out,",
        "Sorry about that, what I truly wanted to ask is,",
        "Oh right, I wanted to ask,",
        "What I really meant was,",
        "Wait a minute,",
        "Uh, hold on,"
    ]

    noise_adj = np.random.choice(noise_adj_list, size=1, replace=False)[0]

    return "{}{}{}".format(noise, noise_adj, question)


def generate_noise_condition_facts_role_06a(graph_list):
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
                'attr': (k, v),
                'message': text,
                'time': time_clock.get_current_time(),
                'place': graph['user_profile']['work_location']
            })
            time_clock.update_time()

        for qid in range(question_num):
            inx_01, inx_02 = np.random.choice(range(len(message_list)), size=2, replace=False)
            real_attr_01, real_attr_02 = message_list[inx_01], message_list[inx_02]
            question = "那个{}是{}的人, {}是什么?".format(real_attr_01['attr'][0], real_attr_01['attr'][1], real_attr_02['attr'][0])
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
                        'attr': (k, v)
                    })
                    time_clock.update_time()
            
            prompt = "[Context] {}\n".format(question)
            prompt += "Please randomly generate some murmuring that does not contain specific information from the context. Only output the murmur, without any other descriptive information.\n"
            prompt += "Example output: "
            prompt += "I met a client today, he seemed to be 25 years old, I can't quite remember his profession. When is my father's birthday again?"

            noise = chatgpt(prompt)
            question = rewrite_question_translate(question)
            question = rewrite_question_noise(noise, question)
            # print(question)

            question, choices, ground_truth = formulate_QA(question, answer)
            question_list.append({
                'qid': qid,
                'question': question,
                'answer': answer,
                'target_step_id': [int(inx_01), int(inx_02)],
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
    output_path = outpath_pre + '06_noisy_roles.json'
    for graph in graph_list:
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


def generate_noise_condition_facts_event_06b(graph_list):
    key_features = ['main_content', 'location', 'scale', 'duration']
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

        text = rewrite_message_event("I am going to attend {}.".format(event_C1['event_name']), charact)
        message_list.append({
            'name': event_C1['event_name'],
            'attr': ('Event I am attending', event_C1['event_name']),
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
                    if k == 'Event I am attending':
                        v = event_list[noise_event_id]['event_name']
                        text = rewrite_message_event("I am going to attend {}.".format(name), charact)
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
            if real_attr_01['attr'][0] == 'time' and real_attr_01['attr'][1][0] == 'next':
                abs_pre = real_attr_01['time']
                rel_pre = real_attr_01['attr'][1]
                rel_cur = time_clock.refine_rel_time(abs_pre, rel_pre, time_clock.get_current_timestamp())
                conditional_ans = rel_cur

            if real_attr_01['attr'][0] == 'main_content':
                question = "那个主要内容是\'{}\'的活动，{}是什么？".format(conditional_ans, real_attr_02['attr'][0])
            else:
                question = "那个{}是{}的活动, {}是什么?".format(real_attr_01['attr'][0], conditional_ans, real_attr_02['attr'][0])
            answer = real_attr_02['attr'][1]

            if real_attr_02['attr'][0] == 'time' and 'next' in answer:
                answer = time_clock.reltime_to_abstime(time_clock.get_current_timestamp(), answer)
            
            question = rewrite_question_translate(question)
            prompt = "[Context] {}\n".format(question)
            prompt += "Please randomly generate a murmur related to the context but without specific information from it. Only output the murmur, without any additional description.\n"
            prompt += "Example output: "
            prompt += "I met a client today, he seemed around 25 years old, but I can't recall his profession. When was my father's birthday again?"

            noise = chatgpt(prompt)
            question = rewrite_question_noise(noise, question)

            question, choices, ground_truth = formulate_QA(question, answer)
            question_list.append({
                'qid': qid,
                'question': question,
                'answer': answer,
                'target_step_id': [int(inx_01), int(inx_02)],
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
    output_path = outpath_pre + '06_noisy_events.json'
    for graph in graph_list:
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

trajectory_per_graph = 1  # 10


def generate_condition_facts_addition(graph_list):
  
    def generate_condition_facts_01a_item(graph):
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

        question = "How do you feel about my {}'s {}?".format(item['relationship'], item['item_type'])

        prompt = "Please summarize my review concisely in two sentences: {}\n".format(item['item_review'])
        prompt += "Output only the summary, do not repeat the question or provide any additional information."
        prompt += "Example output: High performance, battery life needs improvement"
        answer = chatgpt(prompt)

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

        prompt = "[Context] {}\n".format(question)
        prompt += "Please generate a random murmur unrelated to the context without specific details. Output only the murmur, no additional information.\n"
        prompt += "Example output: I met a client today, he seemed around 25, but I can’t recall his profession. When is my father's birthday again?"

        noise = chatgpt(prompt)
        question = rewrite_question_noise(noise, question)
        print(question)

        question, choices, ground_truth = formulate_QA_additional_judge(question, answer)

        question_list.append({
            'qid': 0,
            'question': question,
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

        question = "How do you feel about my {}'s {}?".format(place['relationship'], place['place_type'])

        prompt = "Please summarize my review concisely in two sentences: {}\n".format(place['place_review'])
        prompt += "Output only the summary, do not repeat the question or provide any additional information."
        prompt += "Example output: Beautiful environment, but inconvenient transportation"
        answer = chatgpt(prompt)

        prompt = "[Context] {}\n".format(question)
        prompt += "Please generate a random murmur unrelated to the context without specific details. Output only the murmur, no additional information.\n"
        prompt += "Example output: I met a client today, he seemed around 25, but I can’t recall his profession. When is my father's birthday again?"

        noise = chatgpt(prompt)
        question = rewrite_question_noise(noise, question)
        print(question)

        question, choices, ground_truth = formulate_QA_additional_judge(question, answer)

        question_list.append({
            'qid': 0,
            'question': question,
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

    output_path_item = outpath_pre + '06_noisy_items.json'
    output_path_place = outpath_pre + '06_noisy_places.json'
    data_list_item = []
    data_list_place = []
    for index, graph in enumerate(graph_list):
        print("--- {} Graph ---".format(index))
        for trj in range(trajectory_per_graph):
            message_list, question_list = generate_condition_facts_01a_item(graph)
            data_list_item.append({
                'tid': len(data_list_item),
                'message_list': message_list,
                'question_list': question_list
            })
            print("{} Finish!".format(len(data_list_item) - 1))
        for trj in range(trajectory_per_graph):
            message_list, question_list = generate_condition_facts_01a_place(graph)
            data_list_place.append({
                'tid': len(data_list_place),
                'message_list': message_list,
                'question_list': question_list
            })
            print("{} Finish!".format(len(data_list_place) - 1))
    
        with open(output_path_item, 'w', encoding='utf-8') as f:
            json.dump(data_list_item, f, indent=4, ensure_ascii=False)
        with open(output_path_place, 'w', encoding='utf-8') as f:
            json.dump(data_list_place, f, indent=4, ensure_ascii=False)

def generate_memory_and_questions(demo_mode=False):
    profiles_path = '../graphs.json'
    with open(profiles_path, 'r', encoding='utf-8') as f:
        graph_list = json.load(f)

    # generate_noise_condition_facts_role_06a(graph_list)
    generate_noise_condition_facts_event_06b(graph_list)
    generate_condition_facts_addition(graph_list)

if __name__ == '__main__':
    generate_memory_and_questions(demo_mode=True)


