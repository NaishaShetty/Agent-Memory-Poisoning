import json
import os
import numpy as np
import random
import sys
sys.path.append('..')
from utils import chatgpt, rewrite_message, TimeClock, formulate_QA
from prompt_template import extend_prompt, extend_prompt_couple
import copy


def load_json_data(path):
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)
    return data


def json_judge(data):
    try:
        json.loads(data)
        if data == None:
            return False
    except:
        return False
    return True

start_message_map = {'movie': 'I like watching the movie {}', 'book': 'I like reading the book {}', 'dish': 'I like this {} dish'}

question_map = {'movie': 'According to the movies I mentioned, what kind of movies might I prefer to watch?', 'dish': 'According to the dishes I mentioned, Which flavor I might prefer?', 'book': 'Accodring to the books I mentioned, What kind of books do I probably prefer to read?'}


def generate_low_level_message_one_graph(graph, high_level, low_level_data, kind):
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
    low_level_preference = np.random.choice(low_level_data[high_level_preference], size=random.choice([3,4,5]), replace=False)
    other_answer = random.sample([x for x in low_level_data.keys() if x != high_level_preference], k=3)

    target_id_list = []
    for i, low_i in enumerate(low_level_preference):
        if i == 0:
            text = rewrite_message("I like the {} {}".format(kind, low_i))
        else:
            text = rewrite_message("Except the {} {}, I also like the {} {}".format(kind, low_level_preference[i-1], kind, low_i))
        target_id_list.append(copy.deepcopy(len(message_list)))
        message_list.append({
                'message': text,
                'time': time_clock.get_current_time(),
                'place': graph['user_profile']['work_location']
            })
        time_clock.update_time_minute()

        extend_length = random.choice([1,2,3,4])

        max_tries = 10

        while max_tries!=0:
            max_tries-=1
            extend_text = chatgpt(extend_prompt.format(kind=kind, entity=low_i, extend_length=extend_length)).replace("```json", '').replace("```", '')
            if json_judge(extend_text):
                extend_text=json.loads(extend_text)
                max_tries=0
        print('{}: {} message Finish!'.format(kind, i))

        for i in range(extend_length):
            message_list.append({
            'message': extend_text[i][str(i+1)],
            'time': time_clock.get_current_time(),
            'place': graph['user_profile']['work_location']
            })
            time_clock.update_time_minute()
        
    question_num = 1
    
    for qid in range(question_num):
        question = question_map[kind]
        chatgpt("Rephrase this question without changing its core meaning. Question:{}. Only return new question".format(question))

        question, choices, ground_truth = formulate_QA(question, answer=high_level_preference, other_answers=other_answer)
        question_list.append({
            'qid': qid,
            'question': question,
            'answer': high_level_preference,
            'target_step_id': target_id_list,
            'choices': choices,
            'ground_truth': ground_truth,
            'time': time_clock.get_current_time()
        })
        time_clock.update_time_minute()
    print("{}: question Finish!".format(kind))

    message_list = [{
        'mid': mid,
        'message': m['message'],
        'time': m['time'],
        'place': m['place']
    } for mid, m in enumerate(message_list)]

    return message_list, question_list


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
    low_level_preference = np.random.choice(low_level_data[high_level_preference], size=random.choice([3,4,5]), replace=False)
    other_answer = random.sample([x for x in low_level_data.keys() if x != high_level_preference], k=3)

    target_id_list = []
    for i, low_i in enumerate(low_level_preference):
        if i == 0:
            text_user = rewrite_message("I like the {} {}".format(kind, low_i))
            text_assistant = chatgpt("[User's Message]:{}\nPlease, as a personal assistant, provide a reasonably short response to user's message, but within the scope of user's conversation and without mentioning new entities".format(text_user))
        else:
            text_user = rewrite_message("Except the {} {}, I also like the {} {}".format(kind, low_level_preference[i-1], kind, low_i))
            text_assistant = chatgpt("[User's Message]:{}\nPlease, as a personal assistant, provide a reasonably short response to user's message, but within the scope of user's conversation and without mentioning new entities".format(text_user))

        target_id_list.append(copy.deepcopy(len(message_list)))
        message_list.append({
                'user_message': text_user,
                'assistant_message': text_assistant,
                'time': time_clock.get_current_time(),
                'place': graph['user_profile']['work_location']
            })
        time_clock.update_time_minute()

        extend_length = random.choice([2,3,4])

        max_tries = 10

        while max_tries!=0:
            max_tries-=1
            extend_text = chatgpt(extend_prompt_couple.format(kind=kind, entity=low_i, extend_length=extend_length, extend_length_new = 2 * extend_length)).replace("```json", '').replace("```", '')
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

    for qid in range(question_num):
        question = question_map[kind]
        chatgpt("Rephrase this question without changing its core meaning. Question:{}. Only return new question".format(question))

        question, choices, ground_truth = formulate_QA(question, answer=high_level_preference, other_answers=other_answer)
        question_list.append({
            'qid': qid,
            'question': question,
            'answer': high_level_preference,
            'target_step_id': target_id_list,
            'choices': choices,
            'ground_truth': ground_truth,
            'time': time_clock.get_current_time()
        })
        time_clock.update_time_minute()
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
output_file_map = {'movie_genre_preference': 'highlevel_movie', 'taste_preference': 'highlevel_food', 'book_preference': 'highlevel_book'}
kind_map = {'movie_genre_preference': 'movie', 'taste_preference': 'dish', 'book_preference': 'book'}

