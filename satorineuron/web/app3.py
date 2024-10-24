import requests

headers = {
    'public-key': '02152c825b8e6f84becd770806d77c3fae2ab2470172ffde766d6b80846825a4da',
    'message': 'your_message',
    'signature': 'your_signature',
    'address': 'EHkDUkADkYnUY1cjCa5Lgc9qxLTMUQEBQm'
}

response = requests.post('http://satoricentral:5000/proposals/vote', 
    headers=headers,
    json={
        'proposal_id': 1,
        'vote': True
    }
)
print(response.status_code)
print(response.text)