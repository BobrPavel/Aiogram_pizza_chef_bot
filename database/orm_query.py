import math
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database.models import Banner, Cart, Category, Order_items, Orders, Product, User, Messages


############### Работа с сообщениями ###############

async def orm_add_message(
    session: AsyncSession,
    user_id: int,
    chat_id: int,
    message_id: int,
):
    query = select(Messages).where(Messages.user_id == user_id)
    result = await session.execute(query)
    if result.first() is None:
        session.add(
            Messages(user_id=user_id, chat_id=chat_id, message_id=message_id)
        )
        await session.commit()

async def orm_get_message(session: AsyncSession, user_id: int):
    query = select(Messages).where(Messages.user_id == user_id)
    result = await session.execute(query)
    return result.scalar()

async def orm_delete_message(session: AsyncSession, user_id: int):
    query = delete(Messages).where(Messages.user_id == user_id)
    await session.execute(query)
    await session.commit()

############### Работа с баннерами (информационными страницами) ###############

async def orm_add_banner_description(session: AsyncSession, data: dict):
    #Добавляем новый или изменяем существующий по именам
    #пунктов меню: main, about, cart, shipping, payment, catalog
    query = select(Banner)
    result = await session.execute(query)
    if result.first():
        return
    session.add_all([Banner(name=name, description=description) for name, description in data.items()]) 
    await session.commit()


async def orm_change_banner_image(session: AsyncSession, name: str, image: str):
    query = update(Banner).where(Banner.name == name).values(image=image)
    await session.execute(query)
    await session.commit()


async def orm_get_banner(session: AsyncSession, page: str):
    query = select(Banner).where(Banner.name == page)
    result = await session.execute(query)
    return result.scalar()


async def orm_get_info_pages(session: AsyncSession):
    query = select(Banner)
    result = await session.execute(query)
    return result.scalars().all()


############################ Категории ######################################

async def orm_get_categories(session: AsyncSession):
    query = select(Category)
    result = await session.execute(query)
    return result.scalars().all()

async def orm_create_categories(session: AsyncSession, categories: list):
    query = select(Category)
    result = await session.execute(query)
    if result.first():
        return
    session.add_all([Category(name=name) for name in categories]) 
    await session.commit()

############ Админка: добавить/изменить/удалить товар ########################

async def orm_add_product(session: AsyncSession, data: dict):
    obj = Product(
        name=data["name"],
        description=data["description"],
        price=float(data["price"]),
        image=data["image"],
        category_id=int(data["category"]),
    )
    session.add(obj)
    await session.commit()


async def orm_get_products(session: AsyncSession, category_id):
    query = select(Product).where(Product.category_id == int(category_id))
    result = await session.execute(query)
    return result.scalars().all()


async def orm_get_product(session: AsyncSession, product_id: int):
    query = select(Product).where(Product.id == product_id)
    result = await session.execute(query)
    return result.scalar()


async def orm_update_product(session: AsyncSession, product_id: int, data):
    query = (
        update(Product)
        .where(Product.id == product_id)
        .values(
            name=data["name"],
            description=data["description"],
            price=float(data["price"]),
            image=data["image"],
            category_id=int(data["category"]),
        )
    )
    await session.execute(query)
    await session.commit()


async def orm_delete_product(session: AsyncSession, product_id: int):
    query = delete(Product).where(Product.id == product_id)
    await session.execute(query)
    await session.commit()


##################### Добавляем юзера в БД #####################################

async def orm_add_user(
    session: AsyncSession,
    user_id: int,
    first_name: str | None = None,
    phone: str | None = None,
):
    query = select(User).where(User.user_id == user_id)
    result = await session.execute(query)
    if result.first() is None:
        session.add(
            User(user_id=user_id, first_name=first_name, phone=phone)
        )
        await session.commit()

async def orm_update_user(
    session: AsyncSession,
    user_id: int,
    first_name: str | None = None,
    phone: str | None = None,
):
    query = (
            update(User)
            .where(User.user_id == user_id)
            .values(
            
            first_name=first_name,
            phone=phone,
        )
    )
    await session.execute(query)
    await session.commit()



######################## Работа с корзинами #######################################

async def orm_add_to_cart(session: AsyncSession, user_id: int, product_id: int):
    query = select(Cart).where(Cart.user_id == user_id, Cart.product_id == product_id).options(joinedload(Cart.product))
    cart = await session.execute(query)
    cart = cart.scalar()
    if cart:
        cart.quantity += 1
        await session.commit()
        return cart
    else:
        session.add(Cart(user_id=user_id, product_id=product_id, quantity=1))
        await session.commit()



async def orm_get_user_carts(session: AsyncSession, user_id):
    query = select(Cart).filter(Cart.user_id == user_id).options(joinedload(Cart.product))
    result = await session.execute(query)
    return result.scalars().all()


async def orm_delete_from_cart(session: AsyncSession, user_id: int, product_id: int):
    query = delete(Cart).where(Cart.user_id == user_id, Cart.product_id == product_id)
    await session.execute(query)
    await session.commit()


async def orm_reduce_product_in_cart(session: AsyncSession, user_id: int, product_id: int):
    query = select(Cart).where(Cart.user_id == user_id, Cart.product_id == product_id)
    cart = await session.execute(query)
    cart = cart.scalar()

    if not cart:
        return
    if cart.quantity > 1:
        cart.quantity -= 1
        await session.commit()
        return True
    else:
        await orm_delete_from_cart(session, user_id, product_id)
        await session.commit()
        return False


######################## Работа с заказами #######################################


# async def orm_add_order(session: AsyncSession, user_id: int, phone_number: str, delivery_address: str, status: str):
#     session.add(Orders(user_id=user_id, phone_number=phone_number, delivery_address=delivery_address, status=status))
#     await session.commit()


async def orm_add_order(session: AsyncSession, user_id: int, data: dict):
    obj = Orders(
        user_id=user_id,
        # phone=data["phone"],
        delivery_address=data["delivery_address"],
    )
    session.add(obj)
    await session.commit()
    return obj.id


async def orm_get_user_orders(session: AsyncSession, user_id):
    query = select(Orders).filter(Orders.user_id == user_id)
    result = await session.execute(query)
    return result.scalars().all()






async def orm_update_order(session: AsyncSession, orders_id: int, data):
    query = (
        update(Orders)
        .where(Orders.id == orders_id)
        .values(
            user_id=data["user_id"],
            phone_number=data["phone_number"],
            delivery_address=data["delivery_address"],
            status=float(data["status"]),
        )
    )
    await session.execute(query)
    await session.commit()


async def orm_add_order_items(session: AsyncSession, order_id: int, product_id: int, quantity: int):
    session.add(Order_items(order_id=order_id, product_id=product_id, quantity=quantity))
    await session.commit()


async def orm_get_order_items(session: AsyncSession, order_id: int):
    query = select(Order_items).filter(Order_items.order_id == order_id).options(joinedload(Order_items.product))
    result = await session.execute(query)
    return result.scalars().all()




