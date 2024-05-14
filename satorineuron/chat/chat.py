import ollama
from typing import Callable


def session(model: str = 'llama3', message: str = None):
    ''' [{'role': 'user', 'content': 'in very few words, why is the sky blue?'}] '''
    if message == None:
        return
    return ollama.chat(
        model=model,
        messages=[{'role': 'user', 'content': message}],
        stream=True)


def printOnSessionValue(session):
    full = ""
    for words in session:
        buff = words['message']['content']
        full += buff
        print(buff, end='', flush=True)
    return full
