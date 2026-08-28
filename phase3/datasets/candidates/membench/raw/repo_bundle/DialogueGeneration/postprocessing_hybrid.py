import json
import numpy as np
import sys
sys.path.append('..')
from utils import chatgpt, TimeClock, rewrite_message, formulate_QA, rewrite_message_event, rewrite_question_translate
import string

outpath_pre = '../OutData/ThirdAgent/LowLevel/'

trajectory_per_graph = 1

all_item_dict = {
   "Smartphone": ["Apple iPhone 15", "Samsung Galaxy S24", "Google Pixel 8", "OnePlus 11", "Xiaomi 13", "Oppo Find X6", "Sony Xperia 1 IV"],
    "Home Appliance": ["Dyson V15 Vacuum Cleaner", "Samsung Family Hub Refrigerator", "LG Smart Washing Machine", "iRobot Roomba", "KitchenAid Stand Mixer", "Nespresso Vertuo Plus"],
    "Sneakers": ["Nike Air Max", "Adidas Yeezy", "Reebok Classic", "New Balance 990", "Under Armour HOVR", "Converse All Star", "Puma Suede", "Vans Old Skool"],
    "Laptop": ["MacBook Air M2", "Dell XPS 13", "HP Spectre x360", "Lenovo ThinkPad X1 Carbon", "Asus ZenBook 14", "Microsoft Surface Laptop 4", "Acer Swift 3"],
    "Backpack": ["Herschel Little America", "North Face Recon", "Targus CitySmart", "Everlane Modern Backpack", "Osprey Daylite Plus", "Samsonite Tectonic"],
    "Wristwatch": ["Rolex Submariner", "Omega Seamaster", "Casio G-Shock", "Apple Watch Series 9", "Seiko 5", "Tag Heuer Monaco", "Fossil Gen 6"],
    "Headphones": ["Sony WH-1000XM5", "Bose QuietComfort 45", "Apple AirPods Pro", "Sennheiser Momentum 4", "JBL Tune 700BT", "Beats Studio Buds", "Bang & Olufsen Beoplay H95"],
    "Water Bottle": ["Hydro Flask Standard Mouth", "S'well Stainless Steel Bottle", "Contigo Autoseal", "Nalgene Tritan Wide Mouth", "Klean Kanteen Classic", "Thermos Hydration Bottle"],
    "Wallet": ["Bellroy Slim Wallet", "Ridge Wallet", "Tanner Goods Minimal Wallet", "Herschel Supply Co. Roy Wallet", "Fossil Quinn Wallet", "Tommy Hilfiger Leather Wallet"],
    "Sunglasses": ["Ray-Ban Wayfarer", "Oakley Radar EV Path", "Maui Jim Peahi", "Persol 714", "Warby Parker Durand", "Prada Linea Rossa", "Carrera 5001S"],
    "Coffee Mug": ["Contigo Travel Mug", "Yeti Rambler Mug", "Ember Temperature Control Mug", "Swell Travel Mug", "Hydro Flask Coffee Mug", "Bodum Bistro Mug"],
    "Keychain": ["Leather Keychain", "Tactical Keychain Multi-tool", "Herschel Supply Co. Keychain", "Nike Swoosh Keychain", "Chrome Industries Keychain", "Carabiner Keychain"],
    "Pen": ["Pilot G2 Gel Pen", "Parker Jotter", "Uni-ball Jetstream", "Lamy Safari", "Cross Century II", "Sharpie Pen", "Zebra Sarasa Clip"],
    "Notebook": ["Moleskine Classic Notebook", "Leuchtturm1917 Bullet Journal", "Rhodia Webnotebook", "Field Notes Memo Book", "Midori MD Notebook", "Paperblanks Journal"],
    "Desk Lamp": ["BenQ e-Reading LED Desk Lamp", "Ikea SINNERLIG Table Lamp", "LIFX Beam Smart Lamp", "Taotronics LED Desk Lamp", "Phive LED Desk Lamp", "Tomons Swing Arm Desk Lamp"],
    "Vacuum Cleaner": ["Dyson V11 Torque Drive", "iRobot Roomba 960", "Shark Navigator Lift-Away", "Miele Complete C3", "Hoover WindTunnel 3", "Bissell PowerForce Helix"],
    "Umbrella": ["Repel Windproof Travel Umbrella", "Blunt Metro Umbrella", "Totes Automatic Umbrella", "Senz Smart Umbrella", "Samsonite Windguard Umbrella", "Lewis N. Clark Umbrella"],
    "Power Bank": ["Anker PowerCore 10000", "RAVPower 26800mAh", "Aukey 20000mAh", "Zendure A3PD", "Mophie Powerstation Plus", "Goal Zero Sherpa 100PD"],
    "Suitcase": ["Away Bigger Carry-On", "Samsonite Winfield 3 DLX", "Tumi Alpha 3 Expandable", "Rimowa Essential Cabin S", "Briggs & Riley Baseline", "American Tourister Moonlight"],
    "Toothbrush": ["Philips Sonicare DiamondClean", "Oral-B Pro 1000", "Quip Electric Toothbrush", "Colgate Hum Smart Toothbrush", "Fairywill Sonic Electric Toothbrush", "Burst Sonic Toothbrush"],
    "Hair Dryer": ["Dyson Supersonic", "Revlon One-Step Hair Dryer", "Conair Infiniti Pro", "Panasonic Nanoe", "T3 Cura Luxe", "Elchim 3900 Healthy Ionic Hair Dryer"],
    "Microwave Oven": ["Panasonic NN-SN966S", "Breville Quick Touch", "Toshiba EM131A5C-SS", "Sharp Carousel", "GE Profile Series", "Samsung MS19M8000AS"],
    "Blender": ["Vitamix 5200", "Ninja Professional BL610", "Blendtec Total Classic", "KitchenAid KSB1570SL", "Oster Pro 1200", "Hamilton Beach Personal Blender"],
    "Electric Kettle": ["Breville BKE820XL", "Cuisinart CPK-17", "Hamilton Beach 40880", "Zojirushi Hybrid Water Boiler", "Chefman Electric Kettle", "Secura Stainless Steel Electric Kettle"],
    "Electric Shaver": ["Braun Series 9", "Philips Norelco 9000", "Panasonic Arc5", "Remington F5-5800", "Wahl LifeProof", "Braun Series 7"],
    "Air Purifier": ["Dyson Pure Cool", "Honeywell HPA300", "Levoit Core 300", "Coway AP-1512HH", "Winix 5500-2", "Coway Airmega 400S"],
    "Tablet": ["Apple iPad Pro", "Samsung Galaxy Tab S8", "Microsoft Surface Pro 9", "Amazon Fire HD 10", "Lenovo Tab P11", "Huawei MatePad Pro"],
    "Fitness Tracker": ["Fitbit Charge 5", "Garmin Forerunner 245", "Apple Watch Series 9", "WHOOP Strap 4.0", "Samsung Galaxy Watch 6", "Oura Ring Gen 3"],
    "Television": ["Samsung QLED 4K", "LG OLED C2", "Sony Bravia XR A90J", "Vizio 4K Smart TV", "TCL 6-Series", "Hisense U8H"],
    "Gaming Console": ["PlayStation 5", "Xbox Series X", "Nintendo Switch OLED", "Xbox Series S", "PlayStation 4 Pro", "Nintendo Switch Lite"],
    "Fan": ["Dyson Cool Tower Fan", "Vornado 660 Whole Room Fan", "Lasko 20” Box Fan", "Honeywell Quietset Tower Fan", "Rowenta VU5670 Turbo Silence", "Vornado 630 Mid-Size Air Circulator"],
    "Heater": ["Dyson Pure Hot + Cool", "De'Longhi Oil-Filled Radiator", "Lasko Ceramic Heater", "Vornado VH10", "Honeywell HZ-7300", "Pelonis Oscillating Heater"],
    "Refrigerator": ["Samsung Family Hub Refrigerator", "LG InstaView Door-in-Door", "Whirlpool French Door Refrigerator", "GE Profile Refrigerator", "Bosch 800 Series", "Frigidaire Gallery"],
    "Dishwasher": ["Bosch 300 Series", "Miele G 7000", "Whirlpool WDT710PAHZ", "GE Profile PDT775SYNFS", "Samsung StormWash", "KitchenAid KDTM804KPS"],
    "Laundry Detergent": ["Tide Pods", "Persil ProClean", "Arm & Hammer Liquid Detergent", "Seventh Generation Free & Clear", "All Free Clear", "Method Laundry Detergent"],
    "Cooking Pot": ["Le Creuset Dutch Oven", "Staub Cast Iron Pot", "Lodge Enameled Dutch Oven", "T-fal Ultimate Hard Anodized", "Cuisinart MultiClad Pro", "All-Clad Stainless Steel"],
    "Frying Pan": ["T-fal Ultimate Fry Pan", "Lodge Cast Iron Skillet", "All-Clad Stainless Steel Fry Pan", "Cuisinart Chef's Classic", "Calphalon Contemporary", "Scanpan Classic"],
    "Spatula": ["OXO Good Grips Spatula", "Cuisinart Heat Resistant Silicone", "Di Oro Silicone Spatula", "Lodge Cast Iron Spatula", "Le Creuset Wooden Spatula", "Jamie Oliver Silicone Spatula"],
    "Cutting Board": ["John Boos Maple Cutting Board", "OXO Good Grips Bamboo Cutting Board", "Epicurean Kitchen Series", "Seville Classics Bamboo Cutting Board", "Totally Bamboo Cutting Board"],
    "Laundry Basket": ["Sterilite Laundry Basket", "Rubbermaid Laundry Basket", "Simplehuman Rectangular Laundry Hamper", "IRIS USA Laundry Basket", "Oceanstar Bamboo Hamper", "Honey-Can-Do Laundry Hamper"],
    "Iron": ["Rowenta DW5080", "Black+Decker IR1350", "Hamilton Beach Durathon", "Sunbeam Steam Master", "Cuisinart CIM-100", "Panasonic NI-E650TS"],
    "Broom": ["OXO Good Grips Broom", "Libman Precision Angle Broom", "Quickie Professional Broom", "Rubbermaid Commercial Broom", "Swiffer Sweeper Broom"],
    "Dustpan": ["OXO Good Grips Dustpan", "Eyliden Handheld Dustpan", "Quickie Dustpan", "Squeegee Dustpan", "Casabella Dustpan", "Rubbermaid Commercial Dustpan"],
    "Toilet Paper": ["Charmin Ultra Soft", "Cottonelle Ultra ComfortCare", "Scott 1000", "Angel Soft", "Quilted Northern Ultra Plush", "Seventh Generation Toilet Paper"],
    "Hand Soap": ["Dove Hand Soap", "Method Gel Hand Soap", "Mrs. Meyer's Clean Day", "Dial Antibacterial Hand Soap", "Softsoap Liquid Hand Soap", "Burt's Bees Hand Soap"],
    "Body Lotion": ["Nivea Soft", "CeraVe Moisturizing Cream", "Aveeno Daily Moisturizing Lotion", "Eucerin Advanced Repair", "Neutrogena Hydro Boost Body Gel Cream", "Kiehl's Crème de Corps"],
    "Face Mask": ["Dr. Jart+ Rubber Mask", "Origins Clear Improvement Mask", "Glossier Mega Greens Galaxy Pack", "The Ordinary AHA 30% + BHA 2% Peeling Solution", "L'Oréal Paris Pure Clay Mask", "Peter Thomas Roth Cucumber Gel Mask"],
    "Shampoo": ["Pantene Pro-V", "Head & Shoulders", "Aveeno Pure Renewal", "L'Oréal Elvive", "Redken All Soft", "Biolage Colorlast"],
    "Conditioner": ["Aussie 3 Minute Miracle", "Moroccanoil Moisture Repair", "Pantene Pro-V Conditioner", "TRESemmé Keratin Smooth", "Bumble and Bumble Hairdresser's Invisible Oil", "L'Oréal Paris EverPure Conditioner"],
    "Deodorant": ["Secret Clinical Strength", "Degree UltraClear", "Old Spice Swagger", "Dove Men+Care", "Native Deodorant", "Schmidt's Natural Deodorant"],
    "Camera": ["Canon EOS R5", "Nikon Z7 II", "Sony A7 III", "Fujifilm X-T4", "Panasonic Lumix GH5", "Olympus OM-D E-M10", "GoPro Hero 9", "DJI Osmo Pocket"],
    "Cosmetics": ["Lipstick", "Foundation", "Mascara", "Blush", "Eyeliner", "Nail Polish", "Perfume", "Eyeshadow Palette"]

}

