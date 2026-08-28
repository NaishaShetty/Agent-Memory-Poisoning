## TODO:
## 1. 由user请求推荐，assistant进行推荐开始
## 2. 关键信息为user是否接受推荐
## 3. QA设计为genre偏好


## 有修改
import json
import numpy as np
import random
import sys
sys.path.append('..')
from utils import chatgpt, rewrite_message, TimeClock, formulate_QA
from prompt_template import extend_prompt_couple, extend_prompt_couple_assistant
import copy
import os


highlevel_file_map = {'movie_genre_preference': 'HighLevelMovies.json', 'taste_preference': 'HighLevelFlavour.json', 'book_preference': 'HighLevelBook.json'}
output_file_map = {'movie_genre_preference': 'highlevel_movie_rec_session.json', 'taste_preference': 'highlevel_food_rec_session.json', 'book_preference': 'highlevel_book_rec_session.json'}
kind_map = {'movie_genre_preference': 'movie', 'taste_preference': 'dish', 'book_preference': 'book'}
# kind_map_re = {'movie': 'movie_genre_preference', 'dish': 'taste_preference', 'book': 'book_preference'}

# movie_genre = ['Action', 'Adventure', 'Animation', 'Children', 'Comedy', 'Crime', 'Documentary', 'Drama', 'Drama', 'Fantasy', 'Film-Hoir', 'Horror', 'Musical', 'Mystery', 'Romance', 'Sci-Fi', 'Thriller', 'War', 'Western']


def load_json_data(path):
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)
    return data


def json_judge(data):
    if data == None:
        return False
    
    try:
        data = json.loads(data)
        if data == None:
            return False
        
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

question_map = {'movie': 'According to the movies I mentioned, what kind of movies might I prefer to watch?', 'dish': 'According to the dishes I mentioned, Which flavor I might prefer?', 'book': 'Accodring to the books I mentioned, What kind of books do I probably prefer to read?'}

start_rec_message_map = {'movie': 'Could you recommend a wonderful movie for me to watch?', 
                          'dish': 'Could you recommend a delicious dish for me to try?', 
                          'book': 'Could you recommend a good book for me to read?'}

demand_rec_message_map = {'movie': 'Except for the movies mentioned earlier, could you recommend a wonderful movie for me to watch?', 
                          'dish': 'Except for the dishes mentioned earlier, Could you recommend a delicious dish for me to try?', 
                          'book': 'Except for the books mentioned earlier, Could you recommend a good book for me to read?'}

rej_message_map = {'movie': "Sorry, according to what you said, the movie {} you recommended sounds really wonderful, but I'm still not interested enough in it",
                   'dish': "Sorry, according to what you said, the dish {} you recommended sounds really delicious, but I don't really want to eat it",
                   'book': "Sorry, according to what you said, the book {} you recommended sounds really wonderful, but I'm still not interested enough in it"}


