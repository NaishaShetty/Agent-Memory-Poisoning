## TODO: 加入抽样的代码
import os
import json
import sys
sys.path.append('..')
from utils import TimeClock
import numpy as np
import random


def load_json(path):
    with open(path,'r',encoding='utf-8') as f:
        data = json.load(f)
    # new_data = {}
    # for i, j in data.items():
    #     new_data[i] = j[:5]
    return data
    # return new_data

def save_json(data, path):
    with open(path,'w', encoding='utf-8') as f:
        json.dump(data,f, indent=4,ensure_ascii=False)


def infuse_single_trajectory_message(traj, noise_pool, length):
    if length == 0:
        noisy_traj = {}
        noisy_traj['tid'] = traj['tid']
        noisy_traj['message_list'] =  ['{} (place: {}; time{})'.format(m['message'], m['place'], m['time']) for m in traj['message_list']]
        noisy_traj['QA'] = traj['QA']
        return noisy_traj
    
    noisy_traj = {}
    noisy_traj['tid'] = traj['tid']
    new_message_list = []
    raw_message_list = traj['message_list']

    total_step = len(raw_message_list) + length  # 一个noise message长度为3

    # print(len(raw_message_list))
    tmp = sorted(np.random.choice(range(total_step), size=len(raw_message_list), replace=False))
    # print(len(tmp))
    relocate_dict = {(int(tmp) - index) * 3 + index : index for index, tmp in enumerate(tmp)}
    reverse_relocate_dict = {index: (int(tmp) - index) * 3 + index for index, tmp in enumerate(tmp)}
    # print(relocate_dict)
    # reverse_relocate_dict = {index:int(tmp) for index, tmp in enumerate(tmp)}  ## 方便获取新的target_step_id
    
    noise_list = np.random.choice(noise_pool, size=length, replace=False)
    noise_id = 0
    index = 0
    
    while index < len(raw_message_list) + (3 * length) - 1:
        # print(index)
        if index in relocate_dict:
            # print(index)
            re_index = relocate_dict[index]
            new_message_list.append('{} (place: {}; time{})'.format(raw_message_list[re_index]['message'], raw_message_list[re_index]['place'], raw_message_list[re_index]['time']))
        else:
            ##TODO: 这里noise_message的格式不对，不能这样直接append----------------------------------------------------
            # print(noise_id)
            noise_message = ['{}'.format(i['message']) for i in noise_list[noise_id]['noise_message']]
            new_message_list.extend(noise_message)
            noise_id += 1
            
            index += 2 ## 连续跳过4个
            # print(index)
        index += 1
        # print('---------------')
    
    noisy_traj['message_list'] = new_message_list
    noisy_traj['QA'] = traj['QA']
    noisy_traj['QA']['target_step_id'] = [reverse_relocate_dict[step_id] for step_id in noisy_traj['QA']['target_step_id']]

    return noisy_traj


# 实现对message的延长
def MakeNoiseMessage(RawDataPath, length = 10):
    NoiseDataPath = '../MakeNoiseNew/NoiseMeta/messagenoise_new.json'
    NoisePool = load_json(NoiseDataPath)

    output_data = {}

    RawData = load_json(RawDataPath)
    for QAtype, QAtype_data in RawData.items():  # 获得simple
        output_data[QAtype] = {}
        for scenario, scenario_data in QAtype_data.items():  # 获得role
            output_data[QAtype][scenario] = []
            print(QAtype, scenario)
            scenario_traj_all = []
            for traj in scenario_data:
                noisy_traj = infuse_single_trajectory_message(traj, NoisePool, length)
                # output_data[QAtype][scenario].append(noisy_traj)
                scenario_traj_all.append(noisy_traj)
            if length == 0:
                scenario_traj_all = random.sample(scenario_traj_all, 10)
            elif length == 100:
                scenario_traj_all = random.sample(scenario_traj_all, 3)
            elif length == 99:
                scenario_traj_all = random.sample(scenario_traj_all, 10)
            output_data[QAtype][scenario] = scenario_traj_all
            print(QAtype, scenario, 'Finish!')
    
    RawDataPathSplit = RawDataPath.split('/') 
    output_path = RawDataPathSplit[0] + '/' + 'data2test/' + RawDataPathSplit[1].replace('.json', '') + '_multiple_{}.json'.format(length)
    save_json(output_data, output_path)