all_place_dict = {
    "Apartment": ['The Luxe Apartments', 'Parkside Residences', 'City View Lofts', 'Sunset Towers', 'Greenwood Apartments', 'Oakridge Estates', 'The Heights', 'Lakeview Apartments'],
    "Park": ['Central Park', 'Golden Gate Park', 'Millennium Park', 'Balboa Park', 'Prospect Park', 'Zilker Park', 'Piedmont Park', 'Hermann Park', 'Forest Park'],
    "Mall": ['Mall of America', 'Westfield Century City', 'The Grove', 'South Coast Plaza', 'King of Prussia Mall', 'Tysons Corner Center', 'Aventura Mall', 'The Galleria'],
    "Hospital": ['Mayo Clinic', 'Cleveland Clinic', 'Johns Hopkins Hospital', 'Massachusetts General Hospital', 'UCLA Medical Center', 'NewYork-Presbyterian Hospital', 'UCSF Medical Center', 'Cedars-Sinai Medical Center'],
    "Tourist Spot": ['Grand Canyon', 'Yellowstone National Park', 'Statue of Liberty', 'Golden Gate Bridge', 'Mount Rushmore', 'Yosemite National Park', 'Walt Disney World', 'Niagara Falls'],
    "University Campus": ['Harvard University', 'Stanford University', 'Massachusetts Institute of Technology', 'University of California, Berkeley', 'University of Michigan', 'Columbia University', 'University of Texas at Austin', 'Yale University'],
    "Gym": ['Equinox', 'LA Fitness', 'Planet Fitness', 'Golds Gym', '24 Hour Fitness', 'Anytime Fitness', 'Crunch Fitness', 'Lifetime Fitness'],
    "Museum": ['The Metropolitan Museum of Art', 'Smithsonian National Museum of Natural History', 'American Museum of Natural History', 'The Getty Center', 'Museum of Modern Art', 'Art Institute of Chicago', 'National Gallery of Art', 'San Francisco Museum of Modern Art'],
    "Library": ['New York Public Library', 'Boston Public Library', 'Library of Congress', 'Los Angeles Public Library', 'San Francisco Public Library', 'Seattle Central Library', 'Chicago Public Library', 'Hennepin County Library']
}

