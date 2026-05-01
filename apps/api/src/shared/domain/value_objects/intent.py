from enum import StrEnum


class Intent(StrEnum):
    ACCESS = "access"
    REFUND = "refund"
    LOJA_EXPRESS = "loja_express"
    KNOWLEDGE = "knowledge"
    WELCOME_RESPONSE = "welcome_response"
    UNKNOWN = "unknown"
    ESCALATE = "escalate"
