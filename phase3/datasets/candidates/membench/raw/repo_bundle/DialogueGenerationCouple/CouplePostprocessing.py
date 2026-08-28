import json
import numpy as np
import sys
import random
import os
sys.path.append('..')
from utils import TimeClock, rewrite_message, formulate_QA, rewrite_question, rewrite_question_translate, chatgpt, other_answer_format
from prompt_template import couple_gen_prompt, couple_gen_prompt_event
import string

output_pre_path = '../OutData/FirstAgent/LowLevel/'

trajectory_per_graph = 1

def json_judge(data):
    try:
        json.loads(data)
    except:
        return False
    return True


def generate_other_choices_05(attr, answer, feature):
    def get_other_answers(res):
        ans_list = []
        lines = [l for l in res.splitlines() if l != '']
        if len(lines) != 3:
            return None
        for line in lines:
            if line[:len('A. ')] in ['A. ', 'B. ', 'C. ']:
                ans_list.append(line[len('A. '):])
            else:
                return None
        return ans_list

    prompt = 'Question: What is the {}?\n'.format(attr)
    prompt += 'Correct Answer: {}\n'.format(answer)
    prompt += 'Please help me generate three different confusing options based on the above question and answer.\n'
    prompt += 'If the correct answer is a string of numbers, you can modify 1 to 3 digits.\n'
    prompt += 'Please return it in json format. The output should follow the example format below:\n'
    prompt += "{{'A': 'Chengdu', 'B': 'Beijing', 'C':'Shanghai'}}"

    res = chatgpt(prompt, response_format=other_answer_format)
    other_answers = get_other_answers(res)

    max_tries = 10
    while not other_answers:
        res = chatgpt(prompt)
        max_tries -= 1
        other_answers = get_other_answers(res)
        if max_tries <= 0:
            other_answers = ['Unknown', 'None are correct', 'Not mentioned']

    other_features = []

    for oa in other_answers:
        prompt = 'Please provide a unique feature of {}, but do not include {}.\n'.format(oa, oa)
        prompt += 'Only output the feature, no additional descriptive content.\n'
        prompt += 'Example output: {}'.format(feature)

        other_features.append(chatgpt(prompt))
    return other_features


