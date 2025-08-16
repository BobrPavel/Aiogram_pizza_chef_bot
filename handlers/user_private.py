import asyncio

from aiogram import F, types, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup


from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query import (
    orm_add_message,
    orm_add_order,
    orm_delete_from_cart,
    orm_delete_message,
    orm_add_to_cart,
    orm_get_user_carts,
    orm_add_user,
    orm_update_user,
    orm_add_order_items,
)

from filters.chat_types import ChatTypeFilter

from handlers.menu_processing import get_menu_content

from kbds.inline import MenuCallBack
from kbds.reply import get_keyboard, del_reply_kd




user_private_router = Router()
user_private_router.message.filter(ChatTypeFilter(["private"]))




SHIPPING_KB = get_keyboard(
    "Отмена заказа",
    "Шаг назад",
    "На месте",
    "Cамовывоз",
    placeholder="Введите адрес доставки",
    sizes=(2,),
)

PHONE_KB = get_keyboard(
    "Отмена заказа",
    "Шаг назад",
    "Отправить номер ☎️",
    placeholder="Нажмите на кнопку <Отправить номер>",
    request_contact=2,
    sizes=(1,2,),
)

async def inline_kb_create(message: types.Message, session: AsyncSession):
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
        chat_id = msg.chat.id,
        message_id = msg.message_id,
        
    )
    await asyncio.sleep(30)  # 100800 или 3 часа
    try:
        await msg.delete()
        await message.answer("Бот в спящем режиме, но все ваши действия сохранены. Введите команду /start")  
        await orm_delete_message(session, user_id=user.id)

    except Exception:  
        pass 


@user_private_router.message(CommandStart())
async def start_cmd(message: types.Message, session: AsyncSession):
    await inline_kb_create(message, session)



async def add_to_cart(callback: types.CallbackQuery, callback_data: MenuCallBack, session: AsyncSession):
    user = callback.from_user
    await orm_add_user(
        session,
        user_id=user.id,
        first_name=None,
        phone=None,
    )
    await orm_add_to_cart(session, user_id=user.id, product_id=callback_data.product_id)
    await callback.answer("Товар добавлен в корзину.", show_alert=True)



# ######################### FSM для заказа товаров ###################

class Ordering(StatesGroup):
    # Шаги состояний
    first_name = State()
    phone = State()
    delivery_address = State()



# Становимся в состояние ожидания ввода first_name
async def create_order(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):

    try:
        user = callback.from_user
        await orm_delete_message(session, user_id=user.id)
        msg = callback.message
        await msg.delete()
    except Exception:  
        pass 


    await callback.message.answer("Создание заказа. Введите своё имя")
    await state.set_state(Ordering.first_name)


# отмена всех шагов
@user_private_router.message(F.text == 'Отмена заказа')
async def cancel_handler(message: types.Message, state: FSMContext, session:AsyncSession) -> None:
    current_state = await state.get_state()
    if current_state is None:
        return

    await state.clear()

    await message.answer("Действия отменены", reply_markup=del_reply_kd)

    await inline_kb_create(message, session)


# вернуться на шаг назад
@user_private_router.message(F.text == "Шаг назад")
async def back_step_handler(message: types.Message, state: FSMContext) -> None:
    current_state = await state.get_state()

    if current_state == Ordering.first_name:
        await message.answer(
            'Предидущего шага нет, или введите название товара или напишите "Отмена заказа"'
        )
        return

    previous = None
    for step in Ordering.__all_states__:
        if step.state == current_state:
            await state.set_state(previous)
            await message.answer(
                f"Ок, вы вернулись к прошлому шагу \n {Ordering.texts[previous.state]}"
            )
            return
        previous = step


# Ловим данные для состояние first_name и потом меняем состояние на phone
@user_private_router.message(Ordering.first_name, F.text)
async def first_name(message: types.Message, state: FSMContext):
    
    if 2 > len(message.text) >= 150:
        await message.answer(
            "Нам кажется это не ваше имя, пожалуйста введите своё имя"
        )
        return
    
    await state.update_data(first_name=message.text)
    await message.answer("Предоставьте нам свой номер телефона, нажав на кнопку", reply_markup=PHONE_KB)
    await state.set_state(Ordering.phone)

# Хендлер для отлова некорректных вводов для состояния first_name
@user_private_router.message(Ordering.first_name)
async def first_name2(message: types.Message):
    await message.answer("Вы ввели не допустимые данные, введите имя тексом")


# Ловим данные для состояние phone и потом меняем состояние на adres
@user_private_router.message(Ordering.phone, F.contact)
async def add_phone(message: types.Message, state: FSMContext):
  
        
    
    await state.update_data(phone=message.contact.phone_number)
    await message.answer("Введите свой адресс для доставки или нажмите на одну из окнопок", reply_markup=SHIPPING_KB)
    await state.set_state(Ordering.delivery_address)

# Хендлер для отлова некорректных вводов для состояния phone
@user_private_router.message(Ordering.phone)
async def add_phone2(message: types.Message):
    await message.answer("Чтобы предоставить свой номер телефона, нажмите на кнопку")


# Ловим данные для состояние adres и потом сохраняем заказ в БД
@user_private_router.message(Ordering.delivery_address, F.text)
async def adres(message: types.Message, state: FSMContext, session: AsyncSession):

    if 4 >= len(message.text):
        await message.answer(
            "Адресс слишком короткий"
        )
        return
    await state.update_data(delivery_address=message.text)
    await message.answer("Заказ принят", reply_markup=del_reply_kd)

    user = message.from_user
    data = await state.get_data()

    await orm_update_user(session, user_id=user.id, first_name=data["first_name"], phone=data["phone"])
    order_id = await orm_add_order(session, user.id, data)
    await orm_get_user_carts(session, user_id=user.id)
    for cart in await orm_get_user_carts(session, user_id=user.id):
        await orm_add_order_items(session, order_id=order_id, product_id=cart.product.id, quantity=cart.quantity)
        await orm_delete_from_cart(session, user_id=user.id, product_id=cart.product.id)


    await inline_kb_create(message, session)
    


# Хендлер для отлова некорректных вводов для состояния adres
@user_private_router.message(Ordering.delivery_address)
async def adres2(message: types.Message):
    await message.answer("Вы ввели не допустимые данные, введите текст описания товара")
# Конец FSM машины для создания заказа


@user_private_router.callback_query(MenuCallBack.filter())
async def user_menu(callback: types.CallbackQuery, callback_data: MenuCallBack, state: FSMContext, session: AsyncSession):

    if callback_data.menu_name == "add_to_cart":
        await add_to_cart(callback, callback_data, session)
        return
    
    if callback_data.menu_name == "create_order":
        await create_order(callback, state, session)
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

