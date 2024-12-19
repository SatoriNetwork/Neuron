
import click
from satorilib.wallet import evrmore
from satorilib.wallet.concepts import authenticate
from satorilib.wallet import EvrmoreWallet


@click.group()
def main():
    '''Satori CLI'''


@main.command()
def help():
    '''open this file to modify'''
    print('used to verify a signed message')


@main.command()
@click.argument('message', type=str, required=True)
@click.argument('signature', type=str, required=True)
@click.argument('pubkey', type=str, required=True)
def verify(message: str, signature: str, pubkey: str):
    '''verifies a message and signature and public key'''
    print(evrmore.verify(
        message=message,
        signature=signature,
        publicKey=pubkey
    ))


@main.command()
@click.argument('message', type=str, required=True)
@click.argument('signature', type=str, required=True)
@click.argument('address', type=str, required=True)
def verify_by_address(message: str, signature: str, address: str):
    '''verifies a message and signature and address'''
    print(evrmore.verify(
        message=message,
        signature=signature,
        address=address
    ))


@main.command()
def create_wallet_auth_payload():
    '''uses existing saved wallet to sign a message for authentication'''
    w = EvrmoreWallet()
    w.init()
    print(authenticate.authPayload(w))


@main.command()
def create_test_wallet_auth_payload():
    '''generates a new wallet and signs a message for authentication'''
    w = EvrmoreWallet()
    w.generate()
    print(authenticate.authPayload(w))


@main.command()
def saveRepos():
    ''' saves repo hashes '''
    r'''
    docker run --rm -it --name satorineuron -p 127.0.0.1:24601:24601 -v c:\repos\Satori\Neuron:/Satori/Neuron -v c:\repos\Satori\Synapse:/Satori/Synapse -v c:\repos\Satori\Lib:/Satori/Lib -v c:\repos\Satori\Wallet:/Satori/Wallet -v c:\repos\Satori\Engine:/Satori/Engine --env-file c:\repos\Satori\Neuron\.env --env ENV=prod --env RUNMODE=wallet satorinet/satorineuron:latest bash
    '''
    from satorineuron.update import hashes
    hashes.saveTargets()