trajectory_per_graph = 1


def generate_low_level_message(graph_list):
    
    # key_facture = ['movie_genre_preference', 'taste_preference', 'book_preference']
    key_facture = ['book_preference']

    for key in key_facture:
        path = "../rawDatasets/HighLevel/" + highlevel_file_map[key]
        LowLevelData = load_json_data(path)
        data_list = []
        output_path = "../OutData/ThirdAgent/HighLevel/" + output_file_map[key] + '_messages.json'

        with open(output_path, 'r') as f:
            data_list = json.load(f)
        # print(len(data_list))
        for index, graph in enumerate(graph_list):
            if index <= 436:
                continue
            print('--- %d Graph ---' % index)
            for trj in range(trajectory_per_graph):
                message_list, question_list = generate_low_level_message_one_graph(graph, key, LowLevelData, kind_map[key])
                data_list.append({
                    'gid': len(data_list),
                    'message_list': message_list,
                    'question_list': question_list,
                })
                print(len(data_list)-1, 'Finish!')
        #print(data_list)
            with open(output_path,'w', encoding='utf-8') as f:
                json.dump(data_list, f, indent=4,ensure_ascii=False)


def generate_low_level_session(graph_list):
    # key_facture = ['movie_genre_preference', 'taste_preference']
    key_facture = ['book_preference']

    for key in key_facture:
        path = "../rawDatasets/HighLevel/" + highlevel_file_map[key]
        LowLevelData = load_json_data(path)
        data_list = []
        output_path = "../OutData/FirstAgent/HighLevel/" + output_file_map[key] + '_sessions.json'
        if os.path.exists(output_path):
            with open(output_path, 'r') as f:
                data_list = json.load(f)
        for index, graph in enumerate(graph_list):
            if index < len(data_list):
                continue
            print('--- %d Graph ---' % index)
            for trj in range(trajectory_per_graph):
                message_list, question_list = generate_low_level_session_one_graph(graph, key, LowLevelData, kind_map[key])
                data_list.append({
                    'tid': len(data_list),
                    'message_list': message_list,
                    'question_list': question_list,
                })
                print(len(data_list)-1, 'Finish!')
                
            with open(output_path,'w', encoding='utf-8') as f:
                json.dump(data_list, f, indent=4,ensure_ascii=False)


def generate_highlevel_memory_and_question():
    profiles_path = '../graphs.json'
    with open(profiles_path,'r', encoding='utf-8') as f:
        graph_list = json.load(f)
    # generate_low_level_message(graph_list)
    generate_low_level_session(graph_list)


if __name__ == '__main__':
    generate_highlevel_memory_and_question()