def infuse_single_trajectory_message_special(traj, noise_pool, length):
    # print(len(traj['message_list']))
    if length == 0:
        noisy_traj = {}
        noisy_traj['tid'] = traj['tid']
        noisy_traj['message_list'] =  ['{} (place: {}; time{})'.format(m['message'], m['place'], m['time']) for m in traj['message_list'][0]]
        noisy_traj['QA'] = traj['QA']
        noisy_traj['QA']['target_step_id'] = [id[0] for id in noisy_traj['QA']['target_step_id']]

        return noisy_traj
    
    noisy_traj = {}
    noisy_traj['tid'] = traj['tid']
    new_message_list = []
    raw_message_list = traj['message_list'] ## 这里格式为[[], [], []]

    total_traj = len(raw_message_list) + length

    tmp = sorted(np.random.choice(range(total_traj), size=len(raw_message_list), replace=False))
    relocate_dict = {int(tmp): index for index, tmp in enumerate(tmp)}
    reverse_relocate_dict = {index: int(tmp)-index for index, tmp in enumerate(tmp)}

    noise_list = np.random.choice(noise_pool, size=length, replace=False)
    noise_id = 0
    re_index = 0
    # print(tmp)
    for index in range(total_traj):
        if index in tmp:
            # print(raw_message_list)
            for i in raw_message_list[re_index]:
                # print(i)
                new_message_list.append('{} (place: {}; time{})'.format(i['message'], i['place'], i['time']))
            re_index += 1
        else:
            noise_message = ['{}'.format(i['message']) for i in noise_list[noise_id]['noise_message']]
            new_message_list.extend(noise_message)
            noise_id += 1
    
    noisy_traj['message_list'] = new_message_list
    noisy_traj['QA'] = traj['QA']
    
    noisy_traj['QA']['target_step_id'] = [reverse_relocate_dict[step_id[1]] * 3 + step_id[0] for step_id in noisy_traj['QA']['target_step_id']]

    return noisy_traj


def MakeNoiseMessageHighLevel(RawDataPath, length):
    NoiseDataPath = '../MakeNoiseNew/NoiseMeta/messagenoise_new.json'
    NoisePool = load_json(NoiseDataPath)

    output_data = {}

    RawData = load_json(RawDataPath)
    for QAtype, QAtype_data in RawData.items():  # 获得simple
        output_data[QAtype] = {}
        for scenario, scenario_data in QAtype_data.items():  # 获得role
            output_data[QAtype][scenario] = []
            print(QAtype, scenario)
            scenario_traj_all_pre = []
            for traj in scenario_data:
                noisy_traj = infuse_single_trajectory_message_special(traj, NoisePool, length)
                scenario_traj_all_pre.append(noisy_traj)
            if length == 0:
                scenario_traj_all = random.sample(scenario_traj_all_pre, 20)
            # elif length == 50:
            #     scenario_traj_all = random.sample(scenario_traj_all,  )
            elif length == 100 or length == 500:
                scenario_traj_all = random.sample(scenario_traj_all_pre, 5)
            else:
                print('......')
                return False
            output_data[QAtype][scenario] = scenario_traj_all
            print(QAtype, scenario, 'Finish!')
    
    print(len(output_data))
    RawDataPathSplit = RawDataPath.split('/') 
    output_path = RawDataPathSplit[0] + '/' + 'data2test/' + RawDataPathSplit[1].replace('.json', '') + '_multiple_{}.json'.format(length)
    save_json(output_data, output_path)                


def infuse_single_trajectory_session(traj, noise_pool, length):
    if length == 0:
        noisy_traj = {}
        noisy_traj['tid'] = traj['tid'] 
        new_message_list = []
        for m in traj['message_list']:
            # print(m)
            for m_i in m:
                try:
                    new_message_list.append({
                        'user': '{} (place: {}; time{})'.format(m_i['user_message'], m_i['place'], m_i['time']),
                        'agent': '{} (place: {}; time{})'.format(m_i['assistant_message'], m_i['place'], m_i['time'])
                    })
                except:
                    new_message_list.append({
                        'user': '{} (place: {}; time{})'.format(m_i['user'], m_i['place'], m_i['time']),
                        'agent': '{} (place: {}; time{})'.format(m_i['assistant'], m_i['place'], m_i['time'])
                    })
        noisy_traj['message_list'] =  new_message_list
        noisy_traj['QA'] = traj['QA']
        noisy_traj['QA']['target_step_id'] = [id[0] for id in noisy_traj['QA']['target_step_id']]

        return noisy_traj
    
    noisy_traj = {}
    noisy_traj['tid'] = traj['tid']
    new_message_list = []
    raw_message_list = traj['message_list'] ## 这里格式为[[], [], []]

    total_traj = len(raw_message_list) + length

    tmp = sorted(np.random.choice(range(total_traj), size=len(raw_message_list), replace=False))
    relocate_dict = {int(tmp): index for index, tmp in enumerate(tmp)}
    reverse_relocate_dict = {index: int(tmp)-index for index, tmp in enumerate(tmp)}

    noise_list = np.random.choice(noise_pool, size=length, replace=False)
    noise_id = 0
    re_index = 0
    for index in range(total_traj):
        if index in tmp:
            # print(index)
            for i in raw_message_list[re_index]:
                # print(i)
                try: 
                    new_message_list.append({
                        'user': '{} (place: {}; time{})'.format(i['user_message'], i['place'], i['time']),
                        'agent': '{} (place: {}; time{})'.format(i['assistant_message'], i['place'], i['time'])
                    })
                except:
                    new_message_list.append({
                        'user': '{} (place: {}; time{})'.format(i['user'], i['place'], i['time']),
                        'agent': '{} (place: {}; time{})'.format(i['assistant'], i['place'], i['time'])
                    })
            re_index += 1
        else:
            noise_message = [{
                'user': '{}'.format(i['user']),
                'agent': '{}'.format(i['assistant'])
            } for i in noise_list[noise_id]['noise_message']]
            new_message_list.extend(noise_message)
            noise_id += 1
    
    noisy_traj['message_list'] = new_message_list
    noisy_traj['QA'] = traj['QA']
    
    noisy_traj['QA']['target_step_id'] = [reverse_relocate_dict[step_id[1]] * 3 + step_id[0] for step_id in noisy_traj['QA']['target_step_id']]

    return noisy_traj

