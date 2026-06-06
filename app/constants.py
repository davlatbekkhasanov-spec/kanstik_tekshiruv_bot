import enum


class UserRole(str, enum.Enum):
    picker = "picker"
    reviewer = "reviewer"
    admin = "admin"


class InspectionStatus(str, enum.Enum):
    pending = "pending"
    in_review = "in_review"
    approved = "approved"
    returned = "returned"
    fix_submitted = "fix_submitted"


class InspectionResult(str, enum.Enum):
    correct = "correct"
    error = "error"


class ErrorType(str, enum.Enum):
    item_missing = "item_missing"
    extra_not_on_invoice = "extra_not_on_invoice"
    wrong_item = "wrong_item"
    wrong_quantity = "wrong_quantity"
    wrong_store_mixed = "wrong_store_mixed"
    incomplete_set = "incomplete_set"
    duplicate_item = "duplicate_item"
    damaged_item = "damaged_item"
    wrong_color = "wrong_color"
    other = "other"


ERROR_TYPE_LABELS: dict[ErrorType, str] = {
    ErrorType.item_missing: "Tovar umuman yo'q",
    ErrorType.extra_not_on_invoice: "Fakturada yo'q tovar bor",
    ErrorType.wrong_item: "Noto'g'ri tovar",
    ErrorType.wrong_quantity: "Noto'g'ri miqdor",
    ErrorType.wrong_store_mixed: "Boshqa do'kon tovari aralashgan",
    ErrorType.incomplete_set: "Komplekt to'liq emas",
    ErrorType.duplicate_item: "Dublikat tovar",
    ErrorType.damaged_item: "Shikastlangan tovar",
    ErrorType.wrong_color: "Tovar rangida adashish",
    ErrorType.other: "Boshqa xato",
}