def generate_other_choices_05(attr, answer, fea):
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

    prompt = 'Question: What is its {}?\n'.format(attr)
    prompt += 'Correct Answer: {}\n'.format(answer)
    prompt += 'Please generate three different confusing options based on the above question and answer.\n'
    prompt += 'Each confusing option should be similar in length to the answer and clearly distinguishable.\n'
    prompt += 'The output should follow this example format:\n'
    prompt += 'A. Chengdu\n'
    prompt += 'B. Beijing\n'
    prompt += 'C. Shanghai\n'

    res = chatgpt(prompt)
    other_answers = get_other_answers(res)

    max_tries = 10
    while not other_answers:
        res = chatgpt(prompt)
        max_tries -= 1
        other_answers = get_other_answers(res)
        if max_tries <= 0:
            other_answers = ['I don’t know', 'None are correct', 'Not mentioned in the answer']

    other_feas = []

    for oa in other_answers:
        prompt = 'Please give the most unique feature of {} in a short sentence, but do not include {}.\n'.format(oa, oa)
        prompt += 'Only output the feature, no other descriptive content is needed.\n'
        prompt += 'Example output: {}'.format(fea)

        other_feas.append(chatgpt(prompt))
    return other_feas

def get_role_data(graph, time_clock):
    key_features = ['name', 'age', 'birthday', 'hometown', 'work_location', 'education', 'occupation', 'position', 'hobby', 'contact_number', 'email_address']
    targeted_features = ['name', 'birthday', 'work_location', 'occupation', 'hobby', 'contact_number', 'email_address']
    B1_attrs_num = 5
    question_num = 1

    charact = graph['user_profile']['character']
    message_list = []
    noise_message_list = []
    question_list = []

    role_list = graph['relation_profiles'] + graph['colleague_profiles']
    role_B1_id = np.random.choice(range(len(role_list)), size=1, replace=False)[0]
    role_B1 = role_list[role_B1_id]
    relation = role_B1['relationship']
    attrs_other = np.random.choice(key_features, size=B1_attrs_num-1, replace=False)
    attrs_target = np.random.choice(list(set(targeted_features)-set(attrs_other)), size=1, replace=False)

    for k in attrs_target:
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

    for k in attrs_other:
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
        inx_01, inx_02 = np.random.choice(range(len(message_list[1:])), size=1, replace=False)[0] + 1, 0

        real_attr_01, real_attr_02 = message_list[inx_01], message_list[inx_02]

        other_answers = None
        for noise_role_id in range(len(role_list)):
            if noise_role_id != role_B1_id:
                name, k = role_list[noise_role_id]['name'], real_attr_02['attr'][0]
                v = role_list[noise_role_id][k]
                text = rewrite_message("Hello, assistant, {}'s {} is {}.".format(name, k, v), charact)

                noise_message_list.append({
                    'message': text,
                    'time': time_clock.get_current_time(),
                    'place': graph['user_profile']['work_location'],
                    'rel': role_list[noise_role_id]['relationship'],
                    'attr': (k, v)
                })
                time_clock.update_time()

        if real_attr_02['attr'][0] in ['contact_number']:
            sum_num = int(np.random.choice(range(2, 6 + 1), size=1, replace=False)[0])
            question = "那个{}是{}的人, 其{}的后{}位之和是多少?".format(real_attr_01['attr'][0], real_attr_01['attr'][1], real_attr_02['attr'][0], sum_num)
            answer = str(sum(int(digit) for digit in real_attr_02['attr'][1][-sum_num:]))
        elif real_attr_02['attr'][0] in ['email_address']:
            question = "那个{}是{}的人, 其{}的后缀是多少?".format(real_attr_01['attr'][0], real_attr_01['attr'][1], real_attr_02['attr'][0])
            answer = real_attr_02['attr'][1][real_attr_02['attr'][1].find('@'):]
        elif real_attr_02['attr'][0] in ['name']:
            question = "那个{}是{}的人, 其{}的有几个字?".format(real_attr_01['attr'][0], real_attr_01['attr'][1], real_attr_02['attr'][0])
            answer = '{} characters'.format(len(real_attr_02['attr'][1]))
            other_answers = ['{} characters'.format(i + len(real_attr_02['attr'][1])) for i in [-1, 1, 2]]
        elif real_attr_02['attr'][0] in ['birthday']:
            question = "那个{}是{}的人, 其生日是在哪个季节?".format(real_attr_01['attr'][0], real_attr_01['attr'][1])
            print(real_attr_02['attr'][1])
            month_dig = int(real_attr_02['attr'][1].split(' ')[0].split('/')[0])
            print('Month: {} month({})'.format(month_dig, real_attr_02['attr'][1]))
            if 3 <= month_dig <= 5:
                answer = 'Spring'
            elif 6 <= month_dig <= 8:
                answer = 'Summer'
            elif 9 <= month_dig <= 11:
                answer = 'Autumn'
            else:
                answer = 'Winter'
            other_answers = [season for season in ['Spring', 'Summer', 'Autumn', 'Winter'] if answer != season]
        elif real_attr_02['attr'][0] in ['occupation']:
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
            question = "那个{}是{}的人，其职业的主要职责是什么".format(real_attr_01['attr'][0], real_attr_01['attr'][1])
            answer = work_explain[real_attr_02['attr'][1]]

            other_works = np.random.choice(list(set(work_explain.keys()) - set([real_attr_02['attr'][1]])), size=3, replace=False)
            other_answers = [work_explain[owk] for owk in other_works]
        elif real_attr_02['attr'][0] in ['hobby']:
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

            question = "那个{}是{}的人, 其兴趣爱好的主要内容是什么?".format(real_attr_01['attr'][0], real_attr_01['attr'][1])
            answer = hobby_explain[real_attr_02['attr'][1]]

            other_hobbies = np.random.choice(list(set(hobby_explain.keys()) - set([real_attr_02['attr'][1]])), size=3, replace=False)
            other_answers = [hobby_explain[owk] for owk in other_hobbies]
        elif real_attr_02['attr'][0] in ['work_location']:
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

            question = "那个{}是{}的人, 以下哪一项符合其工作地的描述?".format(real_attr_01['attr'][0], real_attr_01['attr'][1])
            answer = place_explain[real_attr_02['attr'][1]]

            other_places = np.random.choice(list(set(place_explain.keys()) - set([real_attr_02['attr'][1]])), size=3, replace=False)
            other_answers = [place_explain[owk] for owk in other_places]
        else:
            raise Exception("Role targeted attr error: {}.".format(real_attr_02['attr'][0]))

        question = rewrite_question_translate(question)

        question, choices, ground_truth = formulate_QA(question, answer, other_answers=other_answers)
        # print(question)
        # print(answer)
        # print(other_answers)
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


