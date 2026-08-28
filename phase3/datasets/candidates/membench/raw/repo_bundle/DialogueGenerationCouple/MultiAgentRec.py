# 如何创建multi session的
import os
import json
import numpy as np
import random
import sys
sys.path.append('..')
from utils import chatgpt, rewrite_message, TimeClock, formulate_QA
from prompt_template import extend_prompt, extend_prompt_couple, extend_prompt_couple_assistant
import copy


output_pre_path = '../OutData/FirstAgent/LowLevel/'


def load_json_data(path):
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)
    return data

def json_judge(data):
    if data == None:
        return False
    try:
        data = json.loads(data)
        for i in data:
            if 'user' not in i:
                return False
            if 'assistant' not in i:
                return False
            if i['user'] == None:
                return False
            if i['assistant'] == None:
                return False
    except:
        return False
    
    return True

start_message_map = {'movie': 'I like watching the movie {}', 'book': 'I like reading the book {}', 'dish': 'I like this {} dish'}

demand_rec_message_map = {'movie': 'Except for the movies mentioned earlier, could you recommend a wonderful movie for me to watch?', 
                          'dish': 'Except for the dishes mentioned earlier, Could you recommend a delicious dish for me to try?', 
                          'book': 'Except for the books mentioned earlier, Could you recommend a good book for me to read?'}

# question_map = {'movie': 'What movies have you recommended to me before?', 
#                 'dish': 'What dishes have you recommended to me before?', 
#                 'book': 'What books have you recommended to me before?'}


epsilon = 0.4

trajectory_per_graph = 1


highlevel_file_map = {'movie_genre_preference': 'HighLevelMovies.json', 'taste_preference': 'HighLevelFlavour.json', 'book_preference': 'HighLevelBook.json'}
kind_map = {'movie_genre_preference': 'movie', 'taste_preference': 'dish', 'book_preference': 'book'}