# 实现对session的延长
def MakeNoiseSession(RawDataPath, length):
    NoiseDataPath = '../MakeNoiseNew/NoiseMeta/sessionnoise_new.json'
    NoisePool = load_json(NoiseDataPath)

    output_data = {}

    RawData = load_json(RawDataPath)
    for QAtype, QAtype_data in RawData.items():  # 获得simple
        output_data[QAtype] = {}
        for scenario, scenario_data in QAtype_data.items():  # 获得role
            output_data[QAtype][scenario] = []
            scenario_traj_all_pre = []
            for traj in scenario_data:
                noisy_traj = infuse_single_trajectory_session(traj, NoisePool, length)
                # output_data[QAtype][scenario].append(noisy_traj)
                scenario_traj_all_pre.append(noisy_traj)
            if length == 0:
                scenario_traj_all = random.sample(scenario_traj_all_pre, 20)
            elif length == 100 or length == 500:
                scenario_traj_all = random.sample(scenario_traj_all_pre, 5)
            else:
                scenario_traj_all = scenario_traj_all_pre
            output_data[QAtype][scenario] = scenario_traj_all
            print(QAtype, scenario, 'Finish!')
    
    RawDataPathSplit = RawDataPath.split('/')
    output_path = RawDataPathSplit[0] + '/' + 'data2test/' + RawDataPathSplit[1].replace('.json', '') + '_multiple_{}.json'.format(length)
    save_json(output_data, output_path)                


# 混合不同类的message
def MixMessage():
    dir_path = '../MemData/ThirdAgent'
    filenames = os.listdir(dir_path)
    lowlevel_data_list = {}
    highlevel_data_list = {}
    for filename in filenames:
        file_path = '{}/{}'.format(dir_path, filename)

        QA_type = filename.split('.')[0]

        sub_data = load_json(file_path)

        if 'highlevel' in filename:
            highlevel_data_list[QA_type] = sub_data
        else:
            lowlevel_data_list[QA_type] = sub_data
    
    lowlevel_outpath = 'data/ThirdAgentDataLowLevel.json'
    save_json(lowlevel_data_list, lowlevel_outpath)
    highlevel_outpath = 'data/ThirdAgentDataHighLevel.json'
    save_json(highlevel_data_list, highlevel_outpath)


# 混合不同类的session
def MixSession():
    dir_path = '../MemData/FirstAgent'
    filenames = os.listdir(dir_path)
    lowlevel_data_list = {}
    highlevel_data_list = {}
    for filename in filenames:
        file_path = '{}/{}'.format(dir_path, filename)

        QA_type = filename.split('.')[0]

        sub_data = load_json(file_path)

        if 'highlevel' in filename:
            highlevel_data_list[QA_type] = sub_data
        else:
            lowlevel_data_list[QA_type] = sub_data

    
    lowlevel_outpath = 'data/FirstAgentDataLowLevel.json'
    save_json(lowlevel_data_list, lowlevel_outpath)
    highlevel_outpath = 'data/FirstAgentDataHighLevel.json'
    save_json(highlevel_data_list, highlevel_outpath)


def MakeNoiseSessionOther():
    return


if __name__ == "__main__":
    MixMessage()
    MixSession()
    # MakeNoiseMessage('data/ThirdAgentDataLowLevel.json', length=0)
    # MakeNoiseMessage('data/ThirdAgentDataLowLevel.json', length=100)

    # MakeNoiseMessageHighLevel('data/ThirdAgentDataHighLevel.json', length=0)
    # MakeNoiseMessageHighLevel('data/ThirdAgentDataHighLevel.json', length=100)

    # MakeNoiseSession('data/FirstAgentDataLowLevel.json', length=0)
    # MakeNoiseSession('data/FirstAgentDataLowLevel.json', length=100)

    # MakeNoiseSession('data/FirstAgentDataHighLevel.json', length=0)
    # MakeNoiseSession('data/FirstAgentDataHighLevel.json', length=100)

    # MakeNoiseMessage('data/ThirdAgentDataLowLevel.json', length=99)