def get_event_data(graph, time_clock):
    key_features = ['location', 'time', 'main_content']
    B1_attrs_num = 3
    question_num = 1

    charact = graph['user_profile']['character']
    message_list = []
    noise_message_list = []
    question_list = []
    second_sample_pool = []

    event_list = graph['work_events'] + graph['rest_events']
    event_C1_id = np.random.choice(range(len(event_list)), size=1, replace=False)[0]
    event_C1 = event_list[event_C1_id]

    text = rewrite_message_event("I am going to participate in {}.".format(event_C1['event_name']), charact)
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

        if message_list[-1]['attr'][0] in ['location', 'time']:
            second_sample_pool.append(len(message_list) - 1)

    for qid in range(question_num):
        inx_01 = np.random.choice(range(len(message_list)), size=1, replace=False)[0]
        
        inx_02 = np.random.choice(second_sample_pool, size=1, replace=False)[0]
        while inx_02 == inx_01:
            inx_02 = np.random.choice(second_sample_pool, size=1, replace=False)[0]
            print('Resample index_02')
        real_attr_01, real_attr_02 = message_list[inx_01], message_list[inx_02]

        for noise_event_id in range(len(event_list)):
            if noise_event_id != event_C1_id:
                name, k = event_list[noise_event_id]['event_name'], real_attr_02['attr'][0]
                if k == 'Event I am attending':
                    v = event_list[noise_event_id]['event_name']
                    text = rewrite_message_event("I am going to participate in {}.".format(name), charact)
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

        if real_attr_02['attr'][0] == 'location':
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
            
            question = "那个{}是{}的活动, 哪一个符合它的活动地点描述?".format(real_attr_01['attr'][0], real_attr_01['attr'][1])
                
            answer = city_explain[real_attr_02['attr'][1]]
            other_cities = np.random.choice(
                list(set(city_explain.keys()) - set([real_attr_02['attr'][1]])), size=3, replace=False
            )
            other_answers = [city_explain[city] for city in other_cities]

        elif real_attr_02['attr'][0] == 'time':
            given_time = real_attr_02['attr'][1]
            pre_abs_time = message_list[inx_02]['time']
            pre_abs_time = pre_abs_time.rsplit(' ', 1)[0].replace("'", '')
            # print(pre_abs_time)
            # print(given_time)
            if 'next' in given_time:
                new_given_time = time_clock.reltime_to_abstime(
                    time_clock.format_time_to_timestamp(pre_abs_time), given_time
                )
            else:
                new_given_time = time_clock.calculate_reltime(
                    time_clock.format_time_to_timestamp(pre_abs_time), given_time
                )
            
            answer = new_given_time
            other_answers = None
            if real_attr_01['attr'][0] == 'main_content':
                question = "那个主要内容是'{}'的活动，其{}是什么?".format(real_attr_01['attr'][1], real_attr_02['attr'][0])

            else:
                question = "那个{}是{}的活动, 其{}是什么?".format(real_attr_01['attr'][0], real_attr_01['attr'][1], real_attr_02['attr'][0])

        
        # elif real_attr_02['attr'][0] == 'event_type':
            # event_type_explain = {
            #         'Travel': 'Read thousands of books, travel thousands of miles, experience different cultures',
            #         'Reading': 'Enjoy the knowledge and pleasure brought by books',
            #         'Watching Movies': 'Appreciate films, relax the mind',
            #         'Fitness': 'Engage in sports, maintain health',
            #         'Food Festival': 'Taste various cuisines, enjoy culinary culture',
            #         'Concert': 'Listen to music, feel the charm of music',
            #         'Art Exhibition': 'Appreciate artworks, enhance aesthetic ability',
            #         'Friends Gathering': 'Gather with friends, enhance friendships',
            #         'Shopping': 'Shop for goods, enjoy the fun of shopping',
            #         'Outdoor Hiking': 'Hike outdoors, get close to nature',
            #         'Business Meeting': 'A meeting in the business world to discuss strategies and promote business development',
            #         'Vocational Training': 'Conduct vocational skills training',
            #         'Job Fair': 'Look for job opportunities, recruit talents',
            #         'Product Launch': 'Launch new products, showcase innovation',
            #         'Industry Exchange': 'Exchange experiences and insights within the industry',
            #         'Company Team Building': 'Team building to enhance cohesion and promote employee communication',
            #         'Year-End Summary Meeting': 'Review a year’s work, summarize experiences and lessons',
            #         'Project Kickoff Meeting': 'Kick off a new project, clarify goals and plans',
            #         'Academic Exchange Meeting': 'An academic exchange meeting to share research results',
            #         'Innovation Seminar': 'An innovation seminar to explore innovative ideas and spark creativity'
            #     }
            #
            # question = "What is the event description for '{}' under the category of {}?".format(
            #     real_attr_01['attr'][1], real_attr_01['attr'][0]
            # )
            # answer = event_type_explain[real_attr_02['attr'][1]]
            # other_event_types = np.random.choice(
            #     list(set(event_type_explain.keys()) - set([real_attr_02['attr'][1]])), size=3, replace=False
            # )
            # other_answers = [event_type_explain[event] for event in other_event_types]
        
        else:
            raise ValueError("Event targeted attribute error: {}.".format(real_attr_02['attr'][0]))
        
        question = rewrite_question_translate(question)
        question, choices, ground_truth = formulate_QA(question, answer, other_answers=other_answers)
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


