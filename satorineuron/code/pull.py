'''
>>> out
b'Updating 2f27f85..451da7e\nFast-forward\n satoriengine/veda/pipelines/__init__.py                |   2 +-\n satoriengine/veda/pipelines/meta/__init__.py           |  24 ++++++++++++++++++\n satoriengine/veda/pipelines/meta/embedding_complete.py | 143 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++\n satoriengine/veda/pipelines/meta/embeddings.py         | 141 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++\n satoriengine/veda/pipelines/meta/embeding_knn.py       |  48 +++++++++++++++++++++++++++++++++++\n satoriengine/veda/pipelines/meta/o.py                  | 151 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++\n satoriengine/veda/pipelines/meta/o_test.py             | 134 ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++\n satoriengine/veda/pipelines/meta/test.py               |  74 +++++++++++++++++++++++++++++++++++++++++++++++++++++\n satoriengine/veda/pipelines/meta/transform.py          |  64 ++++++++++++++++++++++++++++++++++++++++++++++\n satoriengine/veda/pipelines/meta/visualize.png         | Bin 0 -> 51072 bytes\n satoriengine/veda/pipelines/{ => sktime}/sk.py         |   0\n 11 files changed, 780 insertions(+), 1 deletion(-)\n create mode 100644 satoriengine/veda/pipelines/meta/__init__.py\n create mode 100644 satoriengine/veda/pipelines/meta/embedding_complete.py\n create mode 100644 satoriengine/veda/pipelines/meta/embeddings.py\n create mode 100644 satoriengine/veda/pipelines/meta/embeding_knn.py\n create mode 100644 satoriengine/veda/pipelines/meta/o.py\n create mode 100644 satoriengine/veda/pipelines/meta/o_test.py\n create mode 100644 satoriengine/veda/pipelines/meta/test.py\n create mode 100644 satoriengine/veda/pipelines/meta/transform.py\n create mode 100644 satoriengine/veda/pipelines/meta/visualize.png\n rename satoriengine/veda/pipelines/{ => sktime}/sk.py (100%)\n'
>>> err
b'From https://github.com/SatoriNetwork/Engine\n   2f27f85..451da7e  main       -> origin/main\n'
>>> process.returncode
0
>>> out2, err2 = process.communicate()
>>> out2
b'Already up to date.\n'
>>> err2
b''
>>> process.returncode
0
'''


def fromServer(repo: str) -> bool:
    '''Get the repo code from the server and save to files'''

    import requests
    import os
    import shutil
    import requests
    import zipfile
    from io import BytesIO
    from satorilib.wallet import evrmore

    def accept(response:requests.Response):
        ''' handle multipart '''
        message = None
        signature = None
        zipped = None
        if response.status_code == 200 and "multipart/form-data" in response.headers["Content-Type"]:
            boundary = response.headers["Content-Type"].split("boundary=")[1]
            parts = response.content.split(f"--{boundary}".encode())
            for part in parts:
                # Ignore empty parts and the closing boundary
                if not part.strip() or part == b"--":
                    continue
                try:
                    headers, content = part.split(b"\r\n\r\n", 1)
                except ValueError:
                    # Skip malformed parts
                    print("Skipping malformed part:")
                    input('...')
                    print("Skipping malformed part:", part)
                    continue
                # Match and handle each content type
                if b'Content-Disposition: form-data; name="message"' in headers:
                    message = content.strip().decode()
                    print("Message:", message)
                elif b'Content-Disposition: form-data; name="signature"' in headers:
                    signature = content.strip().decode()
                    print("Signature:", signature)
                elif b'Content-Disposition: form-data; name="file"' in headers:
                    zipped = BytesIO(content)
                    print("Received ZIP file.")
        return message, signature, zipped

    # Public key and address fetched from the server
    pubkey = '03eb71612d60ab1a9a5656929b1f2329c72373988313df1ea130b137ba0c239c69'
    address = 'EU1EnRbBMDAU3PcyZ63FXrdV2U6xHAqbUv'
    # Get the repository data
    response = requests.get(f'https://stage.satorinet.io/download/repo/{repo}')
    message, signature, zipped = accept(response)
    if (
        zipped is not None and
        evrmore.verify(
            message=message,
            signature=signature,
            publicKey=pubkey,
            address=address)
    ):
        # Convert base64-encoded binary (if applicable) into BytesIO (if string)
        #zipped = BytesIO(bytes.fromhex(zipped))  # Replace with `base64.b64decode` if base64 is used
        # Unzip the contents
        destination = f'/Satori/{repo.title()}/satori{repo.lower()}'
        os.makedirs(destination, exist_ok=True)
        with zipfile.ZipFile(zipped, 'r') as zipRef:
            # Extract files and overwrite existing ones
            for member in zipRef.namelist():
                memberPath = os.path.join(destination, member)
                # Ensure directories exist for the current member
                os.makedirs(os.path.dirname(memberPath), exist_ok=True)
                if not member.endswith('/'):  # Skip directories (handled by makedirs)
                    with open(memberPath, 'wb') as f:
                        f.write(zipRef.read(member))
        return True
    return False


def fromGithub(repo:str):

    import subprocess

    def innerPull(first:bool=True):
        '''
        #print("STDOUT:", stdout.decode())
        #print("STDERR:", stderr.decode())
        '''
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            return False
        if (
            process.returncode == 0 and
            (stderr == b'' and stdout == b'Already up to date.\n')
        ):
            return True
        else:
            if first:
                return innerPull(first=False)
            else:
                return False

    process = subprocess.Popen(
        ['/bin/bash', f'/Satori/Neuron/satorineuron/code/pull-{repo}.sh'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    process.wait()
    return None


def pullReposFromGithub():
    fromGithub('lib')
    fromGithub('engine')
    fromGithub('neuron')
    # not used any more, phasing out
    #fromGithub('synapse')
    #fromGithub('wallet')
