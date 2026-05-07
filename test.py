from web3 import Web3

account = Web3().eth.account.create()
print('Address:    ', account.address)
print('Private Key:', account.key.hex())
