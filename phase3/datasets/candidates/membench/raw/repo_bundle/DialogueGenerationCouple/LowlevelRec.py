## TODO: 
## 1.在high level对话的基础上加上请求推荐
## 2.每次指定交互需要以threshold的概率进行推荐交互，否则为表达交互，如果为推荐交互，则需要把推荐列物品放入给定集合
## 3.QA设定为assistant所推荐过的low level集合, 因为这里不设计到high level的喜好，所以low level 不需要有什么特别的要求，只是为了code方便
## 4.只有第一人称交互式对话
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

question_map = {'movie': 'What movies have you recommended to me before?', 
                'dish': 'What dishes have you recommended to me before?', 
                'book': 'What books have you recommended to me before?'}


epsilon = 0.4
# 第一次为表达， 第二次为推荐，其余随机
def generate_low_level_session_one_graph(graph, high_level, low_level_data, kind):
    time_clock = TimeClock()
    charact = graph['user_profile']['character']
    message_list = []
    question_list = []

    high_level_list = graph['highlevel_preference'][high_level]

    # 获取high level的偏好
    if isinstance(high_level_list, list):
        high_level_preference = np.random.choice(high_level_list, size=1, replace=False)[0]
    else:
        high_level_preference = high_level_list
    
    # 利用high level: low level 的字典获取low level的表示, 从而获取QA和answer
    low_level_preference = np.random.choice(low_level_data[high_level_preference], size=random.choice([4,5]), replace=False)

    target_id_list = []
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
            target_id_list.append(copy.deepcopy(len(message_list)))

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
                extend_text=json.loads(extend_text)
                max_tries=0
                
        print('{}: {} session Finish!'.format(kind, i))

        for i in range(extend_length):
            message_list.append({
            'user_message': extend_text[i]['user'],
            'assistant_message': extend_text[i]['assistant'],
            'time': time_clock.get_current_time(),
            'place': graph['user_profile']['work_location']
            })
            time_clock.update_time_minute()
        
    question_num = 1

    other_answer = []

    if len(answer) == 1:
        other_answer.append("I haven't recommended you anything!")
    else:
        other_answer.append(copy.deepcopy(answer[1:]))
    
    other_answer.append(copy.deepcopy(answer[:] + [low_level_preference[0]]))

    other_answer.append(copy.deepcopy(answer[1:] + [low_level_preference[0]]))

    while len(other_answer) != 3:
        noise_answer_i = np.random.choice(low_level_preference, size=len(answer), replace=False)
        if set(answer) != set(noise_answer_i):
            other_answer.append(noise_answer_i)

    
    # print(answer)
    # for i in other_answer:
    #     print(i)
    
    for qid in range(question_num):
        question = question_map[kind]
        chatgpt("Rephrase this question without changing its core meaning. Question:{}. Only return new question".format(question))
        time_clock.update_time()
        question, choices, ground_truth = formulate_QA(question, answer=answer, other_answers=other_answer)
        question_list.append({
            'qid': qid,
            'question': question,
            'answer': answer,
            'target_step_id': target_id_list,
            'choices': choices,
            'ground_truth': ground_truth,
            'time': time_clock.get_current_time()
        })
    print("{}: question Finish!".format(kind))

    message_list = [{
        'mid': mid,
        'user': m['user_message'],
        'assistant': m['assistant_message'],
        'time': m['time'],
        'place': m['place']
    } for mid, m in enumerate(message_list)]

    return message_list, question_list


highlevel_file_map = {'movie_genre_preference': 'HighLevelMovies.json', 'taste_preference': 'HighLevelFlavour.json', 'book_preference': 'HighLevelBook.json'}
output_file_map = {'movie_genre_preference': 'lowlevel_movie_rec.json', 'taste_preference': 'lowlevel_food_rec.json', 'book_preference': 'lowlevel_book_rec.json'}
kind_map = {'movie_genre_preference': 'movie', 'taste_preference': 'dish', 'book_preference': 'book'}

trajectory_per_graph = 1


def data_judge(data):
    for message in data['message_list']:
        if message['user'] == None or message['assistant'] == None:
            return False
    return True


def generate_low_level_session(graph_list):
    key_facture = ['movie_genre_preference', 'taste_preference', 'book_preference']

    for key in key_facture:
        path = "../rawDatasets/HighLevel/" + highlevel_file_map[key]
        LowLevelData = load_json_data(path)
        data_list = []
        output_path = "../OutData/FirstAgent/LowLevel/" + output_file_map[key]
        if os.path.exists(output_path):
            with open(output_path, 'r') as f:
                data_list = json.load(f)
        for index, graph in enumerate(graph_list):
            if data_judge(data_list[index]):
                continue
            print('--- %d Graph ---' % index)
            for trj in range(trajectory_per_graph):
                message_list, question_list = generate_low_level_session_one_graph(graph, key, LowLevelData, kind_map[key])
                data = {
                'tid': len(data_list),
                'message_list': message_list,
                'question_list': question_list,
                }
                tries = 0
                while data_judge(data) == False and tries <= 10:
                    print('{} tries'.format(tries))
                    message_list, question_list = generate_low_level_session_one_graph(graph, key, LowLevelData, kind_map[key])
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