# 思路就是随机mask掉一个feature设计QA和单独的一轮target对话，其余profile部分作为对话bg用于生成对话
# 只设计1个问题
def generate_simple_session_role(graph_list):
    key_features = ['name', 'age', 'height', 'birthday', 'hometown', 'work_location', 'education', 'occupation', 'position', 'company_name', 'hobby', 'contact_number', 'email_address']
    targeted_features = ['name', 'birthday', 'work_location', 'occupation', 'hobby', 'contact_number', 'email_address']

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
            mask_attr = np.random.choice(targeted_features, size=1, replace=False)[0]
           
            mask_value = role_b1[mask_attr]

            mask_attr_other = np.random.choice(key_features, size=1, replace=False)[0]
            while mask_attr_other == mask_attr:
                mask_attr_other = np.random.choice(key_features, size=1, replace=False)[0]
            mask_value_other = role_b1[mask_attr_other]

            # 利用Key feature生成证据对话
            text_user_1= rewrite_message("My {}'s {} is {}.".format(relation, mask_attr, mask_value))
            text_assistant_1 = chatgpt("[User's Message]:{}\nPlease, as a personal assistant, provide a reasonably short response to user's message, but within the scope of user's conversation and without mentioning new entities. Be careful not to end with a question".format(text_user_1))

            text_user_2 = rewrite_message("My {}'s {} is {}.".format(relation, mask_attr_other, mask_value_other))
            text_assistant_2 = chatgpt("[User's Message]:{}\nPlease, as a personal assistant, provide a reasonably short response to user's message, but within the scope of user's conversation and without mentioning new entities. Be careful not to end with a question".format(text_user_2))

            mask_dia_1 = {'user': text_user_1, 'assistant': text_assistant_1}
            mask_dia_2 = {'user': text_user_2, 'assistant': text_assistant_2}

            # 剩余的feature作为topic feature生成对话
            topic_attr = [k for k in key_features if k != mask_attr and k != mask_attr_other]

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

            target_step_id_1, target_step_id_2 = sorted(random.sample(range(len(sessions) + 2), 2))
            target_step_id = [target_step_id_1, target_step_id_2]

            role_message_list = []

            sessions.insert(target_step_id_1, mask_dia_1)
            sessions.insert(target_step_id_2, mask_dia_2)

            # 需要处理一下插入后的上下相关句，使之更加流畅
            # 暂时不处理
            # process_prompt = 

            for i in range(len(sessions)):
                if i == target_step_id_1:
                    role_message_list.append({
                    'sid': i,
                    'user_message': sessions[i]['user'],
                    'assistant_message': sessions[i]['assistant'],
                    'time': time_clock.get_current_time(),
                    'place': graph['user_profile']['work_location'],
                    'rel': relation,
                    'attr': mask_attr,
                    'value': mask_value
                    })
                elif i == target_step_id_2:
                    role_message_list.append({
                    'sid': i,
                    'user_message': sessions[i]['user'],
                    'assistant_message': sessions[i]['assistant'],
                    'time': time_clock.get_current_time(),
                    'place': graph['user_profile']['work_location'],
                    'rel': relation,
                    'attr': mask_attr_other,
                    'value': mask_value_other
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
            
            if mask_attr in ['contact_number']:
                sum_num = int(np.random.choice(range(2, 6 + 1), size=1, replace=False)[0])
                question = "那个{}是{}的人, 其{}的后{}位之和是多少?".format(mask_attr_other, mask_value_other, mask_attr, sum_num)
                print(mask_value)
                answer = str(sum(int(digit) for digit in mask_value[-sum_num:]))
                print(answer)
                other_answers=None
            elif mask_attr in ['email_address']:
                question = "那个{}是{}的人, 其{}的后缀是多少?".format(mask_attr_other, mask_value_other, mask_attr)
                answer = mask_value[mask_value.find('@'):]
                other_answers=None
            elif mask_attr in ['name']:
                question = "那个{}是{}的人, 其{}的有几个字母?".format(mask_attr_other, mask_value_other, mask_attr)
                answer = '{} characters'.format(len(mask_value.replace(' ', '')))
                other_answers = ['{} characters'.format(i + len(mask_value.replace(' ', ''))) for i in [-1, 1, 2]]
            elif mask_attr in ['birthday']:
                question = "那个{}是{}的人, 其生日是在哪个季节?".format(mask_attr_other, mask_value_other)
                month_dig = int(mask_value.split('/')[0])
                print('Month: {} month ({})'.format(month_dig, mask_value))
                if 3 <= month_dig <= 5:
                    answer = 'Spring'
                elif 6 <= month_dig <= 8:
                    answer = 'Summer'
                elif 9 <= month_dig <= 11:
                    answer = 'Autumn'
                else:
                    answer = 'Winter'
                other_answers = [season for season in ['Spring', 'Summer', 'Autumn', 'Winter'] if answer != season]
            elif mask_attr in ['occupation']:
                work_explain = {
                    'Software Engineer': 'Develop, test, and maintain software applications',
                    'Doctor': 'Cure patients and ensure public health',
                    'Teacher': 'Educate and guide students',
                    'Lawyer': 'Uphold the law and provide legal services',
                    'Nurse': 'Assist doctors in treating patients',
                    'Chef': 'Prepare delicious food for customers',
                    'Accountant': 'Manage finances and ensure compliance',
                    'Sales Manager': 'Drive sales growth and manage sales teams',
                    'Bank Teller': 'Handle financial transactions and serve clients',
                    'Construction Worker': 'Perform various tasks on construction sites, including building, repairing, and maintaining structures',
                    'Graphic Designer': 'Create visual content to communicate messages',
                    'Journalist': 'Report news and disseminate information',
                    'Electrician': 'Install, repair, and maintain electrical systems',
                    'Data Analyst': 'Analyze data to support decision-making',
                    'Pilot': 'Fly and navigate aircraft safely',
                    'Social Worker': 'Support individuals in need and advocate for social change',
                    'Financial Advisor': 'Provide financial planning and investment advice',
                    'Real Estate Agent': 'Assist clients in buying and selling properties',
                    'Musician': 'Compose and perform music',
                    'Photographer': 'Capture images to tell stories or preserve memories',
                    'Police Officer': 'Maintain public safety and security',
                    'Programmer': 'Write code and develop software',
                    'Salesperson': 'Promote products and achieve sales goals',
                    'Designer': 'Create innovative designs',
                    'Courier': 'Deliver goods swiftly',
                    'Translator': 'Facilitate communication across languages',
                    'Farmer': 'Cultivate crops and raise livestock',
                    'Flight Attendant': 'Provide quality service to passengers',
                    'Truck Driver': 'Transport goods safely and punctually to designated locations',
                    'Researcher': 'Conduct studies and experiments to gain new knowledge and develop solutions in specific fields',
                    'Scientist': 'Conduct research and experiments to advance scientific understanding',
                    'Professor': 'Teach and conduct research at a university level',
                    'Engineer': 'Design, develop, and maintain systems and structures',
                    'Cashier': 'Process customer purchases and handle payments',
                    'Sales Associate': 'Assist customers and promote products in retail environments'
                }
                question = "那个{}是{}的人，其职业的主要职责是什么".format(mask_attr_other, mask_value_other)
                answer = work_explain[mask_value]

                other_works = np.random.choice(list(set(work_explain.keys()) - set(mask_value)), size=3, replace=False)
                other_answers = [work_explain[owk] for owk in other_works]
            elif mask_attr in ['hobby']:
                hobby_explain = {
                    'Hiking': 'Explore nature on foot and enjoy the scenery',
                    'Photography': 'Capture moments and record life',
                    'Reading': 'Enjoy the beauty of words, enrich the inner world',
                    'Traveling': 'Reading thousands of books is not as good as traveling thousands of miles',
                    'Cooking': 'Make delicious dishes and enjoy cooking',
                    'Gardening': 'Nurture plants and get close to nature',
                    'Fishing': 'Patiently wait and enjoy the pleasure of fishing',
                    'Cycling': 'Explore the outdoors on a bike',
                    'Yoga': 'Relax the body and mind, cultivate oneself',
                    'Running': 'Aerobic exercise to improve cardiovascular health',
                    'Watching Movies': 'Appreciate films and experience different lives',
                    'Playing Video Games': 'Experience fun in the virtual gaming world',
                    'Woodworking': 'Create functional or artistic pieces with wood',
                    'Collecting Antiques': 'Gather historical items and appreciate their value',
                    'Bird Watching': 'Observe and identify different bird species',
                    'Camping': 'Stay outdoors and enjoy the simplicity of nature',
                    'Knitting': 'Create handmade clothing and items with yarn',
                    'Writing': 'Express thoughts and record life through writing',
                    'Surfing': 'Ride the waves and enjoy the sea',
                    'Rock Climbing': 'Extreme sport that tests courage and skill',
                    'Volunteering': 'Help others and contribute to the community',
                    'Playing Musical Instruments': 'Express oneself through music',
                    'Sports': 'Enhance fitness and maintain health',
                    'Listening to Music': 'Relax and feel the beauty of melodies',
                    'Painting': 'Express emotions with a brush and create beauty',
                    'Dancing': 'Express yourself through dance and enjoy the rhythm',
                    'Fitness': 'Use weights and push-ups to shape the body',
                    'Handicrafts': 'Create with your hands and experience craftsmanship',
                    'Model Making': 'Delicate crafting that showcases creativity',
                    'Stamp Collecting': 'Collect stamps and learn about history',
                    'Swimming': 'Water-based exercise that trains the whole body',
                    'Climbing': 'Challenge oneself and conquer peaks',
                    'Playing Golf': 'A graceful sport that enhances coordination',
                    'Chess': 'A game of intellect that sharpens logical thinking',
                    'Programming': 'Write software to solve problems',
                    'Learning Languages': 'Master new languages to broaden horizons',
                    'Calligraphy': 'Practice calligraphy and inherit culture',
                    'Theater': 'Appreciate theater and experience the variety of life',
                    'Attending Concerts': 'Listen to live music and enjoy the artistic atmosphere'
                }
                question = "那个{}是{}的人, 其兴趣爱好的主要内容是什么?".format(mask_attr_other, mask_value_other)
                answer = hobby_explain[mask_value]

                other_hobbies = np.random.choice(list(set(hobby_explain.keys()) - set([mask_value])), size=3, replace=False)
                other_answers = [hobby_explain[owk] for owk in other_hobbies] 
            elif mask_attr in ['work_location']:
                place_explain = {
                    'New York, NY': 'The largest city in the U.S., known for its iconic skyline and diverse culture.',
                    'Los Angeles, CA': 'Famous for Hollywood, beaches, and a vibrant arts scene.',
                    'Chicago, IL': 'Known for its architecture, museums, and deep-dish pizza.',
                    'Houston, TX': 'A major city in Texas, known for its energy industry and space exploration.',
                    'Phoenix, AZ': 'The capital of Arizona, known for its hot desert climate.',
                    'Philadelphia, PA': 'Known for its historical significance and the Liberty Bell.',
                    'San Antonio, TX': 'Famous for the Alamo and its rich Texan culture.',
                    'San Diego, CA': 'Known for its beautiful beaches and mild climate.',
                    'Dallas, TX': 'A major business and cultural hub in Texas, known for its skyline.',
                    'San Jose, CA': 'The heart of Silicon Valley, known for its tech industry.',
                    'Austin, TX': 'The capital of Texas, known for its music scene and cultural events.',
                    'Jacksonville, FL': 'Known for its extensive park system and scenic waterfront.',
                    'San Francisco, CA': 'Known for the Golden Gate Bridge and its tech industry.',
                    'Columbus, OH': 'The capital of Ohio, known for its innovation and arts scene.',
                    'Charlotte, NC': 'A major financial hub in North Carolina, known for its NASCAR history.',
                    'Indianapolis, IN': 'Known for the Indianapolis 500 and its vibrant sports culture.',
                    'Seattle, WA': 'Famous for its coffee culture, tech industry, and the Space Needle.',
                    'Denver, CO': 'Known for its proximity to the Rocky Mountains and outdoor activities.',
                    'Washington, DC': 'The capital of the U.S., known for its national monuments and museums.',
                    'Boston, MA': 'Known for its history, education, and sports teams.',
                    'Atlanta, GA': 'A major cultural and economic center in the southeastern U.S.',
                    'Miami, FL': 'Known for its beaches, nightlife, and multicultural atmosphere.',
                    'Las Vegas, NV': 'Famous for its entertainment, casinos, and vibrant nightlife.',
                    'Portland, OR': 'Famous for its eco-friendliness and vibrant arts scene.',
                    'Orlando, FL': 'Known for its theme parks, including Walt Disney World.',
                    'New Orleans, LA': 'Famous for its unique culture, music, and cuisine.'
                }

                question = "那个{}是{}的人, 以下哪一项符合其工作地的描述?".format(mask_attr, mask_value)
                answer = place_explain[mask_value]

                other_places = np.random.choice(list(set(place_explain.keys()) - set(mask_value)), size=3, replace=False)
                other_answers = [place_explain[owk] for owk in other_places] 
            else:
                raise Exception("Role targeted attr error: {}.".format(mask_attr))
            
            
            question = rewrite_question_translate(question)
                
            question, choices, ground_truth = formulate_QA(question, answer, other_answers=other_answers)
            question_json = {
                'qid': 0,
                'question': rewrite_question_translate(question),
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
    output_path = output_pre_path + '05_post_processing_roles_session.json'
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


def generate_simple_session_events(graph_list):
    key_features = ['main_content', 'location', 'time', 'scale', 'duration']
    key_features_choice = ['location', 'time', 'scale', 'duration']
    target_features_choice = ['location', 'time']
    round_length = 10
    session_num = 10

    def generate_couple_event_one_graph(graph):
        time_clock = TimeClock()
        charact = graph['user_profile']['character']
        tid_event = 0
        session_list = []

        # 选取聊天任务主题--event
        event_list = graph['work_events'] + graph['rest_events']
        event_c1_id = np.random.choice(range(len(event_list)), size=session_num, replace=False)
        event_c1_list =  [event_list[id] for id in event_c1_id]

        for event_c1 in event_c1_list:
            event_name = event_c1['event_name']
            # mask key feature
            mask_attr = np.random.choice(target_features_choice, size=1, replace=False)[0]
            mask_value = event_c1[mask_attr]

            mask_attr_other = np.random.choice(key_features_choice, size=1, replace=False)[0]
            while mask_attr_other == mask_attr:
                mask_attr_other = np.random.choice(key_features_choice, size=1, replace=False)[0]

            mask_value_other = event_c1[mask_attr_other]

            # 利用Key feature生成证据对话
            text_user = rewrite_message("{}'s {} is {}.".format(event_name, mask_attr, mask_value))
            text_assistant = chatgpt("[User's Message]:{}\nPlease, as a personal assistant, provide a reasonably short response to user's message, but within the scope of user's conversation and without mentioning new entities. Be careful not to end with a question".format(text_user))

            text_user_other = rewrite_message("{}'s {} is {}.".format(event_name, mask_attr_other, mask_value_other))
            text_assistant_other = chatgpt("[User's Message]:{}\nPlease, as a personal assistant, provide a reasonably short response to user's message, but within the scope of user's conversation and without mentioning new entities. Be careful not to end with a question".format(text_user_other))

            mask_dia = {'user': text_user, 'assistant': text_assistant}
            mask_dia_other = {'user': text_user_other, 'assistant': text_assistant_other}

            # 剩余的feature作为topic feature生成对话
            topic_attr = [k for k in key_features if k != mask_attr and k != mask_attr_other]

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

            target_step_id_1, target_step_id_2 = sorted(random.sample(range(len(sessions) + 2), 2))
            target_step_id = [target_step_id_1, target_step_id_2]

            event_message_list = []

            sessions.insert(target_step_id_1, mask_dia)
            sessions.insert(target_step_id_2, mask_dia_other)


            for i in range(len(sessions)):
                if i == target_step_id_1:
                    event_message_list.append({
                    'sid': i,
                    'user_message': sessions[i]['user'],
                    'assistant_message': sessions[i]['assistant'],
                    'time': time_clock.get_current_time(),
                    'place': graph['user_profile']['work_location'],
                    'event_name': event_name,
                    'attr': mask_attr,
                    'value': mask_value 
                    })
                elif i == target_step_id_2:
                    event_message_list.append({
                    'sid': i,
                    'user_message': sessions[i]['user'],
                    'assistant_message': sessions[i]['assistant'],
                    'time': time_clock.get_current_time(),
                    'place': graph['user_profile']['work_location'],
                    'event_name': event_name,
                    'attr': mask_attr_other,
                    'value': mask_value_other
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

            
            if mask_attr in ['location']:
                city_explain = {
                    'New York, NY': 'The largest city in the U.S., known for its iconic skyline and diverse culture.',
                    'Los Angeles, CA': 'Famous for Hollywood, beaches, and a vibrant arts scene.',
                    'Chicago, IL': 'Known for its architecture, museums, and deep-dish pizza.',
                    'Houston, TX': 'A major city in Texas, known for its energy industry and space exploration.',
                    'Phoenix, AZ': 'The capital of Arizona, known for its hot desert climate.',
                    'Philadelphia, PA': 'Known for its historical significance and the Liberty Bell.',
                    'San Antonio, TX': 'Famous for the Alamo and its rich Texan culture.',
                    'San Diego, CA': 'Known for its beautiful beaches and mild climate.',
                    'Dallas, TX': 'A major business and cultural hub in Texas, known for its skyline.',
                    'San Jose, CA': 'The heart of Silicon Valley, known for its tech industry.',
                    'Austin, TX': 'The capital of Texas, known for its music scene and cultural events.',
                    'Jacksonville, FL': 'Known for its extensive park system and scenic waterfront.',
                    'San Francisco, CA': 'Known for the Golden Gate Bridge and its tech industry.',
                    'Columbus, OH': 'The capital of Ohio, known for its innovation and arts scene.',
                    'Charlotte, NC': 'A major financial hub in North Carolina, known for its NASCAR history.',
                    'Indianapolis, IN': 'Known for the Indianapolis 500 and its vibrant sports culture.',
                    'Seattle, WA': 'Famous for its coffee culture, tech industry, and the Space Needle.',
                    'Denver, CO': 'Known for its proximity to the Rocky Mountains and outdoor activities.',
                    'Washington, DC': 'The capital of the U.S., known for its national monuments and museums.',
                    'Boston, MA': 'Known for its history, education, and sports teams.',
                    'Atlanta, GA': 'A major cultural and economic center in the southeastern U.S.',
                    'Miami, FL': 'Known for its beaches, nightlife, and multicultural atmosphere.',
                    'Las Vegas, NV': 'Famous for its entertainment, casinos, and vibrant nightlife.',
                    'Portland, OR': 'Famous for its eco-friendliness and vibrant arts scene.',
                    'Orlando, FL': 'Known for its theme parks, including Walt Disney World.',
                    'New Orleans, LA': 'Famous for its unique culture, music, and cuisine.'
                }

                question = "那个{}是{}的活动, 哪一个符合它的活动地点描述?".format(mask_attr_other, mask_value_other)
                answer = city_explain[mask_value]

                other_cities = np.random.choice(list(set(city_explain.keys()) - set([mask_value])), size=3, replace=False)
                other_answers = [city_explain[owk] for owk in other_cities]

            elif mask_attr in ['time']:
                given_time = mask_value
                pre_abs_time = event_message_list[target_step_id_1]['time']
                pre_abs_time = pre_abs_time.rsplit(' ', 1)[0].replace("'", '')

                if 'next' in given_time:  # Given time is relative time.
                    new_given_time = time_clock.reltime_to_abstime(time_clock.format_time_to_timestamp(pre_abs_time), given_time)
                else:  # Given time is absolute time.
                    new_given_time = time_clock.calculate_reltime(time_clock.format_time_to_timestamp(pre_abs_time), given_time)

                answer = new_given_time
                other_answers = None
                
                question = "那个{}是{}的活动, 其{}是什么?".format(mask_attr_other, mask_value_other, mask_attr)
            else:
                raise Exception("Event targeted attribute error: {}.".format(mask_attr))
            
            question = rewrite_question_translate(question)
            question, choices, ground_truth = formulate_QA(question, answer, other_answers=other_answers)
            
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

            tid_event += 1

            session_list.append({'tid': tid_event, 'session':event_message_list, 'question': question_json})
        
        return session_list
    
    data_list = []
    output_path = output_pre_path + '05_post_processing_events_session.json'
    if os.path.exists(output_path):
        with open(output_path, 'r') as f:
            data_list = json.load(f)
    # Retri_index = [82, 129, 153, 175, 182, 207, 215, 218]
    for index, graph in enumerate(graph_list):
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
    generate_simple_session_role(graph_list)
    generate_simple_session_events(graph_list)
    # generate_simple_item_place(graph_list)


if __name__ == "__main__":
    generate_memory_and_questions()