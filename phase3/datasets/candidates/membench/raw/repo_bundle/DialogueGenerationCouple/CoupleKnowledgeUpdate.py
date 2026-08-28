## TODO:
## 完成Knowledge Update的对话形式
import os
import json
import numpy as np
import sys
import random
sys.path.append('..')
from utils import TimeClock, rewrite_message, formulate_QA, rewrite_question, rewrite_message_event, chatgpt
from prompt_template import couple_gen_prompt, couple_gen_prompt_event
import string

trajectory_per_graph = 1

output_pre_path = '../OutData/FirstAgent/LowLevel/'

def json_judge(data):
    try:
        data = json.loads(data)
        if data == None:
            return False
        for i in data:
            if 'assistant' not in i:
                return False
    except:
        return False
    return True

# 思路就是随机mask掉一个feature设计QA和单独的一轮target对话，其余profile部分作为对话bg用于生成对话
# 只设计1个问题
def generate_simple_session_role(graph_list):
    key_features = ['name', 'age', 'height', 'birthday', 'hometown', 'work_location', 'education', 'occupation', 'position', 'company_name', 'hobby', 'contact_number', 'email_address']
    round_length = 20
    session_num = 8

    def generate_couple_role_one_graph(graph):
        time_clock = TimeClock()
        charact = graph['user_profile']['character']
        session_list = []
        tid_role = 0

        # 选取聊天任务主题--角色
        role_list = graph['relation_profiles'] + graph['colleague_profiles']
        role_b1_id = np.random.choice(range(len(role_list)), size=session_num, replace=False)
        role_b1_list =  [role_list[id] for id in role_b1_id]
        for role_b1 in role_b1_list:
            relation = role_b1['relationship']
            # mask key feature
            mask_attr = np.random.choice(key_features, size=1, replace=False)[0]
            mask_value = role_b1[mask_attr]

            question = "What is my {}'s {}?".format(relation, mask_attr)
            answer = mask_value

            question, choices, ground_truth = formulate_QA(question, answer)

            noise_answer_id = np.random.choice(['A', 'B', 'C', 'D'])[0]
            while noise_answer_id == ground_truth:
                noise_answer_id = np.random.choice(['A', 'B', 'C', 'D'])[0]
            noise_answer = choices[noise_answer_id]

            text_user_noise = rewrite_message("My {}'s {} is {}.".format(relation, mask_attr, noise_answer))
            text_assistant_noise = chatgpt("[User's Message]:{}\nPlease, as a personal assistant, provide a reasonably short response to user's message, but within the scope of user's conversation and without mentioning new entities. Be careful not to end with a question".format(text_user_noise))

            # 利用Key feature生成证据对话
            text_user = rewrite_message("Sorry, I need to correct what I said earlier. My {}'s {} is {}.".format(relation, mask_attr, mask_value))
            text_assistant = chatgpt("[User's Message]:{}\nPlease, as a personal assistant, provide a reasonably short response to user's message, but within the scope of user's conversation and without mentioning new entities. Be careful not to end with a question".format(text_user))

            mask_dia_noise = {'user': text_user_noise, 'assistant': text_assistant_noise}
            mask_dia = {'user': text_user, 'assistant': text_assistant}

            # 剩余的feature作为topic feature生成对话
            topic_attr = [k for k in key_features if k != mask_attr]

            topic = ''
            for k in topic_attr:
                v = role_b1[k]
                topic += '{}: {}\n'.format(k, v)

            prompt = couple_gen_prompt.format(round_length=round_length, sentence_length = 2 * round_length, entity=relation, information=topic)

            max_tries = 10

            sessions = []
            while max_tries!= 0 :
                max_tries -= 1
                sessions = chatgpt(prompt).replace('```json', '').replace('```', '')
                if json_judge(sessions):
                    sessions = json.loads(sessions)
                    max_tries = 0
            
            print('role {} Finish!'.format(relation))


            target_step_id_noise, target_step_id = sorted(random.sample(range(len(sessions) + 2), 2))

            role_message_list = []

            sessions.insert(target_step_id_noise, mask_dia_noise)
            sessions.insert(target_step_id, mask_dia)

            target_step_id = [target_step_id]

            # 需要处理一下插入后的上下相关句，使之更加流畅
            # 暂时不处理
            # process_prompt = 

            for i in range(len(sessions)):
                if i == target_step_id_noise:
                    role_message_list.append({
                    'sid': i,
                    'user_message': sessions[i]['user'],
                    'assistant_message': sessions[i]['assistant'],
                    'time': time_clock.get_current_time(),
                    'place': graph['user_profile']['work_location'],
                    "rel": relation,
                    "attr": mask_attr,
                    "value": noise_answer
                    })
                elif i == target_step_id[0]:
                    role_message_list.append({
                    'sid': i,
                    'user_message': sessions[i]['user'],
                    'assistant_message': sessions[i]['assistant'],
                    'time': time_clock.get_current_time(),
                    'place': graph['user_profile']['work_location'],
                    "rel": relation,
                    "attr": mask_attr,
                    "value": mask_value
                    })
                else:
                    role_message_list.append({
                    'sid': i,
                    'user_message': sessions[i]['user'],
                    'assistant_message': sessions[i]['assistant'],
                    'time': time_clock.get_current_time(),
                    'place': graph['user_profile']['work_location']
                    })
                    time_clock.update_time_minute()
            
            question_json = {
                'qid': 0,
                'question': rewrite_question(question),
                'answer': answer,
                'target_step_id': target_step_id,
                'choices': choices,
                'ground_truth': ground_truth,
                'time': time_clock.get_current_time()
            }
            time_clock.update_time()

            session_list.append({'tid': tid_role, 'session': role_message_list, 'question': question_json})
            tid_role += 1
        
        return session_list
    
    data_list = []
    output_path = output_pre_path + '07_knowledgeupdate_roles_session.json'
    if os.path.exists(output_path):
        with open(output_path, 'r') as f:
            data_list = json.load(f)
    for index, graph in enumerate(graph_list):
        if index < len(data_list):
            continue
        print('--- %d graph ---' % index)
        for trj in range(trajectory_per_graph):
            session_list = generate_couple_role_one_graph(graph)
            data_list.append({
                'tid': len(data_list),
                'session_list': session_list
            })
            print(len(data_list)-1, 'finish!')
    
        with open(output_path,'w', encoding='utf-8') as f:
            json.dump(data_list, f, indent=4, ensure_ascii=False)


