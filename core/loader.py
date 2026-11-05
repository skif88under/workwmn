import importlib
import pkgutil

from aiogram import Bot, Dispatcher


async def load_modules(bot: Bot, dp: Dispatcher):
    import modules

    module_list = []

    # Поиск модулей
    for module_info in pkgutil.iter_modules(modules.__path__):

        module_name = module_info.name

        if module_name.startswith("_"):
            continue

        full_name = f"modules.{module_name}"

        try:
            module = importlib.import_module(full_name)

            setup = getattr(module, "setup", None)

            if not callable(setup):
                print(
                    f"Модуль {module_name} пропущен: "
                    "отсутствует функция setup"
                )
                continue

            order = getattr(module, "order", 100)

            if isinstance(order, bool):
                raise ValueError("order должен быть целым числом")

            order = int(order)

            module_list.append({
                "name": module_name,
                "setup": setup,
                "order": order
            })

        except Exception as error:
            print(f"Ошибка загрузки {module_name}: {error}")

    # Сортировка модулей
    module_list.sort(
        key=lambda module: (
            module["order"],
            module["name"]
        )
    )

    # Подключение модулей
    for module in module_list:

        try:
            await module["setup"](bot, dp)

            print(
                f"Модуль загружен: {module['name']} "
                f"(order: {module['order']})"
            )

        except Exception as error:
            print(
                f"Ошибка запуска модуля "
                f"{module['name']}: {error}"
            )
