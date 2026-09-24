# curl -X POST https://malpractice-campus-receives-lip.trycloudflare.com/v1/systemone \
#   -H "Content-Type: application/json" \
#   -d '{
#   "state": "This is the SECOND month in a row I have been billed twice for the Pro plan. Fix it ASAP.",
#   "questions": {
#     "department": {
#       "type": "choice",
#       "instructions": "Which team should handle this?",
#       "criteria": {
#         "billing": "Charges, refunds, invoices",
#         "technical": "Bugs or product issues",
#         "account": "Login / access problems",
#         "other": "Does not fit above"
#       }
#     },
#     "urgency": {
#       "type": "score",
#       "instructions": "How urgent is this?",
#       "criteria": {
#         "0": "Low",
#         "1": "Medium",
#         "2": "High",
#         "3": "Critical"
#       }
#     },
#     "angry": {
#       "type": "noul",
#       "instructions": "Is the customer expressing strong frustration or anger?"
#     }
#   }
# }' | jq

curl -X POST https://success-postcards-africa-serial.trycloudflare.com/v1/systemone \
  -H "Content-Type: application/json" \
  -d '{
  "state": "This is the SECOND month in a row I have been billed twice for the Pro plan. Fix it ASAP.",
  "questions": {
    "department": {
      "type": "choice",
      "instructions": "Which team should handle this?",
      "criteria": {
        "billing": "Charges, refunds, invoices",
        "technical": "Bugs or product issues",
        "account": "Login / access problems",
        "other": "Does not fit above"
      }
    },
    "urgency": {
      "type": "score",
      "instructions": "How urgent is this?",
      "criteria": ["Low", "Medium", "High", "Critical"]
    },
    "angry": {
      "type": "noul",
      "instructions": "Is the customer expressing strong frustration or anger?"
    }
  },
  "independent": true
}
' | jq