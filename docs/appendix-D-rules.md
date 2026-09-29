# Приложение Д. Правила подбора, формулы количества и ранжирование по процессам

Приложение закрывает п. 7.1 дополнений к ТЗ («условия исключения неподходящих решений») и п. 3.4.2 ТЗ. Таблицы выгружены из работающей платформы (`GET /api/v1/admin/processes/{code}`) на 29.09.2026. Правила и формулы редактируются в админке («Процессы»), поэтому после правок приложение надо перегенерировать: `python docs/tools/gen_appendices.py`.

**Сводка.** Процессов в справочнике: 65. Настроены фильтры у 19 процессов (всего правил: 47), формула количества роботов у 20, ключ ранжирования у 20. У остальных процессов настройки нет: все назначенные им роботы получат вердикт «Подходит» без проверки, а число роботов не рассчитывается (в экономике берётся одна машина, если у неё есть цена).

## Как читать правило

- **Режим `hard`** (жёсткое): невыполнение даёт вердикт «Не подходит». **Режим `conditional`** (с условием): невыполнение даёт «С условием» и причину в списке замечаний.
- В формуле `robot.<ключ>` — характеристика робота из каталога, остальные имена — входы, привязанные к параметрам площадки (столбец «Входы»). Если параметр площадки пуст, правило пропускается. Если у робота нет нужной характеристики, вердикт «Уточнить».
- Допустимы операции `+ - * /`, сравнения `< <= > >= == !=`, логика `and`, `or`, функции `ceil floor abs round min max sqrt`.

## Правила исключения (фильтры)

