# import ollama
# session = ollama.chat(
#    model='llama3',
#    messages=[{
#        'role': 'user',
#        'content': 'in very few words, why is the sky blue?'}],
#    stream=True)
# print(response['messages']['content']) # stream=False
#
# buff = ""
# full = ""
# for words in session:
#    buff = words['message']['content']
#    full += buff
#    print(buff, end='', flush=True)
#    # if words['done']:
#    # print('no need to break?')
#
# print('---')
# print(full)
