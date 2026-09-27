# Пересмотр процессов роботов

Источник: `platform/seed/platform.sql`. Рассмотрены названия, описания, назначение и кейсы 555 карточек. Явные назначения и основания хранятся в `platform/seed/process_assignments.json`; идентификация — по UUID, а не по похожему названию или грузоподъёмности.

Результат: 446 карточек получили задачи, 109 оставлены без связей. Связей стало 496 вместо 1768. Из 26 прежних процессов объединены 5 дублирующих; добавлены 44 задачи, подтверждённые карточками. Итого 65 процессов. Разные операции (упаковка и паллетирование, уборка и дезинфекция) не объединены.

Объединения:

| Старый код | Канонический код |
| --- | --- |
| `floor_washing` | `floor_cleaning` |
| `inventory` | `warehouse_inventory` |
| `auto_pallet_storage` | `pallet_storage` |
| `pallet_handling` | `palletizing` |
| `box_transport` | `parcel_sorting` |

Комбинированное название «Сортировка и транспорт коробов» заменено сортировкой; перевозка грузов отдельно представлена доставкой внутри помещений. Паллетное и автоматическое хранение объединены в автоматизированное хранение грузов, включая ящики.

Примеры исправлений: роботы для паллет не получают перевозку багажа; лёгкие роботы — доставку биоматериалов; обычные манипуляторы — паллетирование; дроны — осмотр кровли. Багаж назначен тягачу Cognitive Pilot на основании кейса Пулково. miniSIGMA и SIGMA отнесены к мониторингу лесов по кейсам, а не к одноимённой серии трубных роботов.

## Применение

Миграция `0011_review_process_assignments` выполняется один раз при обновлении платформы. Она работает как для существующей БД, так и после восстановления начального SQL-снимка. Повторный старт приложения не переопределяет ручные назначения.

```bash
docker compose up -d --build platform-api platform-worker
```

Миграция переносит связи объектов и проектов, привязки входных параметров и фильтры объединяемых процессов. При конфликте настройки канонического процесса имеют приоритет. Карточки вне рассмотренного списка и связи с пользовательскими процессами сохраняются. Импорт новых роботов не назначает задачи по ключевым словам; их можно связать вручную. Новые задачи добавлены к подходящим типам объектов; существующие настройки выбора процессов в проектах не включаются заново.

Для новых задач формулы количества, фильтры и экономические нормативы требуют отдельной настройки в админке; они не выводятся из названия задачи.

## Проверка

Миграция выполнена на временной PostgreSQL 16 с копией исходного SQL-снимка. Получены 555 карточек, 496 связей, 109 карточек без процессов и 65 процессов; все 19 проектов сохранены, старые коды объединённых процессов отсутствуют. Рабочая БД не изменялась. Тесты не запускались и не изменялись.

## Состав процессов