| Процесс | Правило | Режим | Формула | Входы (параметры площадки) |
|---|---|---|---|---|
| Автоматизированное хранение и выдача грузов | Груз | hard | `robot.payload_kg >= load` | `load` (Масса паллеты) |
| Автоматизированное хранение и выдача грузов | Автономность смены | conditional | `robot.work_time_h >= shift` | `shift` (Длительность смены) |
| Буксировка тележек | Тяга | hard | `robot.payload_kg >= load` | `load` (Масса паллеты/состава) |
| Доставка биоматериалов | Груз | hard | `robot.payload_kg >= load` | `load` (Масса единицы) |
| Доставка биоматериалов | Проезд | hard | `robot.min_aisle_width_m <= aisle` | `aisle` (Ширина проездов) |
| Доставка биоматериалов | Шум | conditional | `robot.uroven_shuma <= noise` | `noise` (Лимит шума) |
| Доставка биоматериалов | Автономность смены | conditional | `robot.work_time_h >= shift` | `shift` (Длительность смены) |
| Доставка грузов внутри помещений | Груз | hard | `robot.payload_kg >= load` | `load` (Масса тары) |
| Доставка грузов внутри помещений | Проезд | hard | `robot.min_aisle_width_m <= aisle` | `aisle` (Ширина прохода) |
| Доставка грузов внутри помещений | Автономность смены | conditional | `robot.work_time_h >= shift` | `shift` (Длительность смены) |
| Доставка грузов внутри помещений | Шум | conditional | `robot.uroven_shuma <= noise` | `noise` (Лимит шума) |
| Доставка лекарств и медицинских материалов | Груз | hard | `robot.payload_kg >= load` | `load` (Масса единицы) |
| Доставка лекарств и медицинских материалов | Проезд | hard | `robot.min_aisle_width_m <= aisle` | `aisle` (Ширина проездов) |
| Доставка лекарств и медицинских материалов | Шум | conditional | `robot.uroven_shuma <= noise` | `noise` (Лимит шума) |
| Доставка лекарств и медицинских материалов | Автономность смены | conditional | `robot.work_time_h >= shift` | `shift` (Длительность смены) |
| Инвентаризация товаров | Автономность смены | conditional | `robot.work_time_h >= shift` | `shift` (Длительность смены) |
| Информирование и сопровождение посетителей | Груз | hard | `robot.payload_kg >= load` | `load` (Масса единицы) |
| Информирование и сопровождение посетителей | Автономность смены | conditional | `robot.work_time_h >= shift` | `shift` (Длительность смены) |
| Комплектация заказов | Груз | hard | `robot.payload_kg >= load` | `load` (Масса штуки) |
| Комплектация заказов | Автономность смены | conditional | `robot.work_time_h >= shift` | `shift` (Длительность смены) |
| Обследование территории | Автономность смены | conditional | `robot.work_time_h >= shift` | `shift` (Длительность смены) |
| Осмотр кровли | Автономность смены | conditional | `robot.work_time_h >= shift` | `shift` (Длительность смены) |
| Охрана и патрулирование территории | Автономность смены | conditional | `robot.work_time_h >= shift` | `shift` (Длительность смены) |
| Паллетирование | Груз | hard | `robot.payload_kg >= load` | `load` (Масса штуки) |
| Паллетирование | Автономность смены | conditional | `robot.work_time_h >= shift` | `shift` (Длительность смены) |
| Перевозка багажа | Груз | hard | `robot.payload_kg >= load` | `load` (Масса багажа/паллеты) |
| Перевозка багажа | Проезд | hard | `robot.min_aisle_width_m <= aisle` | `aisle` (Ширина проездов) |
| Перевозка багажа | Автономность смены | conditional | `robot.work_time_h >= shift` | `shift` (Длительность смены) |
| Перевозка паллет | Груз | hard | `robot.payload_kg >= load` | `load` (Масса паллеты) |
| Перевозка паллет | Проезд | hard | `robot.min_aisle_width_m <= aisle` | `aisle` (Ширина проезда) |
| Перевозка паллет | Автономность смены | conditional | `robot.work_time_h >= shift` | `shift` (Длительность смены) |
| Помощь пациентам в отделениях | Груз | hard | `robot.payload_kg >= load` | `load` (Масса единицы) |
| Помощь пациентам в отделениях | Автономность смены | conditional | `robot.work_time_h >= shift` | `shift` (Длительность смены) |
| Размещение грузов на ярусах стеллажей | Груз | hard | `robot.payload_kg >= load` | `load` (Масса паллеты) |
| Размещение грузов на ярусах стеллажей | Автономность смены | conditional | `robot.work_time_h >= shift` | `shift` (Длительность смены) |
| Сортировка грузов и посылок | Груз | hard | `robot.payload_kg >= load` | `load` (Масса штуки) |
| Сортировка грузов и посылок | Груз | hard | `robot.payload_kg >= load` | `load` (Масса посылки) |
| Сортировка грузов и посылок | Проезд | hard | `robot.min_aisle_width_m <= aisle` | `aisle` (Ширина прохода) |
| Сортировка грузов и посылок | Автономность смены | conditional | `robot.work_time_h >= shift` | `shift` (Длительность смены) |
| Уборка помещений | Проезд | hard | `robot.min_aisle_width_m <= aisle` | `aisle` (Минимальная ширина прохода) |
| Уборка помещений | Автономность смены | conditional | `robot.work_time_h >= shift` | `shift` (Время работы) |
| Уборка помещений | Шум | conditional | `robot.uroven_shuma <= noise` | `noise` (Уровень шума) |
| Уборка помещений | Проезд | hard | `robot.min_aisle_width_m <= aisle` | `aisle` (Ширина проездов) |
| Уборка помещений | Автономность смены | conditional | `robot.work_time_h >= shift` | `shift` (Длительность смены) |
| Уборка помещений | Шум | conditional | `robot.uroven_shuma <= noise` | `noise` (Лимит шума) |
| Упаковка продукции | Груз | hard | `robot.payload_kg >= load` | `load` (Масса штуки) |
| Упаковка продукции | Автономность смены | conditional | `robot.work_time_h >= shift` | `shift` (Длительность смены) |

## Формулы количества роботов

Формула считает число машин выбранной модели для процесса. Переменные `robot.*` берутся из карточки робота, остальные из параметров площадки. Числа `0,82`, `80`, `240` и другие зашитые константы перечислены в приложении А (C-011…C-017).