def get_item_data(graph, time_clock):
    user = graph['user_profile']
    charact = user['character']
    message_list = []
    noise_message_list = []
    question_list = []

    item = graph['items'][0]
    message_list.append({
        'message': rewrite_message("My {}'s {} is {}.".format(item['relationship'], item['item_type'], item['item_name']), charact),
        'time': time_clock.get_current_time(),
        'place': user['work_location'],
        'rel': item['relationship'],
        'attr': item['item_type'],
        'value': item['item_name']
    })
    time_clock.update_time()

    message_list.append({
        'message': rewrite_message("I think {} is {}.".format(item['item_name'], item['item_review']), charact),
        'time': time_clock.get_current_time(),
        'place': user['work_location'],
        'rel': item['relationship'],
        'attr': item['item_type'],
        'value': item['item_review']
    })
    time_clock.update_time()

    noise_message_list = []
    place = graph['places'][0]
    noise_message_list.append({
        'message': rewrite_message("My {}'s {} is {}.".format(place['relationship'], place['place_type'], place['place_name']), charact),
        'time': time_clock.get_current_time(),
        'place': user['work_location'],
        'rel': place['relationship'],
        'attr': place['place_type'],
        'value': place['place_name']
    })
    time_clock.update_time()

    noise_message_list.append({
        'message': rewrite_message("I think {} is {}.".format(place['place_name'], place['place_review']), charact),
        'time': time_clock.get_current_time(),
        'place': user['work_location'],
        'rel': place['relationship'],
        'attr': place['place_type'],
        'value': place['place_review']
    })
    time_clock.update_time()

    question = "What is the most likely description for my {}'s {}?".format(item['relationship'], item['item_type'])
    answer = item['item_review']
    
    other_answers = []
    other_item_types = list(set(['Smartphone', 'Home Appliance', 'Sneakers', 'Laptop', 'Backpack', 'Wristwatch', 'Headphones', 'Water Bottle', 'Wallet', 'Sunglasses', 'Coffee Mug', 'Keychain', 'Pen', 'Notebook', 'Desk Lamp', 'Vacuum Cleaner', 'Umbrella', 'Power Bank', 'Suitcase', 'Toothbrush', 'Hair Dryer', 'Microwave Oven', 'Blender', 'Electric Kettle', 'Electric Shaver', 'Air Purifier', 'Tablet', 'Fitness Tracker', 'Television', 'Gaming Console', 'Fan', 'Heater', 'Refrigerator', 'Dishwasher', 'Laundry Detergent', 'Cooking Pot', 'Frying Pan', 'Spatula', 'Cutting Board', 'Laundry Basket', 'Iron', 'Broom', 'Dustpan', 'Toilet Paper', 'Hand Soap', 'Body Lotion', 'Face Mask', 'Shampoo', 'Conditioner', 'Deodorant', 'Camera', 'Cosmetics']) - set([item['item_type']]))

    for oit in other_item_types:
        ot_item = np.random.choice(all_item_dict[oit], size=1, replace=False)[0]
        prompt = "Please role-play as a {}-year-old with the profession of {} at {}, holding the position of {}. Your hobby is {} and character is {}. Provide an evaluation for your {}'s {}. Output only the evaluation.".format(
            user['age'], user['occupation'], user['company_name'], user['position'], user['hobby'], user['character'], oit, ot_item
        )

        other_answers.append(chatgpt(prompt))
    
    question, choices, ground_truth = formulate_QA(question, answer, other_answers=other_answers)

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

