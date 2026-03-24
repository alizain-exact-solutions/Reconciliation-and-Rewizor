import requests

response =requests.get(
    "http://financial.exactflow.ngrok.dev/api/BankAccount",
    headers={"x-api-key": "rida_Wmw3xVlImfAoaiTzeTb6zRtOoyGrSWXAekXR5Shap0iRAbHtwr0MnpKQ6gjh4I37"}
) 

print(response.json()) 


# {
#     'accountId': 1,
#     'accountName': 'Rachunek bieżący w PLN',
#     'accountNumber': '59105010121000009032979818',
#     'accountProviderId': 65,
#     'accountGroupId': 2,
#     'accountBalance': -1136806.82,
#     'accountAvailableFunds': 33193.18,
#     'accountPrevBalance': -1034646.15,
#     'accountPrevAvailableFunds': 135353.85,
#     'timeStamp': 'AAAAAAAAD2U=',
#     'createdOn': '2026-02-06T14:17:18.127',
#     'modifiedOn': '2026-03-19T03:09:14.74',
#     'accountCurrency': 'PLN',
#     'accountIsClosed': False
#   },
#   {
#     'accountId': 2,
#     'accountName': 'Rachunek bieżący w EUR',
#     'accountNumber': '38105010121000009082639734',
#     'accountProviderId': 65,
#     'accountGroupId': 2,
#     'accountBalance': 35.38,
#     'accountAvailableFunds': 35.38,
#     'accountPrevBalance': 42.26,
#     'accountPrevAvailableFunds': 42.26,
#     'timeStamp': 'AAAAAAAADnA=',
#     'createdOn': '2026-02-10T13:27:56.983',
#     'modifiedOn': '2026-03-17T02:56:17.56',
#     'accountCurrency': 'EUR',
#     'accountIsClosed': False
#   }