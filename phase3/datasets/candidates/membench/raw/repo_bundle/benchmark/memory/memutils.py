from openai import OpenAI

def get_word_num(text):
    return len(text.split())

def get_truncated_context(context, num):
    return ' '.join(context.split(' ')[:num])

class LLM():
    def __init__(self, config):
        self.config = config

        self.client = OpenAI(
            api_key=self.config['api_key'],
            base_url=self.config['base_url']
        )

    def parse_response(self, response):
        return {
            'run_id': response.id,
            'time_stamp': response.created,
            'result': response.choices[0].message.content,
            'input_token': response.usage.prompt_tokens,
            'output_token': response.usage.completion_tokens
        }

    def run(self, message_list):
        response = self.client.chat.completions.create(
            model=self.config['name'],
            messages=message_list,
            temperature=self.config['temperature']
        )
        response = self.parse_response(response)
        return response

    def fast_run(self, query):
        response = self.run([{"role": "user", "content": query}])
        return response['result']