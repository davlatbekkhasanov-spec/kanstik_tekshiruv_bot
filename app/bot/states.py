from aiogram.fsm.state import State, StatesGroup


class PickerStates(StatesGroup):
    invoice = State()
    cargo_photo = State()


class ReviewerStates(StatesGroup):
    error_comment = State()
    error_photo = State()