def generate_low_level_session_one_graph(graph, high_level, low_level_data, kind):
    time_clock = TimeClock()
    charact = graph['user_profile']['character']
    # message_list = []
    question_list = []

    high_level_list = graph['highlevel_preference'][high_level]

    # path = "../rawDatasets/HighLevel/" + highlevel_file_map[kind_map_re[kind]]

    # 获取high level的偏好
    if isinstance(high_level_list, list):
        high_level_preference = np.random.choice(high_level_list, size=1, replace=False)[0]
    else:
        high_level_preference = high_level_list
    
    # 利用high level: low level 的字典获取low level的表示, 从而获取QA和answer
    low_level_preference = np.random.choice(low_level_data[high_level_preference], size=random.choice([3,4,5]), replace=False)
    
    # 根据这里给定的other answer中的high level选取low level干扰项
    other_answer = random.sample([x for x in low_level_data.keys() if x != high_level_preference], k=3)

    other_low_level_preference = []
    for other_genre in other_answer:
        other_low_level_preference.append(np.random.choice(low_level_data[other_genre], size=1)[0])
    
    to_data = low_level_preference[1:].tolist()
    to_data.extend(other_low_level_preference[:])
    # print(to_data)
    random.shuffle(to_data)
    # 保证第一个必然为喜好的
    # print(to_data)
    to_data.insert(0, low_level_preference[0])

    target_id_list = []
    
    epsilon_setting = 0.3
    all_message_list = []  ##########################
    prelen = 0
    for i, low_i in enumerate(to_data):
        message_list = []

        epsilon_getting = random.random()  # 设定这么一个值，使得一定概率不全是推荐，也有自己表达的部分
        is_like = True
        if low_i in other_low_level_preference:
            is_like = False

        if i == 0:
            # 第一个为了简单，保证为推荐，使得对话比较合适
            text_user = rewrite_message(start_rec_message_map[kind])
            while text_user == None:
                text_user = rewrite_message(start_rec_message_map[kind])

            text_assistant = rewrite_message('I highly recommend the {} {}'.format(kind, low_i))
        else:
            if epsilon_getting <= epsilon_setting:
                text_user = rewrite_message("Except the {} {}, I also like the {} {}".format(kind, to_data[i-1], kind, low_i))
                text_assistant = chatgpt("[User's Message]:{}\nPlease, as a personal assistant, provide a reasonably short response to user's message, but within the scope of user's conversation and without mentioning new entities".format(text_user))
            else: 
                text_user = rewrite_message(demand_rec_message_map['movie'])
                text_assistant = rewrite_message("I highly recommend the {} {}".format(kind, low_i))

        message_list.append({
                'user_message': text_user,
                'assistant_message': text_assistant,
                'time': time_clock.get_current_time(),
                'place': graph['user_profile']['work_location']
            })
        time_clock.update_time_minute()

        if is_like:
            target_id_list.append(prelen)

        extend_length = random.choice([2,3,4])

        if i != 0 and epsilon_getting <= epsilon_setting:
            prompt = extend_prompt_couple
        else:
            prompt = extend_prompt_couple_assistant

        max_tries = 30

        while max_tries!= 0:
            max_tries-=1
            extend_text = chatgpt(prompt.format(kind=kind, entity=low_i, extend_length=extend_length, extend_length_new = 2 * extend_length))
            if extend_text:
                extend_text = extend_text.replace("```json", '').replace("```", '')
            if json_judge(extend_text):
                extend_text = json.loads(extend_text)
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
        
        # 加一个拒绝的部分
        if is_like == False:
            text_user_rej = rewrite_message(rej_message_map[kind].format(low_i))
            text_assistant_rej = text_assistant = chatgpt("[User's Message]:{}\nPlease, as a personal assistant, provide a reasonably short response to user's message, but within the scope of user's conversation and without mentioning new entities".format(text_user_rej))
        
            message_list.append({
                'user_message': text_user_rej,
                'assistant_message': text_assistant_rej,
                'time': time_clock.get_current_time(),
                'place': graph['user_profile']['work_location']
            })
            time_clock.update_time_minute()
        
        prelen += len(message_list)
        all_message_list.append(copy.deepcopy(message_list))
        time_clock.update_time()

    question_num = 1

    for qid in range(question_num):
        question = question_map[kind]
        chatgpt("Rephrase this question without changing its core meaning. Question:{}. Only return new question".format(question))

        question, choices, ground_truth = formulate_QA(question, answer=high_level_preference, other_answers=other_answer)
        
        time_clock.update_time()
        question_list.append({
            'qid': qid,
            'question': question,
            'answer': high_level_preference,
            'target_step_id': target_id_list,
            'choices': choices,
            'ground_truth': ground_truth,
            'time': time_clock.get_current_time()
        })
    print("{}: question Finish!".format(kind))

    new_all_message_list = []
    for message_list in all_message_list:

        message_list_ = [{
            'mid': mid,
            'user': m['user_message'],
            'assistant': m['assistant_message'],
            'time': m['time'],
            'place': m['place']
        } for mid, m in enumerate(message_list)]

        new_all_message_list.append(copy.deepcopy(message_list_))

    return new_all_message_list, question_list

trajectory_per_graph = 1

def data_judge(data):
    for message_list in data['message_list']: 
        for message in message_list:
            if message['user'] == None or message['assistant'] == None:
                return False
    return True

def generate_low_level_session(graph_list):
    key_facture = ['movie_genre_preference', 'taste_preference', 'book_preference']

    for key in key_facture:
        path = "../rawDatasets/HighLevel/" + highlevel_file_map[key]
        LowLevelData = load_json_data(path)
        data_list = []
        output_path = "../OutData/FirstAgent/HighLevel/" + output_file_map[key]
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
                json.dump(data_list, f, indent=4, ensure_ascii=False)


def generate_highlevel_memory_and_question():
    profiles_path = '../graphs.json'
    with open(profiles_path,'r', encoding='utf-8') as f:
        graph_list = json.load(f)
    generate_low_level_session(graph_list)
        


if __name__ == '__main__':
    generate_highlevel_memory_and_question()


