import json
import numpy as np
import sys
import os
import random
sys.path.append('..')
from utils import TimeClock, rewrite_message, formulate_QA, rewrite_question, rewrite_question_translate, chatgpt, rewrite_message_role, rewrite_message_event
from prompt_template import couple_gen_prompt, couple_gen_prompt_event
import string

output_pre_path = '../OutData/FirstAgent/LowLevel/'

trajectory_per_graph = 1

def json_judge(data):
    try:
        if data == None:
            return False
        data = json.loads(data)
        for i in data:
            if 'user' not in i:
                return False
            if 'assistant' not in i:
                return False
    except:
        return False
    return True

# 思路就是随机mask掉一个feature设计QA和单独的一轮target对话，其余profile部分作为对话bg用于生成对话
# 只设计1个问题
def generate_session_role_long(graph_list):
    key_features = ['name', 'age', 'height', 'birthday', 'hometown', 'work_location', 'education', 'occupation', 'position', 'company_name', 'hobby', 'contact_number', 'email_address']
    key_features_choice = ['age', 'height', 'birthday', 'hometown', 'work_location', 'education']
    round_length = 20
    session_num = 1

    def get_QA_info(whole_message_str, aggr_attr_k):
        prompt = '[User Information] {}\n'.format('\n'.join(whole_message_str))
        prompt += 'Based on the above user information, for the aspect of {}, please generate a counting question starting with "How many people...?", in a casual first-person style.\n'.format(aggr_attr_k)
        prompt += 'Only output the generated question, do not provide any other descriptive information.\n'
        prompt += 'Example output: How many people are aged 35 or below?\n'

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

    def generate_couple_role_one_graph(graph):
        time_clock = TimeClock()
        charact = graph['user_profile']['character']
        session_list = []

        # 选取聊天任务主题--角色
        role_list = graph['relation_profiles'] + graph['colleague_profiles']
        # 选取准备聚合的对象
        mask_attr_list = np.random.choice(key_features_choice, size=session_num, replace=False)

        role_message_list = []
        tid_attr = 0
        target_step_id = []

        for qid, mask_attr in enumerate(mask_attr_list):
            whole_message_str = []
        
            for role in role_list:
                relation = role['relationship']
                # mask key feature
                mask_value = role[mask_attr]
                name = role['name']
                gender = 'his'
                if role['gender'] == 'Female':
                    gender = 'her'

                # 利用Key feature生成证据对话
                text_user = rewrite_message_role("{} is my {}, and {} {} is {}.".format(name, relation, gender, mask_attr, mask_value), charact)
                whole_message_str.append(text_user)

                text_assistant = chatgpt("[User's Message]:{}\nPlease, as a personal assistant, provide a reasonably short response to user's message, but within the scope of user's conversation and without mentioning new entities. Be careful not to end with a question".format(text_user))

                mask_dia = {'user': text_user, 'assistant': text_assistant}

                # 剩余的feature作为topic feature生成对话
                topic_attr = [k for k in key_features if k != mask_attr]

                topic = ''
                for k in topic_attr:
                    v = role[k]
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

                target_step_id_one = random.sample(range(len(sessions) + 1), 1)[0]
                target_step_id.append(target_step_id_one + len(role_message_list))

                role_message_list_one_role = []

                sessions.insert(target_step_id_one, mask_dia)
                
                # 需要处理一下插入后的上下相关句，使之更加流畅
                # 暂时不处理
                # process_prompt = 

                for i in range(len(sessions)):
                    if i == target_step_id_one:
                        role_message_list_one_role.append({
                        'sid': i + len(role_message_list),
                        'user_message': sessions[i]['user'],
                        'assistant_message': sessions[i]['assistant'],
                        'time': time_clock.get_current_time(),
                        'place': graph['user_profile']['work_location'],
                        'rel': relation,
                        'attr': mask_attr,
                        'value': mask_value
                    })
                    else:
                        role_message_list_one_role.append({
                            'sid': i + len(role_message_list),
                            'user_message': sessions[i]['user'],
                            'assistant_message': sessions[i]['assistant'],
                            'time': time_clock.get_current_time(),
                            'place': graph['user_profile']['work_location']
                        })
                    time_clock.update_time_minute()
                
                role_message_list.extend(role_message_list_one_role)
                
            question, answer = get_QA_info(whole_message_str, mask_attr)

            tries = 0
            while question == None or answer == None:
                print('{} tries!'.format(tries))
                question, answer = get_QA_info(whole_message_str, mask_attr)
                tries += 1

            if question is None:
                question, choices, ground_truth = '[ERRORQ]', '[ERRORC]', '[ERRORG]'
            else:
                question, choices, ground_truth = formulate_QA(question, answer)
                    
            question, choices, ground_truth = formulate_QA(question, answer)
            question_json = {
                'qid': qid,
                'question': rewrite_question_translate(question),
                'answer': answer,
                'target_step_id': target_step_id,
                'choices': choices,
                'ground_truth': ground_truth,
                'time': time_clock.get_current_time()
            }
            time_clock.update_time()

            tid_attr += 1

            session_list.append({'tid': tid_attr, 'session': role_message_list, 'question': question_json})
            
        return session_list
        
    data_list = []
    output_path = output_pre_path + '04_aggregative_roles_session.json'
    if os.path.exists(output_path):
        with open(output_path, 'r') as f:
            data_list = json.load(f)
    
    for index, graph in enumerate(graph_list):
        # if index < len(data_list):
        #     continue
        if check_null(data_list[index]):
            continue
        print('--- %d graph ---' % index)
        for trj in range(trajectory_per_graph):
            session_list = generate_couple_role_one_graph(graph)
            # data_list.append({
            #     'gid': len(data_list),
            #     'session_list': session_list
            # })
            data_list[index] = {
                'gid': index,
                'session_list': session_list
            }
            print(len(data_list)-1, 'finish!')
    
        with open(output_path,'w', encoding='utf-8') as f:
            json.dump(data_list, f, indent=4, ensure_ascii=False)