def get_place_data(graph, time_clock):
    user = graph['user_profile']
    charact = user['character']
    message_list = []
    noise_message_list = []
    question_list = []

    place = graph['places'][0]
    message_list.append({
        'message': rewrite_message("My {}'s {} is {}.".format(place['relationship'], place['place_type'], place['place_name']), charact),
        'time': time_clock.get_current_time(),
        'place': user['work_location'],
        'rel': place['relationship'],
        'attr': place['place_type'],
        'value': place['place_name']
    })
    time_clock.update_time()

    message_list.append({
        'message': rewrite_message("I think {} is {}.".format(place['place_name'], place['place_review']), charact),
        'time': time_clock.get_current_time(),
        'place': user['work_location'],
        'rel': place['relationship'],
        'attr': place['place_type'],
        'value': place['place_review']
    })
    time_clock.update_time()

    item = graph['items'][0]
    noise_message_list.append({
        'message': rewrite_message("My {}'s {} is {}.".format(item['relationship'], item['item_type'], item['item_name']), charact),
        'time': time_clock.get_current_time(),
        'place': user['work_location'],
        'rel': item['relationship'],
        'attr': item['item_type'],
        'value': item['item_name']
    })
    time_clock.update_time()

    noise_message_list.append({
        'message': rewrite_message("I think {} is {}.".format(item['item_name'], item['item_review']), charact),
        'time': time_clock.get_current_time(),
        'place': user['work_location'],
        'rel': item['relationship'],
        'attr': item['item_type'],
        'value': item['item_review']
    })
    time_clock.update_time()

    question = "What is the most likely description for my {}'s {}?".format(place['relationship'], place['place_type'])
    answer = place['place_review']

    other_answers = []
    other_place_types = np.random.choice(list(set(['Apartment', 'Park', 'Mall', 'Tourist Spot', 'University Campus', 'Gym', 'Museum', 'Library']) - set([place['place_type']])), size=3, replace=False).tolist()
    for opt in other_place_types:
        ot_place = np.random.choice(all_place_dict[opt], size=1, replace=False)[0]
        prompt = "Please role-play as a {}-year-old with the profession of {} at {}, holding the position of {}. Your hobby is {} and character is {}. Provide an evaluation for your {}'s {}. Output only the evaluation.".format(
            user['age'], user['occupation'], user['company_name'], user['position'], user['hobby'], user['character'], opt, ot_place
        )

        other_answers.append(chatgpt(prompt))
    
    question, choices, ground_truth = formulate_QA(question, answer, other_answers=other_answers)

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


