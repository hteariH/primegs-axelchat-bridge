# primegs-axelchat-bridge

Мост **prime.gs → AxelChat**: опрашивает чат [prime.gs](https://prime.gs) и переливает
новые сообщения в локальный API [AxelChat](https://github.com/3dproger/AxelChat)
(`POST /api/v1/receive-events`, появился в AxelChat 0.44.0).

AxelChat нативно prime.gs не поддерживает, но его HTTP-эндпоинт `receive-events`
предназначен ровно для сторонних интеграций — исходники AxelChat трогать не нужно.

Зависимостей нет — только стандартная библиотека Python 3.

## Запуск из исходника

Рядом с работающим AxelChat:

```bash
python primegs_bridge.py 257
```

где `257` — id чата из URL `https://prime.gs/chat/257/messages`.

### Конфиг

`chat_id` и прочие параметры можно один раз прописать в `primegs_bridge.json`
рядом со скриптом, тогда запуск сокращается до:

```bash
python primegs_bridge.py
```

Скопируйте `primegs_bridge.example.json` в `primegs_bridge.json` и впишите свой
`chat_id`. Если файла нет, программа создаст шаблон при первом запуске.
Аргументы командной строки, если переданы, перекрывают значения из конфига.

| Параметр   | По умолчанию              | Описание                                         |
|------------|---------------------------|--------------------------------------------------|
| `chat_id`  | —                         | id чата prime.gs (обязателен)                    |
| `axel_url` | `http://127.0.0.1:8356`   | базовый URL локального AxelChat                  |
| `interval` | `2.0`                     | пауза между опросами, сек                        |
| `period`   | `current_stream`          | параметр `period` запроса к prime.gs             |
| `limit`    | `50`                      | limit сообщений на запрос                        |
| `backfill` | `false`                   | отправить и стартовую пачку уже существующих     |

## Сборка .exe (Windows)

Запустите `build_exe.bat` — он установит PyInstaller и соберёт один файл
`dist\primegs_bridge.exe`. Положите рядом с ним `primegs_bridge.json`
(или запустите exe один раз — он создаст шаблон).

Нужен установленный Python с галочкой «Add python.exe to PATH».

## Лицензия

MIT