def generate_session_event_long(graph_list):
    key_features = ['main_content', 'time', 'location', 'scale', 'duration']
    key_features_choice = ['location', 'scale', 'duration']
    round_length = 10
    session_num = 1

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
        print(question, answer)
        return question, answer

    def generate_couple_event_one_graph(graph):
        time_clock = TimeClock()
        charact = graph['user_profile']['character']
        session_list = []

        # 选取聊天任务主题--角色
        event_list = graph['work_events'] + graph['rest_events']
        # 选取准备聚合的对象
        mask_attr_list = np.random.choice(key_features_choice, size=session_num, replace=False)

        event_message_list = []
        tid_attr = 0
        target_step_id = []

        for qid, mask_attr in enumerate(mask_attr_list):
            whole_message_str = []
        
            for event in event_list:
                
                # mask key feature
                mask_value = event[mask_attr]
                name = event['event_name']

                # 利用Key feature生成证据对话
                text_user = rewrite_message_event("{}'s {} is {}.".format(name, mask_attr, mask_value), charact)
                whole_message_str.append(text_user)

                text_assistant = chatgpt("[User's Message]:{}\nPlease, as a personal assistant, provide a reasonably short response to user's message, but within the scope of user's conversation and without mentioning new entities. Be careful not to end with a question".format(text_user))

                mask_dia = {'user': text_user, 'assistant': text_assistant}

                # 剩余的feature作为topic feature生成对话
                topic_attr = [k for k in key_features if k != mask_attr]

                topic = ''
                for k in topic_attr:
                    v = event[k]
                    topic += '{}: {}\n'.format(k, v)

                prompt = couple_gen_prompt_event.format(round_length=round_length, sentence_length = 2 * round_length, event_name=name, information=topic)

                max_tries = 10

                sessions = []
                while max_tries!= 0 :
                    max_tries -= 1
                    sessions = chatgpt(prompt).replace('```json', '').replace('```', '')
                    if json_judge(sessions):
                        sessions = json.loads(sessions)
                        max_tries = 0
                
                print('event {} Finish!'.format(name))


                target_step_id_one = random.sample(range(len(sessions) + 1), 1)[0]
                target_step_id.append(target_step_id_one + len(event_message_list))

                event_message_list_one_event = []

                sessions.insert(target_step_id_one, mask_dia)
                
                # 需要处理一下插入后的上下相关句，使之更加流畅
                # 暂时不处理
                # process_prompt = 
                j = 0
                for i in range(len(sessions)):
                    if i == target_step_id_one:
                        event_message_list_one_event.append({
                        'sid': i + len(event_message_list),
                        'user_message': sessions[i]['user'],
                        'assistant_message': sessions[i]['assistant'],
                        'time': time_clock.get_current_time(),
                        'place': graph['user_profile']['work_location'],
                        'rel': name,
                        'attr': mask_attr,
                        'value': mask_value
                    })
                    else: 
                        event_message_list_one_event.append({
                            'sid': i + len(event_message_list),
                            'user_message': sessions[i]['user'],
                            'assistant_message': sessions[i]['assistant'],
                            'time': time_clock.get_current_time(),
                            'place': graph['user_profile']['work_location']
                        })
                    time_clock.update_time_minute()
                
                event_message_list.extend(event_message_list_one_event)
                
            question, answer = get_QA_info(whole_message_str, mask_attr)

            tries = 0
            while question == None or answer == None:
                print('{} tries!'.format(tries))
                question, answer = get_QA_info(whole_message_str, mask_attr)
                tries += 1

            if question is None:
                question, choices, ground_truth = '[ERRORQ]', '[ERRORC]', '[ERRORG]'
            else:
                question, choices, ground_truth = formulate_QA(question, answer)
                    
            question, choices, ground_truth = formulate_QA(question, answer)
            question_json = {
                'qid': qid,
                'question': rewrite_question_translate(question),
                'answer': answer,
                'target_step_id': target_step_id,
                'choices': choices,
                'ground_truth': ground_truth,
                'time': time_clock.get_current_time()
            }
            time_clock.update_time()

            tid_attr += 1

            session_list.append({'tid': tid_attr, 'session': event_message_list, 'question': question_json})
            
        return session_list
        
    data_list = []
    output_path =output_pre_path +  '04_aggregative_events_session.json'
    if os.path.exists(output_path):
        with open(output_path, 'r') as f:
            data_list = json.load(f)
    for index, graph in enumerate(graph_list):
        # if index < len(data_list):
        #     continue
        if check_null(data_list[index]):
            continue
        print('--- %d graph ---' % index)
        for trj in range(trajectory_per_graph):
            session_list = generate_couple_event_one_graph(graph)
            # data_list.append({
            #     'gid': len(data_list),
            #     'session_list': session_list
            # })
            data_list[index] = {
                'gid': index,
                'session_list': session_list
            }
            print(len(data_list)-1, 'finish!')
    
        with open(output_path,'w', encoding='utf-8') as f:
            json.dump(data_list, f, indent=4, ensure_ascii=False)
  

# item用place做噪声，place用item做噪声
def generate_simple_session_item_place(graph_list):

    def generate_couple_item_one_graph(graph):
     
        return 

def check_null(gid):
    for tid_ in gid['session_list']:
        for session in tid_['session']:
            if session['user_message'] == None or session['assistant_message'] == None: 
                return False
        if tid_['question']['question'] == None or tid_['question']['answer'] == None:
            return False
    return True


def generate_memory_and_questions():
    profiles_path = '../graphs.json'
    with open(profiles_path,'r', encoding='utf-8') as f:
        graph_list = json.load(f)
    # generate_simple_session_role(graph_list)
    generate_session_role_long(graph_list)
    # generate_session_event_long(graph_list)
    # generate_simple_item_place(graph_list)
    print('yes')

if __name__ == "__main__":
    generate_memory_and_questions()