def generate_simple_session_events(graph_list):
    key_features = ['main_content', 'location', 'time', 'scale', 'duration']
    key_features_choice = ['location', 'time', 'scale', 'duration']
    round_length = 10
    session_num = 10

    def generate_couple_event_one_graph(graph):
        time_clock = TimeClock()
        charact = graph['user_profile']['character']
        session_list = []
        tid_event = 0

        # 选取聊天任务主题--event
        event_list = graph['work_events'] + graph['rest_events']
        event_c1_id = np.random.choice(range(len(event_list)), size=session_num, replace=False)
        event_c1_list =  [event_list[id] for id in event_c1_id]

        for event_c1 in event_c1_list:
            event_name = event_c1['event_name']
            # mask key feature
            mask_attr = np.random.choice(key_features_choice, size=1, replace=False)[0]
            mask_value = event_c1[mask_attr]

            question = "What is {}'s {}?".format(event_name, mask_attr)
            answer = mask_value
                
            question, choices, ground_truth = formulate_QA(question, answer)

            noise_answer_id = np.random.choice(['A', 'B', 'C', 'D'])[0]
            while noise_answer_id == ground_truth:
                noise_answer_id = np.random.choice(['A', 'B', 'C', 'D'])[0]
            noise_answer = choices[noise_answer_id]

            text_user_noise = rewrite_message("{}'s {} is {}.".format(event_name, mask_attr, noise_answer))
            text_assistant_noise = chatgpt("[User's Message]:{}\nPlease, as a personal assistant, provide a reasonably short response to user's message, but within the scope of user's conversation and without mentioning new entities. Be careful not to end with a question".format(text_user_noise))
            
            # 利用Key feature生成证据对话
            text_user = rewrite_message("Sorry, I need to correct what I said earlier. {}'s {} is {}.".format(event_name, mask_attr, mask_value))
            text_assistant = chatgpt("[User's Message]:{}\nPlease, as a personal assistant, provide a reasonably short response to user's message, but within the scope of user's conversation and without mentioning new entities. Be careful not to end with a question".format(text_user))
            
            mask_dia_noise = {'user': text_user_noise, 'assistant': text_assistant_noise}
            mask_dia = {'user': text_user, 'assistant': text_assistant}

            # 剩余的feature作为topic feature生成对话
            topic_attr = [k for k in key_features if k != mask_attr]

            topic = ''
            for k in topic_attr:
                v = event_c1[k]
                topic += '{}: {}\n'.format(k, v)
            
            prompt = couple_gen_prompt_event.format(round_length=round_length, sentence_length = 2 * round_length, event_name=event_name, information=topic)

            max_tries = 10

            sessions = []
            while max_tries!= 0 :
                max_tries -= 1
                sessions = chatgpt(prompt).replace('```json', '').replace('```', '')
                if json_judge(sessions):
                    sessions = json.loads(sessions)
                    max_tries = 0
            
            print('event {} Finish!'.format(event_name))

            target_step_id_noise, target_step_id = sorted(random.sample(range(len(sessions) + 2), 2))

            event_message_list = []

            sessions.insert(target_step_id_noise, mask_dia_noise)
            sessions.insert(target_step_id, mask_dia)

            target_step_id = [target_step_id]

            answer = mask_value

            for i in range(len(sessions)):
                if i == target_step_id_noise:
                    event_message_list.append({
                    'sid': i,
                    'user_message': sessions[i]['user'],
                    'assistant_message': sessions[i]['assistant'],
                    'time': time_clock.get_current_time(),
                    'place': graph['user_profile']['work_location'],
                    "rel": event_name,
                    'attr': mask_attr,
                    "value": noise_answer 
                    })
                elif i == target_step_id[0]:
                    event_message_list.append({
                    'sid': i,
                    'user_message': sessions[i]['user'],
                    'assistant_message': sessions[i]['assistant'],
                    'time': time_clock.get_current_time(),
                    'place': graph['user_profile']['work_location'],
                    "rel": event_name,
                    'attr': mask_attr,
                    "value": mask_value
                    })
                    if mask_attr == 'time' and 'next' in answer:
                        answer = time_clock.reltime_to_abstime(time_clock.get_current_timestamp(), answer)
                else:
                    event_message_list.append({
                    'sid': i,
                    'user_message': sessions[i]['user'],
                    'assistant_message': sessions[i]['assistant'],
                    'time': time_clock.get_current_time(),
                    'place': graph['user_profile']['work_location']
                    })
                time_clock.update_time_minute()
            
            question = "What is {}'s {}?".format(event_name, mask_attr)
            
            # if mask_attr == 'time' and 'next' in answer:
            #     answer = time_clock.reltime_to_abstime(time_clock.get_current_timestamp(), answer)
                
            question, choices, ground_truth = formulate_QA(question, answer)
            question_json = {
                'qid': 0,
                'question': rewrite_question(question),
                'answer': answer,
                'target_step_id': target_step_id,
                'choices': choices,
                'ground_truth': ground_truth,
                'time': time_clock.get_current_time()
            }
            time_clock.update_time()

            session_list.append({'tid': tid_event, 'session':event_message_list, 'question': question_json})
            tid_event += 1
        
        return session_list
    
    data_list = []
    output_path = output_pre_path + '07_knowledgeupdate_events_session.json'
    if os.path.exists(output_path):
        with open(output_path, 'r') as f:
            data_list = json.load(f)
    for index, graph in enumerate(graph_list):
        if index < len(data_list):
            continue
        print('--- %d graph ---' % index)
        for trj in range(trajectory_per_graph):
            session_list = generate_couple_event_one_graph(graph)
            data_list.append({
                'gid': len(data_list),
                'session_list': session_list
            })
            print(len(data_list)-1, 'finish!')
    
        with open(output_path,'w', encoding='utf-8') as f:
            json.dump(data_list, f, indent=4, ensure_ascii=False)
  

# item用place做噪声，place用item做噪声
def generate_simple_session_item_place(graph_list):

    def generate_couple_item_one_graph(graph):
     
        return 


def generate_memory_and_questions():
    profiles_path = '../graphs.json'
    with open(profiles_path,'r', encoding='utf-8') as f:
        graph_list = json.load(f)
    # generate_simple_session_role(graph_list)
    generate_simple_session_events(graph_list)
    # generate_simple_item_place(graph_list)


if __name__ == "__main__":
    generate_memory_and_questions()