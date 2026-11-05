import importlib
import pkgutil

from aiogram import Bot, Dispatcher


async def load_modules(bot: Bot, dp: Dispatcher):
    import modules

    module_list = []

    for module_info in pkgutil.iter_modules(modules.__path__):
        module_name = module_info.name

        if module_name.startswith("_"):
            continue

        try:
            module = importlib.import_module(
                f"modules.{module_name}"
            )

            setup = getattr(module, "setup", None)

            if not callable(setup):
                print(f"Модуль {module_name} пропущен")
                continue

            order = getattr(module, "order", 100)

            if isinstance(order, bool):
                raise ValueError("order должен быть числом")

            order = int(order)

            module_list.append({
                "name": module_name,
                "module": module,
                "setup": setup,
                "order": order
            })

        except Exception as error:
            print(f"Ошибка импорта {module_name}: {error}")

    module_list.sort(
        key=lambda x: (x["order"], x["name"])
    )

    menu_items = []

    for item in module_list:
        try:
            await item["setup"](bot, dp)

            print(
                f"Модуль загружен: {item['name']} "
                f"(order: {item['order']})"
            )

            items = getattr(
                item["module"],
                "MENU_ITEMS",
                []
            )

            for menu_item in items:
                menu_items.append({
                    "text": menu_item["text"],
                    "callback_data": menu_item["callback_data"],
                    "order": item["order"]
                })

        except Exception as error:
            print(
                f"Ошибка запуска {item['name']}: {error}"
            )

    return menu_items