| Процесс | Код | Карточек |
| --- | --- | ---: |
| Автоматизированное хранение и выдача грузов | `pallet_storage` | 4 |
| Автономное управление сельхозтехникой | `vehicle_guidance` | 2 |
| Буксировка тележек | `cart_towing` | 2 |
| Вакцинация птицы | `poultry_vaccination` | 1 |
| Внесение веществ на поля | `field_spraying` | 1 |
| Внутритрубная диагностика | `in_pipe_diagnostics` | 4 |
| Геодезические и геофизические изыскания | `aerial_survey` | 13 |
| Дезинфекция помещений | `disinfection` | 2 |
| Демонтаж объектов | `demolition` | 1 |
| Доение | `milking` | 1 |
| Дорожные и земляные работы | `road_works` | 3 |
| Доставка биоматериалов | `biomaterial_delivery` | 5 |
| Доставка блюд и сбор посуды | `food_delivery` | 52 |
| Доставка грузов вне помещений | `outdoor_delivery` | 22 |
| Доставка грузов внутри помещений | `tote_delivery` | 40 |
| Доставка грузов под водой | `underwater_transport` | 1 |
| Доставка лекарств и медицинских материалов | `medicine_delivery` | 2 |
| Загрузка и обслуживание станков | `machine_tending` | 4 |
| Зарядка электромобилей | `ev_charging` | 1 |
| Захват и перекладка изделий | `blank_stacking` | 9 |
| Инвентаризация товаров | `warehouse_inventory` | 2 |
| Информирование и сопровождение посетителей | `passenger_service` | 26 |
| Комплектация заказов | `order_picking` | 9 |
| Лабораторный анализ пластовых вод | `lab_water_analysis` | 1 |
| Магистральная перевозка грузов | `long_haul_freight` | 1 |
| Медицинская помощь и реабилитация | `medical_assistance` | 1 |
| Мобильная торговля | `mobile_retail` | 1 |
| Мойка фасадов и окон | `facade_washing` | 3 |
| Мониторинг окружающей среды | `environmental_monitoring` | 14 |
| Мониторинг состояния посевов | `crop_monitoring` | 2 |
| Обработка почвы | `ploughing` | 4 |
| Обследование инфраструктуры и поиск дефектов | `infrastructure_inspection` | 17 |
| Обследование подводных объектов и акваторий | `underwater_inspection` | 10 |
| Обследование территории | `territory_inspection` | 3 |
| Обслуживание вагонов | `railway_service` | 3 |
| Обучение робототехнике и исследовательские эксперименты | `education` | 65 |
| Осмотр кровли | `roof_inspection` | 0 |
| Охрана и патрулирование территории | `perimeter_security` | 12 |
| Очистка промышленных резервуаров и оборудования | `industrial_cleaning` | 1 |
| Паллетирование | `palletizing` | 2 |
| Патрулирование акватории | `water_patrol` | 3 |
| Перевозка багажа | `baggage_transport` | 1 |
| Перевозка грузов на перроне | `apron_transport` | 0 |
| Перевозка грузов по воде | `water_transport` | 5 |
| Перевозка паллет | `pallet_transport` | 13 |
| Перевозка пассажиров | `passenger_transport` | 3 |
| Погрузка и разгрузка грузов | `loading_unloading` | 5 |
| Поиск пропавших людей | `missing_person_search` | 2 |
| Покос травы | `lawn_mowing` | 3 |
| Помощь пациентам в отделениях | `ward_service` | 0 |
| Приготовление напитков | `beverage_preparation` | 2 |
| Размещение грузов на ярусах стеллажей | `rack_placement` | 2 |
| Сбор мусора с поверхности воды | `water_cleaning` | 1 |
| Сбор напольных яиц и павшей птицы | `poultry_collection` | 1 |
| Сбор урожая | `harvesting` | 4 |
| Сборка изделий | `assembly` | 6 |
| Сварка | `welding` | 7 |
| Сортировка грузов и посылок | `parcel_sorting` | 5 |
| Социальное общение и помощь в быту | `social_companionship` | 4 |
| Строительство объектов | `construction` | 2 |
| Тушение пожаров | `firefighting` | 4 |
| Уборка помещений | `floor_cleaning` | 65 |
| Уборка улиц и территорий | `street_cleaning` | 7 |
| Удалённое общение и телеприсутствие | `telepresence` | 1 |
| Упаковка продукции | `packing` | 3 |

## Карточки без назначенных задач

Пустые списки в JSON являются явным решением: описание не устанавливает конкретную задачу либо относится к аксессуару/макету. У универсальных платформ не подставлены возможные задачи только на основании класса, массы или наличия манипулятора.