| Процесс | Формула | Входы |
|---|---|---|
| Автоматизированное хранение и выдача грузов | `ceil(((inbound_pallets_per_day + outbound_pallets_per_day) / (shift_hours * shifts_per_day)) / (3600 / (2 * picker_route_m / robot.speed_loaded_ms + 80) * 0.82)) + 1` | `inbound_pallets_per_day`, `outbound_pallets_per_day`, `shift_hours`, `shifts_per_day`, `picker_route_m` |
| Буксировка тележек | `ceil(((inbound_pallets_per_day + outbound_pallets_per_day) / (shift_hours * shifts_per_day)) / (3600 / (2 * picker_route_m / robot.speed_loaded_ms + 80) * 0.82)) + 1` | `inbound_pallets_per_day`, `outbound_pallets_per_day`, `shift_hours`, `shifts_per_day`, `picker_route_m` |
| Доставка биоматериалов | `ceil((1200 / (shift_hours * shifts_per_day)) / (3600 / (360 / robot.speed_loaded_ms + 80) * 0.82)) + 1` | `shift_hours`, `shifts_per_day` |
| Доставка грузов внутри помещений | `ceil((pick_units_per_day / (shift_hours * shifts_per_day)) / (3600 / (2 * picker_route_m / robot.speed_loaded_ms + 80) * 0.82)) + 1` | `pick_units_per_day`, `shift_hours`, `shifts_per_day`, `picker_route_m` |
| Доставка лекарств и медицинских материалов | `ceil((1200 / (shift_hours * shifts_per_day)) / (3600 / (360 / robot.speed_loaded_ms + 80) * 0.82)) + 1` | `shift_hours`, `shifts_per_day` |
| Инвентаризация товаров | `ceil(pallet_places / (robot.throughput * 0.82 * shift_hours * shifts_per_day)) + 1` | `pallet_places`, `shift_hours`, `shifts_per_day` |
| Информирование и сопровождение посетителей | `ceil((420 / (shift_hours * shifts_per_day)) / (3600 / (584 / robot.speed_loaded_ms + 80) * 0.82)) + 1` | `shift_hours`, `shifts_per_day` |
| Комплектация заказов | `ceil((pick_lines_per_day / (shift_hours * shifts_per_day)) / (3600 / (2 * picker_route_m / robot.speed_loaded_ms + 80) * 0.82)) + 1` | `pick_lines_per_day`, `shift_hours`, `shifts_per_day`, `picker_route_m` |
| Обследование территории | `ceil(24 * (4 * sqrt(area_m2) / robot.speed_loaded_ms + 240) / (shift_hours * shifts_per_day * 3600 * 0.82)) + 1` | `area_m2`, `shift_hours`, `shifts_per_day` |
| Осмотр кровли | `ceil(24 * (4 * sqrt(area_m2) / robot.speed_loaded_ms + 240) / (shift_hours * shifts_per_day * 3600 * 0.82)) + 1` | `area_m2`, `shift_hours`, `shifts_per_day` |
| Охрана и патрулирование территории | `ceil(24 * (4 * sqrt(area_m2) / robot.speed_loaded_ms + 240) / (shift_hours * shifts_per_day * 3600 * 0.82)) + 1` | `area_m2`, `shift_hours`, `shifts_per_day` |
| Паллетирование | `ceil(((inbound_pallets_per_day + outbound_pallets_per_day) / (shift_hours * shifts_per_day)) / (3600 / (2 * picker_route_m / robot.speed_loaded_ms + 80) * 0.82)) + 1` | `inbound_pallets_per_day`, `outbound_pallets_per_day`, `shift_hours`, `shifts_per_day`, `picker_route_m` |
| Перевозка багажа | `ceil((420 / (shift_hours * shifts_per_day)) / (3600 / (584 / robot.speed_loaded_ms + 80) * 0.82)) + 1` | `shift_hours`, `shifts_per_day` |
| Перевозка грузов на перроне | `ceil((420 / (shift_hours * shifts_per_day)) / (3600 / (584 / robot.speed_loaded_ms + 80) * 0.82)) + 1` | `shift_hours`, `shifts_per_day` |
| Перевозка паллет | `ceil(((inbound_pallets_per_day + outbound_pallets_per_day) / (shift_hours * shifts_per_day)) / (3600 / (2 * picker_route_m / robot.speed_loaded_ms + 80) * 0.82)) + 1` | `inbound_pallets_per_day`, `outbound_pallets_per_day`, `shift_hours`, `shifts_per_day`, `picker_route_m` |
| Помощь пациентам в отделениях | `ceil((850 / (shift_hours * shifts_per_day)) / (3600 / (360 / robot.speed_loaded_ms + 80) * 0.82)) + 1` | `shift_hours`, `shifts_per_day` |
| Размещение грузов на ярусах стеллажей | `ceil(((inbound_pallets_per_day + outbound_pallets_per_day) / (shift_hours * shifts_per_day)) / (3600 / (2 * picker_route_m / robot.speed_loaded_ms + 80) * 0.82)) + 1` | `inbound_pallets_per_day`, `outbound_pallets_per_day`, `shift_hours`, `shifts_per_day`, `picker_route_m` |
| Сортировка грузов и посылок | `ceil((pick_units_per_day / (shift_hours * shifts_per_day)) / (3600 / (2 * picker_route_m / robot.speed_loaded_ms + 80) * 0.82)) + 1` | `pick_units_per_day`, `shift_hours`, `shifts_per_day`, `picker_route_m` |
| Уборка помещений | `ceil(clean_area_m2 / robot.proizvoditelnost / shift_hours)` | `clean_area_m2`, `shift_hours` |
| Упаковка продукции | `ceil(((inbound_pallets_per_day + outbound_pallets_per_day) / (shift_hours * shifts_per_day)) / (3600 / (2 * picker_route_m / robot.speed_loaded_ms + 80) * 0.82)) + 1` | `inbound_pallets_per_day`, `outbound_pallets_per_day`, `shift_hours`, `shifts_per_day`, `picker_route_m` |

