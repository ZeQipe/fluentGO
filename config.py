# ========================================
# PAYMENT CONFIGURATION
# ========================================

# Языки, при которых показываем модалку выбора платежной системы
MODAL_LANGUAGES = ["ru"]

# Платежные системы для разовых покупок (type = "one-time")
ONE_TIME_PAYMENT_SYSTEMS = [
    {"label": "💳Яндекс Пэй", "key": "yandex_pay"},
    {"label": "💲PayPal", "key": "paypal"}
]

# Платежные системы для подписок (type = "subscription")
SUBSCRIPTION_PAYMENT_SYSTEMS = [
    {"label": "💳ЮКасса", "key": "yookassa"},
    {"label": "💲PayPal", "key": "paypal"}
]

# Платежная система по умолчанию (когда hasModal = False)
DEFAULT_PAYMENT_SYSTEM = [
    {"label": "💲PayPal", "key": "paypal"}
]