epsilon = 0.4
# 第一次为表达， 第二次为推荐，其余随机
def generate_low_level_session_one_graph(graph):
    time_clock = TimeClock()
    charact = graph['user_profile']['character']
    all_message_list = []
    question_list = []

    high_level_ = ['movie_genre_preference', 'taste_preference', 'book_preference']
    all_answer = []

    target_id_list = []

    pre_len = 0

    for high_level in high_level_:

        message_list = []

        path = "../rawDatasets/HighLevel/" + highlevel_file_map[high_level]
        low_level_data = load_json_data(path)

        kind = kind_map[high_level]

        high_level_list = graph['highlevel_preference'][high_level]
        # 获取high level的偏好
        if isinstance(high_level_list, list):
            high_level_preference = np.random.choice(high_level_list, size=1, replace=False)[0]
        else:
            high_level_preference = high_level_list
         # 利用high level: low level 的字典获取low level的表示, 从而获取QA和answer
        low_level_preference = np.random.choice(low_level_data[high_level_preference], size=random.choice([3]), replace=False)

        answer = []
        for i, low_i in enumerate(low_level_preference):
            rec_flag = False
            if i == 0:
                text_user = rewrite_message("I like the {} {}".format(kind, low_i))
                text_assistant = chatgpt("[User's Message]:{}\nPlease, as a personal assistant, provide a reasonably short response to user's message, but within the scope of user's conversation and without mentioning new entities".format(text_user))
                rec_flag = False
            elif i == 1:
                text_user = rewrite_message(demand_rec_message_map[kind])
                text_assistant = rewrite_message("I highly recommend the {} {}. You can try it!".format(kind, low_i))
                answer.append(low_i)
                rec_flag = True
            else:
                if random.random() <= epsilon:
                    text_user = rewrite_message(demand_rec_message_map[kind])
                    text_assistant = rewrite_message("I highly recommend the {} {}. You can try it".format(kind, low_i))
                    rec_flag = True
                    answer.append(low_i)
                else:
                    text_user = rewrite_message("I like the {} {}".format(kind, low_i))
                    text_assistant = chatgpt("[User's Message]:{}\nPlease, as a personal assistant, provide a reasonably short response to user's message, but within the scope of user's conversation and without mentioning new entities".format(text_user))
                
            if rec_flag:
                target_id_list.append(pre_len + copy.deepcopy(len(message_list)))

            message_list.append({
                    'user_message': text_user,
                    'assistant_message': text_assistant,
                    'time': time_clock.get_current_time(),
                    'place': graph['user_profile']['work_location']
                })
            time_clock.update_time_minute()

            extend_length = random.choice([2,3,4])

            max_tries = 20

            while max_tries!=0:
                max_tries-=1
                if rec_flag:
                    extend_text = chatgpt(extend_prompt_couple_assistant.format(kind=kind, entity=low_i, extend_length=extend_length, extend_length_new = 2 * extend_length))
                    if extend_text:
                        extend_text = extend_text.replace("```json", '').replace("```", '')
                else:
                    extend_text = chatgpt(extend_prompt_couple.format(kind=kind, entity=low_i, extend_length=extend_length, extend_length_new = 2 * extend_length))
                    if extend_text:
                        extend_text = extend_text.replace("```json", '').replace("```", '')

                if json_judge(extend_text):
                    extend_text = json.loads(extend_text)
                    max_tries=0

            for i in range(extend_length):
                message_list.append({
                'user_message': extend_text[i]['user'],
                'assistant_message': extend_text[i]['assistant'],
                'time': time_clock.get_current_time(),
                'place': graph['user_profile']['work_location']
                })
                time_clock.update_time_minute()
        
        pre_len += len(message_list)
            
        time_clock.update_time()
        
        all_message_list.append(copy.deepcopy(message_list))

        all_answer.append(copy.deepcopy(answer))
        
    print(all_answer)

    true_answer = [item for sub_answer in all_answer for item in sub_answer]
    
    other_answer = []

    if len(true_answer) == 3:
        other_answer.append("I haven't recommended you anything!")
    else:
        other_answer.append(copy.deepcopy(true_answer[1:]))
    
    other_answer.append(copy.deepcopy(true_answer[:1] + true_answer[2:]))

    other_answer.append(copy.deepcopy(true_answer[:-1]))

    question = 'What movies, books and dishes have you recommended to me?'

    question, choices, ground_truth = formulate_QA(question, answer=true_answer, other_answers=other_answer)
    question_list.append({
        'qid': 0,
        'question': question,
        'answer': true_answer,
        'target_step_id': target_id_list,
        'choices': choices,
        'ground_truth': ground_truth,
        'time': time_clock.get_current_time()
    })
    time_clock.update_time_minute()

    new_all_message_list = []
    for message_list in all_message_list:
        message_list = [{
            'mid': mid,
            'user': m['user_message'],
            'assistant': m['assistant_message'],
            'time': m['time'],
            'place': m['place']
        } for mid, m in enumerate(message_list)]
        
        new_all_message_list.append(message_list)
    
    return new_all_message_list, question_list


def data_judge(data):
    for message_list in data['message_list']:
        for message in message_list:
            if message['user'] == None or message['assistant'] == None:
                return False
    return True



def generate_low_level_session(graph_list):
    data_list = []
    output_path = "../OutData/FirstAgent/LowLevel/RecMultiSession.json" 
    if os.path.exists(output_path):
        with open(output_path, 'r') as f:
            data_list = json.load(f)
    for index, graph in enumerate(graph_list):
        if data_judge(data_list[index]):
            continue
        print('--- %d Graph ---' % index)
        for trj in range(trajectory_per_graph):
            message_list, question_list = generate_low_level_session_one_graph(graph)
            # data_list.append({
            #     'tid': len(data_list),
            #     'message_list': message_list,
            #     'question_list': question_list,
            # })
            data = {
                'tid': len(data_list),
                'message_list': message_list,
                'question_list': question_list,
            }
            tries = 0
            while data_judge(data) == False and tries <= 10:
                print('{} tries'.format(tries))
                message_list, question_list = generate_low_level_session_one_graph(graph)
                data = {
                    'tid': len(data_list),
                    'message_list': message_list,
                    'question_list': question_list,
                }
                tries += 1
            data_list[index] = data
            print(index, 'Finish!')
            
        with open(output_path,'w', encoding='utf-8') as f:
            json.dump(data_list, f, indent=4,ensure_ascii=False)


def generate_highlevel_memory_and_question():
    profiles_path = '../graphs.json'
    with open(profiles_path,'r', encoding='utf-8') as f:
        graph_list = json.load(f)
    generate_low_level_session(graph_list)
        

if __name__ == '__main__':
    generate_highlevel_memory_and_question()