## Ранжирование: какой робот считается лучшим

Взвешенной оценки нет (см. раздел 4 документации). Для каждого процесса можно задать характеристику, по которой среди роботов с вердиктом «Подходит» (а если таких нет, «С условием») выбирается один «лучший». Он ставится в сравнении по умолчанию и идёт в экономику. Если ключ не задан, лучшим считается самый дешёвый.

| Процесс | Характеристика | Порядок |
|---|---|---|
| Автоматизированное хранение и выдача грузов | `payload_kg` | по убыванию |
| Буксировка тележек | `payload_kg` | по убыванию |
| Доставка биоматериалов | `payload_kg` | по убыванию |
| Доставка грузов внутри помещений | `payload_kg` | по убыванию |
| Доставка лекарств и медицинских материалов | `payload_kg` | по убыванию |
| Инвентаризация товаров | `lift_height_mm` | по убыванию |
| Информирование и сопровождение посетителей | `payload_kg` | по убыванию |
| Комплектация заказов | `payload_kg` | по убыванию |
| Обследование территории | `work_time_h` | по убыванию |
| Осмотр кровли | `work_time_h` | по убыванию |
| Охрана и патрулирование территории | `work_time_h` | по убыванию |
| Паллетирование | `payload_kg` | по убыванию |
| Перевозка багажа | `payload_kg` | по убыванию |
| Перевозка грузов на перроне | `payload_kg` | по убыванию |
| Перевозка паллет | `payload_kg` | по убыванию |
| Помощь пациентам в отделениях | `payload_kg` | по убыванию |
| Размещение грузов на ярусах стеллажей | `lift_height_mm` | по убыванию |
| Сортировка грузов и посылок | `payload_kg` | по убыванию |
| Уборка помещений | `proizvoditelnost` | по убыванию |
| Упаковка продукции | `payload_kg` | по убыванию |

## Процессы без настроенных правил

Ниже процессы (45), для которых нет ни фильтров, ни формулы количества. Это задел каталога: роботы назначены, правила подбора добавляются в админке.

Автономное управление сельхозтехникой, Вакцинация птицы, Внесение веществ на поля, Внутритрубная диагностика, Геодезические и геофизические изыскания, Дезинфекция помещений, Демонтаж объектов, Доение, Дорожные и земляные работы, Доставка блюд и сбор посуды, Доставка грузов вне помещений, Доставка грузов под водой, Загрузка и обслуживание станков, Зарядка электромобилей, Захват и перекладка изделий, Лабораторный анализ пластовых вод, Магистральная перевозка грузов, Медицинская помощь и реабилитация, Мобильная торговля, Мойка фасадов и окон, Мониторинг окружающей среды, Мониторинг состояния посевов, Обработка почвы, Обследование инфраструктуры и поиск дефектов, Обследование подводных объектов и акваторий, Обслуживание вагонов, Обучение робототехнике и исследовательские эксперименты, Очистка промышленных резервуаров и оборудования, Патрулирование акватории, Перевозка грузов по воде, Перевозка пассажиров, Погрузка и разгрузка грузов, Поиск пропавших людей, Покос травы, Приготовление напитков, Сбор мусора с поверхности воды, Сбор напольных яиц и павшей птицы, Сбор урожая, Сборка изделий, Сварка, Социальное общение и помощь в быту, Строительство объектов, Тушение пожаров, Уборка улиц и территорий, Удалённое общение и телеприсутствие.