def get_single_type_data(graph, time_clock, type):
    if type == 'role':
        return get_role_data(graph, time_clock)
    elif type == 'event':
        return get_event_data(graph, time_clock)
    elif type == 'item':
        return get_item_data(graph, time_clock)
    else:
        return get_place_data(graph, time_clock)

def merge_message_and_QA(meta_message_list, meta_question_list, message_list, question_list):
    mid_prefix = len(meta_message_list)
    meta_message_list += [{
        'mid': mid_prefix + mid,
        'message': m['message'],
        'time': m['time'],
        'place': m['place'],
        'rel': m['rel'],
        'attr': m['attr'],
        'value': m['value']
    } for mid, m in enumerate(message_list)]

    qid_prefix = len(meta_question_list)
    meta_question_list += [{
        'qid': qid_prefix + q['qid'],
        'question': q['question'],
        'answer': q['answer'],
        'target_step_id': [mid_prefix + ref_id for ref_id in q['target_step_id']],
        'choices': q['choices'],
        'ground_truth': q['ground_truth'],
        'time': q['time']
    } for qid, q in enumerate(question_list)]


def get_new_question_list(meta_question_list):
    def get_choices(ans,other_ans):
        choices = {}

        cvt = {0:'A',1:'B',2:'C',3:'D'}
        ans_tag = np.random.choice(range(4),size=1,replace=False)[0]
        ans_temp = [0 for i in range(4)]
        ans_temp[ans_tag] = 1
        groud_truth = cvt[ans_tag]

        choices[groud_truth] = ans
        for i in range(3):
            for index, t in enumerate(ans_temp):
                if t == 0:
                    ans_temp[index] = 1
                    cur_tag = index
                    break
            choices[cvt[cur_tag]] = other_ans[i]
        choices = {k: choices[k] for k in sorted(choices)}
        return groud_truth,choices
    question_text = ''
    answer_text = ''
    confuse_choices_text_list = ['', '', '']
    target_step_id_list = []
    for qid, q in enumerate(meta_question_list):
        target_step_id_list += q['target_step_id']
        if qid >= 1:
            question_text += 'In addition, {}'.format(q['question'])
            answer_text += '; %s' % q['answer']
            confuse_choices = [v for k,v in q['choices'].items() if k != q['ground_truth']]
            confuse_choices_text_list = [choice_text+'; %s' % confuse_choices[cid] for cid, choice_text in enumerate(confuse_choices_text_list)]
        else:
            question_text += '%s' % q['question']
            answer_text += '%s' % q['answer']
            confuse_choices = [v for k,v in q['choices'].items() if k != q['ground_truth']]
            confuse_choices_text_list = confuse_choices

    groud_truth, choices = get_choices(answer_text, confuse_choices_text_list)
    return {
        'qid': 0,
        'question': question_text,
        'answer': answer_text,
        'target_step_id': target_step_id_list,
        'choices': choices,
        'ground_truth': groud_truth,
        'time': meta_question_list[-1]['time']
    }
    
