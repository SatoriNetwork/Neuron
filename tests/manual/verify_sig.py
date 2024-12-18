
def test():
    from satorilib.wallet.evrmore.sign import signMessage, CEvrmoreSecret
    from satorilib.wallet.evrmore.verify import verify
    address='EKjdaWZFP2tZb1U7jBHEy1fgmHcokMKL5u'
    message='1734503836.909'
    key='L5Lf9YAQAN6sbrD1Vk8vDLn2gmWG9ToiB6cW9tuZUEeUsPB5MEv2'
    signature='ICBCwtbIUcbYRLYNvLeOpcv67NN+SHizIhU+pXV5HBPjfQR7enr5ded9bov6JzhD0ysZ9HNQYJxLH1ZJLwmLTfI='
    # make a signature in python
    signMessage(CEvrmoreSecret(key), message)
    # verify it
    print(verify(message=message, signature=signMessage(CEvrmoreSecret(key), message), address=address))
    # try to verify the signature provided
    print(verify(message=message, signature=signature, address=address))
    # try bytes instead of string like the signature python generated
    signature.encode()
    print(verify(message=message, signature=signature.encode(), address=address))
