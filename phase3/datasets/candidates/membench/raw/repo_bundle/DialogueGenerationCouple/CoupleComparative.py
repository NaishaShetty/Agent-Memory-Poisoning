import json
import os
import numpy as np
import sys
import random
sys.path.append('..')
from utils import TimeClock, rewrite_message, rewrite_question, rewrite_question_translate, chatgpt, get_choices
from prompt_template import couple_gen_prompt, couple_gen_prompt_event, compare_couple_prompt

output_pre_path = '../OutData/FirstAgent/LowLevel/'

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
def generate_simple_session_role(graph_list):
    key_features = ['name', 'age', 'height', 'birthday', 'hometown', 'work_location', 'education', 'occupation', 'position', 'company_name', 'hobby', 'contact_number', 'email_address']
    key_features_choice = ['age', 'height', 'birthday', 'education']

    round_length = 20
    session_num =  4

    def generate_couple_role_one_graph(graph):
        time_clock = TimeClock()
        charact = graph['user_profile']['character']
        session_list = []

        # 选取聊天任务主题--角色
        role_list = graph['relation_profiles'] + graph['colleague_profiles']
        role_b1_id = np.random.choice(range(len(role_list)), size=session_num * 2, replace=False)
        role_list_choice =  [role_list[id] for id in role_b1_id]
        tid_role = 0
        for i in range(0, len(role_list_choice), 2):
            role_b1 = role_list_choice[i]
            role_b2 = role_list_choice[i+1]

            relation_b1 = role_b1['relationship']
            relation_b2 = role_b2['relationship']
            # mask key feature
            mask_attr = np.random.choice(key_features_choice, size=1, replace=False)[0]
            mask_value_1 = role_b1[mask_attr]
            mask_value_2 = role_b2[mask_attr]

            # 利用Key feature生成证据对话
            text_user_1 = rewrite_message("{} is my {}, their {} is {}.".format(role_b1['name'], relation_b1, mask_attr, mask_value_1))
            text_assistant_1 = chatgpt("[User's Message]:{}\nPlease, as a personal assistant, provide a reasonably short response to user's message, but within the scope of user's conversation and without mentioning new entities. Be careful not to end with a question".format(text_user_1))

            text_user_2 = rewrite_message("{} is my {}, their {} is {}.".format(role_b2['name'], relation_b2, mask_attr, mask_value_2))
            text_assistant_2 = chatgpt("[User's Message]:{}\nPlease, as a personal assistant, provide a reasonably short response to user's message, but within the scope of user's conversation and without mentioning new entities. Be careful not to end with a question".format(text_user_2))

            mask_dia_1 = {'user': text_user_1, 'assistant': text_assistant_1}
            mask_dia_2 = {'user': text_user_2, 'assistant': text_assistant_2}

            # 剩余的feature作为topic feature生成对话
            topic_attr = [k for k in key_features if k != mask_attr]

            topic_1 = ''
            for k in topic_attr:
                v = role_b1[k]
                topic_1 += '{}: {}\n'.format(k, v)

            prompt = couple_gen_prompt.format(round_length=round_length, sentence_length = 2 * round_length, entity=relation_b1, information=topic_1)

            max_tries = 10

            sessions = []
            while max_tries != 0 :
                max_tries -= 1
                sessions = chatgpt(prompt)
                if sessions != None:
                    sessions = sessions.replace('```json', '').replace('```', '')
                if json_judge(sessions):
                    sessions = json.loads(sessions)
                    max_tries = 0
            
            print('role {} Finish!'.format(relation_b1))

            target_step_id_1 = random.sample(range(len(sessions) + 1), 1)[0]
            sessions.insert(target_step_id_1, mask_dia_1)

            topic_2 = ''
            for k in topic_attr:
                v = role_b2[k]
                topic_2 += '{}: {}\n'.format(k, v)

            prompt = couple_gen_prompt.format(round_length=round_length, sentence_length = 2 * round_length, entity=relation_b2, information=topic_2)

            max_tries = 10

            sessions_2 = []
            while max_tries!= 0 :
                max_tries -= 1
                sessions_2 = chatgpt(prompt)
                if sessions_2 != None:
                    sessions_2 = sessions_2.replace('```json', '').replace('```', '')
                if json_judge(sessions_2):
                    sessions_2 = json.loads(sessions_2)
                    max_tries = 0
            
            print('role {} Finish!'.format(relation_b2))

            target_step_id_2 = random.sample(range(len(sessions_2) + 1), 1)[0]
            sessions_2.insert(target_step_id_2, mask_dia_2)

            target_step_id_2 = target_step_id_2 + len(sessions)
            sessions.extend(sessions_2)

            target_step_id = [target_step_id_1, target_step_id_2]

            role_message_list = []

            # 需要处理一下插入后的上下相关句，使之更加流畅
            # 暂时不处理
            # process_prompt = 
            # print(len(sessions))
            # print(len(sessions_2))

            for i in range(len(sessions)):
                if i == target_step_id_1:
                    role_message_list.append({
                    'sid': i,
                    'user_message': sessions[i]['user'],
                    'assistant_message': sessions[i]['assistant'],
                    'time': time_clock.get_current_time(),
                    'place': graph['user_profile']['work_location'],
                    'rel': relation_b1,
                    'attr': mask_attr,
                    'value': mask_value_1
                    })
                elif i == target_step_id_2:
                    role_message_list.append({
                    'sid': i,
                    'user_message': sessions[i]['user'],
                    'assistant_message': sessions[i]['assistant'],
                    'time': time_clock.get_current_time(),
                    'place': graph['user_profile']['work_location'],
                    'rel': relation_b2,
                    'attr': mask_attr,
                    'value': mask_value_2
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
            
            nameB1 = role_b1['name']
            nameB2 = role_b2['name']
            
            prompt = '[Info] {}\'s {} is {}; {}\'s {} is {}.\n'.format(nameB1, mask_attr, mask_value_1, nameB2, mask_attr, mask_value_2)
            prompt += 'Based on the information of the two people provided, please generate a question to compare {}.'.format(mask_attr)
            prompt += 'The answer should be {}, {} or both the same.\n'.format(nameB1, nameB2)
            prompt += 'Only output the generated question, do not output the answer, and do not output other descriptive information.\n'
            prompt += 'Output example: Who has a higher position, Zhang San or Li Si?'
            question = chatgpt(prompt)

            prompt = '[Info] {}\'s {} is {}; {}\'s {} is {}.\n'.format(nameB1, mask_attr, mask_value_1, nameB2, mask_attr, mask_value_2)
            prompt += 'Based on the information of the two people provided, please help me answer the question: {}.\n'.format(question)
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
            
            question_json = {
                'qid': 0,
                'question': question,
                'answer': answer,
                'target_step_id': target_step_id,
                'choices': choices,
                'ground_truth': ground_truth,
                'time': time_clock.get_current_time()
            }

################################这里要加入tid#######################################
            session_list.append({'tid': tid_role, 'session': role_message_list, 'question': question_json})
            tid_role += 1
        return session_list
    
    data_list = []
    output_path = output_pre_path + '03_comparative_roles_session.json'
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
            print(len(data_list) - 1, 'finish!')
    
        with open(output_path,'w', encoding='utf-8') as f:
            json.dump(data_list, f, indent=4, ensure_ascii=False)


def generate_simple_session_events(graph_list):
    key_features = ['main_content', 'location', 'time', 'scale', 'duration']
    key_features_choice = ['scale', 'duration']
    round_length = 10
    session_num = 5

    def generate_couple_event_one_graph(graph):
        time_clock = TimeClock()
        charact = graph['user_profile']['character']
        session_list = []
        tid_event = 0

        # 选取聊天任务主题--event
        event_list = graph['work_events'] + graph['rest_events']
        event_c1_id = np.random.choice(range(len(event_list)), size=session_num * 2, replace=False)
        event_list_choice =  [event_list[id] for id in event_c1_id]

        for i in range(0, len(event_list_choice), 2):
            event_c1 = event_list_choice[i]
            event_c2 = event_list_choice[i+1]

            event_name_1 = event_c1['event_name']
            event_name_2 = event_c2['event_name']

            # mask key feature
            mask_attr= np.random.choice(key_features_choice, size=1, replace=False)[0]
            mask_value_1 = event_c1[mask_attr]
            mask_value_2 = event_c2[mask_attr]

            # 利用Key feature生成证据对话
            text_user_1 = rewrite_message("{}'s {} is {}.".format(event_name_1, mask_attr, mask_value_1))
            text_assistant_1 = chatgpt("[User's Message]:{}\nPlease, as a personal assistant, provide a reasonably short response to user's message, but within the scope of user's conversation and without mentioning new entities. Be careful not to end with a question".format(text_user_1))

            text_user_2 = rewrite_message("{}'s {} is {}.".format(event_name_2, mask_attr, mask_value_2))
            text_assistant_2 = chatgpt("[User's Message]:{}\nPlease, as a personal assistant, provide a reasonably short response to user's message, but within the scope of user's conversation and without mentioning new entities. Be careful not to end with a question".format(text_user_2))

            mask_dia_1 = {'user': text_user_1, 'assistant': text_assistant_1}
            mask_dia_2 = {'user': text_user_2, 'assistant': text_assistant_2}

            # 剩余的feature作为topic feature生成对话
            topic_attr = [k for k in key_features if k != mask_attr]

            topic_1 = ''
            for k in topic_attr:
                v = event_c1[k]
                topic_1 += '{}: {}\n'.format(k, v)

            prompt = couple_gen_prompt_event.format(round_length=round_length, sentence_length = 2 * round_length, event_name=event_name_1, information=topic_1)

            max_tries = 10

            sessions = []
            while max_tries!= 0 :
                max_tries -= 1
                sessions = chatgpt(prompt).replace('```json', '').replace('```', '')
                if json_judge(sessions):
                    sessions = json.loads(sessions)
                    max_tries = 0
            
            print('event {} Finish!'.format(event_name_1))

            target_step_id_1 = random.sample(range(len(sessions) + 1), 1)[0]
            sessions.insert(target_step_id_1, mask_dia_1)

            topic_2 = ''
            for k in topic_attr:
                v = event_c2[k]
                topic_2 += '{}: {}\n'.format(k, v)

            prompt = couple_gen_prompt_event.format(round_length=round_length, sentence_length = 2 * round_length, event_name = event_name_2, information=topic_2)

            max_tries = 10

            sessions_2 = []
            while max_tries!= 0 :
                max_tries -= 1
                sessions_2 = chatgpt(prompt).replace('```json', '').replace('```', '')
                if json_judge(sessions_2):
                    sessions_2 = json.loads(sessions_2)
                    max_tries = 0
            
            print('event {} Finish!'.format(event_name_2))


            target_step_id_2 = random.sample(range(len(sessions) + 1), 1)[0]
            sessions_2.insert(target_step_id_2, mask_dia_2)

            target_step_id_2 = target_step_id_2 + len(sessions)

            sessions.extend(sessions_2)            
            target_step_id = [target_step_id_1, target_step_id_2]

            event_message_list = []
            for i in range(len(sessions)):
                if i == target_step_id_1:
                     event_message_list.append({
                    'sid': i,
                    'user_message': sessions[i]['user'],
                    'assistant_message': sessions[i]['assistant'],
                    'time': time_clock.get_current_time(),
                    'place': graph['user_profile']['work_location'],
                    'rel': event_name_1,
                    'attr': mask_attr,
                    'value': mask_value_1
                    })
                elif i == target_step_id_2:
                    event_message_list.append({
                    'sid': i,
                    'user_message': sessions[i]['user'],
                    'assistant_message': sessions[i]['assistant'],
                    'time': time_clock.get_current_time(),
                    'place': graph['user_profile']['work_location'],
                    'rel': event_name_2,
                    'attr': mask_attr,
                    'value': mask_value_2
                    })
                else:
                    event_message_list.append({
                    'sid': i,
                    'user_message': sessions[i]['user'],
                    'assistant_message': sessions[i]['assistant'],
                    'time': time_clock.get_current_time(),
                    'place': graph['user_profile']['work_location']
                    })
                time_clock.update_time_minute()
            
            prompt = '[Info] {}\'s {} is {}; {}\'s {} is {}.\n'.format(event_name_1, mask_attr, mask_value_1, event_name_2, mask_attr, mask_value_2)
            prompt += 'Based on the information of the two events provided, please generate a question that compares them from the perspective of {}.'.format(mask_attr)
            prompt += ' Only output the generated question, do not output other descriptive information.\n'
            prompt += 'Output example: Which event has a larger scale, the Innovation Competition or the Food Festival?'
            question = chatgpt(prompt)
        
            prompt = '[Info] {}\'s {} is {}; {}\'s {} is {}.\n'.format(event_name_1, mask_attr, mask_value_1, event_name_2, mask_attr, mask_value_2)
            prompt += 'Based on the information of the two events provided, please help me answer the question: {}.\n'.format(question)
            prompt += 'If you cannot determine based on the information, please output Unable to determine; if both are the same, please output Both the same; otherwise, the answer should be {} or {}.\n'.format(event_name_1, event_name_2)

            prompt += 'Only output the answer to this question, do not output other descriptive information, do not output reasoning or explanations.\n'
            prompt += 'Output example: Unable to determine'

            ans_pre = chatgpt(prompt)
            ans_ex = chatgpt('RandomSeed({})\n{}'.format(np.random.randint(1, 100), prompt))
            max_try = 0
            while ans_ex != ans_pre:
                ans_pre = ans_ex
                ans_ex = chatgpt('RandomSeed({})\n{}'.format(np.random.randint(1, 100), prompt))
                max_try += 1
                print('tries:{}'.format(max_try))
                if max_try >= 50:
                    ans_ex = None
            
            if ans_ex:
                answer = ans_ex
            else:
                answer = None
            
            if answer:
                question, choices, ground_truth = formulate_QA(question, answer, event_name_1, event_name_2)
            else:
                choices, ground_truth = '[ERRORC]', '[ERRORG]'
            
            question_json = {
                'qid': 0,
                'question': question,
                'answer': answer,
                'target_step_id': target_step_id,
                'choices': choices,
                'ground_truth': ground_truth,
                'time': time_clock.get_current_time()
            }
            time_clock.update_time()

            session_list.append({'tid': tid_event, 'session':event_message_list, 'question': question_json})
        
        return session_list
    
    data_list = []
    output_path = output_pre_path + '03_comparative_events_session.json'
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
  

def check_null(gid):
    for tid_ in gid['session_list']:
        for session in tid_['session']:
            if session['user_message'] == None or session['assistant_message'] == None: 
                return False
        if tid_['question']['question'] == None or tid_['question']['answer'] == None:
            return False
    return True


# item用place做噪声，place用item做噪声
def generate_simple_session_item_place(graph_list):

    def generate_couple_item_one_graph(graph):
     
        return 


def generate_memory_and_questions():
    profiles_path = '../graphs.json'
    with open(profiles_path,'r', encoding='utf-8') as f:
        graph_list = json.load(f)
    generate_simple_session_role(graph_list)
    # generate_simple_session_events(graph_list)
    # generate_simple_item_place(graph_list)


if __name__ == "__main__":
    generate_memory_and_questions()