def check_both(tp1, tp2):
    if tp1 == 'item' and tp2 == 'place':
        return False
    if tp1 == 'place' and tp2 == 'item':
        return False
    return True

def generate_simple_facts_addition(graph_list):
    B1_attrs_num = 5
    question_num = 1
    def generate_single_02_combination(graph):
        time_clock = TimeClock()
        combination_cand = ['role', 'event', 'item', 'place']
        p = [0.35, 0.35, 0.15, 0.15]
        combination_types = np.random.choice(combination_cand,size=2,replace=False,p = p)
        while combination_types[0] == 'event' or not check_both(combination_types[0], combination_types[1]):
            combination_types = np.random.choice(combination_cand,size=2,replace=False,p = p)

        meta_message_list, meta_question_list = [], []

        for ct in combination_types:
            message_list, question_list = get_single_type_data(graph, time_clock, ct)
            merge_message_and_QA(meta_message_list, meta_question_list, message_list, question_list)
        # print(meta_message_list,meta_question_list)

        meta_question_list = [get_new_question_list(meta_question_list)]
        
        return meta_message_list, meta_question_list
        
    data_list = []
    output_path = outpath_pre + '05_post_processing_hybrid.json'
    with open(output_path, 'r') as f:
        data_list = json.load(f)
    for index, graph in enumerate(graph_list):
        if index < len(data_list):
            continue
        print('--- %d Graph ---' % index)
        for trj in range(trajectory_per_graph):
            message_list, question_list = generate_single_02_combination(graph)
            data_list.append({
                'tid': len(data_list),
                'message_list': message_list,
                'question_list': question_list
            })
            print(len(data_list)-1, 'Finish!')
    
        with open(output_path,'w', encoding='utf-8') as f:
            json.dump(data_list, f, indent=4,ensure_ascii=False)

def generate_memory_and_questions(demo_mode = False):
    profiles_path = '../graphs.json'
    with open(profiles_path,'r', encoding='utf-8') as f:
        graph_list = json.load(f)

    generate_simple_facts_addition(graph_list)

if __name__ == '__main__':
    generate_memory_and_questions(demo_mode=True)