- Робот гуманоид Noetix Robotics N2 (`feec5363-9d97-47a5-9699-ec4fff2045b7`).
- Noetix Hobbs (`149adfb1-1bf1-412f-826f-d0f9f9fe042a`).
- Unitree R1 (`d3ae3162-3c5c-4b1c-b068-277dcce65e9c`).
- Weilan BabyAlpha A2 Plus (`779a5dd4-5ca6-435e-938c-8e547e608918`).
- Weilan BabyAlpha A2 Pro (`cfc45869-0e7a-449a-9188-3294417ad3c8`).
- Робот гуманоид Unitree G1 (`caf0458c-2355-4022-b665-280c138f1da6`).
- Unitree H1 (`b82f7aaf-573f-4530-859d-6030452e2d8b`).
- AiNex ROS (`c454effc-7ce7-4dc5-bab8-63cab24b6e56`).
- Unitree G1 Basic / Ultra-Power Bundle (Inklusive EcoFlow Delta 3 Ultra Plus Powerstation) (`9cf34c0e-7dac-4f14-ad52-1a0395771abc`).
- Робот-гуманоид Deep Robotics DR 02 (`13c15ca8-2fce-4abe-97b3-274c4c7b31a0`).
- Weilan BabyAlpha A2 Standart (`4d2f6407-d3ed-41bf-9471-83af50d68e08`).
- Pudu SH1 Scheuersaugmaschine dunkel Grau (`b0f87eb3-3ab3-4d15-9c7d-865fc256839b`).
- Weilan BabyAlpha A2 Ultra (`b3a0b462-a9d4-4441-b571-a96e8620b933`).
- Грин (`a9c720bc-e618-4dcc-90e1-990c5a3d1ae2`).
- RC5-16 (`0a4cab58-e194-4329-8f23-6074a5f7455f`).
- Берилл (`72acd18d-325d-4a3e-9472-093ecdcdbb4b`).
- ARM95-200 (грузоподъемность до 18 кг) (`d6f3eec1-61c1-40ac-98b1-0f5d80877cb7`).
- Dobot CRA Hebe- und Palettier-Arbeitsstation (ohne Roboter) (`ea9b319d-773f-4d6a-8ff6-de2b6d932eb6`).
- МК (`45487628-a2c6-421f-9ea4-761b6c3be240`).
- ОМДЖЕТ -ГМ01 (`f6cc47ab-c645-4fe5-9bd1-0acc609758f0`).
- Робот гуманоид Noetix Robotics E1 (`ddfb587d-792c-4ec7-930d-3acaaff3580e`).
- Deeprobotics LynX M20 Pro (`ae0ae23c-2bd3-4172-bfbf-f5bb60e27548`).
- Inchbot M1 (`2e191c86-50c7-4f06-b994-3a5b05d14834`).
- Unitree A2 (`6115ae59-11e8-48d3-aeb6-77708f1ad37e`).
- Робот платформа AMR Reeman Chassis (`10d39c1c-a031-49d9-813a-d29314be7a69`).
- Робот собака Unitree Go2 Pro (`28f2b26e-6a24-4f3c-bf19-a1a74ac677df`).
- Magiclab MagicDog Pro (`7142ce85-eac4-4102-90c4-c55344617c0d`).
- DeepRobotics Lite3 (`3ed6d031-47df-40b9-ae13-eabae87d45df`).
- DeepRobotics X30 (`7a538cf9-7d3a-4c3c-9421-32f9b2ec4256`).
- Unitree GO2-W (`c3c1a78f-b4b9-48c5-a06c-f23052e3ea26`).
- Unitree D1 (`5b0cab2d-b19f-4238-95a0-205f8fdd0e41`).
- Робот собака Unitree Go2 Air (`14ecfdcd-9e1d-4b49-b471-94c37a698ba8`).
- IKitbot ONE Pro S55 Pro UVC Commercial Cleaning Robot Dummy (`a95f54e4-3b9b-4db2-b14a-f8b423e3beae`).
- Unitree Go2 Pro / Ultra-Autonomy Bundle (Inklusive EcoFlow Delta 3 Ultra Plus Powerstation) (`9a6a2883-d51b-4b1b-8a42-3828104cd3ea`).
- Коллаборативный робот Elephant Robotics модель myCobot‑320 M5 (`d71d7684-9c10-4ed1-94c4-48a648ac1a6b`).
- Коллаборативный робот Elephant Robotics mechArm‑270 M5 (`a29da1fd-b47a-4761-ab44-d665430adeef`).
- Коллаборативный робот Elephant Robotics myCobot‑280 M5 (`4e2a907c-03c9-4df4-8ae3-501a37c83dbc`).
- Программно-аппаратный комплекс бренда AgiBot модели G2 (`0de6c1f6-d4bc-4dd2-9d44-aa7bc5f0da4e`).
- Робот-манипулятор AgileX PiPER (`a97ea442-20bb-426b-ad4f-0e6befa9c467`).
- Рука-манипулятор UFACTORY 850, модель XI15 (`612e747d-c8a2-424d-998f-f167f8e1b7f3`).
- Рука-манипулятор UFACTORY xArm 7, модель XS13 (`be8c7c99-2b06-47f0-ab99-2a63cb6638b4`).
- Unitree Go2 X (`2cfdf7ab-6b9f-4782-8cee-502eca93bc80`).
- Робот AgileX LIMO (`cdc3a70a-27f7-4400-af8f-967488e0e7bb`).
- Коллаборативный робот JAKA DP16 (`eee8fbff-ba47-4bd0-a097-cd8776265804`).
- Коллаборативный робот JAKA DP12 (`4291ee7e-0043-4a3d-9d45-4941f56c05c9`).
- Коллаборативный робот JAKA DP5 (`a62db0bd-9c83-43de-acae-282b6ce3a25b`).
- Коллаборативный робот JAKA D30 (`d6be208d-e1a5-4428-acc5-61ca9dc29576`).
- Рука-манипулятор Unitree D1-T (`e13fd685-86cf-4831-93db-1e802e64a8e9`).
- Рука-манипулятор Unitree D1 (`6d541380-a963-43c5-88bf-223530e3e464`).
- Роботизированная рука ABB GoFa CRB 15000 (`1c6007e3-1eb8-4e41-aff6-d9d795b5b098`).
- Рука-манипулятор UFACTORY Lite 6, модель LI10 (`309a62b5-1cff-42ae-9b76-fcd40240e3af`).
- Рука-манипулятор UFACTORY xArm 6, модель XI13 (`3a3a13ee-5aa3-4fd5-a059-138f1f025316`).
- Рука-манипулятор UFACTORY xARM 5, модель XF13 (`2265eefc-84dc-497c-b8f2-a5e95683b108`).
- Робот AgileX Ranger Mini (`b7529d81-a596-4a7d-9c33-a7ecd0c56f14`).
- Робот AgileX Ranger (`e074d011-5d07-4eb8-9b76-d8474330d4ce`).
- Многофункциональная промышленная роботизированная платформа бренда AgileX модели COBOT Magic (`0829c8b9-9812-414e-a350-b1d3ad2ce00c`).
- Многофункциональная промышленная роботизированная платформа бренда AgileX модели COBOT S KIT (`1105970c-41b8-4339-83ba-e1c5b2e16768`).
- Многофункциональная промышленная роботизированная платформа бренда AgileX модели COBOT KIT (`60fd7bf2-58c0-45f3-838a-83dd1abd3833`).
- Мобильная платформа Elephant Robotics myAGV 2023 Jetson Nano (`2d62f6bb-9ac6-4fbf-9eb8-b37ac4bb5077`).
- Робот AgileX LIMO COBOT (`984039da-a319-478a-902c-bca25b63aed4`).
- Робот AgileX LIMO ROS2 (`733eccc1-2019-4bcb-9825-721cdf64a432`).
- Робот AgileX LIMO PRO (`3f5672fd-550a-4056-9865-1c93a02d6634`).
- Робот AgileX Scout Mini R&D Kit (`27efc5e5-c0fa-464c-a2b7-781fe365c03c`).
- Робот AgileХ Scout Mini (`2812171d-3c88-445c-8dda-6193342014a8`).
- Робот AgileХ Scout 2.0 (`a2064c28-3832-488f-a4cf-7ac075ea01ce`).
- Робот AgileX Bunker Pro (`b3202dcf-75f5-4597-8c9e-f842ee0babd7`).
- Робот AgileX Bunker Mini (`44da86e7-ae3d-441d-a19b-c2b44690bc86`).
- Робот-гуманоид Agibot Lingxi X2 (`5d6dc6d5-542a-4d7d-86c6-c0a65d64dbb0`).
- Роботизированная рука ABB GoFa CRB 15000 (`fdcffc14-794d-4335-b093-abc6858599f9`).
- Робот-манипулятор Kinova Gen3 7DOF (`79fdf643-64c5-4af5-8d1c-c61bae304a34`).
- Unitree H2 (`ae251df0-c0e6-4234-b716-bce8a001619b`).
- UBtech Walker S2 (`2720a4e5-88f2-4ad7-88b6-75f5fef19922`).
- Робот-манипулятор Kinova Gen3 6DOF (`5bf6689f-68d1-43d7-9f09-0d3805d3282c`).
- Бионический робот гуманоид Unitree Robotics H1 (`90edbb47-bb83-4b71-b32b-885e7c29fb14`).
- Бионический робот гуманоид Unitree Robotics H2 (`0cb03c9c-1c86-49f4-8c23-edd505f676c6`).
- Dobot E6 Roboter (Inklusive ES01 Saugnapf) (`1bfface3-d6c5-4976-b811-340bd6660c74`).
- Dobot CR3A Roboterarm (`6a00e5ac-c8d8-4653-bf6c-da6d31733f8e`).
- Бионический робот гуманоид Unitree Robotics G1 (`37f2cce5-23e4-4fa2-8483-d0266911be61`).
- UBtech Walker Tienkung (`fc229e3d-6b5e-4e71-b77a-1573f65298aa`).
- Робот гуманоид Booster K1 (`8e0b614b-7923-4f2b-8b23-c133fa208a78`).
- Робот гуманоид Noetix Robotics Hobbs (`20c59645-0cdd-46ea-bd04-bd62a00547c1`).
- Многофункциональная промышленная роботизированная платформа AgileX UMR (`69b3780d-5271-457f-a251-865fd824e3fb`).
- Многофункциональная промышленная роботизированная платформа AgileX COBOT KIT (`05e20243-3c86-49b2-b14b-ef4bc229ac99`).
- Базовая роботизированная платформа Droneshub FRAME (`74402e87-933b-4cc3-a95a-4e0f7b1325d1`).
- Программно-аппаратный комплекс бренда AgiBot G2 (`d02640e8-361a-49c8-b1cd-f1d9d94d8d2d`).
- Программно-аппаратный комплекс бренда AgiBot G1 (`50f0751b-a26f-4c53-98c6-3aa75db25bf8`).
- Программно-аппаратный комплекс Elephant Robotics Mercury X1 (`32a4f02d-ae6d-450b-977c-b49ec912da0e`).
- Робот AgileX Scout Mini (`5b7562b7-b15d-4554-b25b-f2aa9f294b25`).
- Робот AgileX Scout 2.0 (`96242256-91fa-455a-aa69-6c3d2baa1c7d`).
- Робот AgileX Ranger Mini (`b6c05493-aec0-453d-b914-629356962c45`).
- Робот AgileX Ranger (`55f99caa-1d71-451a-a053-9c49d1818c96`).
- Робот AgileX Bunker Pro (`518d2800-aeef-42f3-a4a8-683167e70590`).
- Мобильная платформа Elephant Robotics myAGV 2023 JN (`e473eb53-b5c2-478e-b2a7-a850cdfec30e`).
- Гусеничный робот AgileX Bunker Mini 2.0 (`5577bb2d-8e0c-424c-ab2b-44f9ae06ef24`).
- Коллаборативный робот Elephant Robotics myCobot‑280 M5 + AI KIT (`cc9b4b5b-fd5f-4800-b879-1c41f8941ccb`).
- Коллаборативный робот Elephant Robotics mechArm 270M5 (`5cfacd9f-882c-4fd7-9c76-159ea477dd5f`).
- Робот Unitree Go2-W (`96b5111b-66c4-4e84-ba64-a5ec1adb0f57`).
- Робот Unitree Go2 Pro (`7f956297-fa01-467d-a642-dfbc5aa5aa92`).
- Робот Unitree Go2 Air (`a41e4680-3ed8-4c30-8b18-332207a842ed`).
- Робот Unitree Go1 Pro (`14833906-5e03-41f4-8fab-3c9efd21ed7d`).
- Робот Unitree B1 (`3a9df076-6a19-4ee0-95f5-1d63e2cec5b2`).
- Робот Deep Robotics Lynx M20 PRO (`160b0fc7-5dec-42fd-adf3-520a4de92b46`).
- Бионический четырехопорный робот Unitree B2 (`de6f9bc8-054f-4ef6-a0cd-3c002785db6c`).
- Бионический четырехопорный робот Unitree A2-W (`1728529e-592f-4f39-b790-4365cb43c9da`).
- Бионический четырехопорный робот Unitree A2 (`06f17f91-d2a3-41fa-be9d-a09019c253ec`).
- Бионический четырехопорный колесный робот Unitree B2-W (`8b7bd710-7eb1-48a7-bf39-eb67e8014eaa`).
- Inchbot L1/L1EDU (`c00f6874-7f8b-410a-b717-c87cb2570471`).
- Unitree B2 Roboterhund (`235b574c-0414-4483-b494-c0f2674124aa`).
- Unitree B2-W Roboterhund (`5e830d78-261f-46c8-aa3f-7ba7bcd4d3b0`).
