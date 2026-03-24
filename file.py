import requests

resp = requests.get(
    "http://financial.exactflow.ngrok.dev/api/Transaction",
    headers={"x-api-key": "rida_Wmw3xVlImfAoaiTzeTb6zRtOoyGrSWXAekXR5Shap0iRAbHtwr0MnpKQ6gjh4I37"}
)
data = resp.json()
print(data)

# {
#   'transactionId': 1,
#   'transactionAccountId': 1,
#   'transactionRefNumber': '64001139026',
#   'transactionOperationDate': '2025-11-12T00:00:00',
#   'transactionBookingDate': '2025-11-12T00:00:00',
#   'transactionAmount': -14760.0,
#   'transactionBalance': -1085559.04,
#   'transactionGroupId': 1,
#   'transactionType': 'CIB OBCY BANK Z PROWIZJĄ WN.',
#   'transactionDescription': 'K & K PRZYJAZNI KSIEGOWA SP Z O O ROZLOGI 14A/88 0132-310 WARSAW NIP 5223254964\r\n25114020040000310283566269\r\n/NIP/5223254964/FAKTURA 74/2025',
#   'transactionNote': '',
#   'transactionHash': '3A-C0-51-E1-A5-FE-30-AC-0F-5B-26-A1-53-B9-0D-1F-77-B5-10-BF',
#   'transactionSortOrder': 1,
#   'timeStamp': 'AAAAAAAAB+I=',
#   'createdOn': '2026-02-09T11:47:13.64',
#   'modifiedOn': '2026-02-09T11:47:13.64',
#   'transactionStatusId': 1,
#   'transactionBookingDateOrder': 1,
#   'transactionPartnerName': 'K & K PRZYJAZNI KSIEGOWA SP Z O O',
#   'transactionPaymentDetails': '/NIP/5223254964/FAKTURA 74/2025',
#   'transactionPartnerAccountNo': '25114020040000310283566269',
#   'account': None
# }

# # ------------------------------------

# {
#   'transactionId': 3,
#   'transactionAccountId': 1,
#   'transactionRefNumber': '64001139035',
#   'transactionOperationDate': '2025-11-12T00:00:00',
#   'transactionBookingDate': '2025-11-12T00:00:00',
#   'transactionAmount': -817.95,
#   'transactionBalance': -1088590.99,
#   'transactionGroupId': 1,
#   'transactionType': 'CIB OBCY BANK Z PROWIZJĄ WN.',
#   'transactionDescription': 'SERWISPAK DARIUSZ MRÓZ UL. TURYSTYCZNA 48 97-570 PRZEDBÓRZ\r\n11102031470000880200482232\r\n/NIP/7291198110/PROFORMA P/114/2025',
#   'transactionNote': '',
#   'transactionHash': 'B3-61-81-87-41-00-75-A0-8F-4A-BD-BF-5E-48-3D-7C-72-5A-EF-C7',
#   'transactionSortOrder': 3,
#   'timeStamp': 'AAAAAAAAB+Q=',
#   'createdOn': '2026-02-09T11:47:13.783',
#   'modifiedOn': '2026-02-09T11:47:13.783',
#   'transactionStatusId': 1,
#   'transactionBookingDateOrder': 3,
#   'transactionPartnerName': 'SERWISPAK DARIUSZ MRÓZ',
#   'transactionPaymentDetails': '/NIP/7291198110/PROFORMA P/114/2025',
#   'transactionPartnerAccountNo': '11102031470000880200482232',
#   'account': None
# }