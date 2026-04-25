from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from ..db import get_user
from ..keyboards import main_menu
from .. import texts as t

router = Router()


@router.callback_query(F.data == "menu")
async def cb_menu(
    callback: CallbackQuery,
    state: FSMContext,
    db_path: str,
) -> None:
    await state.clear()
    user = await get_user(db_path, callback.from_user.id)
    if not user or not user["selection_key"]:
        from ..states import GroupSelection
        from ..keyboards import cancel_input
        await state.set_state(GroupSelection.waiting_for_query)
        await callback.message.edit_text(t.ASK_GROUP_AGAIN, reply_markup=cancel_input())
        await callback.answer()
        return

    await callback.message.edit_text(t.MAIN_MENU, reply_markup=main_menu())
    await callback.answer()
