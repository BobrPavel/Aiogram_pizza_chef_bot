import asyncio

from aiogram import F, types, Router
from aiogram.filters import CommandStart

from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query import (
    orm_add_message,
    orm_delete_message,
    orm_add_to_cart,
    orm_add_user,
)

from filters.chat_types import ChatTypeFilter

from handlers.menu_processing import get_menu_content

from kbds.inline import MenuCallBack, get_callback_btns



user_private_router = Router()
user_private_router.message.filter(ChatTypeFilter(["private"]))


@user_private_router.message(CommandStart())
async def start_cmd(message: types.Message, session: AsyncSession):
    media, reply_markup = await get_menu_content(session, level=0, menu_name="main")
    msg = await message.answer_photo(media.media, caption=media.caption, reply_markup=reply_markup)
   
   
    '''
    Код ниже удаляет inline клавиатуру через некоторое время. В рабочем режиме через 3 часа или 10800 секунд.
    Этот же код сохраняет id сообщения в БД, благодаря чему можно будет удалить клавиатуру при запуске FSM для 
    создания заказа.
    '''

    user = message.from_user
    await orm_add_message(
        session,
        user_id=user.id,
        message_id = msg.message_id,
    )
    await asyncio.sleep(5)  
    try:
        await msg.delete()
        await message.answer("Бот в спящем режиме, но все ваши действия сохранены. Введите команду /start")  
        await orm_delete_message(session, user_id=user.id)

    except Exception:  
        pass 

async def add_to_cart(callback: types.CallbackQuery, callback_data: MenuCallBack, session: AsyncSession):
    user = callback.from_user
    await orm_add_user(
        session,
        user_id=user.id,
        first_name=user.first_name,
        # last_name=user.last_name,
        phone=None,
    )
    await orm_add_to_cart(session, user_id=user.id, product_id=callback_data.product_id)
    await callback.answer("Товар добавлен в корзину.", show_alert=True)


@user_private_router.callback_query(MenuCallBack.filter())
async def user_menu(callback: types.CallbackQuery, callback_data: MenuCallBack, session: AsyncSession):

    if callback_data.menu_name == "add_to_cart":
        await add_to_cart(callback, callback_data, session)
        return


    media, reply_markup = await get_menu_content(
        session,
        level=callback_data.level,
        menu_name=callback_data.menu_name,
        category=callback_data.category,
        page=callback_data.page,
        product_id=callback_data.product_id,
        user_id=callback.from_user.id,
    )

    await callback.message.edit_media(media=media, reply_markup=reply_markup)
    await callback.answer()












# @user_private_router.message(CommandStart())
# async def start_cmd(message: types.Message):
#     await message.answer("Привет, я виртуальный помощник",
#                          reply_markup=get_callback_btns(btns={
#                              'Нажми меня': 'some_1'
#                          }))
    
# @user_private_router.callback_query(F.data.startswith('some_'))
# async def counter(callback: types.CallbackQuery):
#     number = int(callback.data.split('_')[-1])

     
#     await callback.message.edit_text(
#         text=f"Нажатий - {number}",
#         reply_markup=get_callback_btns(btns={
#                              'Нажми еще раз': f'some_{number+1}'
#                          }))
    

# Пример для видео как делать не нужно:
# menu_level_menuName_category_page_productID