'''
we were going to use this to allow everyone to have a url that is always 
reachable incase their machine acts as primary data but the better way to 
handle a situation like that is to allow it to be blank and if so, not make the
call and just run the function.
'''
# from unittest.mock import patch
# import requests
#
#
# def mockRequestGet(*args, **kwargs):
#    class MockResponse:
#        def __init__(self, json_data, status_code):
#            self.json_data = json_data
#            self.status_code = status_code
#
#        def json(self):
#            return self.json_data
#
#        def raise_for_status(self):
#            if 400 <= self.status_code < 600:
#                raise requests.HTTPError(f"{self.status_code} Error")
#    if args[0] == '':
#        return MockResponse({"key": "value"}, 200)
#    else:
#        return MockResponse(None, 404)
#
# # with patch('requests.get', side_effect=mockRequestGet):
# #     response = requests.get('')
# #     print(response.json())  # Output will be: {'key': 'value'}
# #     print(response.status_code)  # Output will be: 200
