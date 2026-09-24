curl http://localhost:8000/v1/systemone \
  -H "Content-Type: application/json" \
  -d '{
    "state": "Customer was charged twice and is very angry",
    "questions": {
      "department": {
        "type": "choice",
        "instructions": "Which team should handle this?",
        "criteria": {
          "billing": "Payments and refunds",
          "technical": "Bugs and outages",
          "sales": "Pricing and upgrades"
        }
      },
      "urgent": {
        "type": "noul",
        "instructions": "Does this need urgent attention?"
      }
    }
  }'